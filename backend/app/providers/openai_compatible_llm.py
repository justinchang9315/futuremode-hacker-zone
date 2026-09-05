import json
from typing import Any

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
)

from app.exceptions import UpstreamServiceError
from app.providers.prompts import CHILD_COMPANION_INSTRUCTIONS


class OpenAICompatibleLLMProvider:
    """Adapter for providers exposing an OpenAI-compatible Chat Completions API."""

    def __init__(
        self,
        *,
        provider_name: str,
        display_name: str,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ):
        self.name = provider_name
        self.display_name = display_name
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )

    async def _create_response(self, input_text: str) -> str:
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": CHILD_COMPANION_INSTRUCTIONS},
                    {"role": "user", "content": input_text},
                ],
                max_tokens=180,
            )
        except AuthenticationError as exc:
            raise UpstreamServiceError(
                f"{self.display_name} API Key 無效，請確認金鑰屬於該服務。"
            ) from exc
        except PermissionDeniedError as exc:
            raise UpstreamServiceError(
                f"{self.display_name} 沒有使用模型 '{self.model}' 的權限。"
            ) from exc
        except RateLimitError as exc:
            raise UpstreamServiceError(
                f"{self.display_name} 額度不足或已超過速率限制。"
            ) from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise UpstreamServiceError(
                f"無法連線到 {self.display_name}，請檢查 Base URL 與網路。"
            ) from exc
        except OpenAIError as exc:
            raise UpstreamServiceError(
                f"{self.display_name} LLM API 呼叫失敗。"
            ) from exc

        if not completion.choices:
            raise UpstreamServiceError(f"{self.display_name} 沒有回傳回答。")
        output_text = completion.choices[0].message.content
        if not output_text or not output_text.strip():
            raise UpstreamServiceError(f"{self.display_name} 沒有回傳可用的文字內容。")
        return output_text.strip()

    async def compose_feedback(self, context: dict[str, Any]) -> str:
        context_text = json.dumps(context, ensure_ascii=False)
        return await self._create_response(
            "請根據這次朗讀評量提供一句鼓勵和一個可執行的練習建議。"
            f"評量資料：{context_text}"
        )

    async def reply(self, message: str, context: dict[str, Any]) -> str:
        context_text = json.dumps(context, ensure_ascii=False)
        return await self._create_response(
            f"孩子說：{message}\n對話限制：{context_text}"
        )
