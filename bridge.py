#!/usr/bin/env python3
import sys
import os
import socket
import subprocess
import json
import shutil
import time
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
    current = load_config() or {}
    current.update(new_data)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(current, f, indent=4)
    os.chmod(CONFIG_FILE, 0o600)

# --- UTILS ---

def check_connection(host, port):
    try:
        socket.create_connection((host, port), timeout=0.5)
        return True
    except OSError:
        return False

def ensure_ollama_running():
    """Checks if Ollama is running, starts it if not."""
    if check_connection("localhost", 11434):
        return True

    console.print("[yellow]Ollama is stopped. Starting local server...[/yellow]")
    try:
        # Start Ollama in the background
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Wait up to 10 seconds for it to respond
        for _ in range(20):
            if check_connection("localhost", 11434):
                console.print("[green]Ollama started![/green]")
                return True
            time.sleep(0.5)

        console.print("[red]Could not start Ollama automatically.[/red]")
        return False
    except FileNotFoundError:
        console.print("[red]Ollama is not installed. Run: brew install ollama[/red]")
        return False

def ensure_model_pulled(model_id):
    """Checks if the specific model exists locally, pulls if missing."""
    # Strip 'ollama/' prefix if present for the check
    clean_id = model_id.replace("ollama/", "")

    # Check if model exists
    result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    if clean_id in result.stdout:
        return True

    console.print(f"[bold cyan]Model '{clean_id}' not found. Downloading (this happens once)...[/bold cyan]")
    try:
        subprocess.run(["ollama", "pull", clean_id], check=True)
        console.print("[green]Download complete![/green]")
        return True
    except subprocess.CalledProcessError:
        console.print("[red]Failed to download model. Check internet?[/red]")
        return False

def get_aider_path():
    """Finds the aider executable inside the current virtualenv."""
    # Since we are running in a venv, 'aider' should be in the same bin dir as python
    venv_bin = os.path.dirname(sys.executable)
    aider_path = os.path.join(venv_bin, "aider")

    if os.path.exists(aider_path):
        return aider_path

    # Fallback: check system path
    which_aider = shutil.which("aider")
    if which_aider:
        return which_aider

    return None

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
            new_model = Prompt.ask("Enter Cloud Model ID", default=cfg.get("GEMINI_MODEL"))
            save_config({"GEMINI_MODEL": new_model})
        elif choice == "3":
            new_model = Prompt.ask("Enter Local Model ID", default=cfg.get("LOCAL_MODEL"))
            save_config({"LOCAL_MODEL": new_model})
        elif choice == "4":
            break

# --- MAIN ---

def main():
    if not load_config():
        console.print(Panel("[bold cyan]Welcome to Bridge[/bold cyan]\nLet's set up your API key."))
        key = Prompt.ask("Gemini API Key (optional for local use)", password=True)
        save_config({
            "GEMINI_API_KEY": key,
            "GEMINI_MODEL": "gemini/gemini-1.5-pro-latest",
            "LOCAL_MODEL": "ollama/qwen2.5-coder:32b"
        })

    while True:
        console.clear()
        online = check_connection("8.8.8.8", 53)
        ollama_up = check_connection("localhost", 11434)
        cfg = load_config()

        status = Text()
        status.append("Internet: ")
        status.append("Online ✅" if online else "Offline ❌", style="green" if online else "red")
        status.append("  |  Ollama: ")
        status.append("Running ✅" if ollama_up else "Stopped ⚠️", style="green" if ollama_up else "yellow")

        console.print(Panel(status, title="[bold magenta]BRIDGE v2.0[/bold magenta]", expand=False))
        console.print("[bold underline]Select Mode:[/bold underline]")

        # 1. Cloud (Depends on Internet + Key)
        cloud_ready = online and cfg.get("GEMINI_API_KEY")
        c_style = "bold white" if cloud_ready else "dim"
        console.print(f"[{c_style}]1) Cloud (Gemini) [/{c_style}]" + (" ✅" if cloud_ready else " ❌ (Unavailable)"))

        # 2. Local (Always available to select, we auto-start if needed)
        console.print(f"[bold white]2) Local (Qwen)   [/bold white]" + (" ✅" if ollama_up else " ⚡ (Auto-start)"))

        console.print(f"[cyan]3) Settings ⚙️[/cyan]")
        console.print(f"[red]q) Quit[/red]")

        choice = Prompt.ask("\nChoose", choices=["1", "2", "3", "q"], default="1" if cloud_ready else "2")

        if choice == "q": sys.exit(0)
        if choice == "3":
            settings_menu()
            continue

        selected_model = ""
        env = os.environ.copy()

        # CLOUD LAUNCH
        if choice == "1":
            if not cloud_ready:
                console.print("[red]Cloud unavailable. Check internet or API key.[/red]")
                time.sleep(2)
                continue
            selected_model = cfg.get("GEMINI_MODEL")
            env["GEMINI_API_KEY"] = cfg.get("GEMINI_API_KEY")

        # LOCAL LAUNCH
        elif choice == "2":
            # AUTO-SETUP MAGIC
            if not ensure_ollama_running():
                Prompt.ask("Press Enter to return to menu...")
                continue

            selected_model = cfg.get("LOCAL_MODEL")
            if not ensure_model_pulled(selected_model):
                Prompt.ask("Press Enter to return to menu...")
                continue

        # FIND AIDER
        aider_executable = get_aider_path()
        if not aider_executable:
            console.print("[red]Error: 'aider' not found in virtual environment.[/red]")
            console.print(f"Looked in: {os.path.dirname(sys.executable)}")
            sys.exit(1)

        console.print(f"\n[green]🚀 Initializing {selected_model}...[/green]")

        cmd = [
            aider_executable, # Use full path!
            "--model", selected_model,
            "--architect",
            "--watch-files",
            "--no-auto-commits",
        ]

        try:
            subprocess.run(cmd, env=env)
        except KeyboardInterrupt:
            pass