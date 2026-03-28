import json
import subprocess
import time
from pathlib import Path

import structlog
from redis.asyncio import Redis

from app import stats
from app.crm.bitrix24 import Bitrix24Client
from app.exceptions import Bitrix24APIError, EmptyTranscriptionError
from app.llm.base import LLMClient
from app.models.schemas import CallData, LLMResponse, PendingDealBinding, Qualification
from app.novofon.api import NovofonAPI
from app.stt.s3 import S3Client
from app.stt.speechkit import SpeechKitClient

logger = structlog.get_logger()

_SKIP_QUALIFICATIONS = {Qualification.REJECTED, Qualification.SPAM}


async def process_call(
    call_data: CallData,
    *,
    redis: Redis,
    novofon: NovofonAPI,
    s3: S3Client,
    stt: SpeechKitClient,
    llm: LLMClient,
    bitrix: Bitrix24Client,
    qa_entity_type_id: int = 0,
    qa_field_map: dict[str, str] | None = None,
    company_segment_field: str = "",
) -> PendingDealBinding | None:
    """Main pipeline: download -> S3 -> STT -> LLM -> CRM -> QA (best-effort).

    Raises RetryableError on transient failures (download, S3 upload, STT transcription).
    EmptyTranscriptionError (not retryable) is handled internally with early return.
    LLMAnalysisError is terminal (worker sends to DLQ).
    CRM and QA failures are best-effort (logged, not sent to DLQ).
    """
    log = logger.bind(call_id=call_data.call_id)
    mp3_path = None
    s3_key = f"{call_data.call_id}.mp3"

    try:
        # 1. Download recording
        start = time.monotonic()
        mp3_path = await novofon.download_recording(
            call_data.call_id, recording_url=call_data.recording_url,
        )
        log.info("stage_complete", stage="download", duration_ms=_elapsed(start))

        # 1b. Mix stereo to mono (both voices audible)
        mp3_path = _mix_to_mono(mp3_path)

        # 2. Upload to S3
        start = time.monotonic()
        s3_uri = await s3.upload(mp3_path, s3_key)
        log.info("stage_complete", stage="s3_upload", duration_ms=_elapsed(start))

        # 3. Transcribe
        start = time.monotonic()
        try:
            segments = await stt.transcribe(s3_uri, call_data.call_id)
        except EmptyTranscriptionError:
            log.info("empty_transcription", stage="stt", duration_ms=_elapsed(start))
            await stats.increment(redis, call_data.timestamp.date(), "no_transcript")
            return
        finally:
            await s3.delete(s3_key)

        transcript = stt.segments_to_text(segments)
        log.info("stage_complete", stage="stt", duration_ms=_elapsed(start))

        # 4. Analyze via LLM
        start = time.monotonic()
        analysis = await llm.analyze_call(
            transcript=transcript,
            caller_number=call_data.caller_number,
            duration=call_data.duration,
            direction=call_data.direction,
        )
        log.info("stage_complete", stage="llm", duration_ms=_elapsed(start))
        await stats.increment(redis, call_data.timestamp.date(), f"qual:{analysis.qualification}")

        # 5. Skip non-actionable calls
        if analysis.qualification in _SKIP_QUALIFICATIONS:
            log.info("call_skipped", qualification=analysis.qualification)
            return

        # 6. Attach analysis to deal or company in Bitrix24 (best-effort)
        deal = None
        pending: PendingDealBinding | None = None
        start = time.monotonic()
        raw_phone = (
            call_data.called_number
            if call_data.direction == "outgoing"
            else call_data.caller_number
        )
        # Bitrix24 expects phone with '+' prefix
        phone = raw_phone if raw_phone.startswith("+") else f"+{raw_phone}"
        company_id: int | None = None
        crm_manager_name: str | None = None
        crm_segment: str | None = None
        extra_fields = [company_segment_field] if company_segment_field else []
        try:
            company = await bitrix.find_company_by_phone(phone, extra_fields)
            if not company:
                log.warning("company_not_found_saving_locally", phone=phone)
                _save_failed_crm_result(log, call_data, analysis)
            else:
                company_id = int(company["ID"])

                # Fetch manager name and segment from CRM
                assigned_id = company.get("ASSIGNED_BY_ID")
                if assigned_id:
                    crm_manager_name = await bitrix.get_user_name(int(assigned_id))
                log.info(
                    "manager_resolved",
                    assigned_id=assigned_id,
                    crm_manager_name=crm_manager_name,
                )
                if company_segment_field:
                    seg_raw = company.get(company_segment_field)
                    if seg_raw:
                        crm_segment = await bitrix.resolve_enum_value(
                            "company", company_segment_field, seg_raw,
                        )

                # Build comment with CRM manager name (preferred) or LLM-extracted
                mgr_name = crm_manager_name or analysis.manager_name
                comment = _format_comment(analysis, call_data, manager_name=mgr_name)

                deal = await bitrix.find_open_deal(company_id)

                if deal:
                    deal_id = int(deal["ID"])
                    await bitrix.add_timeline_comment(
                        "deal", deal_id, comment, audio_path=mp3_path,
                    )
                    log.info(
                        "stage_complete", stage="crm",
                        entity="deal", entity_id=deal_id,
                        duration_ms=_elapsed(start),
                    )
                else:
                    # Deal not yet created — attach to company now, retry later
                    await bitrix.add_timeline_comment(
                        "company", company_id, comment, audio_path=mp3_path,
                    )
                    log.info(
                        "stage_complete", stage="crm",
                        entity="company", entity_id=company_id,
                        duration_ms=_elapsed(start),
                    )
        except Bitrix24APIError as exc:
            log.error("crm_failed_saving_locally", error=str(exc))
            _save_failed_crm_result(log, call_data, analysis)

        # 7. QA analysis for outgoing calls (best-effort)
        qa_item_id: int | None = None
        if call_data.direction == "outgoing" and qa_entity_type_id and qa_field_map:
            try:
                start = time.monotonic()
                mgr_for_qa = crm_manager_name or analysis.manager_name
                log.info(
                    "qa_manager",
                    crm_name=crm_manager_name,
                    llm_name=analysis.manager_name,
                    final=mgr_for_qa,
                )
                qa_result = await llm.analyze_qa(
                    transcript=transcript,
                    manager_name=mgr_for_qa,
                    duration=call_data.duration,
                )
                log.info("stage_complete", stage="qa_llm", duration_ms=_elapsed(start))

                start = time.monotonic()
                deal_id_for_qa = int(deal["ID"]) if deal else None
                date_str = call_data.timestamp.strftime("%Y-%m-%d")
                qa_item_id = await bitrix.add_qa_item(
                    qa=qa_result,
                    entity_type_id=qa_entity_type_id,
                    field_map=qa_field_map,
                    deal_id=deal_id_for_qa,
                    manager_name=mgr_for_qa,
                    segment=crm_segment,
                    call_date=date_str,
                    audio_path=mp3_path,
                )
                log.info("stage_complete", stage="qa_crm", duration_ms=_elapsed(start))
                await stats.increment(redis, call_data.timestamp.date(), "qa_assessed")

                # Save transcript to QA item timeline
                try:
                    await bitrix.add_timeline_comment(
                        "", qa_item_id, f"📝 Транскрипция\n\n{transcript}",
                        entity_type_id=qa_entity_type_id,
                    )
                    log.info("qa_transcript_saved", item_id=qa_item_id)
                except Bitrix24APIError as exc:
                    log.error("qa_transcript_failed", item_id=qa_item_id, error=repr(exc))
            except Exception as exc:
                log.error("qa_failed", error=repr(exc))

        # 8. Schedule deferred deal binding if company found but no deal
        if company_id and not deal:
            pending = PendingDealBinding(
                company_id=company_id,
                comment=comment,
                qa_item_id=qa_item_id,
                call_id=call_data.call_id,
                phone=phone,
            )
            log.info("deal_binding_deferred", company_id=company_id)

        return pending

    finally:
        if mp3_path and mp3_path.exists():
            mp3_path.unlink()
            log.info("mp3_cleaned")


