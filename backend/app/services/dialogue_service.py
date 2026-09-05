from time import monotonic

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.domain.companion import compose_dialogue_response
from app.domain.safety import SafetyService
from app.enums import ResponseSource, SafetyLevel
from app.exceptions import ConflictError
from app.models import DialogueTurn, ModelRun, SafetyEvent
from app.providers.base import LLMProvider
from app.schemas import DialogueTurnCreate, DialogueTurnRead
from app.services.session_service import get_active_session


async def create_dialogue_turn(
    db: Session,
    *,
    request: DialogueTurnCreate,
    settings: Settings,
    llm: LLMProvider,
) -> DialogueTurnRead:
    session, child = get_active_session(db, request.session_id, settings)
    existing = db.scalar(
        select(DialogueTurn).where(DialogueTurn.request_id == request.request_id)
    )
    if existing is not None:
        if existing.session_id != session.id:
            raise ConflictError("同一個 request_id 不可跨學習階段重複使用。")
        return DialogueTurnRead(
            turn_id=existing.id,
            safety_level=SafetyLevel(existing.safety_level),
            response={
                "level": existing.companion_level,
                "speech": existing.speech,
                "body_actions": existing.body_actions,
                "response_source": existing.response_source,
                "follow_up": None,
            },
        )
    decision = SafetyService().classify(request.message)
    started = monotonic()
    response = await compose_dialogue_response(
        level=child.current_level,
        message=request.message,
        safety_level=decision.level,
        safety_speech=decision.speech,
        llm=llm,
        settings=settings,
    )

    turn = DialogueTurn(
        session_id=session.id,
        child_id=child.id,
        request_id=request.request_id,
        input_text="[NOT_STORED]",
        safety_level=decision.level.value,
        companion_level=child.current_level,
        speech=response.speech,
        body_actions=response.body_actions,
        response_source=response.response_source.value,
    )
    db.add(turn)

    if child.current_level >= 3 and decision.level is SafetyLevel.NORMAL:
        db.add(
            ModelRun(
                session_id=session.id,
                child_id=child.id,
                operation="DIALOGUE",
                provider=llm.name,
                model=getattr(llm, "model", None),
                prompt_version="child-companion-v2",
                success=response.response_source is ResponseSource.CONSTRAINED_LLM,
                output_valid=response.response_source is ResponseSource.CONSTRAINED_LLM,
                latency_ms=round((monotonic() - started) * 1000),
                error_code=(
                    None
                    if response.response_source is ResponseSource.CONSTRAINED_LLM
                    else "LLM_FALLBACK"
                ),
            )
        )

    if decision.script_id:
        db.add(
            SafetyEvent(
                session_id=session.id,
                child_id=child.id,
                safety_level=decision.level.value,
                reason_code=decision.reason_code,
                response_script_id=decision.script_id,
                minimal_data={"policy_version": settings.safety_policy_version},
            )
        )
    db.commit()
    return DialogueTurnRead(
        turn_id=turn.id,
        safety_level=decision.level,
        response=response,
    )
