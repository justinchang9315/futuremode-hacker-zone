from typing import Any

import httpx

from app.exceptions import UpstreamServiceError
from app.providers.base import TTSResult

CONTENT_TYPES = {"wav": "audio/wav", "mp3": "audio/mpeg", "pcm": "audio/pcm"}
# 清單裡的 gender 欄位用中文，前端與 API 用 male/female。
VOICE_GENDERS = {"male": "男聲", "female": "女聲"}


def flatten_speakers(payload: Any) -> list[dict[str, Any]]:
    """把 GetSpeaker 的回應攤平成一維聲優清單。

    VoAI 回的是 {"data": {"models": [{"info": {"version": "Neo"}, "speakers": [...]}]}}，
    同一個名字可能同時出現在 Classic / Neo / Sota+ 底下且風格不同，
    所以攤平時要把版本補進每一筆，選聲優時才能對得上 VOAI_MODEL。
    """
    data = payload.get("data", payload) if isinstance(payload, dict) else None
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list):
        return []
    speakers: list[dict[str, Any]] = []
    for model in models:
        if not isinstance(model, dict):
            continue
        info = model.get("info")
        version = info.get("version") if isinstance(info, dict) else None
        for speaker in model.get("speakers") or []:
            if isinstance(speaker, dict) and speaker.get("name"):
                speakers.append({**speaker, "version": version})
    return speakers


class VoAITTSProvider:
    """VoAI（絕好聲創）文字轉語音。

    API Key 只留在後端；前端一律呼叫 /v1/tts 取音檔，不會拿到金鑰。
    文件：https://connect.voai.ai/doc-vocal/index.html
    """

    name = "voai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        speaker_male: str,
        speaker_female: str,
        default_voice: str,
        style: str,
        speed: float,
        pitch_shift: int,
        style_weight: float,
        breath_pause: int,
        output_format: str,
        sample_rate: int | None,
        timeout_seconds: float,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.style = style
        self.speed = speed
        self.pitch_shift = pitch_shift
        self.style_weight = style_weight
        self.breath_pause = breath_pause
        self.output_format = output_format
        self.sample_rate = sample_rate
        self.timeout_seconds = timeout_seconds
        self.default_voice = default_voice
        # 空字串代表「還沒挑聲優」：第一次合成時依 gender 自動挑，之後沿用同一位。
        self._speakers = {
            "male": speaker_male.strip(),
            "female": speaker_female.strip(),
        }

    @property
    def content_type(self) -> str:
        return CONTENT_TYPES.get(self.output_format, "application/octet-stream")

    def _headers(self) -> dict[str, str]:
        headers = {"x-api-key": self.api_key, "x-output-format": self.output_format}
        if self.sample_rate:
            headers["x-sample-rate"] = str(self.sample_rate)
        return headers

    def _failure(self, response: httpx.Response) -> UpstreamServiceError:
        if response.status_code in {401, 403}:
            return UpstreamServiceError("VoAI API Key 無效或沒有這個服務的權限。")
        if response.status_code == 429:
            return UpstreamServiceError("VoAI 點數不足或已超過速率限制。")
        if response.status_code == 404:
            return UpstreamServiceError(
                f"VoAI 找不到這位聲優或風格 '{self.style}'，"
                "請用 GET /v1/tts/speakers 確認可用名稱。"
            )
        return UpstreamServiceError(
            f"VoAI 合成失敗（HTTP {response.status_code}）。{response.text.strip()[:200]}"
        )

    async def list_speakers(self) -> list[dict[str, Any]]:
        """回傳帳號可用的聲優清單，給家長／開發者挑 VOAI_SPEAKER 用。"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(
                    f"{self.base_url}/TTS/GetSpeaker", headers=self._headers()
                )
        except httpx.HTTPError as exc:
            raise UpstreamServiceError("無法連線到 VoAI，請檢查網路後重試。") from exc
        if response.status_code >= 400:
            raise self._failure(response)
        return flatten_speakers(response.json())

    async def _speaker_name(self, voice: str | None) -> str:
        voice = voice if voice in self._speakers else self.default_voice
        if self._speakers[voice]:
            return self._speakers[voice]
        # 只挑得起目前 VOAI_MODEL 的聲優，選到別版的會被上游退回。
        gender = VOICE_GENDERS[voice]
        for entry in await self.list_speakers():
            if entry.get("version") != self.model or entry.get("gender") != gender:
                continue
            styles = entry.get("styles") or []
            if styles and self.style not in styles:
                continue
            self._speakers[voice] = str(entry["name"]).strip()
            return self._speakers[voice]
        raise UpstreamServiceError(
            f"VoAI 清單裡沒有支援 {self.model} 模型、風格「{self.style}」的{gender}，"
            f"請在 backend/.env 指定 VOAI_SPEAKER_{voice.upper()}。"
        )

    async def synthesize(self, text: str, voice: str | None = None) -> TTSResult:
        body = {
            "version": self.model,
            "text": text,
            "speaker": await self._speaker_name(voice),
            "style": self.style,
            "speed": self.speed,
            "pitch_shift": self.pitch_shift,
            "style_weight": self.style_weight,
            "breath_pause": self.breath_pause,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/TTS/Speech", headers=self._headers(), json=body
                )
        except httpx.HTTPError as exc:
            raise UpstreamServiceError("無法連線到 VoAI，請檢查網路後重試。") from exc
        if response.status_code >= 400:
            raise self._failure(response)
        content_type = response.headers.get("content-type", "")
        if "json" in content_type.lower():
            raise UpstreamServiceError(
                f"VoAI 回傳的不是音訊：{response.text.strip()[:200]}"
            )
        if not response.content:
            raise UpstreamServiceError("VoAI 沒有回傳音訊內容。")
        return TTSResult(
            provider=self.name,
            audio_url=None,
            audio=response.content,
            content_type=content_type or self.content_type,
        )
