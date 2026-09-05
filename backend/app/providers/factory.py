from app.config import Settings, get_settings
from app.exceptions import ProviderConfigurationError
from app.providers.base import ASRProvider, LLMProvider, TTSProvider
from app.providers.fake import FakeASRProvider, FakeLLMProvider, FakeTTSProvider
from app.providers.gemini_llm import GeminiLLMProvider
from app.providers.openai_compatible_llm import OpenAICompatibleLLMProvider
from app.providers.openai_llm import OpenAILLMProvider
from app.providers.voai_tts import VoAITTSProvider


def _only_fake(provider_kind: str, provider_name: str) -> None:
    if provider_name != "fake":
        raise ProviderConfigurationError(
            f"{provider_kind} provider '{provider_name}' 尚未實作。"
            "請先保持 fake，或新增 Adapter 後再於 .env 設定 API Key。"
        )


def get_asr_provider(settings: Settings | None = None) -> ASRProvider:
    settings = settings or get_settings()
    _only_fake("ASR", settings.asr_provider)
    return FakeASRProvider()


def get_tts_provider(settings: Settings | None = None) -> TTSProvider:
    settings = settings or get_settings()
    if settings.tts_provider == "fake":
        return FakeTTSProvider()
    if settings.tts_provider == "voai":
        secret = settings.voai_api_key
        api_key = secret.get_secret_value().strip() if secret else ""
        if not api_key:
            raise ProviderConfigurationError(
                "缺少 VOAI_API_KEY，請在 backend/.env 中設定 VoAI（絕好聲創）API Key。"
            )
        output_format = settings.voai_output_format.strip().lower()
        if output_format not in {"wav", "mp3"}:
            raise ProviderConfigurationError(
                "VOAI_OUTPUT_FORMAT 只能是 wav 或 mp3；pcm 是串流格式，瀏覽器播不了。"
            )
        if settings.voai_model not in {"Neo", "Classic"}:
            raise ProviderConfigurationError("VOAI_MODEL 只能是 Neo 或 Classic。")
        sample_rate = settings.voai_sample_rate
        if sample_rate and sample_rate not in {8000, 16000, 32000, 44100}:
            raise ProviderConfigurationError(
                "VOAI_SAMPLE_RATE 只能是 8000、16000、32000、44100，或留空使用預設。"
            )
        if settings.voai_model == "Neo" and sample_rate and sample_rate > 32000:
            raise ProviderConfigurationError("Neo 模型的取樣率上限是 32000。")
        return VoAITTSProvider(
            api_key=api_key,
            base_url=settings.voai_base_url,
            model=settings.voai_model,
            speaker_male=settings.voai_speaker_male,
            speaker_female=settings.voai_speaker_female,
            default_voice=settings.voai_default_voice,
            style=settings.voai_style,
            speed=settings.voai_speed,
            pitch_shift=settings.voai_pitch_shift,
            style_weight=settings.voai_style_weight,
            breath_pause=settings.voai_breath_pause,
            output_format=output_format,
            sample_rate=sample_rate,
            timeout_seconds=settings.voai_timeout_seconds,
        )
    raise ProviderConfigurationError(
        f"TTS provider '{settings.tts_provider}' 尚未實作。可用值為 fake 或 voai。"
    )


def get_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if settings.llm_provider == "fake":
        return FakeLLMProvider()
    if settings.llm_provider == "openai":
        secret = settings.openai_api_key
        api_key = secret.get_secret_value().strip() if secret else ""
        if not api_key:
            raise ProviderConfigurationError(
                "缺少 OPENAI_API_KEY，請在 backend/.env 中設定 OpenAI Platform API Key；"
                "Atlas Oracle API Key 不能用於 LLM。"
            )
        return OpenAILLMProvider(
            api_key=api_key,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if settings.llm_provider == "gemini":
        secret = settings.gemini_api_key
        api_key = secret.get_secret_value().strip() if secret else ""
        if not api_key:
            raise ProviderConfigurationError(
                "缺少 GEMINI_API_KEY，請在 backend/.env 中設定 Google Gemini API Key。"
            )
        return GeminiLLMProvider(
            api_key=api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if settings.llm_provider == "gmi_cloud":
        secret = settings.gmi_cloud_api_key
        api_key = secret.get_secret_value().strip() if secret else ""
        if not api_key:
            raise ProviderConfigurationError(
                "缺少 GMI_CLOUD_API_KEY，請在 backend/.env 中設定 GMI Cloud API Key。"
            )
        return OpenAICompatibleLLMProvider(
            provider_name="gmi_cloud",
            display_name="GMI Cloud",
            api_key=api_key,
            base_url=settings.gmi_cloud_base_url,
            model=settings.gmi_cloud_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if settings.llm_provider == "eastrouter":
        secret = settings.eastrouter_api_key
        api_key = secret.get_secret_value().strip() if secret else ""
        base_url = settings.eastrouter_base_url.strip()
        model = settings.eastrouter_model.strip()
        if not api_key:
            raise ProviderConfigurationError(
                "缺少 EASTROUTER_API_KEY，請在 backend/.env 中設定 EastRouter API Key。"
            )
        if not base_url or not model:
            raise ProviderConfigurationError(
                "EastRouter 還需要 EASTROUTER_BASE_URL 與 EASTROUTER_MODEL。"
            )
        return OpenAICompatibleLLMProvider(
            provider_name="eastrouter",
            display_name="EastRouter",
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    raise ProviderConfigurationError(
        f"LLM provider '{settings.llm_provider}' 尚未實作。"
    )
