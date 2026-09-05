from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import AccessClaims, verify_access_token
from app.config import Settings, get_settings
from app.database import get_db
from app.domain.companion import capabilities_for_level
from app.domain.progression import content_progress, evaluate_progression
from app.domain.rewards import (
    REWARD_CATALOG,
    get_or_create_wallet,
    list_reward_items,
    redeem_catalog_item,
)
from app.domain.zhuyin import annotate
from app.enums import ASRQuality
from app.exceptions import (
    DomainError,
    ForbiddenError,
    NotFoundError,
    ProviderConfigurationError,
    UnauthorizedError,
)
from app.models import (
    ChildProfile,
    ContentItem,
    DialogueTurn,
    FeedbackEvent,
    ReadingAssessment,
    ReadingAttempt,
    RewardTransaction,
)
from app.providers.factory import (
    get_asr_provider,
    get_llm_provider,
    get_tts_provider,
)
from app.schemas import (
    AssessmentResponse,
    ContentItemRead,
    DeleteChildResponse,
    DemoLevelRequest,
    DialogueTurnCreate,
    DialogueTurnRead,
    FeedbackCreate,
    FeedbackRead,
    GuardianLevelApproval,
    HealthResponse,
    LevelStatusRead,
    ReadingAttemptCreate,
    RedemptionRequest,
    RedemptionResponse,
    RewardItemRead,
    RewardTransactionRead,
    SessionCreate,
    SessionRead,
    SessionSummary,
    TTSRequest,
    WalletRead,
    ZhuyinEntry,
    ZhuyinRequest,
)
from app.services.assessment_service import AssessmentSubmission, assess_reading
from app.services.dialogue_service import create_dialogue_turn
from app.services.privacy_service import delete_child_data, get_session_summary
from app.services.session_service import create_session, end_session, get_active_session

router = APIRouter()
MAX_ZHUYIN_TEXT_CHARS = 400
DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _read_session_token(
    token: Annotated[str | None, Header(alias="X-Session-Token")] = None,
) -> str | None:
    return token


def _read_guardian_token(
    token: Annotated[str | None, Header(alias="X-Guardian-Token")] = None,
) -> str | None:
    return token


SessionToken = Annotated[str | None, Depends(_read_session_token)]
GuardianToken = Annotated[str | None, Depends(_read_guardian_token)]


def _authorize_session(
    token: str | None,
    *,
    settings: Settings,
    session_id: str | None = None,
    child_id: str | None = None,
) -> AccessClaims:
    if not token:
        raise UnauthorizedError("缺少學習階段憑證。")
    return verify_access_token(
        token,
        settings=settings,
        expected_role="session",
        session_id=session_id,
        child_id=child_id,
    )


def _authorize_guardian(
    token: str | None,
    *,
    settings: Settings,
    session_id: str | None = None,
    child_id: str | None = None,
) -> AccessClaims:
    if not token:
        raise UnauthorizedError("這個操作需要家長憑證。")
    return verify_access_token(
        token,
        settings=settings,
        expected_role="guardian",
        session_id=session_id,
        child_id=child_id,
    )


def _wallet_read(child_id: str, wallet) -> WalletRead:
    return WalletRead(
        child_id=child_id,
        coin_balance=wallet.coin_balance,
        gem_balance=wallet.gem_balance,
        lifetime_coins=wallet.lifetime_coins,
        lifetime_gems=wallet.lifetime_gems,
    )


def _browser_submission(
    request: ReadingAttemptCreate, settings: Settings
) -> AssessmentSubmission:
    transcript = request.transcript.strip()
    if not transcript:
        quality = ASRQuality.NO_SPEECH
        audio_quality = 0.0
    elif (
        request.recognition_confidence is not None
        and request.recognition_confidence < settings.min_browser_asr_confidence
    ):
        quality = ASRQuality.UNCERTAIN
        audio_quality = 0.75
    else:
        quality = ASRQuality.USABLE
        audio_quality = request.recognition_confidence or 0.75
    return AssessmentSubmission(
        session_id=request.session_id,
        content_id=request.content_id,
        request_id=request.request_id,
        transcript=transcript,
        asr_quality=quality,
        provider_confidence=request.recognition_confidence,
        audio_quality_score=audio_quality,
        duration_ms=request.duration_ms,
        input_mode="BROWSER_ASR",
    )


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health(settings: AppSettings) -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        providers={
            "llm": settings.llm_provider,
            "asr": settings.asr_provider,
            "tts": settings.tts_provider,
        },
    )


