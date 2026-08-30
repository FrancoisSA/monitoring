"""
Hermes Agent via Mammouth AI - Point d'entrée principal (terminal interactif)

Usage :
    python -m src.main
"""

from __future__ import annotations

import os
import sys

# Importer le module hermes_agent (fonctionne en `python -m src.main` et en script direct)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console

from hermes_agent import run_agent, AgentResponse

console = Console()


def display_response(result: AgentResponse) -> None:
    """Affiche les outils appelés puis la réponse finale de l'agent."""
    if result.tools_used:
        console.print(f"  🔧 [cyan]{', '.join(result.tools_used)}[/cyan] — {result.rounds} tour(s) LLM")
    content = result.message.content.strip()
    if content:
        console.print(f"🤖 [bold]Hermes[/bold] : {content}")
    else:
        console.print("🤖 [yellow]Hermes n'a pas produit de réponse.[/yellow]")


def main():
    """Boucle interactive : une erreur d'API n'interrompt pas la session."""
    console.print("[bold blue]Hermes Agent via Mammouth AI[/bold blue]")
    console.print("[dim](ligne vide ou Ctrl+C pour quitter)[/dim]")

    messages: list = []

    while True:
        try:
            user_input = console.input("\n👤 Vous : ")
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input.strip():
            break

        messages.append({"role": "user", "content": user_input.strip()})

        with console.status("[yellow]Hermes est en train de réfléchir...[/yellow]"):
            try:
                result = run_agent(messages)
            except Exception as e:
                # Une erreur (réseau, API, quota…) n'arrête pas la session ;
                # on retire le message de l'historique pour pouvoir réessayer.
                console.print(f"❌ [red]Erreur : {e}[/red]")
                messages.pop()
                continue

        display_response(result)
        messages.append(result.message)

    console.print("\n👋 Au revoir !")


if __name__ == "__main__":
    main()
