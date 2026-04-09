from __future__ import annotations

from typing import TYPE_CHECKING

from .log import get_logger

if TYPE_CHECKING:
    from .llm import LLMClient

log = get_logger(__name__)

COMPRESSION_SYSTEM_PROMPT = (
    "You are a conversation summarizer. "
    "Summarize the following conversation history concisely, "
    "preserving key facts, decisions, and results. "
    "Reply with only the summary text."
)


class Memory:
    """Multi-turn conversation memory with LLM-based context compression.

    Two-tier storage:
    - compressed_summary: LLM summary of older turns (may be None)
    - messages:           Recent turns kept verbatim
    """

    def __init__(
        self,
        llm: LLMClient,
        context_limit: int = 65536,
        compress_threshold: float = 0.75,
        keep_recent_turns: int = 8,
    ) -> None:
        self._llm = llm
        self._compress_at = int(context_limit * compress_threshold)
        self._keep_recent = keep_recent_turns
        self.messages: list[dict] = []
        self.compressed_summary: str | None = None
        log.debug(
            "Memory initialized: context_limit=%d compress_at=%d keep_recent=%d",
            context_limit,
            self._compress_at,
            keep_recent_turns,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})
        tokens = self._estimate_tokens()
        log.debug(
            "Memory.add [%s]: %d chars → estimated %d tokens total",
            role, len(content), tokens,
        )
        if tokens >= self._compress_at:
            log.info(
                "Memory: token estimate %d ≥ compress_at %d — triggering compression",
                tokens, self._compress_at,
            )
            self._compress()

    def get_messages(self, system_prompt: str) -> list[dict]:
        result: list[dict] = [{"role": "system", "content": system_prompt}]
        if self.compressed_summary:
            result.append(
                {
                    "role": "system",
                    "content": f"[Earlier conversation summary]\n{self.compressed_summary}",
                }
            )
        result.extend(self.messages)
        log.debug(
            "Memory.get_messages: %d message(s) returned (summary=%s, recent=%d)",
            len(result),
            "yes" if self.compressed_summary else "no",
            len(self.messages),
        )
        return result

    def estimate_tokens(self) -> int:
        return self._estimate_tokens()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _estimate_tokens(self) -> int:
        total = sum(len(m["content"]) for m in self.messages)
        if self.compressed_summary:
            total += len(self.compressed_summary)
        return total // 4

    def _compress(self) -> None:
        if len(self.messages) <= self._keep_recent:
            log.debug("Memory: compression skipped (messages=%d ≤ keep_recent=%d)", len(self.messages), self._keep_recent)
            return

        n_compress = len(self.messages) - self._keep_recent
        log.info("Memory: compressing %d turn(s), keeping %d recent", n_compress, self._keep_recent)

        to_compress = self.messages[: -self._keep_recent]
        self.messages = self.messages[-self._keep_recent :]

        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in to_compress
        )
        if self.compressed_summary:
            log.debug("Memory: chaining with existing summary (%d chars)", len(self.compressed_summary))
            history_text = (
                f"[Previous summary]\n{self.compressed_summary}\n\n"
                f"[New messages]\n{history_text}"
            )

        summary_messages = [
            {"role": "system", "content": COMPRESSION_SYSTEM_PROMPT},
            {"role": "user", "content": history_text},
        ]
        response = self._llm.chat(summary_messages)
        self.compressed_summary = response.content or ""
        log.info(
            "Memory: compression done — summary=%d chars, remaining messages=%d",
            len(self.compressed_summary),
            len(self.messages),
        )
