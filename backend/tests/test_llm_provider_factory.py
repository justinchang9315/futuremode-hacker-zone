import pytest

from app.config import Settings
from app.exceptions import ProviderConfigurationError
from app.providers.factory import get_llm_provider
from app.providers.gemini_llm import GeminiLLMProvider
from app.providers.openai_compatible_llm import OpenAICompatibleLLMProvider


def test_gemini_provider_uses_its_own_configuration() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="gemini",
        gemini_api_key="gemini-test-key",
        gemini_model="gemini-test-model",
    )

    provider = get_llm_provider(settings)

    assert isinstance(provider, GeminiLLMProvider)
    assert provider.name == "gemini"
    assert provider.model == "gemini-test-model"


def test_gmi_cloud_provider_uses_its_own_configuration() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="gmi_cloud",
        gmi_cloud_api_key="gmi-test-key",
        gmi_cloud_base_url="https://api.gmi-serving.com/v1",
        gmi_cloud_model="test-model",
    )

    provider = get_llm_provider(settings)

    assert isinstance(provider, OpenAICompatibleLLMProvider)
    assert provider.name == "gmi_cloud"
    assert provider.model == "test-model"


def test_eastrouter_requires_key_base_url_and_model() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="eastrouter",
        eastrouter_api_key="east-test-key",
    )

    with pytest.raises(ProviderConfigurationError):
        get_llm_provider(settings)


def test_eastrouter_provider_uses_its_own_configuration() -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="eastrouter",
        eastrouter_api_key="east-test-key",
        eastrouter_base_url="https://example.invalid/v1",
        eastrouter_model="test-model",
    )

    provider = get_llm_provider(settings)

    assert isinstance(provider, OpenAICompatibleLLMProvider)
    assert provider.name == "eastrouter"
    assert provider.model == "test-model"
