import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .log import get_logger

log = get_logger(__name__)

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "agent-skeleton" / "config.toml"


@dataclass
class LLMConfig:
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "dummy"
    model: str = "local-model"
    context_limit: int = 65536


@dataclass
class AgentConfig:
    compress_threshold: float = 0.75
    keep_recent_turns: int = 8
    max_iterations: int = 20
    max_tool_output_chars: int = 20000


@dataclass
class SecurityConfig:
    # Roots in addition to cwd and /tmp that the agent is allowed to access.
    allowed_paths: list[str] = field(default_factory=list)


@dataclass
class MCPServerConfig:
    transport: str = "stdio"   # "stdio" or "sse"
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""              # used when transport == "sse"


@dataclass
class Config:
    llm: LLMConfig = field(default_factory=LLMConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    mcp_servers: dict[str, MCPServerConfig] = field(default_factory=dict)


def load_config(path: Path | None = None) -> Config:
    resolved = path or DEFAULT_CONFIG_PATH
    if not resolved.exists():
        return Config()

    with open(resolved, "rb") as f:
        data = tomllib.load(f)

    llm = _build_section(LLMConfig, data.get("llm", {}), "llm")
    agent = _build_section(AgentConfig, data.get("agent", {}), "agent")
    security = _build_section(SecurityConfig, data.get("security", {}), "security")

    # Top-level unknown keys (excluding known sections)
    known_top = {"llm", "agent", "security", "mcp"}
    for key in data:
        if key not in known_top:
            log.warning("config: unknown top-level key '%s' (typo?)", key)

    mcp_servers: dict[str, MCPServerConfig] = {}
    for name, srv in data.get("mcp", {}).get("servers", {}).items():
        mcp_servers[name] = _build_section(
            MCPServerConfig, srv, f"mcp.servers.{name}",
        )

    return Config(llm=llm, agent=agent, security=security, mcp_servers=mcp_servers)


def _build_section(cls: type, raw: dict, section: str):
    """Build a dataclass from raw dict, warning on unknown keys."""
    known = cls.__dataclass_fields__
    for key in raw:
        if key not in known:
            log.warning(
                "config [%s]: unknown key '%s' (typo?); known keys: %s",
                section, key, ", ".join(sorted(known)),
            )
    return cls(**{k: v for k, v in raw.items() if k in known})