@router.get("/content", response_model=list[ContentItemRead], tags=["content"])
def list_content(db: DbSession) -> list[ContentItemRead]:
    items = db.scalars(
        select(ContentItem).where(ContentItem.active.is_(True)).order_by(ContentItem.id)
    )
    return [
        ContentItemRead.model_validate(item).model_copy(
            update={"zhuyin": annotate(item.reference_text)}
        )
        for item in items
    ]


@router.post("/zhuyin", response_model=list[ZhuyinEntry], tags=["content"])
def annotate_zhuyin(request: ZhuyinRequest) -> list[ZhuyinEntry]:
    """把介面上的文字標成注音。純字典查詢，不涉及孩童資料，所以不需要權杖。"""
    entries: list[ZhuyinEntry] = []
    for text in request.texts:
        if len(text) > MAX_ZHUYIN_TEXT_CHARS:
            raise DomainError("要標注音的文字太長了。")
        entries.append(ZhuyinEntry(text=text, readings=annotate(text)))
    return entries


@router.post("/tts", tags=["speech"])
async def synthesize_speech(
    request: TTSRequest,
    settings: AppSettings,
    session_token: SessionToken,
) -> Response:
    """把小芽要說的話合成語音。

    需要學習階段權杖：VoAI 是按字扣點，不能開成任何人都能打的免費轉語音。
    回傳原始音檔位元組，前端直接丟給 <audio> 播。Provider 是 fake 時回 204，
    前端就會自動退回瀏覽器內建的語音合成。
    """
    _authorize_session(session_token, settings=settings)
    text = request.text.strip()
    if not text:
        raise DomainError("沒有可以唸的內容。")
    if len(text) > settings.max_tts_chars:
        raise DomainError(f"一次最多唸 {settings.max_tts_chars} 個字。")
    result = await get_tts_provider(settings).synthesize(text, request.voice)
    if not result.audio:
        return Response(status_code=204)
    return Response(
        content=result.audio,
        media_type=result.content_type or "audio/mpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/tts/speakers", tags=["speech"])
async def list_tts_speakers(
    settings: AppSettings,
    guardian_token: GuardianToken,
) -> list[dict]:
    """列出這把金鑰可用的聲優，給大人挑 VOAI_SPEAKER 用。"""
    _authorize_guardian(guardian_token, settings=settings)
    provider = get_tts_provider(settings)
    if not hasattr(provider, "list_speakers"):
        raise ProviderConfigurationError(
            f"目前的 TTS provider '{provider.name}' 沒有聲優清單。"
        )
    return await provider.list_speakers()


@router.post("/sessions", response_model=SessionRead, status_code=201, tags=["sessions"])
def start_session(request: SessionCreate, db: DbSession, settings: AppSettings) -> SessionRead:
    return create_session(db, request, settings)


@router.post("/sessions/{session_id}/end", response_model=SessionRead, tags=["sessions"])
def finish_session(
    session_id: str,
    db: DbSession,
    settings: AppSettings,
    session_token: SessionToken,
) -> SessionRead:
    _authorize_session(session_token, settings=settings, session_id=session_id)
    return end_session(db, session_id, settings)


@router.post(
    "/reading-attempts/transcript",
    response_model=AssessmentResponse,
    status_code=201,
    tags=["assessment"],
)
async def submit_transcript(
    request: ReadingAttemptCreate,
    db: DbSession,
    settings: AppSettings,
    session_token: SessionToken,
) -> AssessmentResponse:
    _authorize_session(
        session_token,
        settings=settings,
        session_id=request.session_id,
    )
    return await assess_reading(
        db,
        request=_browser_submission(request, settings),
        settings=settings,
        llm=get_llm_provider(settings),
    )


