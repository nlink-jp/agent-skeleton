import time

from openai import OpenAI
from openai.types.chat import ChatCompletionMessage

from .log import get_logger

log = get_logger(__name__)


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model
        log.info("LLMClient initialized: model=%s base_url=%s", model, base_url)

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ChatCompletionMessage:
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

        if msg.tool_calls:
            calls = [(tc.function.name, tc.function.arguments[:80]) for tc in msg.tool_calls]
            log.info("LLM response (%.1fs): %d tool_call(s): %s", elapsed, len(msg.tool_calls), calls)
        else:
            preview = (msg.content or "")[:120].replace("\n", " ")
            log.info("LLM response (%.1fs): text=%r", elapsed, preview)

        usage = response.usage
        if usage:
            log.debug(
                "Token usage: prompt=%d completion=%d total=%d",
                usage.prompt_tokens,
                usage.completion_tokens,
                usage.total_tokens,
            )

        return msg
