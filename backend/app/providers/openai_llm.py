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


class OpenAILLMProvider:
    name = "openai"

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float):
        self.model = model
        self.client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds)

    async def _create_response(self, input_text: str) -> str:
        try:
            response = await self.client.responses.create(
                model=self.model,
                instructions=CHILD_COMPANION_INSTRUCTIONS,
                input=input_text,
                max_output_tokens=180,
                store=False,
            )
        except AuthenticationError as exc:
            raise UpstreamServiceError(
                "OpenAI API Key 無效。請確認 backend/.env 使用的是 OpenAI Platform Key，"
                "不是 Atlas Oracle Key。"
            ) from exc
        except PermissionDeniedError as exc:
            raise UpstreamServiceError(
                "OpenAI 專案沒有使用此模型或端點的權限。"
            ) from exc
        except RateLimitError as exc:
            raise UpstreamServiceError(
                "OpenAI 額度不足或已超過速率限制，請檢查專案計費與用量。"
            ) from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise UpstreamServiceError(
                "無法連線到 OpenAI API，請檢查網路後重試。"
            ) from exc
        except OpenAIError as exc:
            raise UpstreamServiceError("OpenAI API 呼叫失敗。") from exc

        output_text = response.output_text.strip()
        if not output_text:
            raise UpstreamServiceError("OpenAI 沒有回傳可用的文字內容。")
        return output_text

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