@router.post(
    "/reading-attempts/audio",
    response_model=AssessmentResponse,
    status_code=201,
    tags=["assessment"],
)
async def submit_audio(
    db: DbSession,
    settings: AppSettings,
    session_id: Annotated[str, Form()],
    content_id: Annotated[str, Form()],
    request_id: Annotated[str, Form(min_length=8, max_length=64)],
    audio: Annotated[UploadFile, File()],
    session_token: SessionToken,
    duration_ms: Annotated[int | None, Form(ge=250, le=300_000)] = None,
) -> AssessmentResponse:
    _authorize_session(session_token, settings=settings, session_id=session_id)
    allowed_content_types = {
        "audio/webm",
        "audio/ogg",
        "audio/wav",
        "audio/mpeg",
        "text/plain",
    }
    if audio.content_type not in allowed_content_types:
        raise DomainError("不支援的音訊格式。請使用 WebM、OGG、WAV 或 MP3。")
    payload = await audio.read(settings.max_audio_bytes + 1)
    if len(payload) > settings.max_audio_bytes:
        raise DomainError("音訊檔案過大，請縮短朗讀內容後再試一次。")
    if settings.asr_provider == "fake" and audio.content_type != "text/plain":
        raise DomainError("目前是 Fake ASR；真實錄音請先使用瀏覽器語音辨識模式。")
    asr_result = await get_asr_provider(settings).transcribe(payload)
    return await assess_reading(
        db,
        request=AssessmentSubmission(
            session_id=session_id,
            content_id=content_id,
            request_id=request_id,
            transcript=asr_result.transcript,
            asr_quality=asr_result.quality,
            provider_confidence=asr_result.provider_confidence,
            audio_quality_score=asr_result.provider_confidence or 0.75,
            duration_ms=duration_ms,
            input_mode="SERVER_ASR",
        ),
        settings=settings,
        llm=get_llm_provider(settings),
    )


@router.get("/children/{child_id}/wallet", response_model=WalletRead, tags=["rewards"])
def read_wallet(
    child_id: str,
    db: DbSession,
    settings: AppSettings,
    session_token: SessionToken,
) -> WalletRead:
    claims = _authorize_session(session_token, settings=settings, child_id=child_id)
    get_active_session(db, claims.session_id, settings)
    if db.get(ChildProfile, child_id) is None:
        raise NotFoundError("找不到指定的孩童設定。")
    return _wallet_read(child_id, get_or_create_wallet(db, child_id))


@router.get(
    "/children/{child_id}/reward-transactions",
    response_model=list[RewardTransactionRead],
    tags=["rewards"],
)
def list_reward_transactions(
    child_id: str,
    db: DbSession,
    settings: AppSettings,
    session_token: SessionToken,
) -> list[RewardTransaction]:
    claims = _authorize_session(session_token, settings=settings, child_id=child_id)
    get_active_session(db, claims.session_id, settings)
    if db.get(ChildProfile, child_id) is None:
        raise NotFoundError("找不到指定的孩童設定。")
    statement = (
        select(RewardTransaction)
        .where(RewardTransaction.child_id == child_id)
        .order_by(RewardTransaction.created_at.desc())
    )
    return list(db.scalars(statement))


@router.get("/reward-catalog", tags=["rewards"])
def reward_catalog() -> list[dict]:
    return [
        {
            "item_code": item.code,
            "currency": item.currency,
            "cost": item.cost,
            "label": item.label,
            "description": item.description,
        }
        for item in REWARD_CATALOG.values()
    ]


@router.get(
    "/children/{child_id}/inventory",
    response_model=list[RewardItemRead],
    tags=["rewards"],
)
def read_inventory(
    child_id: str,
    db: DbSession,
    settings: AppSettings,
    session_token: SessionToken,
) -> list:
    claims = _authorize_session(session_token, settings=settings, child_id=child_id)
    get_active_session(db, claims.session_id, settings)
    return list_reward_items(db, child_id)


@router.post("/rewards/redeem", response_model=RedemptionResponse, tags=["rewards"])
def redeem(
    request: RedemptionRequest,
    db: DbSession,
    settings: AppSettings,
    session_token: SessionToken,
) -> RedemptionResponse:
    claims = _authorize_session(
        session_token,
        settings=settings,
        child_id=request.child_id,
    )
    get_active_session(db, claims.session_id, settings)
    if db.get(ChildProfile, request.child_id) is None:
        raise NotFoundError("找不到指定的孩童設定。")
    item, wallet, inventory = redeem_catalog_item(
        db,
        child_id=request.child_id,
        item_code=request.item_code,
        request_id=request.request_id,
        settings=settings,
    )
    db.commit()
    return RedemptionResponse(
        item_code=item.code,
        currency=item.currency,
        cost=item.cost,
        wallet=_wallet_read(request.child_id, wallet),
        inventory=inventory,
    )


