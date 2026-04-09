# agent-skeleton

自律エージェントの骨格（概念実証）。計画生成 → ユーザー承認 → ステップ実行というループを、内蔵ツールと MCP サーバーサポートとともに実装しています。

## 特徴

- **計画優先の実行** — 自然言語の指示から実行計画を生成し、何も行う前にユーザーの承認を求めます
- **ツール実行の承認** — すべてのツール呼び出し前に、ツール名・引数・理由を提示してユーザーの確認を待ちます
- **マルチターンメモリ** — 会話履歴を保持し、コンテキストウィンドウが逼迫した場合は LLM による自動圧縮を行います
- **内蔵ツール** — `file_read`・`file_write`・`shell_exec`（危険コマンド検出付き）・`web_search`（DuckDuckGo）
- **MCP サポート** — 起動時に MCP サーバー（stdio または SSE）へ接続し、内蔵ツールと同一インターフェースで利用可能
- **コア/UI 分離** — `agent/` パッケージは独立してインポート可能。CLI は薄いラッパーとして機能

## インストール

[uv](https://github.com/astral-sh/uv) が必要です。

```bash
git clone https://github.com/nlink-jp/agent-skeleton
cd agent-skeleton
uv sync
```

## 設定

設定ファイルのサンプルをコピーして編集してください。

```bash
mkdir -p ~/.config/agent-skeleton
cp config.example.toml ~/.config/agent-skeleton/config.toml
$EDITOR ~/.config/agent-skeleton/config.toml
```

最低限必要な設定:

```toml
[llm]
base_url = "http://localhost:1234/v1"   # ローカル LLM のエンドポイント
model    = "your-model-name"
```

## 使い方

```bash
uv run python main.py
```

エージェントが目標を入力するよう促し、計画を生成して承認を求め、ステップごとに実行します。

## テスト実行

```bash
uv run pytest
```

## `agent/` をライブラリとして使う

```python
from agent import Agent

def my_approver(tool_name: str, args: dict, reason: str) -> bool:
    print(f"ツール: {tool_name}  理由: {reason}")
    return input("実行しますか? [y/n] ").lower() == "y"

agent = Agent.from_config(approver=my_approver)
plan = agent.plan("カレントディレクトリの Python ファイルを一覧表示して")
print(agent.format_plan(plan))
result = agent.execute("カレントディレクトリの Python ファイルを一覧表示して", plan)
print(result)
```

## アーキテクチャ

```
ユーザー入力
  → Planner.create_plan()        # LLM が JSON 形式の計画を生成
  → CLI が計画を表示             # ユーザーが承認 / キャンセル
  → Executor.execute_plan()      # ステップを反復処理
      → LLM がツール呼び出しを生成
      → approver(ツール, 引数, 理由)  # ユーザーが承認 / スキップ
      → Tool.execute()
  → 結果を Memory に保存
```

コンテキスト圧縮は推定トークン数が `context_limit × compress_threshold`（デフォルト: 64K × 0.75 = 48K）を超えた時点でトリガーされます。古いターンは LLM が要約し、直近 `keep_recent_turns` ターンはそのまま保持されます。

## ドキュメント

- [English README](README.md)
- [アーキテクチャドキュメント](docs/architecture.ja.md)
- [変更履歴](CHANGELOG.md)
- [設定ファイルサンプル](config.example.toml)
