import json
from typing import Any

from app.enums import ASRQuality
from app.providers.base import ASRResult, TTSResult


class FakeASRProvider:
    name = "fake"

    async def transcribe(self, audio: bytes) -> ASRResult:
        """Decode UTF-8 bytes for deterministic tests; this is not real speech recognition."""
        try:
            transcript = audio.decode("utf-8").strip()
        except UnicodeDecodeError:
            return ASRResult("", ASRQuality.UNCERTAIN, None)
        quality = ASRQuality.USABLE if transcript else ASRQuality.NO_SPEECH
        return ASRResult(transcript, quality, 1.0 if transcript else 0.0)


class FakeTTSProvider:
    name = "fake"

    async def synthesize(self, text: str, voice: str | None = None) -> TTSResult:
        return TTSResult(provider=self.name, audio_url=None)


class FakeLLMProvider:
    name = "fake"

    async def compose_feedback(self, context: dict[str, Any]) -> str:
        score = context.get("score")
        practice_point = context.get("practice_point")
        if score is None:
            speech = "我剛剛沒有聽清楚，我們可以再試一次。"
            return json.dumps({"speech": speech, "follow_up": None}, ensure_ascii=False)
        if practice_point:
            speech = f"你完成這次朗讀了，得到 {score} 分。{practice_point}"
            return json.dumps({"speech": speech, "follow_up": None}, ensure_ascii=False)
        speech = f"你完成這次朗讀了，得到 {score} 分。要不要再挑戰一次？"
        return json.dumps({"speech": speech, "follow_up": None}, ensure_ascii=False)

    async def reply(self, message: str, context: dict[str, Any]) -> str:
        return json.dumps(
            {
                "speech": "我有聽到你的想法。你可以再告訴我一點嗎？",
                "follow_up": None,
            },
            ensure_ascii=False,
        )