def _level_status(db: Session, child: ChildProfile, settings: Settings) -> LevelStatusRead:
    wallet = get_or_create_wallet(db, child.id)
    progression = evaluate_progression(db, child=child, wallet=wallet, settings=settings)
    db.commit()
    return LevelStatusRead(
        child_id=child.id,
        current_level=progression.current_level,
        pending_level=progression.pending_level,
        guardian_approved_level3=child.guardian_approved_level3,
        completed_contents=progression.completed_contents,
        mastered_contents=progression.mastered_contents,
        capabilities=progression.capabilities,
    )


@router.get(
    "/children/{child_id}/level",
    response_model=LevelStatusRead,
    tags=["progression"],
)
def read_level(
    child_id: str,
    db: DbSession,
    settings: AppSettings,
    session_token: SessionToken,
) -> LevelStatusRead:
    claims = _authorize_session(session_token, settings=settings, child_id=child_id)
    get_active_session(db, claims.session_id, settings)
    child = db.get(ChildProfile, child_id)
    if child is None:
        raise NotFoundError("找不到指定的孩童設定。")
    return _level_status(db, child, settings)


@router.put(
    "/children/{child_id}/level-3-approval",
    response_model=LevelStatusRead,
    tags=["progression"],
)
def set_level_three_approval(
    child_id: str,
    request: GuardianLevelApproval,
    db: DbSession,
    settings: AppSettings,
    guardian_token: GuardianToken,
) -> LevelStatusRead:
    claims = _authorize_guardian(
        guardian_token,
        settings=settings,
        child_id=child_id,
    )
    get_active_session(db, claims.session_id, settings)
    child = db.get(ChildProfile, child_id)
    if child is None:
        raise NotFoundError("找不到指定的孩童設定。")
    child.guardian_approved_level3 = request.approved
    if not request.approved and child.current_level >= 3:
        child.current_level = 2
    return _level_status(db, child, settings)


@router.put(
    "/children/{child_id}/demo-level",
    response_model=LevelStatusRead,
    tags=["progression"],
)
def set_demo_level(
    child_id: str,
    request: DemoLevelRequest,
    db: DbSession,
    settings: AppSettings,
    guardian_token: GuardianToken,
) -> LevelStatusRead:
    """Demo 展示用：直接指定角色等級，只在 development 環境開放。"""
    if settings.environment.lower() != "development":
        raise ForbiddenError("展示用的等級切換只在 development 環境開放。")
    claims = _authorize_guardian(guardian_token, settings=settings, child_id=child_id)
    get_active_session(db, claims.session_id, settings)
    child = db.get(ChildProfile, child_id)
    if child is None:
        raise NotFoundError("找不到指定的孩童設定。")
    child.current_level = request.level
    child.guardian_approved_level3 = request.level >= 3
    completed, mastered = content_progress(db, child_id, settings)
    db.commit()
    return LevelStatusRead(
        child_id=child.id,
        current_level=child.current_level,
        pending_level=None,
        guardian_approved_level3=child.guardian_approved_level3,
        completed_contents=completed,
        mastered_contents=mastered,
        capabilities=capabilities_for_level(child.current_level),
    )


@router.post("/dialogue", response_model=DialogueTurnRead, status_code=201, tags=["dialogue"])
async def dialogue(
    request: DialogueTurnCreate,
    db: DbSession,
    settings: AppSettings,
    session_token: SessionToken,
) -> DialogueTurnRead:
    _authorize_session(
        session_token,
        settings=settings,
        session_id=request.session_id,
    )
    return await create_dialogue_turn(
        db,
        request=request,
        settings=settings,
        llm=get_llm_provider(settings),
    )


