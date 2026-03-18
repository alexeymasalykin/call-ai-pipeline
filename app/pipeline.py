import json
import time
from pathlib import Path

import structlog

from app.crm.bitrix24 import Bitrix24Client
from app.exceptions import Bitrix24APIError, EmptyTranscriptionError
from app.llm.base import LLMClient
from app.models.schemas import CallData, LLMResponse, Qualification
from app.novofon.api import NovofonAPI
from app.stt.s3 import S3Client
from app.stt.speechkit import SpeechKitClient

logger = structlog.get_logger()

_SKIP_QUALIFICATIONS = {Qualification.REJECTED, Qualification.SPAM}


async def process_call(
    call_data: CallData,
    *,
    novofon: NovofonAPI,
    s3: S3Client,
    stt: SpeechKitClient,
    llm: LLMClient,
    bitrix: Bitrix24Client,
) -> None:
    """Main pipeline: download -> S3 -> STT -> LLM -> CRM (best-effort).

    Raises RetryableError on transient failures (download, S3 upload, STT transcription).
    EmptyTranscriptionError (not retryable) is handled internally with early return.
    LLMAnalysisError is terminal (worker sends to DLQ).
    CRM failures are saved to /data/failed_crm/, not sent to DLQ.
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

        # 5. Skip non-actionable calls
        if analysis.qualification in _SKIP_QUALIFICATIONS:
            log.info("call_skipped", qualification=analysis.qualification)
            return

        # 6. Attach analysis to deal or company in Bitrix24 (best-effort)
        start = time.monotonic()
        phone = (
            call_data.called_number
            if call_data.direction == "outgoing"
            else call_data.caller_number
        )
        try:
            company = await bitrix.find_company_by_phone(phone)
            if not company:
                log.warning("company_not_found_saving_locally", phone=phone)
                _save_failed_crm_result(log, call_data, analysis)
                return

            company_id = int(company["ID"])
            deal = await bitrix.find_open_deal(company_id)
            comment = _format_comment(analysis)

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


def _format_comment(analysis: LLMResponse) -> str:
    tags = ", ".join(analysis.tags) if analysis.tags else "-"
    objections = "; ".join(analysis.objections) if analysis.objections else "-"
    pain_points = "; ".join(analysis.pain_points) if analysis.pain_points else "-"
    direction_label = (
        "Исходящий" if analysis.call_direction == "outgoing" else "Входящий"
    )
    lines = [
        f"AI-анализ звонка ({direction_label}):\n",
        analysis.summary,
        "",
        f"Квалификация: {analysis.qualification}",
        f"Настроение: {analysis.sentiment}",
        f"ЛПР: {'Да' if analysis.decision_maker else 'Нет' if analysis.decision_maker is False else '?'}",
        f"Запрос клиента: {analysis.client_request or '-'}",
        f"Наше предложение: {analysis.our_offer or '-'}",
        f"Возражения: {objections}",
        f"Боли клиента: {pain_points}",
        f"Следующий шаг: {analysis.next_action or '-'}",
        f"Теги: {tags}",
    ]
    return "\n".join(lines)


def _elapsed(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
