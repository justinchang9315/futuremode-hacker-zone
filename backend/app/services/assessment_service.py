import hashlib
from dataclasses import dataclass
from time import monotonic

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.companion import compose_assessment_response
from app.domain.progression import evaluate_progression, get_personal_best
from app.domain.rewards import apply_assessment_rewards, get_or_create_wallet
from app.domain.scoring import ReadingScorer
from app.enums import ASRQuality, AssessmentStatus, ResponseSource
from app.exceptions import ConflictError, NotFoundError
from app.models import ContentItem, ModelRun, ReadingAssessment, ReadingAttempt
from app.providers.base import LLMProvider
from app.schemas import AssessmentResponse, ScoreBreakdown
from app.services.session_service import get_active_session


@dataclass(frozen=True)
class AssessmentSubmission:
    session_id: str
    content_id: str
    request_id: str
    transcript: str
    asr_quality: ASRQuality
    provider_confidence: float | None
    audio_quality_score: float
    duration_ms: int | None
    input_mode: str


async def assess_reading(
    db: Session,
    *,
    request: AssessmentSubmission,
    settings: Settings,
    llm: LLMProvider,
) -> AssessmentResponse:
    session, child = get_active_session(db, request.session_id, settings)
    existing_attempt = db.scalar(
        select(ReadingAttempt).where(ReadingAttempt.request_id == request.request_id)
    )
    if existing_attempt is not None:
        if existing_attempt.session_id != session.id:
            raise ConflictError("同一個 request_id 不可跨學習階段重複使用。")
        existing_assessment = db.scalar(
            select(ReadingAssessment).where(
                ReadingAssessment.attempt_id == existing_attempt.id
            )
        )
        if existing_assessment and existing_assessment.response_payload:
            return AssessmentResponse.model_validate(existing_assessment.response_payload)
        raise ConflictError("這次朗讀正在處理，請稍候再查看結果。")
    content = db.get(ContentItem, request.content_id)
    if content is None or not content.active:
        raise NotFoundError("找不到指定的朗讀內容。")

    previous_best = get_personal_best(db, child.id, content.id)
    attempt = ReadingAttempt(
        session_id=request.session_id,
        child_id=child.id,
        content_id=content.id,
        request_id=request.request_id,
        input_mode=request.input_mode,
        transcript="sha256:" + hashlib.sha256(request.transcript.encode("utf-8")).hexdigest(),
        asr_quality=request.asr_quality.value,
        provider_confidence=request.provider_confidence,
        audio_quality_score=request.audio_quality_score,
        long_pause_count=0,
        restart_count=0,
        duration_ms=request.duration_ms,
    )
    db.add(attempt)
    db.flush()

    result = ReadingScorer(settings).assess(
        reference_text=content.reference_text,
        transcript=request.transcript,
        asr_quality=request.asr_quality,
        provider_confidence=request.provider_confidence,
        audio_quality_score=request.audio_quality_score,
        duration_ms=request.duration_ms,
    )
    assessment = ReadingAssessment(
        attempt_id=attempt.id,
        status=result.status.value,
        total_score=result.total_score,
        assessment_confidence=result.confidence,
        score_policy_version=settings.score_policy_version,
        breakdown=result.breakdown,
        evidence=result.evidence,
    )
    db.add(assessment)
    db.flush()

    rewards = apply_assessment_rewards(
        db,
        child_id=child.id,
        content_id=content.id,
        assessment=assessment,
        previous_best=previous_best,
        settings=settings,
    )
    wallet = get_or_create_wallet(db, child.id)
    progression = evaluate_progression(db, child=child, wallet=wallet, settings=settings)
    db.commit()

    started = monotonic()
    companion = await compose_assessment_response(
        level=progression.current_level,
        status=result.status,
        score=result.total_score,
        breakdown=result.breakdown,
        evidence=result.evidence,
        llm=llm,
        max_response_characters=settings.max_llm_response_chars,
    )
    if progression.current_level >= 3 and result.status is AssessmentStatus.FINAL:
        db.add(
            ModelRun(
                session_id=session.id,
                child_id=child.id,
                operation="ASSESSMENT_FEEDBACK",
                provider=llm.name,
                model=getattr(llm, "model", None),
                prompt_version="child-companion-v2",
                success=companion.response_source is ResponseSource.CONSTRAINED_LLM,
                output_valid=companion.response_source is ResponseSource.CONSTRAINED_LLM,
                latency_ms=round((monotonic() - started) * 1000),
                error_code=(
                    None
                    if companion.response_source is ResponseSource.CONSTRAINED_LLM
                    else "LLM_FALLBACK"
                ),
            )
        )

    breakdown = ScoreBreakdown(**result.breakdown) if result.breakdown else None
    response = AssessmentResponse(
        attempt_id=attempt.id,
        assessment_id=assessment.id,
        status=result.status,
        score=result.total_score,
        assessment_confidence=result.confidence,
        score_policy_version=settings.score_policy_version,
        breakdown=breakdown,
        evidence=result.evidence,
        rewards=rewards,
        companion=companion,
        current_level=progression.current_level,
        pending_level=progression.pending_level,
    )
    assessment.response_payload = response.model_dump(mode="json")
    db.commit()
    return response
