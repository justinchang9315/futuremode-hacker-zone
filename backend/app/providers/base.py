from dataclasses import dataclass
from typing import Any, Protocol

from app.enums import ASRQuality


@dataclass(frozen=True)
class ASRResult:
    transcript: str
    quality: ASRQuality
    provider_confidence: float | None
    no_speech_probability: float | None = None


@dataclass(frozen=True)
class TTSResult:
    provider: str
    audio_url: str | None
    # 直接回傳音訊位元組的 Provider（例如 VoAI）用這兩欄，/v1/tts 會原樣送給前端。
    audio: bytes | None = None
    content_type: str | None = None


class ASRProvider(Protocol):
    name: str

    async def transcribe(self, audio: bytes) -> ASRResult: ...


class TTSProvider(Protocol):
    name: str

    async def synthesize(self, text: str, voice: str | None = None) -> TTSResult: ...


class LLMProvider(Protocol):
    name: str

    async def compose_feedback(self, context: dict[str, Any]) -> str: ...

    async def reply(self, message: str, context: dict[str, Any]) -> str: ...

