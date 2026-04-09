import re
import time
from dataclasses import dataclass, field

from openai import OpenAI

from .log import get_logger

log = get_logger(__name__)

# Thinking / reasoning blocks emitted by chain-of-thought models.
# Covers both angle-bracket (<think>) and square-bracket ([THINK]) variants.
# Strip the entire block — callers only need the final answer.
_THINK_RE = re.compile(
    r"(<(think|thinking|reasoning)>.*?</\2>|\[THINK\].*?\[/THINK\])",
    re.DOTALL | re.IGNORECASE,
)

# Mistral / Mixtral instruction and sentence boundary tokens that may leak
# into content when the model's chat template is not applied server-side.
_MISTRAL_TOKEN_RE = re.compile(
    r"(\[INST\]|\[/INST\]|<s>|</s>|\[SYS\]|\[/SYS\])",
    re.IGNORECASE,
)


@dataclass
class LLMResponse:
    """Normalised LLM response — content has model-internal markup stripped."""
    content: str
    tool_calls: list = field(default_factory=list)


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        log.info("LLMClient initialized: model=%s base_url=%s", model, base_url)

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        kwargs: dict = {"model": self.model, "messages": messages}
        if tools:
            kwargs["tools"] = tools
            # tool_choice omitted: local LLMs handle tools better without explicit setting

        roles = [m["role"] for m in messages]
        tool_names = [t["function"]["name"] for t in (tools or [])]
        log.debug(
            "LLM request: %d messages %s | tools=[%s]",
            len(messages),
            roles,
            ", ".join(tool_names) if tool_names else "none",
        )

        t0 = time.monotonic()
        response = self._client.chat.completions.create(**kwargs)
        elapsed = time.monotonic() - t0
        msg = response.choices[0].message

        # Normalise content: strip model-internal markup so callers always
        # receive the final answer text only.
        raw_content = msg.content or ""
        clean_content = _THINK_RE.sub("", raw_content).strip()
        if clean_content != raw_content.strip():
            log.debug("Stripped thinking/reasoning block from LLM response")
        before_mistral = clean_content
        clean_content = _MISTRAL_TOKEN_RE.sub("", clean_content).strip()
        if clean_content != before_mistral:
            log.debug("Stripped Mistral instruction tokens from LLM response")

        if msg.tool_calls:
            calls = [(tc.function.name, tc.function.arguments[:80]) for tc in msg.tool_calls]
            log.info("LLM response (%.1fs): %d tool_call(s): %s", elapsed, len(msg.tool_calls), calls)
        else:
            preview = clean_content[:120].replace("\n", " ")
            log.info("LLM response (%.1fs): text=%r", elapsed, preview)

        usage = response.usage
        if usage:
            log.debug(
                "Token usage: prompt=%d completion=%d total=%d",
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
            )

        return LLMResponse(content=clean_content, tool_calls=msg.tool_calls or [])
