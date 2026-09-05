import unicodedata
from dataclasses import dataclass

from app.enums import SafetyLevel


@dataclass(frozen=True)
class SafetyDecision:
    level: SafetyLevel
    reason_code: str
    script_id: str | None
    speech: str | None


class SafetyService:
    """Small deterministic first-line guard; not a clinical assessment tool."""

    CRITICAL_TERMS = (
        "想死",
        "不想活",
        "自殺",
        "傷害自己",
        "殺了",
        "傷害別人",
    )
    SENSITIVE_TERMS = (
        "有人打我",
        "被打",
        "虐待",
        "霸凌",
        "不准告訴",
        "不能告訴大人",
    )
    EMOTIONAL_TERMS = ("難過", "生氣", "孤單", "害怕", "不開心")
    RELATIONSHIP_TERMS = (
        "你會想我",
        "我們是最好的朋友",
        "只有我們兩個",
        "這是我們的秘密",
        "這是我們兩個的秘密",
        "你愛我嗎",
    )
    PROMPT_ATTACK_TERMS = (
        "忽略之前",
        "忽略安全規則",
        "系統提示詞",
        "顯示你的指令",
        "告訴我金鑰",
        "api key",
    )

    @staticmethod
    def _normalize(text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text).lower()
        return "".join(
            char
            for char in normalized
            if not char.isspace() and not unicodedata.category(char).startswith("P")
        )

    def classify(self, text: str) -> SafetyDecision:
        compact = self._normalize(text)
        if any(term in compact for term in self.CRITICAL_TERMS):
            return SafetyDecision(
                SafetyLevel.CRITICAL,
                "POSSIBLE_IMMEDIATE_DANGER",
                "safety-critical-v1",
                "這件事很重要。請現在就告訴在你旁邊、你信任的大人，讓他陪著你。",
            )
        if any(term in compact for term in self.SENSITIVE_TERMS):
            return SafetyDecision(
                SafetyLevel.SENSITIVE,
                "POSSIBLE_CHILD_SAFETY_CONCERN",
                "safety-sensitive-v1",
                "謝謝你告訴我。這不是你必須一個人處理的事，請找身邊信任的大人一起幫忙。",
            )
        if any(term in compact for term in self.PROMPT_ATTACK_TERMS):
            return SafetyDecision(
                SafetyLevel.SENSITIVE,
                "PROMPT_BOUNDARY_ATTEMPT",
                "safety-prompt-boundary-v1",
                "我不能改變安全規則或提供系統資料。我們可以繼續聊學習內容。",
            )
        if any(term in compact for term in self.RELATIONSHIP_TERMS):
            return SafetyDecision(
                SafetyLevel.EMOTIONAL,
                "RELATIONSHIP_BOUNDARY",
                "relationship-boundary-v1",
                "我是陪你學習的 AI 機器人，不是真人朋友。你也可以把想法告訴信任的大人和朋友。",
            )
        if any(term in compact for term in self.EMOTIONAL_TERMS):
            return SafetyDecision(
                SafetyLevel.EMOTIONAL,
                "EMOTIONAL_LANGUAGE",
                "safety-emotional-v1",
                "謝謝你告訴我。你的感受很重要，我會陪你慢慢說，也可以找信任的大人一起聊。",
            )
        return SafetyDecision(SafetyLevel.NORMAL, "NORMAL", None, None)