def _save_failed_crm_result(
    log: structlog.stdlib.BoundLogger,
    call_data: CallData,
    analysis: LLMResponse,
) -> None:
    """Save failed CRM update to local JSON for later processing."""
    try:
        failed_dir = Path("/data/failed_crm")
        failed_dir.mkdir(parents=True, exist_ok=True)
        dest = failed_dir / f"{call_data.call_id}.json"
        dest.write_text(json.dumps({
            "call_data": call_data.model_dump(mode="json"),
            "analysis": analysis.model_dump(mode="json"),
        }, ensure_ascii=False, indent=2))
    except Exception as save_exc:
        log.error(
            "crm_fallback_save_failed",
            error=repr(save_exc),
            call_id=call_data.call_id,
            analysis=analysis.model_dump(mode="json"),
        )


_QUALIFICATION_RU = {
    "hot": "Горячий",
    "warm": "Тёплый",
    "cold": "Холодный",
    "rejected": "Отказ",
    "spam": "Спам",
}

_SENTIMENT_RU = {
    "positive": "Позитивное",
    "neutral": "Нейтральное",
    "negative": "Негативное",
}


def _format_comment(
    analysis: LLMResponse, call_data: CallData, *, manager_name: str | None = None,
) -> str:
    direction_label = (
        "Исходящий" if analysis.call_direction == "outgoing" else "Входящий"
    )
    date_str = call_data.timestamp.strftime("%d.%m.%Y")
    qualification = _QUALIFICATION_RU.get(analysis.qualification, analysis.qualification)
    sentiment = _SENTIMENT_RU.get(analysis.sentiment, analysis.sentiment)
    decision_maker = "Да" if analysis.decision_maker else "Нет" if analysis.decision_maker is False else "?"
    objections = "; ".join(analysis.objections) if analysis.objections else "-"
    pain_points = "; ".join(analysis.pain_points) if analysis.pain_points else "-"
    tags = ", ".join(analysis.tags) if analysis.tags else "-"

    lines = [
        "━━ Анализ звонка ━━",
        f"{direction_label} · {call_data.duration} сек · {date_str}",
        "",
        analysis.summary,
        "",
        "──── Детали ────",
        f"Квалификация: {qualification}",
        f"Настроение: {sentiment}",
        f"ЛПР: {decision_maker}",
        f"Менеджер: {manager_name or analysis.manager_name or '-'}",
        "",
        "──── Клиент ────",
        f"Запрос: {analysis.client_request or '-'}",
        f"Возражения: {objections}",
        f"Боли: {pain_points}",
        "",
        "──── Итог ────",
        f"Наше предложение: {analysis.our_offer or '-'}",
        f"Следующий шаг: {analysis.next_action or '-'}",
        "",
        f"Теги: {tags}",
    ]
    return "\n".join(lines)


def _mix_to_mono(mp3_path: Path) -> Path:
    """Mix stereo MP3 to mono so both channels are audible in Bitrix24 player."""
    mono_path = mp3_path.with_suffix(".mono.mp3")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", str(mp3_path), "-ac", "1", "-q:a", "5", str(mono_path)],
        capture_output=True, timeout=30,
    )
    if result.returncode == 0 and mono_path.exists():
        mp3_path.unlink()
        mono_path.rename(mp3_path)
        logger.info("audio_mixed_to_mono", path=str(mp3_path))
    else:
        logger.warning("mono_mix_failed", stderr=result.stderr.decode()[:200])
        if mono_path.exists():
            mono_path.unlink()
    return mp3_path


def _elapsed(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
