import re
import time
from dataclasses import dataclass, field

from openai import OpenAI

from .log import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Content normalisation patterns
#
# Processing order matters:
#   1. <|token|>  — GPT-OSS special tokens: everything FROM the first token
#                   onwards is model-internal structured payload; discard it all.
#                   Must be first: no point running later patterns on the payload.
#   2. <think>/[THINK] — CoT reasoning blocks: enclosed content is scratch-pad,
#                   not the answer; remove the whole block.
#   3. <tool_call> — hallucinated tool-call markup in text mode (Qwen3, Gemma):
#                   remove the whole block.  Includes Gemma-4 variant with pipe
#                   delimiters: <|tool_call>...<tool_call|>.
#   4. [INST]/<s> — Mistral template tokens: these delimit content that IS the
#                   answer; strip only the tokens, keep the content between them.
# ---------------------------------------------------------------------------

# 1. GPT-OSS <|token|> — split at first occurrence, discard remainder
_GPT_OSS_TOKEN_RE = re.compile(r"<\|[a-zA-Z0-9_]+\|>")

# 2. Thinking / reasoning blocks (angle-bracket and square-bracket variants)
_THINK_RE = re.compile(
    r"(<(think|thinking|reasoning)>.*?</\2>|\[THINK\].*?\[/THINK\])",
    re.DOTALL | re.IGNORECASE,
)

# 3. Hallucinated <tool_call> blocks in text mode
#    Variant A: Qwen3 style  — <tool_call>...</tool_call>
#    Variant B: Gemma-4 style — <|tool_call>...<tool_call|>
_TOOL_CALL_RE = re.compile(
    r"<\|?tool_call\|?>.*?</?(?:\|?tool_call\|?|tool_call\|)>",
    re.DOTALL | re.IGNORECASE,
)

# 4. Mistral / Mixtral template tokens (strip tokens, keep content between them)
_MISTRAL_TOKEN_RE = re.compile(
    r"\[/?INST\]|\[/?SYS\]|</?s>",
    re.IGNORECASE,
)


@dataclass
class _NormResult:
    text: str
    tool_call_stripped: bool = False


def _normalise_content(raw: str) -> _NormResult:
    """Strip model-internal markup from LLM text content.

    Applied in the order documented above so that each step only processes
    content that is genuinely part of the answer.

    Returns a *_NormResult* carrying the cleaned text and flags indicating
    what was stripped (used by callers to distinguish hallucinated tool calls
    from potential prompt injection).
    """
    text = raw
    tool_call_stripped = False

    # 1. GPT-OSS: everything from the first <|token|> is internal payload
    if _GPT_OSS_TOKEN_RE.search(text):
        text = _GPT_OSS_TOKEN_RE.split(text, maxsplit=1)[0]
        log.warning("Stripped GPT-OSS <|special_token|> payload from LLM response")

    # 2. Thinking / reasoning blocks
    cleaned = _THINK_RE.sub("", text)
    if cleaned != text:
        log.debug("Stripped thinking/reasoning block from LLM response")
    text = cleaned

    # 3. Hallucinated tool_call blocks
    cleaned = _TOOL_CALL_RE.sub("", text)
    if cleaned != text:
        log.warning("Stripped hallucinated <tool_call> block from LLM response")
        tool_call_stripped = True
    text = cleaned

    # 4. Mistral template tokens (keep the content between them)
    cleaned = _MISTRAL_TOKEN_RE.sub("", text)
    if cleaned != text:
        log.debug("Stripped Mistral template tokens from LLM response")
    text = cleaned

    return _NormResult(text=text.strip(), tool_call_stripped=tool_call_stripped)


@dataclass
class LLMResponse:
    """Normalised LLM response — content has model-internal markup stripped."""
    content: str
    tool_calls: list = field(default_factory=list)
    tool_call_stripped: bool = False


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

        norm = _normalise_content(msg.content or "")

        if msg.tool_calls:
            calls = [(tc.function.name, tc.function.arguments[:80]) for tc in msg.tool_calls]
            log.info("LLM response (%.1fs): %d tool_call(s): %s", elapsed, len(msg.tool_calls), calls)
        else:
            preview = norm.text[:120].replace("\n", " ")
            log.info("LLM response (%.1fs): text=%r", elapsed, preview)

        usage = response.usage
        if usage:
            log.debug(
                "Token usage: prompt=%d completion=%d total=%d",
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
            )

        return LLMResponse(
            content=norm.text,
            tool_calls=msg.tool_calls or [],
            tool_call_stripped=norm.tool_call_stripped,
        )
