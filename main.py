import os
import asyncio
import threading
import socket
import time
import zlib
import random
from typing import Optional

import discord
from discord import app_commands
from flask import Flask, jsonify
from dotenv import load_dotenv
import requests  # ← do pobrania outbound IP

# ────────────────────────────────────────────────
# Ładowanie env + wyświetlanie outbound IP Render
# ────────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
RCON_IP = os.getenv("RCON_IP")
RCON_PORT_RAW = os.getenv("RCON_PORT")
RCON_PASSWORD = os.getenv("RCON_PASSWORD")

try:
    RCON_PORT = int(RCON_PORT_RAW) if RCON_PORT_RAW else 3705
except:
    RCON_PORT = 3705

print("[START] Skrypt uruchomiony")
print(f"  TOKEN: {'OK' if DISCORD_TOKEN else 'BRAK'}")
print(f"  RCON: {RCON_IP}:{RCON_PORT}  (hasło dł. {len(RCON_PASSWORD or '')})")

# Wyświetlenie outbound IP Render (przez TCP – działa na pewno)
print("\n===== OUTBOUND IP TEST =====")
try:
    outbound_ip = requests.get("https://api.ipify.org", timeout=5).text.strip()
    print(f"[INFO] Twój outbound IP na Render: {outbound_ip}")
    print("     → Podaj TEN IP supportowi g-portal do whitelist!")
except Exception as e:
    print(f"[INFO] Nie udało się pobrać outbound IP: {e}")
    print("     → Spróbuj ręcznie: otwórz https://api.ipify.org w przeglądarce z Render (lub użyj curl w shellu jeśli masz dostęp)")

# ────────────────────────────────────────────────
# Flask health (bez zmian)
# ────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "bot_ready": 'client' in globals() and client.is_ready(),
        "rcon_logged_in": 'rcon' in globals() and rcon and rcon.logged_in,
        "thread_alive": 'bot_thread' in globals() and bot_thread.is_alive()
    })

# ────────────────────────────────────────────────
# BattlEye RCON class (bez zmian – zostawiam jak było)
# ────────────────────────────────────────────────
class BattlEyeRCon:
    def __init__(self, ip: str, port: int, password: str):
        print(f"[RCON] Init → {ip}:{port}")
        self.ip = ip
        self.port = port
        self.password = (password or "").strip()
        self.sock = None
        self.logged_in = False
        self._connect()

    def _connect(self):
        print(f"[RCON] connect() → {self.ip}:{self.port}")
        if self.sock:
            try: self.sock.close()
            except: pass
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(8.0)
            self.sock.connect((self.ip, self.port))
            print("[RCON] connect() OK")
        except Exception as e:
            print(f"[RCON] connect() fail: {e}")
            self.sock = None

    def _crc32(self, data: bytes) -> bytes:
        return zlib.crc32(data).to_bytes(4, 'little')

    def _build_packet(self, typ: int, payload: bytes = b'') -> bytes:
        body = bytes([typ]) + payload
        return b'BE' + self._crc32(body) + b'\xff' + body

    def login(self) -> bool:
        if not self.sock:
            self._connect()
            if not self.sock:
                return False

        for attempt in range(1, 4):
            jitter = random.uniform(0.5, 1.5)
            print(f"[RCON LOGIN] Próba {attempt}/3")
            packet = self._build_packet(0x00, self.password.encode('utf-8', 'replace'))

            try:
                self.sock.send(packet)
                print("[RCON LOGIN] wysłano, czekam...")
                data = self.sock.recv(4096)
                print(f"[RCON LOGIN] recv: {len(data)} bajtów")

                if not data.startswith(b'BE'):
                    print("[RCON LOGIN] brak BE header")
                    return False

                crc_rx = data[2:6]
                payload = data[9:]
                if crc_rx != self._crc32(payload):
                    print("[RCON LOGIN] błędny CRC")
                    return False

                if payload and payload[0] == 0x01:
                    self.logged_in = True
                    print("[RCON LOGIN] SUKCES!")
                    return True
                else:
                    print(f"[RCON LOGIN] odrzucono (status: {payload[0] if payload else '?'})")
                    return False

            except socket.timeout:
                print(f"[RCON LOGIN] timeout {attempt}")
                time.sleep(jitter)
                continue
            except Exception as e:
                print(f"[RCON LOGIN] błąd: {e}")
                break

        return False

    def send_command(self, cmd: str) -> str:
        print(f"[RCON CMD] {cmd}")
        if not self.logged_in and not self.login():
            return "❌ Login failed"
        return f"[DEBUG] wysłano '{cmd}' – brak pełnej obsługi odpowiedzi"

# ────────────────────────────────────────────────
# RCON init + auto test (bez zmian)
# ────────────────────────────────────────────────
rcon = None
if RCON_IP and RCON_PORT and RCON_PASSWORD:
    rcon = BattlEyeRCon(RCON_IP, RCON_PORT, RCON_PASSWORD)
    print("\n===== AUTO TEST =====")
    if rcon.login():
        print("===== RCON OK =====")
    else:
        print("===== RCON FAIL – patrz wyżej =====")

# ────────────────────────────────────────────────
# Discord (bez zmian)
# ────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = False
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    print(f"[DISCORD] Online: {client.user}")
    await tree.sync()
    print("[DISCORD] Komendy sync OK")
    asyncio.create_task(status_loop())

async def status_loop():
    print("[STATUS] start")
    await asyncio.sleep(10)
    while True:
        if rcon:
            try:
                resp = rcon.send_command("players")
                print(f"[STATUS] players: {resp[:150]}")
            except Exception as e:
                print(f"[STATUS] błąd: {e}")
        await asyncio.sleep(60)

def run_bot():
    if DISCORD_TOKEN:
        asyncio.run(client.start(DISCORD_TOKEN))
    else:
        print("[DISCORD] brak tokena")

# ────────────────────────────────────────────────
# Main (bez zmian)
# ────────────────────────────────────────────────
if __name__ == "__main__":
    print("[MAIN] start")
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    time.sleep(5)

    port = int(os.environ.get("PORT", 5000))
    print(f"[MAIN] Flask → :{port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
