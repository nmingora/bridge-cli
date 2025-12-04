#!/usr/bin/env python3
import sys
import os
import socket
import subprocess
import json
import shutil
import time
from pathlib import Path

# --- 1. AUTO-INSTALL DEPENDENCIES ---
def install_package(package_name):
    print(f"📦 Installing {package_name}...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    from rich.table import Table
except ImportError:
    install_package("rich")
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    from rich.table import Table

console = Console()
CONFIG_DIR = Path.home() / ".config" / "bridge-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"

# --- 2. CONFIG ---
def load_config():
    if not CONFIG_FILE.exists(): return None
    with open(CONFIG_FILE, 'r') as f: return json.load(f)

def save_config(new_data):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    current = load_config() or {}
    current.update(new_data)
    with open(CONFIG_FILE, 'w') as f: json.dump(current, f, indent=4)
    os.chmod(CONFIG_FILE, 0o600)

# --- 3. UTILS ---
def check_connection(host, port):
    try:
        socket.create_connection((host, port), timeout=0.5)
        return True
    except OSError:
        return False

def get_aider_path():
    venv_bin = os.path.dirname(sys.executable)
    aider_path = os.path.join(venv_bin, "aider")
    if os.path.exists(aider_path): return aider_path
    return shutil.which("aider")

def ensure_aider():
    """Self-heals if Aider is missing."""
    if get_aider_path(): return
    console.print("[yellow]⚠️  Aider (the brain) is missing. Installing now...[/yellow]")
    install_package("aider-chat")
    console.print("[green]✅ Aider installed![/green]")

def ensure_ollama():
    """Starts Ollama if stopped."""
    if check_connection("localhost", 11434): return True
    console.print("[yellow]⚡ Starting local AI engine...[/yellow]")
    try:
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(20): # Wait 10s
            if check_connection("localhost", 11434):
                console.print("[green]✅ Engine started![/green]")
                return True
            time.sleep(0.5)
        return False
    except FileNotFoundError:
        console.print("[red]❌ Ollama not installed. Run: brew install ollama[/red]")
        return False

def ensure_model(model_id):
    """Downloads model if missing."""
    clean_id = model_id.replace("ollama/", "")
    res = subprocess.run(["ollama", "list"], capture_output=True, text=True)
    if clean_id in res.stdout: return True

    # FIXED: Split long string to prevent syntax errors
    msg = f"[bold cyan]📥 Downloading model '{clean_id}' (One-time setup)...[/bold cyan]"
    console.print(msg)

    try:
        subprocess.run(["ollama", "pull", clean_id], check=True)
        return True
    except:
        return False

# --- 4. MENUS ---
def settings_menu():
    while True:
        console.clear()
        cfg = load_config()
        t = Table(title="⚙️  Bridge Settings", show_header=True, header_style="bold magenta")
        t.add_column("Opt", style="cyan", width=4)
        t.add_column("Setting", style="white")
        t.add_column("Value", style="dim green")
        t.add_row("1", "Gemini Key", "********" if cfg.get("GEMINI_API_KEY") else "Not Set")
        t.add_row("2", "Cloud Model", cfg.get("GEMINI_MODEL", "gemini/gemini-1.5-pro-latest"))
        t.add_row("3", "Local Model", cfg.get("LOCAL_MODEL", "ollama/qwen2.5-coder:32b"))
        t.add_row("4", "Back", "")
        console.print(t)

        c = Prompt.ask("Select", choices=["1","2","3","4"], default="4")
        if c=="1": save_config({"GEMINI_API_KEY": Prompt.ask("New Key", password=True)})
        elif c=="2": save_config({"GEMINI_MODEL": Prompt.ask("Model ID", default=cfg.get("GEMINI_MODEL"))})
        elif c=="3": save_config({"LOCAL_MODEL": Prompt.ask("Model ID", default=cfg.get("LOCAL_MODEL"))})
        elif c=="4": break

def main():
    if not load_config():
        console.print(Panel("[bold cyan]Welcome to Bridge[/bold cyan]"))
        save_config({
            "GEMINI_API_KEY": Prompt.ask("Gemini API Key (optional)", password=True),
            "GEMINI_MODEL": "gemini/gemini-1.5-pro-latest",
            "LOCAL_MODEL": "ollama/qwen2.5-coder:32b"
        })

    # AUTO-INSTALL CHECKS
    ensure_aider()

    while True:
        console.clear()
        online = check_connection("8.8.8.8", 53)
        ollama_up = check_connection("localhost", 11434)
        cfg = load_config()

        status = Text()
        status.append(f"Internet: {'✅' if online else '❌'}  |  Ollama: {'✅' if ollama_up else '⚠️'}")
        console.print(Panel(status, title="[bold magenta]BRIDGE v2.0[/bold magenta]", expand=False))

        # Menu Options
        cloud_ok = online and cfg.get("GEMINI_API_KEY")
        console.print(f"[{'bold white' if cloud_ok else 'dim'}]1) Cloud (Gemini) [{'✅' if cloud_ok else '❌'}]")
        console.print(f"[bold white]2) Local (Qwen)   [{'✅' if ollama_up else '⚡'}]")
        console.print("[cyan]3) Settings ⚙️[/cyan]")
        console.print("[red]q) Quit[/red]")

        choice = Prompt.ask("\nChoose", choices=["1", "2", "3", "q"], default="1" if cloud_ok else "2")
        if choice == "q": sys.exit(0)
        if choice == "3": settings_menu(); continue

        model = ""
        env = os.environ.copy()

        if choice == "1":
            if not cloud_ok: continue
            model = cfg.get("GEMINI_MODEL")
            env["GEMINI_API_KEY"] = cfg.get("GEMINI_API_KEY")
        elif choice == "2":
            if not ensure_ollama(): continue
            model = cfg.get("LOCAL_MODEL")
            if not ensure_model(model): continue

        console.print(f"\n[green]🚀 Launching {model}...[/green]")
        try:
            subprocess.run([get_aider_path(), "--model", model, "--architect", "--watch-files", "--no-auto-commits"], env=env)
        except KeyboardInterrupt: pass

if __name__ == "__main__": main()