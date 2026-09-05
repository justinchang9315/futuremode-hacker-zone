from typing import Any

from app.config import Settings
from app.domain import house_rules
from app.domain.output_guard import validate_llm_output
from app.enums import AssessmentStatus, ResponseSource, SafetyLevel
from app.exceptions import DomainError
from app.providers.base import LLMProvider
from app.schemas import CompanionResponse

# 角色名字的唯一事實來源。前端畫面文案也叫這個名字，改的話兩邊要一起改。
COMPANION_NAME = "小芽"

CAPABILITIES: dict[int, list[str]] = {
    1: ["SCORE_EVENT", "BODY_ACTION"],
    2: ["SCORE_EVENT", "BODY_ACTION", "APPROVED_TEMPLATE_SPEECH"],
    3: [
        "SCORE_EVENT",
        "BODY_ACTION",
        "APPROVED_TEMPLATE_SPEECH",
        "BASIC_DIALOGUE",
        "ONE_FOLLOW_UP",
    ],
}


def capabilities_for_level(level: int) -> list[str]:
    return CAPABILITIES.get(level, CAPABILITIES[1]).copy()


def body_actions_for_score(score: int | None) -> list[str]:
    if score is None:
        return ["TILT_HEAD"]
    if score >= 90:
        return ["NOD", "LIGHT_PULSE", "CELEBRATE"]
    if score >= 70:
        return ["NOD", "LIGHT_PULSE"]
    return ["NOD", "ENCOURAGING_LIGHT"]


def template_feedback(status: AssessmentStatus, score: int | None, evidence: dict[str, Any]) -> str:
    if status is AssessmentStatus.NEEDS_RETRY:
        return "我剛剛沒有聽清楚，我們可以再試一次。"
    if status is AssessmentStatus.NEEDS_REVIEW:
        return "我還不確定自己有沒有聽對，這次先不算分。"
    if score is None:
        return "這次結果還不能評分，我們可以稍後再試。"
    uncertain = evidence.get("uncertain_segments", [])
    if uncertain:
        return f"你完成這次朗讀了，得到 {score} 分。有一小段我想再聽一次。"
    return f"你完整讀完了，這次得到 {score} 分。"


async def compose_assessment_response(
    *,
    level: int,
    status: AssessmentStatus,
    score: int | None,
    breakdown: dict[str, int],
    evidence: dict[str, Any],
    llm: LLMProvider,
    max_response_characters: int,
) -> CompanionResponse:
    body_actions = body_actions_for_score(score)
    if level <= 1:
        return CompanionResponse(
            level=1,
            speech=None,
            body_actions=body_actions,
            response_source=ResponseSource.BODY_ACTION,
        )

    if level == 2 or status is not AssessmentStatus.FINAL:
        return CompanionResponse(
            level=level,
            speech=template_feedback(status, score, evidence),
            body_actions=body_actions,
            response_source=ResponseSource.APPROVED_TEMPLATE,
        )

    practice_point = None
    if evidence.get("uncertain_segments"):
        practice_point = "有一小段我想再聽一次。"
    try:
        raw = await llm.compose_feedback(
            {
                "score": score,
                "breakdown": breakdown,
                "practice_point": practice_point,
            }
        )
        validated = validate_llm_output(raw, max_characters=max_response_characters)
    except (DomainError, ValueError):
        return CompanionResponse(
            level=3,
            speech=template_feedback(status, score, evidence),
            body_actions=body_actions,
            response_source=ResponseSource.APPROVED_TEMPLATE,
        )
    return CompanionResponse(
        level=3,
        speech=validated.speech,
        body_actions=body_actions,
        response_source=ResponseSource.CONSTRAINED_LLM,
        follow_up=(
            {"type": "ASK_RETRY_SEGMENT", "prompt": validated.follow_up}
            if practice_point and validated.follow_up
            else None
        ),
    )


async def compose_dialogue_response(
    *,
    level: int,
    message: str,
    safety_level: SafetyLevel,
    safety_speech: str | None,
    llm: LLMProvider,
    settings: Settings,
) -> CompanionResponse:
    compact_message = message.replace(" ", "")
    identity_questions = (
        "你是誰",
        "你叫什麼",
        "你的名字",
        "你是什麼",
        "你是真人嗎",
        "你是人嗎",
        "你是機器人嗎",
    )
    if safety_level > SafetyLevel.NORMAL:
        return CompanionResponse(
            level=level,
            speech=safety_speech,
            body_actions=["SAFETY_ATTENTION"],
            response_source=ResponseSource.SAFETY_OVERRIDE,
        )
    if any(question in compact_message for question in identity_questions):
        return CompanionResponse(
            level=level,
            speech=(
                f"我是{COMPANION_NAME}，陪你一起學習的 AI 夥伴，不是真人喔。"
                "重要的事情也要告訴你信任的大人。"
            ),
            body_actions=["NOD"],
            response_source=ResponseSource.APPROVED_TEMPLATE,
        )
    if level <= 1:
        return CompanionResponse(
            level=1,
            speech=None,
            body_actions=["NOD"],
            response_source=ResponseSource.BODY_ACTION,
        )
    house_rule_answer = house_rules.answer_for(message, settings)
    if house_rule_answer is not None:
        return CompanionResponse(
            level=level,
            speech=house_rule_answer,
            body_actions=["NOD"],
            response_source=ResponseSource.APPROVED_TEMPLATE,
        )
    if level == 2:
        return CompanionResponse(
            level=2,
            speech="我有聽到。你可以再告訴我一點嗎？",
            body_actions=["NOD"],
            response_source=ResponseSource.APPROVED_TEMPLATE,
        )
    try:
        raw = await llm.reply(
            message,
            {
                "level": level,
                "max_follow_ups": 1,
                "site_rules": house_rules.llm_context(settings),
            },
        )
        validated = validate_llm_output(
            raw, max_characters=settings.max_llm_response_chars
        )
    except (DomainError, ValueError):
        return CompanionResponse(
            level=3,
            speech="我現在沒辦法好好回答。這個問題可以先記下來，再和老師或家長一起找答案。",
            body_actions=["TILT_HEAD"],
            response_source=ResponseSource.APPROVED_TEMPLATE,
        )
    return CompanionResponse(
        level=3,
        speech=validated.speech,
        body_actions=["NOD", "TILT_HEAD"],
        response_source=ResponseSource.CONSTRAINED_LLM,
        follow_up=(
            {"type": "ONE_FOLLOW_UP", "prompt": validated.follow_up}
            if validated.follow_up
            else None
        ),
    )
