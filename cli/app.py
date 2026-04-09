"""CLI UI layer for agent-skeleton.

Responsibilities:
- Interactive chat loop (Rich-based)
- Display plan to user and request overall approval
- Per-tool execution approval dialog
- Show final results
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from agent import Agent

console = Console()


def approval_callback(tool_name: str, args: dict, reason: str) -> bool:
    """Called by Executor before every tool execution."""
    console.print()
    console.print(Panel(
        f"[bold]ツール:[/bold]  [cyan]{tool_name}[/cyan]\n"
        f"[bold]引数:[/bold]   {args}\n"
        f"[bold]理由:[/bold]   {reason}",
        title="[yellow]ツール実行の承認[/yellow]",
        border_style="yellow",
    ))
    return Confirm.ask("実行しますか?", default=True)


def run() -> None:
    console.print(Panel(
        "[bold]Agent Skeleton[/bold]  —  自律エージェント (概念実証)\n"
        "終了: [dim]exit[/dim] または [dim]Ctrl+C[/dim]",
        style="blue",
    ))

    try:
        agent = Agent.from_config(approver=approval_callback)
    except Exception as e:
        console.print(f"[red]初期化エラー: {e}[/red]")
        return

    while True:
        try:
            # Rich の Prompt.ask() はマルチバイト文字の BS を正しく扱えないため、
            # プロンプト表示のみ Rich に任せ、入力収集は組み込み input() を使う。
            console.print("\n[bold green]あなた[/bold green]: ", end="")
            user_input = input().strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "終了"):
            break

        # --- 計画生成 ---
        console.print("\n[dim]計画を生成中...[/dim]")
        try:
            plan = agent.plan(user_input)
        except Exception as e:
            console.print(f"[red]計画生成エラー: {e}[/red]")
            continue

        console.print(Panel(
            agent.format_plan(plan),
            title="[bold yellow]実行計画[/bold yellow]",
            border_style="yellow",
        ))

        if not Confirm.ask("この計画を実行しますか?", default=True):
            console.print("[dim]キャンセルしました[/dim]")
            continue

        # --- 実行 ---
        console.print("\n[dim]実行中...[/dim]")
        try:
            result = agent.execute(user_input, plan)
        except Exception as e:
            console.print(f"[red]実行エラー: {e}[/red]")
            continue

        console.print(Panel(
            result,
            title="[bold green]実行結果[/bold green]",
            border_style="green",
        ))

    console.print("\nさようなら!")
