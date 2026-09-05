from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Child Teaching Companion API"
    environment: str = "development"
    api_prefix: str = "/v1"
    cors_origins: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173"
    )

    database_url: str = "sqlite:///./companion.db"
    auto_create_schema: bool = True
    seed_demo_content: bool = True
    app_secret_key: SecretStr = SecretStr("development-only-change-me")
    access_token_minutes: int = Field(default=30, ge=5, le=1440)
    session_duration_minutes: int = Field(default=10, ge=5, le=60)
    requests_per_minute: int = Field(default=120, ge=10, le=1000)
    max_audio_bytes: int = Field(default=5_000_000, ge=100_000, le=25_000_000)
    max_llm_response_chars: int = Field(default=240, ge=80, le=600)

    llm_provider: str = "fake"
    llm_model: str = "gpt-4o"
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    openai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.6-flash"
    gmi_cloud_api_key: SecretStr | None = None
    gmi_cloud_base_url: str = "https://api.gmi-serving.com/v1"
    gmi_cloud_model: str = "deepseek-ai/DeepSeek-R1"
    eastrouter_api_key: SecretStr | None = None
    eastrouter_base_url: str = ""
    eastrouter_model: str = ""
    asr_provider: str = "fake"
    asr_api_key: SecretStr | None = None
    tts_provider: str = "fake"
    tts_api_key: SecretStr | None = None

    # VoAI（絕好聲創）語音合成。金鑰只留在後端，前端一律走 /v1/tts。
    voai_api_key: SecretStr | None = None
    voai_base_url: str = "https://connect.voai.ai"
    voai_model: str = "Neo"
    # 男聲／女聲各一位，前端可以即時切換。任一欄留空時，會依聲優清單的 gender
    # 自動挑一位符合模型與風格的；用 GET /v1/tts/speakers 可以看有哪些。
    voai_speaker_male: str = "辰辰"
    voai_speaker_female: str = "品妍"
    voai_default_voice: str = "male"
    voai_style: str = "預設"
    voai_speed: float = Field(default=1.0, ge=0.5, le=1.5)
    voai_pitch_shift: int = Field(default=0, ge=-5, le=5)
    voai_style_weight: float = Field(default=0.0, ge=0, le=1)
    voai_breath_pause: int = Field(default=0, ge=0, le=10)
    # pcm 是串流格式，瀏覽器的 <audio> 播不了，所以只開放 wav 與 mp3。
    voai_output_format: str = "mp3"
    voai_sample_rate: int | None = None
    voai_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    # 一句台詞的上限。VoAI 是 1 字 1 點，這個值同時是扣點的煞車。
    max_tts_chars: int = Field(default=200, ge=20, le=2000)

    score_policy_version: str = "reading-v1"
    reward_policy_version: str = "reward-v1"
    safety_policy_version: str = "safety-v1"

    min_audio_quality: float = Field(default=0.50, ge=0, le=1)
    min_browser_asr_confidence: float = Field(default=0.55, ge=0, le=1)
    min_assessment_confidence: float = Field(default=0.65, ge=0, le=1)
    good_reading_score: int = Field(default=60, ge=0, le=100)
    mastery_score: int = Field(default=80, ge=0, le=100)
    mastery_confidence: float = Field(default=0.85, ge=0, le=1)

    level_2_lifetime_coins: int = Field(default=30, ge=0)
    level_2_completed_contents: int = Field(default=2, ge=0)
    level_3_lifetime_gems: int = Field(default=2, ge=0)
    level_3_mastered_contents: int = Field(default=2, ge=0)


    @field_validator("voai_default_voice")
    @classmethod
    def _voice_must_be_known(cls, value: str) -> str:
        voice = value.strip().lower()
        if voice not in {"male", "female"}:
            raise ValueError("VOAI_DEFAULT_VOICE 只能是 male 或 female。")
        return voice

    @field_validator("voai_sample_rate", mode="before")
    @classmethod
    def _blank_sample_rate_means_default(cls, value: object) -> object:
        """.env 裡留空代表「用 VoAI 的預設取樣率」，不是 0 也不是錯誤。"""
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
