import time

import structlog

from app.crm.bitrix24 import Bitrix24Client
from app.exceptions import EmptyTranscriptionError
from app.llm.proxyapi_client import ProxyAPIClient
from app.models.schemas import CallData, LeadData, LLMResponse
from app.novofon.api import NovofonAPI
from app.stt.s3 import S3Client
from app.stt.speechkit import SpeechKitClient

logger = structlog.get_logger()


async def process_call(
    call_data: CallData,
    *,
    novofon: NovofonAPI,
    s3: S3Client,
    stt: SpeechKitClient,
    llm: ProxyAPIClient,
    bitrix: Bitrix24Client,
    skip_spam: bool = False,
) -> None:
    """Main pipeline: download → S3 → STT → LLM → CRM."""
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
        )
        log.info("stage_complete", stage="llm", duration_ms=_elapsed(start))

        # 5. Skip spam if configured
        if analysis.qualification == "spam" and skip_spam:
            log.info("spam_skipped")
            return

        # 6. Find/create lead in Bitrix24 (non-terminal: save to JSON on failure)
        start = time.monotonic()
        try:
            lead = await bitrix.find_lead_by_phone(call_data.caller_number)

            if lead:
                await bitrix.update_lead(lead["ID"], {
                    "TITLE": f"Звонок: {analysis.summary[:50]}",
                    "COMMENTS": analysis.summary,
                })
                await bitrix.add_timeline_comment(
                    "lead", lead["ID"], _format_comment(analysis),
                )
            else:
                lead_data = LeadData(
                    title=f"Звонок: {analysis.summary[:50]}",
                    client_name=analysis.client_name,
                    company=analysis.company,
                    phone=call_data.caller_number,
                    summary=analysis.summary,
                    qualification=analysis.qualification,
                )
                lead_id = await bitrix.create_lead(lead_data)
                await bitrix.add_timeline_comment(
                    "lead", lead_id, _format_comment(analysis),
                )
            log.info("stage_complete", stage="crm", duration_ms=_elapsed(start))
        except Exception as exc:
            log.error("crm_failed_saving_locally", error=str(exc))
            _save_failed_crm_result(call_data, analysis)

    finally:
        if mp3_path and mp3_path.exists():
            mp3_path.unlink()
            log.info("mp3_cleaned")


def _save_failed_crm_result(call_data: CallData, analysis: LLMResponse) -> None:
    """Save failed CRM update to local JSON for later processing."""
    import json
    from pathlib import Path

    failed_dir = Path("/data/failed_crm")
    failed_dir.mkdir(parents=True, exist_ok=True)
    dest = failed_dir / f"{call_data.call_id}.json"
    dest.write_text(json.dumps({
        "call_data": call_data.model_dump(mode="json"),
        "analysis": analysis.model_dump(mode="json"),
    }, ensure_ascii=False, indent=2))


def _format_comment(analysis: LLMResponse) -> str:
    tags = ", ".join(analysis.tags) if analysis.tags else "-"
    return (
        f"AI-анализ звонка:\n\n"
        f"{analysis.summary}\n\n"
        f"Квалификация: {analysis.qualification}\n"
        f"Настроение: {analysis.sentiment}\n"
        f"Следующий шаг: {analysis.next_action or '-'}\n"
        f"Теги: {tags}"
    )


def _elapsed(start: float) -> int:
    return int((time.monotonic() - start) * 1000)
