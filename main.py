import os
import asyncio
import threading
import socket
import discord
from discord import app_commands
import zlib
import time
from dotenv import load_dotenv
from flask import Flask, jsonify

load_dotenv()

# ────────────────────────────────────────────────
# KONFIGURACJA
# ────────────────────────────────────────────────

TOKEN = os.getenv("DISCORD_TOKEN")
RCON_IP = os.getenv("RCON_IP", "127.0.0.1")
RCON_PORT = int(os.getenv("RCON_PORT", "2302"))
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "").strip()

if not TOKEN:
    print("❌ Brak DISCORD_TOKEN")
    exit(1)

# Flask app
app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"status": "ok", "bot_logged_in": rcon.logged_in})

# ────────────────────────────────────────────────
# RCON (bez zmian – możesz użyć swojej klasy)
# ────────────────────────────────────────────────

class BattlEyeRCon:
    def __init__(self, ip: str, port: int, password: str):
        self.ip = ip
        self.port = port
        self.password = password
        self.sock = None
        self.sequence = 0
        self.logged_in = False
        self.last_activity = time.time()
        self._connect()

    def _connect(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.ip, self.port))
            print(f"[RCON] Socket → {self.ip}:{self.port}")
        except Exception as e:
            print(f"[RCON] Błąd socketa: {e}")
            self.sock = None

    # ... (wklej resztę Twojej klasy BattlEyeRCon: _crc32, _build_packet, login, send_command, _send_keepalive, close)

rcon = BattlEyeRCon(RCON_IP, RCON_PORT, RCON_PASSWORD)

# ────────────────────────────────────────────────
# DISCORD BOT
# ────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = False

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot zalogowany: {client.user}")
    asyncio.create_task(status_loop())

# ... (wklej Twoje komendy: players, say, kick, ban, rcon oraz status_loop)

# ────────────────────────────────────────────────
# Uruchomienie
# ────────────────────────────────────────────────

def run_discord_bot():
    """Uruchamia Discorda w osobnym wątku"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(client.start(TOKEN))

if __name__ == "__main__":
    print("🚀 Start Carim Bot + Flask na Renderze")

    # Uruchamiamy Discorda w tle
    bot_thread = threading.Thread(target=run_discord_bot, daemon=True)
    bot_thread.start()

    # Flask na porcie z Render (lub 5000 lokalnie)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
