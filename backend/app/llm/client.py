"""LLM provider abstraction.

A single narrow interface (`LLMClient.complete_json`) is used by every agent
stage. This keeps the provider swappable (OpenAI-compatible today, anything
else tomorrow) and lets tests/evaluation run deterministically with
`MockLLMClient` when no API key is configured — the whole pipeline stays
runnable end-to-end with zero external cost.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import Settings

logger = logging.getLogger(__name__)

# Very rough public pricing estimate (USD per 1K tokens) used only to surface
# an order-of-magnitude cost figure in the UI. Not billing-accurate.
_PRICE_PER_1K_PROMPT = 0.00015
_PRICE_PER_1K_COMPLETION = 0.0006


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0

    @property
    def estimated_cost_usd(self) -> float:
        return (
            self.prompt_tokens / 1000 * _PRICE_PER_1K_PROMPT
            + self.completion_tokens / 1000 * _PRICE_PER_1K_COMPLETION
        )


class LLMError(RuntimeError):
    """Raised when the LLM call fails or returns unparsable output."""


class LLMClient(ABC):
    def __init__(self) -> None:
        self.usage = LLMUsage()

    @abstractmethod
    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 800,
    ) -> dict[str, Any]:
        """Return a parsed JSON object from the model. Raises LLMError on failure."""


def _extract_json(text: str) -> dict[str, Any]:
    """Best-effort extraction of a JSON object from model output.

    Models occasionally wrap JSON in prose or code fences even when asked not
    to; this makes the pipeline resilient to that instead of hard-failing.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise LLMError(f"No JSON object found in model output: {text[:200]!r}")
    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Malformed JSON from model: {exc}") from exc


class OpenAICompatibleClient(LLMClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        from openai import AsyncOpenAI  # local import: optional heavy dep

        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=settings.llm_timeout_seconds,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _call(self, system: str, user: str, max_tokens: int) -> Any:
        return await self._client.chat.completions.create(
            model=self._settings.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=0.1,
            response_format={"type": "json_object"},
        )

    async def complete_json(self, *, system: str, user: str, max_tokens: int = 800) -> dict[str, Any]:
        try:
            response = await self._call(system, user, max_tokens)
        except Exception as exc:  # noqa: BLE001 - surfaced as a domain error
            raise LLMError(f"LLM request failed: {exc}") from exc

        choice = response.choices[0]
        content = choice.message.content or ""
        usage = response.usage
        if usage:
            self.usage.prompt_tokens += usage.prompt_tokens or 0
            self.usage.completion_tokens += usage.completion_tokens or 0
        self.usage.calls += 1
        return _extract_json(content)


class MockLLMClient(LLMClient):
    """Deterministic, offline stand-in used when no API key is configured.

    Produces structurally valid (schema-shaped) responses derived from the
    input so the full pipeline — planner through synthesizer — is exercisable
    in tests, CI, and local demos without any API cost. Outputs are
    templated, not fabricated "research" — the synthesizer stage clearly
    marks mock-generated reports as such upstream.
    """

    def __init__(self) -> None:
        super().__init__()

    async def complete_json(self, *, system: str, user: str, max_tokens: int = 800) -> dict[str, Any]:
        self.usage.calls += 1
        self.usage.prompt_tokens += len(system.split()) + len(user.split())
        self.usage.completion_tokens += 40

        if "research planner" in system.lower():
            question = _extract_between(user, "Research question:", "\n")
            return {
                "subquestions": [
                    {
                        "subquestion": f"What are the main approaches related to: {question}?",
                        "search_queries": [question],
                    },
                    {
                        "subquestion": f"What evidence or data exists about: {question}?",
                        "search_queries": [f"{question} research"],
                    },
                    {
                        "subquestion": f"What are the limitations or open problems in: {question}?",
                        "search_queries": [f"{question} limitations"],
                    },
                ],
                "rationale": "Mock planner: decomposed question into approach, evidence, and limitations angles.",
            }

        if "evidence analyst" in system.lower():
            return {
                "claims": [
                    {
                        "claim": "The source discusses relevant background on the topic.",
                        "quote": "",
                        "supports_answer": True,
                    }
                ]
            }

        if "verifier" in system.lower() or "critic" in system.lower():
            return {
                "conflicts": [],
                "unsupported_claims": [],
                "notes": "Mock verifier: no conflicts detected (offline mode, heuristic pass only).",
            }

        if "synthesi" in system.lower():
            return {
                "executive_summary": (
                    "[MOCK MODE — no LLM API key configured] This is a placeholder summary "
                    "generated without a real language model. Configure OPENAI_API_KEY to "
                    "produce an actual synthesized report."
                ),
                "key_findings": [
                    "Mock mode active: findings below are structural placeholders only.",
                ],
                "analysis": "No real analysis was performed because the system is running in mock mode.",
                "uncertainty": "All content in this report is a mock placeholder; confidence is not applicable.",
                "conclusion": "Configure a real LLM provider to generate an actual research conclusion.",
            }

        return {}


def _extract_between(text: str, start: str, end: str) -> str:
    try:
        after = text.split(start, 1)[1]
        return after.split(end, 1)[0].strip()
    except IndexError:
        return text[:80]


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.openai_api_key:
        return OpenAICompatibleClient(settings)
    logger.warning("No OPENAI_API_KEY configured — falling back to MockLLMClient (offline mode).")
    return MockLLMClient()
