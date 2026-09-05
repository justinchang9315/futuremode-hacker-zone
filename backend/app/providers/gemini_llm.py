import json
from typing import Any

import httpx
from google import genai
from google.genai import errors, types

from app.exceptions import UpstreamServiceError
from app.providers.prompts import CHILD_COMPANION_INSTRUCTIONS


class GeminiLLMProvider:
    name = "gemini"

    def __init__(self, *, api_key: str, model: str, timeout_seconds: float):
        self.model = model
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )

    async def _create_response(self, input_text: str) -> str:
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=input_text,
                config=types.GenerateContentConfig(
                    system_instruction=CHILD_COMPANION_INSTRUCTIONS,
                    max_output_tokens=512,
                    thinking_config=types.ThinkingConfig(
                        thinking_level=types.ThinkingLevel.LOW,
                    ),
                ),
            )
        except errors.APIError as exc:
            if exc.code in {401, 403}:
                message = "Gemini API Key 無效或沒有使用此模型的權限。"
            elif exc.code == 429:
                message = "Gemini 額度不足或已超過速率限制。"
            elif exc.code == 404:
                message = f"找不到 Gemini 模型 '{self.model}'。"
            else:
                message = "Gemini API 呼叫失敗。"
            raise UpstreamServiceError(message) from exc
        except (httpx.HTTPError, TimeoutError) as exc:
            raise UpstreamServiceError(
                "無法連線到 Gemini API，請檢查網路後重試。"
            ) from exc

        output_text = response.text
        if not output_text or not output_text.strip():
            raise UpstreamServiceError("Gemini 沒有回傳可用的文字內容。")
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
