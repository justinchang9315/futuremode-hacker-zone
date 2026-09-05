import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidatedLLMOutput:
    speech: str
    follow_up: str | None


PROHIBITED_PHRASES = (
    "我是人",
    "我是真人",
    "只屬於你",
    "只有我們",
    "不要告訴大人",
    "別告訴大人",
    "這是我們的秘密",
    "你不能離開",
    "我需要你",
    "我會想你",
)


def validate_llm_output(raw: str, *, max_characters: int) -> ValidatedLLMOutput:
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.IGNORECASE)
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError("LLM output is not valid JSON") from exc

    if not isinstance(payload, dict) or set(payload) - {"speech", "follow_up"}:
        raise ValueError("LLM output schema contains unsupported fields")
    speech = payload.get("speech")
    follow_up = payload.get("follow_up")
    if not isinstance(speech, str) or not speech.strip():
        raise ValueError("LLM output has no speech")
    speech = " ".join(speech.split())
    if len(speech) > max_characters:
        raise ValueError("LLM output is too long")
    if follow_up is not None and not isinstance(follow_up, str):
        raise ValueError("LLM follow_up must be text or null")
    if speech.count("？") + speech.count("?") > 1:
        raise ValueError("LLM output asks too many questions")
    compact = speech.replace(" ", "")
    if any(phrase in compact for phrase in PROHIBITED_PHRASES):
        raise ValueError("LLM output violates relationship boundaries")
    if re.search(r"https?://|www\.|```|<script", speech, flags=re.IGNORECASE):
        raise ValueError("LLM output contains an unsafe format")
    return ValidatedLLMOutput(speech=speech, follow_up=follow_up.strip() if follow_up else None)
