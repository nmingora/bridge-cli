#!/usr/bin/env python3
import sys
import os
import socket
import subprocess
import json
from pathlib import Path

# Auto-install rich if missing
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    from rich.table import Table
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "rich"])
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    from rich.table import Table

console = Console()
CONFIG_DIR = Path.home() / ".config" / "bridge-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"

# --- CONFIG MANAGER ---

def load_config():
    if not CONFIG_FILE.exists():
        return None
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(new_data):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Load existing to preserve fields, update with new
    current = load_config() or {}
    current.update(new_data)

    with open(CONFIG_FILE, 'w') as f:
        json.dump(current, f, indent=4)
    os.chmod(CONFIG_FILE, 0o600)

def get_config_value(key, default):
    cfg = load_config()
    return cfg.get(key, default) if cfg else default

# --- UTILS ---

def check_connection(host, port):
    try:
        socket.create_connection((host, port), timeout=1)
        return True
    except OSError:
        return False

# --- SETTINGS MENU ---

def settings_menu():
    while True:
        console.clear()
        cfg = load_config()

        table = Table(title="⚙️  Bridge Settings", show_header=True, header_style="bold magenta")
        table.add_column("Option", style="cyan", width=4)
        table.add_column("Setting", style="white")
        table.add_column("Current Value", style="dim green")

        table.add_row("1", "Gemini API Key", "********" if cfg.get("GEMINI_API_KEY") else "Not Set")
        table.add_row("2", "Cloud Model ID", cfg.get("GEMINI_MODEL", "gemini/gemini-1.5-pro-latest"))
        table.add_row("3", "Local Model ID", cfg.get("LOCAL_MODEL", "ollama/qwen2.5-coder:32b"))
        table.add_row("4", "Back to Main Menu", "")

        console.print(table)

        choice = Prompt.ask("Select setting to change", choices=["1", "2", "3", "4"], default="4")

        if choice == "1":
            new_key = Prompt.ask("Enter new Gemini API Key", password=True)
            if new_key: save_config({"GEMINI_API_KEY": new_key})

        elif choice == "2":
            console.print("\n[dim]Examples: gemini/gemini-1.5-pro-latest, gemini/gemini-1.5-flash[/dim]")
            new_model = Prompt.ask("Enter Cloud Model ID", default=cfg.get("GEMINI_MODEL"))
            save_config({"GEMINI_MODEL": new_model})

        elif choice == "3":
            console.print("\n[dim]Examples:\n - ollama/qwen2.5-coder:32b (Best)\n - ollama/qwen2.5-coder:14b (Faster)\n - ollama/deepseek-coder-v2[/dim]")
            new_model = Prompt.ask("Enter Local Model ID", default=cfg.get("LOCAL_MODEL"))
            save_config({"LOCAL_MODEL": new_model})

        elif choice == "4":
            break

# --- MAIN ---

def main():
    # 1. First Run Check
    if not load_config():
        console.print(Panel("[bold cyan]Welcome to Bridge[/bold cyan]\nLet's set up your API key."))
        key = Prompt.ask("Gemini API Key (optional for local use)", password=True)
        # Default config
        save_config({
            "GEMINI_API_KEY": key,
            "GEMINI_MODEL": "gemini/gemini-1.5-pro-latest",
            "LOCAL_MODEL": "ollama/qwen2.5-coder:32b"
        })

    while True:
        console.clear()

        # 2. Status Check
        online = check_connection("8.8.8.8", 53)
        ollama_up = check_connection("localhost", 11434)
        cfg = load_config()

        status = Text()
        status.append("Internet: ")
        status.append("Online ✅" if online else "Offline ❌", style="green" if online else "red")
        status.append("  |  Ollama: ")
        status.append("Running ✅" if ollama_up else "Stopped ❌", style="green" if ollama_up else "red")

        console.print(Panel(status, title="[bold magenta]BRIDGE v2.0[/bold magenta]", expand=False))

        # 3. Menu
        console.print("[bold underline]Select Mode:[/bold underline]")

        # Cloud Option
        cloud_avail = online and cfg.get("GEMINI_API_KEY")
        c_style = "bold white" if cloud_avail else "dim"
        console.print(f"[{c_style}]1) Cloud (Gemini) [/{c_style}]" + (" ✅" if cloud_avail else " ❌ (Check Internet/Key)"))

        # Local Option
        local_avail = ollama_up
        l_style = "bold white" if local_avail else "dim"
        console.print(f"[{l_style}]2) Local (Qwen)   [/{l_style}]" + (" ✅" if local_avail else " ❌ (Start Ollama)"))

        console.print(f"[cyan]3) Settings ⚙️[/cyan]")
        console.print(f"[red]q) Quit[/red]")

        choice = Prompt.ask("\nChoose", choices=["1", "2", "3", "q"], default="1" if cloud_avail else "2")

        if choice == "q":
            sys.exit(0)

        if choice == "3":
            settings_menu()
            continue

        # 4. Launch Aider
        selected_model = ""
        env = os.environ.copy()

        if choice == "1":
            if not cloud_avail: continue
            selected_model = cfg.get("GEMINI_MODEL")
            env["GEMINI_API_KEY"] = cfg.get("GEMINI_API_KEY")
        elif choice == "2":
            if not local_avail: continue
            selected_model = cfg.get("LOCAL_MODEL")

        console.print(f"\n[green]🚀 Initializing {selected_model}...[/green]")
        console.print("[dim]Use /help to see commands. Use /architect to plan complex changes.[/dim]")

        # COMMAND CONSTRUCTION - This enables the "Claude Code" behavior
        cmd = [
            "aider",
            "--model", selected_model,
            "--architect",          # This enables the "Thinking" -> "Act" loop
            "--watch-files",        # Watches if you edit in WebStorm
            "--no-auto-commits",    # Optional: If you prefer manual commits
        ]

        try:
            subprocess.run(cmd, env=env)
        except KeyboardInterrupt:
            pass