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

    console.print(f"[bold cyan]📥 Downloading model '{clean_id}' (