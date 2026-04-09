import tomllib
from dataclasses import dataclass, field
from pathlib import Path

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

    llm = LLMConfig(**{k: v for k, v in data.get("llm", {}).items() if k in LLMConfig.__dataclass_fields__})
    agent = AgentConfig(**{k: v for k, v in data.get("agent", {}).items() if k in AgentConfig.__dataclass_fields__})
    security = SecurityConfig(**{k: v for k, v in data.get("security", {}).items() if k in SecurityConfig.__dataclass_fields__})

    mcp_servers: dict[str, MCPServerConfig] = {}
    for name, srv in data.get("mcp", {}).get("servers", {}).items():
        mcp_servers[name] = MCPServerConfig(
            **{k: v for k, v in srv.items() if k in MCPServerConfig.__dataclass_fields__}
        )

    return Config(llm=llm, agent=agent, security=security, mcp_servers=mcp_servers)
