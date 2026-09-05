from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.enums import AssessmentStatus, Currency, ResponseSource, SafetyLevel


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str
    environment: str
    providers: dict[str, str]


class SessionCreate(BaseModel):
    child_id: str | None = None
    # 孩子的暱稱。有帶 child_id 時會順便更新，讓改名不用重開一個孩子。
    display_name: str | None = Field(default=None, max_length=20)
    age: int = Field(default=7, ge=6, le=8)
    grade_level: int = Field(default=2, ge=1, le=3)
    guardian_present: bool
    guardian_acknowledged_ai: bool
    guardian_acknowledged_privacy: bool
    # 同意文字改過就要跳版，家長同意的是哪一版才追得回來。
    # v2：加上「保存孩子輸入的暱稱」。
    consent_version: str = Field(default="phase1-v2", min_length=1, max_length=32)


class SessionRead(ORMModel):
    id: str
    child_id: str
    display_name: str | None = None
    status: str
    started_at: datetime
    ended_at: datetime | None
    current_level: int
    session_token: str | None = None
    guardian_token: str | None = None
    token_expires_at: datetime | None = None
    session_expires_at: datetime | None = None


class ContentItemRead(ORMModel):
    id: str
    title: str
    author: str | None
    content_type: str
    reference_text: str
    # 與 reference_text 等長；標點符號為 None。
    zhuyin: list[str | None] = []
    grade_level: int
    source: str
    license_label: str
    scoring_config: dict[str, Any]


class ZhuyinRequest(BaseModel):
    """一次送多段文字，讓前端可以整頁批次標注。"""

    texts: list[str] = Field(min_length=1, max_length=300)


class ZhuyinEntry(BaseModel):
    text: str
    # 與 text 等長；標點與非漢字為 None。
    readings: list[str | None]


class TTSRequest(BaseModel):
    """一句要唸出來的台詞。長度上限在 Settings.max_tts_chars（VoAI 是 1 字 1 點）。"""

    text: str = Field(min_length=1)
    # 男聲／女聲切換；不給就用 VOAI_DEFAULT_VOICE。
    voice: Literal["male", "female"] | None = None


class ReadingAttemptCreate(BaseModel):
    session_id: str
    content_id: str
    request_id: str = Field(min_length=8, max_length=64)
    transcript: str = Field(default="", max_length=4000)
    recognition_confidence: float | None = Field(default=None, ge=0, le=1)
    duration_ms: int | None = Field(default=None, ge=250, le=300_000)


class ScoreBreakdown(BaseModel):
    accuracy: int
    completeness: int
    fluency: int


class RewardGrant(BaseModel):
    currency: Currency
    amount: int
    reason_code: str


class CompanionResponse(BaseModel):
    level: int
    speech: str | None
    body_actions: list[str]
    response_source: ResponseSource
    follow_up: dict[str, Any] | None = None


class AssessmentResponse(BaseModel):
    attempt_id: str
    assessment_id: str
    status: AssessmentStatus
    score: int | None
    assessment_confidence: float
    score_policy_version: str
    breakdown: ScoreBreakdown | None
    evidence: dict[str, Any]
    rewards: list[RewardGrant]
    companion: CompanionResponse
    current_level: int
    pending_level: int | None = None
    measurement_note: str = "Demo 文字對照分數，不代表發音或情緒評量。"


class WalletRead(BaseModel):
    child_id: str
    coin_balance: int
    gem_balance: int
    lifetime_coins: int
    lifetime_gems: int


class RewardTransactionRead(ORMModel):
    id: str
    currency: Currency
    amount: int
    reason_code: str
    policy_version: str
    extra_data: dict[str, Any]
    created_at: datetime


class RewardItemRead(ORMModel):
    item_code: str
    quantity: int
    equipped: bool
    acquired_at: datetime


class LevelStatusRead(BaseModel):
    child_id: str
    current_level: int
    pending_level: int | None
    guardian_approved_level3: bool
    completed_contents: int
    mastered_contents: int
    capabilities: list[str]


class GuardianLevelApproval(BaseModel):
    approved: bool = True


class DemoLevelRequest(BaseModel):
    level: int = Field(ge=1, le=3)


class RedemptionRequest(BaseModel):
    child_id: str
    item_code: str = Field(min_length=1, max_length=64)
    request_id: str = Field(min_length=8, max_length=64)


class RedemptionResponse(BaseModel):
    item_code: str
    currency: Currency
    cost: int
    wallet: WalletRead
    inventory: list[RewardItemRead]


class DialogueTurnCreate(BaseModel):
    session_id: str
    request_id: str = Field(min_length=8, max_length=64)
    message: str = Field(min_length=1, max_length=2000)


class DialogueTurnRead(BaseModel):
    turn_id: str
    safety_level: SafetyLevel
    response: CompanionResponse


class FeedbackCreate(BaseModel):
    session_id: str
    assessment_id: str | None = None
    dialogue_turn_id: str | None = None
    helpful: bool
    relevance: int = Field(ge=1, le=5)
    reason_code: str | None = Field(default=None, max_length=32)


class FeedbackRead(ORMModel):
    id: str
    helpful: bool
    relevance: int
    reason_code: str | None
    created_at: datetime


class SessionSummary(BaseModel):
    session_id: str
    child_id: str
    status: str
    completed_attempts: int
    average_score: float | None
    earned_coins: int
    earned_gems: int
    safety_events: int
    content_titles: list[str]
    guardian_prompt: str


class DeleteChildResponse(BaseModel):
    child_id: str
    deleted: bool


class ErrorResponse(BaseModel):
    code: str
    message: str