# アーキテクチャドキュメント — agent-skeleton

> 対象バージョン: v0.1.0  
> 位置づけ: 概念実証（POC）— 動作検証済み、本番利用は想定しない

---

## 目次

1. [概要](#1-概要)
2. [ディレクトリ構成](#2-ディレクトリ構成)
3. [モジュール依存グラフ](#3-モジュール依存グラフ)
4. [コンポーネント詳細](#4-コンポーネント詳細)
5. [データフロー](#5-データフロー)
6. [メモリ管理](#6-メモリ管理)
7. [ツール層](#7-ツール層)
8. [MCP統合](#8-mcp統合)
9. [設定スキーマ](#9-設定スキーマ)
10. [設計判断の記録](#10-設計判断の記録)
11. [POCとしての割り切りと将来課題](#11-pocとしての割り切りと将来課題)

---

## 1. 概要

agent-skeleton は「自律エージェントの骨格」を実装した概念実証プロジェクトである。

**コアコンセプト:**
- ユーザーが自然言語でゴールを伝えると、エージェントが**計画を立案**し、**ユーザーの承認を得て**から実行する
- ツールを呼び出す前には必ず**「何を・なぜ」を提示して許可を求める**
- 会話の文脈はマルチターンにわたって**メモリに保持**され、コンテキストウィンドウが逼迫したときは**LLMが自動的に要約・圧縮**する
- ツールは内蔵とMCP接続の両方を同一インターフェースで扱う

**対象LLM:** OpenAI互換API（ローカルLLMを主想定）

---

## 2. ディレクトリ構成

```
agent-skeleton/
│
├── main.py                    ← エントリポイント（cli.app.run を呼ぶだけ）
├── config.example.toml        ← 設定ファイルのサンプル
├── pyproject.toml             ← Python パッケージ定義（uv管理）
│
├── agent/                     ← コアパッケージ ★独立してインポート可能★
│   ├── __init__.py            ← Agent をエクスポート
│   ├── agent.py               ← Agent クラス（オーケストレーター）
│   ├── config.py              ← TOML設定の読み込みとデータクラス
│   ├── llm.py                 ← OpenAI互換LLMクライアント
│   ├── log.py                 ← ロギング設定（AGENT_LOG_LEVEL環境変数）
│   ├── memory.py              ← 会話メモリ + コンテキスト圧縮
│   ├── planner.py             ← 計画生成（JSON形式）+ フォーマット
│   ├── executor.py            ← ステップ実行 + 承認ループ
│   │
│   ├── tools/                 ← ツール層
│   │   ├── base.py            ← Tool 抽象基底クラス / ToolResult
│   │   ├── file_tool.py       ← FileReadTool / FileWriteTool
│   │   ├── shell_tool.py      ← ShellTool（危険コマンド検出付き）
│   │   └── web_tool.py        ← WebSearchTool（DuckDuckGo）
│   │
│   └── mcp/
│       └── client.py          ← MCPManager / MCPTool
│
├── cli/
│   └── app.py                 ← Rich ベースのCLI（承認ダイアログ）
│
├── tests/
│   ├── test_file_tool.py
│   ├── test_memory.py
│   ├── test_planner.py
│   └── test_shell_tool.py
│
└── docs/
    └── architecture.ja.md     ← このファイル
```

**重要な設計原則: `agent/` は `cli/` に依存しない。依存は一方向。**

```
cli/ ──依存→ agent/
              ↑
           (外部からのインポートも可能)
```

---

## 3. モジュール依存グラフ

```
main.py
  └── cli.app
        └── agent.Agent
              ├── agent.config      (load_config)
              ├── agent.llm         (LLMClient)
              ├── agent.memory      (Memory)
              ├── agent.planner     (Planner)
              ├── agent.executor    (Executor)
              ├── agent.tools.*     (FileReadTool, FileWriteTool, ShellTool, WebSearchTool)
              └── agent.mcp.client  (MCPManager, MCPTool)

agent.llm         ← agent.log
agent.memory      ← agent.llm, agent.log
agent.planner     ← agent.llm, agent.log
agent.executor    ← agent.llm, agent.log, agent.tools.base
agent.mcp.client  ← agent.tools.base, agent.config
```

---

## 4. コンポーネント詳細

### 4.1 Agent（`agent/agent.py`）

オーケストレーター。他のすべてのコンポーネントを所有し、公開APIを提供する。

```python
class Agent:
    def plan(self, user_goal: str) -> dict        # 計画生成
    def format_plan(self, plan: dict) -> str      # 表示用文字列に変換
    def execute(self, user_goal: str, plan: dict) -> str  # 実行 + メモリ更新

    @classmethod
    def from_config(cls, approver, config_path=None) -> Agent  # ファクトリ
```

`from_config` が単一のエントリポイントとなっており、設定ファイルを読み込んで全コンポーネントを組み上げる。**承認コールバック（`approver`）はここで注入される**ため、UIロジックがコアに漏れない。

---

### 4.2 LLMClient（`agent/llm.py`）

OpenAI互換APIへの薄いラッパー。

```python
class LLMClient:
    def chat(self, messages: list[dict], tools: list[dict] | None = None) -> ChatCompletionMessage
```

**ローカルLLM向けの注意点:**
- `tool_choice` は指定しない（Qwen3等のローカルLLMのjinjaテンプレートがエラーになるため）
- リクエスト・レスポンスのタイミング、トークン使用量をDEBUGログに記録

---

### 4.3 Memory（`agent/memory.py`）

マルチターンの会話履歴を管理する。2層構造でコンテキストウィンドウ圧迫を防ぐ。

```python
class Memory:
    def add(self, role: str, content: str) -> None   # ターン追加（圧縮チェック付き）
    def get_messages(self, system_prompt: str) -> list[dict]  # LLMに渡すメッセージ列を返す
    def estimate_tokens(self) -> int                  # 現在の推定トークン数
```

詳細は [§6 メモリ管理](#6-メモリ管理) を参照。

---

### 4.4 Planner（`agent/planner.py`）

ゴールと利用可能ツールのリストをLLMに渡し、JSON形式の計画を生成する。

```python
class Planner:
    def create_plan(self, user_goal: str) -> dict   # JSON計画を返す
    def format_plan(self, plan: dict) -> str         # CLI表示用文字列
```

**計画のスキーマ:**

```json
{
  "goal": "ゴールの再表現",
  "steps": [
    {
      "step": 1,
      "description": "このステップで何をするか",
      "tool": "tool_name または null",
      "reason": "このステップが必要な理由"
    }
  ]
}
```

JSONパースに失敗した場合は、単一ステップのフォールバック計画を返す（実行が止まらないよう設計）。

---

### 4.5 Executor（`agent/executor.py`）

計画のステップを順番に実行する。各ステップ内でLLMを呼び出してツール引数を決定し、承認を得てから実行する。

```python
class Executor:
    def execute_plan(self, plan: dict, history: list[dict]) -> list[str]
    # 承認コールバック: ApproverFn = Callable[[str, dict, str], bool]
    # (tool_name, args, reason) -> True=実行 / False=スキップ
```

**承認コールバックの分離:**
Executor はユーザーへの表示や入力取得を一切行わない。承認の判断は外部から注入された `approver` 関数が行う。これにより CLI・テスト・自動承認など異なる環境で同じ Executor を使える。

詳細は [§5 データフロー](#5-データフロー) を参照。

---

### 4.6 Config（`agent/config.py`）

TOML設定ファイルを読み込みデータクラスに変換する。

```python
@dataclass class LLMConfig       # LLMエンドポイント・モデル・コンテキスト上限
@dataclass class AgentConfig     # 圧縮閾値・直近ターン数・最大反復数
@dataclass class MCPServerConfig # transport / command / args / env / url
@dataclass class Config          # 上記をまとめたルートクラス

def load_config(path: Path | None = None) -> Config
```

設定ファイルが存在しない場合はデフォルト値でそのまま起動する（デフォルト: `http://localhost:1234/v1`）。

---

### 4.7 log（`agent/log.py`）

全モジュール共通のロガー設定。

```python
def get_logger(name: str) -> logging.Logger
```

`AGENT_LOG_LEVEL` 環境変数でレベルを制御（デフォルト: `INFO`）。

| 環境変数 | 出力内容 |
|---------|---------|
| `INFO`（デフォルト） | 計画生成・ステップ開始/終了・ツール実行結果・メモリ圧縮イベント |
| `DEBUG` | 上記 + LLMへのリクエスト詳細・トークン使用量・各イテレーション |

```bash
AGENT_LOG_LEVEL=DEBUG uv run python main.py
```

---

## 5. データフロー

### 5.1 起動フロー

```
Agent.from_config(approver)
  │
  ├── load_config()          ~/.config/agent-skeleton/config.toml を読む
  ├── LLMClient(...)         OpenAI互換クライアントを初期化
  ├── Memory(...)            空のメモリを初期化
  ├── [FileReadTool, FileWriteTool, ShellTool, WebSearchTool]  内蔵ツール
  ├── MCPManager.load_all()  設定された各MCPサーバーに接続してツールを列挙
  ├── Planner(llm, all_tools)
  └── Executor(llm, all_tools, approver)
```

### 5.2 1ターンの実行フロー

```
ユーザー入力 (user_goal)
  │
  ▼
Agent.plan(user_goal)
  └── Planner.create_plan()
        └── LLM呼び出し（ツールなし）
              → JSON計画を返す
  │
  ▼
CLIが計画を表示 → ユーザーが全体承認 or キャンセル
  │
  ▼（承認された場合）
Agent.execute(user_goal, plan)
  ├── Memory.get_messages()     会話履歴を取得（システムプロンプト + サマリ + 直近ターン）
  ├── Executor.execute_plan()   ← §5.3 へ
  ├── Memory.add("user", ...)   ゴールを記録
  └── Memory.add("assistant", ...) 結果を記録（圧縮チェック）
  │
  ▼
CLIが結果を表示
```

### 5.3 ツール実行ループ（ステップごと）

```
Executor._execute_step(step, history, previous_results)
  │
  ├── [ツールなしの場合]
  │     LLM呼び出し（テキスト応答） → 結果文字列を返す
  │
  └── [ツールありの場合]
        messages = [*history, user(コンテキスト)]
        │
        ▼
      ┌─── LLM呼び出し（tool_call生成） ─────────────────────┐
      │                                                      │
      │  tool_calls あり？                                   │
      │    Yes → tool_call を処理                            │
      │    No  → LLMのテキスト応答を返す（ループ終了）         │
      │                                                      │
      │  各 tool_call に対して:                               │
      │    1. approver(tool_name, args, reason) を呼ぶ       │
      │         → False: "スキップ" をtool結果として追加       │
      │         → True:  Tool.execute(**args) を呼ぶ         │
      │                   → ToolResult.output をtool結果に  │
      │    2. messages に assistant + tool_result を追加     │
      │                                                      │
      └───────────────────────────────────────────┬──────────┘
                          ↑ ループ               │ max_iterations 到達 → 打ち切り
                          └───────────────────────┘
```

**メッセージ構造の変化（イテレーション内）:**

```
イテレーション 1 開始:
  messages = [system, user(コンテキスト)]

  LLM → tool_call(shell_exec, {command: "ls *.py"})

  messages += [
    assistant(tool_calls=[...]),
    tool(tool_call_id=..., content="main.py\n")
  ]

イテレーション 2:
  messages = [system, user, assistant, tool]

  LLM → テキスト応答（ツール不要と判断）→ ループ終了
```

---

## 6. メモリ管理

### 6.1 2層構造

```
Memory
├── compressed_summary: str | None   ← 古いターンのLLM要約（1メッセージ）
└── messages: list[dict]             ← 直近 keep_recent_turns ターン（verbatim）
```

### 6.2 圧縮トリガー

```
tokens_estimated = Σ(len(message.content)) / 4    ← 文字数/4 で近似

if tokens_estimated >= context_limit × compress_threshold:
    compress()    ← デフォルト: 65536 × 0.75 = 49152トークン
```

### 6.3 圧縮の動作

```
compress()
  │
  ├── to_compress = messages[:-keep_recent]    ← 圧縮対象（古いターン）
  ├── messages    = messages[-keep_recent:]    ← 保持（直近 keep_recent_turns ターン）
  │
  ├── history_text = to_compress を文字列化
  │   ＋ 既存 compressed_summary があれば先頭に連結
  │
  ├── LLM呼び出し（要約プロンプト）
  └── compressed_summary = 要約結果
```

### 6.4 get_messages() の返り値構造

```
[
  {"role": "system",    "content": AGENT_SYSTEM_PROMPT},
  {"role": "system",    "content": "[Earlier summary]\n..."},  ← 圧縮済みの場合のみ
  {"role": "user",      "content": "前のゴール"},              ← 直近ターン（verbatim）
  {"role": "assistant", "content": "前の結果"},
  ...
]
```

---

## 7. ツール層

### 7.1 クラス階層

```
Tool (ABC)                         ← agent/tools/base.py
├── FileReadTool                   ← agent/tools/file_tool.py
├── FileWriteTool                  ← agent/tools/file_tool.py
├── ShellTool                      ← agent/tools/shell_tool.py
├── WebSearchTool                  ← agent/tools/web_tool.py
└── MCPTool                        ← agent/mcp/client.py
```

### 7.2 Tool インターフェース

```python
class Tool(ABC):
    name: str              # LLMに公開するツール名（一意）
    description: str       # LLMへのツール説明（計画・実行判断に使われる）
    parameters: dict       # JSONスキーマ（OpenAI function calling形式）
    execute(**kwargs) -> ToolResult

@dataclass
class ToolResult:
    success: bool
    output: str
    error: str = ""
```

`to_openai_schema()` メソッドで LLM に渡す `tools` 配列の要素形式に変換する。

### 7.3 ShellTool の安全策

承認を求める前に（つまりユーザーに見せる前に）危険コマンドパターンを検出して拒否する。

| パターン | 理由 |
|---------|------|
| `rm -r*/f* /` | ルートからの再帰削除 |
| `:(){ :|:& };:` | フォークボム |
| `mkfs.*` | ファイルシステムフォーマット |
| `dd if=` | ディスク直接操作 |
| `> /dev/sd*` | デバイス直書き |
| `chmod -R *7 /` | ルートへの危険なパーミッション変更 |
| `shutdown/reboot/halt/poweroff` | システムシャットダウン |
| `curl/wget ... \| (ba)sh` | ダウンロード→即実行 |

マッチした場合は `ToolResult(success=False, error="Refused: ...")` を返す。承認コールバックは呼ばれない。

---

## 8. MCP統合

### 8.1 起動時のツール検出フロー

```
Agent.from_config()
  └── MCPManager.load_all(cfg.mcp_servers)
        ├── server "fs" (stdio):
        │     asyncio.run(_list_stdio())
        │       stdio_client → ClientSession.initialize()
        │       session.list_tools()
        │       → [MCPTool("fs__read_file", ...), ...]
        │
        └── server "remote" (sse):
              asyncio.run(_list_sse())
              sse_client → ClientSession.initialize()
              session.list_tools()
              → [MCPTool("remote__search", ...), ...]

all_tools = builtin_tools + mcp_tools
```

MCPツールの名前は `{server_name}__{tool_name}` 形式（例: `fs__read_file`）。

### 8.2 MCPTool.execute() の動作

```
MCPTool.execute(**kwargs)
  └── asyncio.run(_async_execute(kwargs))
        ├── stdio の場合:
        │     stdio_client → ClientSession → session.call_tool(name, args)
        └── sse の場合:
              sse_client → ClientSession → session.call_tool(name, args)
```

> **POC上の制約**: 呼び出しのたびに新しいプロセス/接続を開く。本番では永続セッションに置き換えるべき。

### 8.3 設定例

```toml
[mcp.servers.filesystem]
transport = "stdio"
command   = "npx"
args      = ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]

[mcp.servers.remote]
transport = "sse"
url       = "http://localhost:8080/sse"
```

---

## 9. 設定スキーマ

ファイルパス: `~/.config/agent-skeleton/config.toml`  
ファイルが存在しない場合はすべてデフォルト値で動作する。

```toml
[llm]
base_url      = "http://localhost:1234/v1"  # OpenAI互換エンドポイント
api_key       = "dummy"                      # 認証不要のローカルLLMでは "dummy" でよい
model         = "local-model"                # LMStudio上のモデルID
context_limit = 65536                        # 有効トークン上限（64K）

[agent]
compress_threshold = 0.75   # context_limit のこの割合でメモリ圧縮
keep_recent_turns  = 8      # 圧縮後も verbatim で保持するターン数
max_iterations     = 20     # 1ステップあたりの最大LLM呼び出し回数

[mcp.servers.<name>]        # MCPサーバー（複数定義可）
transport = "stdio"         # "stdio" または "sse"
command   = "npx"           # stdio の場合: 起動コマンド
args      = [...]           # stdio の場合: 引数
env       = {}              # 追加環境変数（オプション）
url       = ""              # sse の場合: エンドポイントURL
```

---

## 10. 設計判断の記録

### なぜ Python か

- LLM/エージェント関連ライブラリの充実度
- MCP公式SDKが Python で提供されている
- 組織内の既存 Python プロジェクトとの親和性

### なぜ OpenAI 互換APIか

- ローカルLLM（LM Studio, Ollama等）が同形式に対応している
- `openai` パッケージで抽象化することでバックエンドの差異を吸収
- `LLMClient` を差し替えるだけで Claude API 等にも切り替え可能

### tool_choice を指定しない理由

実機検証（Qwen3.5-9b + LM Studio）で `tool_choice="auto"` を指定すると  
`400 No user query found in messages` エラーが発生した。ローカルLLMの  
jinja テンプレートが OpenAI の仕様と完全には一致しないため、指定を省く。

### なぜ計画をJSON形式にするのか

- ステップ・ツール・理由が構造化されており、CLIで人間が読みやすく表示できる
- パース失敗時にフォールバック計画を生成できる（エージェントが完全に止まらない）
- 将来的にステップの編集・差し替えUIを構築しやすい

### なぜ Executor はユーザー入力を直接行わないか

承認コールバック（`ApproverFn`）を注入することで:
- CLI・テスト・自動承認など異なる環境で同じ `Executor` を使える
- `agent/` パッケージが `cli/` に依存しないという原則を守れる

### メモリ圧縮のトークン推定に `chars / 4` を使う理由

ローカルLLMはモデルごとにトークナイザーが異なり、`tiktoken` 等が使えない。  
英語で1トークン≒4文字という近似は過小推定になりがち（日本語ではもっと過小）だが、  
**圧縮トリガーを少し早めに引く**分には安全側に倒れているため、POCでは許容している。

---

## 11. POCとしての割り切りと将来課題

| 項目 | 現状（POC） | 将来の改善案 |
|------|-----------|------------|
| MCP接続 | 呼び出しのたびに再接続 | バックグラウンドスレッドで永続セッション維持 |
| トークン計算 | `chars / 4` の近似 | モデル固有のトークナイザーを設定から指定 |
| エラーリカバリ | ステップ失敗でも続行、エラー文字列を結果に含める | リトライポリシー、ステップ失敗時の計画再生成 |
| ツール引数の検証 | LLMが生成した引数をそのまま渡す | JSONスキーマバリデーションを `execute()` 前に実施 |
| 計画の修正 | ユーザーは全体を承認/キャンセルのみ | ステップ単位の編集・追加・削除UI |
| 並列実行 | ステップは逐次実行 | 依存関係のないステップを並列化 |
| Qwen3 応答速度 | thinking モードで1呼び出し75〜188秒 | LM Studio設定で `enable_thinking: false` |
| ロギング出力先 | stderr のみ | ファイルへのローテーションログ |
| セキュリティ | ShellTool のパターンマッチのみ | サンドボックス（Docker等）での実行 |