@router.post("/feedback", response_model=FeedbackRead, status_code=201, tags=["evaluation"])
def create_feedback(
    request: FeedbackCreate,
    db: DbSession,
    settings: AppSettings,
    session_token: SessionToken,
) -> FeedbackEvent:
    claims = _authorize_session(
        session_token,
        settings=settings,
        session_id=request.session_id,
    )
    get_active_session(db, request.session_id, settings)
    if bool(request.assessment_id) == bool(request.dialogue_turn_id):
        raise DomainError("回饋必須指定一個評分結果或一個對話回合。")
    if request.assessment_id:
        assessment = db.get(ReadingAssessment, request.assessment_id)
        attempt = db.get(ReadingAttempt, assessment.attempt_id) if assessment else None
        if attempt is None or attempt.session_id != request.session_id:
            raise NotFoundError("找不到指定的評分結果。")
    if request.dialogue_turn_id:
        turn = db.get(DialogueTurn, request.dialogue_turn_id)
        if turn is None or turn.session_id != request.session_id:
            raise NotFoundError("找不到指定的對話回合。")
    feedback = FeedbackEvent(
        session_id=request.session_id,
        child_id=claims.child_id,
        assessment_id=request.assessment_id,
        dialogue_turn_id=request.dialogue_turn_id,
        helpful=request.helpful,
        relevance=request.relevance,
        reason_code=request.reason_code,
    )
    db.add(feedback)
    db.commit()
    return feedback


@router.get(
    "/sessions/{session_id}/summary",
    response_model=SessionSummary,
    tags=["guardians"],
)
def session_summary(
    session_id: str,
    db: DbSession,
    settings: AppSettings,
    guardian_token: GuardianToken,
) -> SessionSummary:
    claims = _authorize_guardian(
        guardian_token,
        settings=settings,
        session_id=session_id,
    )
    if db.get(ChildProfile, claims.child_id) is None:
        raise NotFoundError("找不到指定的孩童設定。")
    return get_session_summary(db, session_id)


@router.delete(
    "/children/{child_id}",
    response_model=DeleteChildResponse,
    tags=["guardians"],
)
def delete_child(
    child_id: str,
    db: DbSession,
    settings: AppSettings,
    guardian_token: GuardianToken,
    confirm_delete: Annotated[str, Header(alias="X-Confirm-Delete")],
) -> DeleteChildResponse:
    _authorize_guardian(guardian_token, settings=settings, child_id=child_id)
    if confirm_delete != "DELETE":
        raise DomainError("刪除資料需要明確確認。")
    if db.get(ChildProfile, child_id) is None:
        raise NotFoundError("找不到指定的孩童設定。")
    delete_child_data(db, child_id)
    return DeleteChildResponse(child_id=child_id, deleted=True)


@router.websocket("/ws/sessions/{session_id}")
async def session_socket(
    websocket: WebSocket,
    session_id: str,
    access_token: str,
    db: DbSession,
    settings: AppSettings,
) -> None:
    """Small event facade for the future browser avatar; JSON messages only."""
    try:
        _authorize_session(access_token, settings=settings, session_id=session_id)
        get_active_session(db, session_id, settings)
    except DomainError:
        await websocket.close(code=1008, reason="Unauthorized")
        return
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            event_type = payload.get("type")
            event_payload = payload.get("payload", {})
            if event_type == "dialogue.submit":
                request = DialogueTurnCreate(
                    session_id=session_id,
                    request_id=event_payload.get("request_id", ""),
                    message=event_payload.get("message", ""),
                )
                response = await create_dialogue_turn(
                    db,
                    request=request,
                    settings=settings,
                    llm=get_llm_provider(settings),
                )
                await websocket.send_json(
                    {"type": "dialogue.completed", "payload": response.model_dump(mode="json")}
                )
            elif event_type == "reading.submit":
                request = ReadingAttemptCreate(session_id=session_id, **event_payload)
                response = await assess_reading(
                    db,
                    request=_browser_submission(request, settings),
                    settings=settings,
                    llm=get_llm_provider(settings),
                )
                await websocket.send_json(
                    {"type": "reading.assessed", "payload": response.model_dump(mode="json")}
                )
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "payload": {
                            "code": "UNKNOWN_EVENT",
                            "message": "不支援的事件類型。",
                        },
                    }
                )
    except WebSocketDisconnect:
        return
    except (DomainError, ValidationError) as exc:
        code = exc.code if isinstance(exc, DomainError) else "VALIDATION_ERROR"
        message = exc.message if isinstance(exc, DomainError) else "事件資料格式不正確。"
        details = exc.errors(include_input=False) if isinstance(exc, ValidationError) else None
        await websocket.send_json(
            {
                "type": "error",
                "payload": {"code": code, "message": message, "details": details},
            }
        )
        await websocket.close(code=1008)
