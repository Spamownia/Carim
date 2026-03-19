import os
import asyncio
import threading
import socket
import time
import zlib
from typing import Optional

import discord
from discord import app_commands
from flask import Flask, jsonify
from dotenv import load_dotenv

# ────────────────────────────────────────────────
# Ładowanie zmiennych środowiskowych
# ────────────────────────────────────────────────
load_dotenv()

DISCORD_TOKEN    = os.getenv("DISCORD_TOKEN")
RCON_IP          = os.getenv("RCON_IP")
RCON_PORT_RAW    = os.getenv("RCON_PORT")
RCON_PASSWORD    = os.getenv("RCON_PASSWORD")

# Port – domyślnie 3705, bo Twój serwer używa game port 3702 → RConPort 3705
try:
    RCON_PORT = int(RCON_PORT_RAW) if RCON_PORT_RAW else 3705
except (ValueError, TypeError):
    print("!!! Błąd: RCON_PORT nie jest liczbą → używam 3705 (z Twojego configu serwera) !!!")
    RCON_PORT = 3705

print("[START] Skrypt uruchomiony")
print(f"  DISCORD_TOKEN  → {'obecny' if DISCORD_TOKEN else 'BRAK'}")
print(f"  RCON_IP        → {RCON_IP or 'BRAK'}")
print(f"  RCON_PORT      → {RCON_PORT}   ← z configu serwera: RConPort 3705")
print(f"  RCON_PASSWORD  → {'obecne' if RCON_PASSWORD else 'BRAK'} (dł. {len(RCON_PASSWORD or '')})")

# ────────────────────────────────────────────────
# Flask – healthcheck
# ────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/health")
def health():
    bot_ready = 'client' in globals() and client.is_ready()
    rcon_ok   = 'rcon' in globals() and rcon is not None and rcon.logged_in
    thread_ok = 'bot_thread' in globals() and bot_thread.is_alive()

    return jsonify({
        "status": "ok",
        "bot_running": bot_ready,
        "rcon_logged_in": rcon_ok,
        "discord_thread_alive": thread_ok
    })

# ────────────────────────────────────────────────
# Klasa BattlEye RCON – poprawiona i z lepszym debugiem
# ────────────────────────────────────────────────
class BattlEyeRCon:
    def __init__(self, ip: str, port: int, password: str):
        print(f"[RCON INIT] Tworzę obiekt → {ip}:{port}  (hasło długość: {len(password)})")
        self.ip = ip
        self.port = port
        self.password = password.strip()  # usuwamy ewentualne białe znaki
        self.sock: Optional[socket.socket] = None
        self.logged_in = False
        self.last_activity = time.time()
        self._connect()

    def _connect(self) -> None:
        print(f"[RCON CONNECT] Tworzenie UDP socket → {self.ip}:{self.port}")
        if self.sock:
            try:
                self.sock.close()
            except:
                pass

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(6.0)
            self.sock.connect((self.ip, self.port))
            print("[RCON CONNECT] Socket utworzony i connect() OK")
        except Exception as e:
            print(f"[RCON CONNECT] Błąd: {type(e).__name__} → {e}")
            self.sock = None

    def _crc32(self, data: bytes) -> bytes:
        return zlib.crc32(data).to_bytes(4, 'little')

    def _build_packet(self, packet_type: int, payload: bytes = b'') -> bytes:
        body = bytes([packet_type]) + payload
        header = b'BE' + self._crc32(body) + b'\xff'
        return header + body

    def login(self) -> bool:
        if not self.sock:
            self._connect()
            if not self.sock:
                print("[RCON LOGIN] Brak socketa – połączenie niemożliwe")
                return False

        print(f"[RCON LOGIN] Wysyłanie loginu (hasło: ***{self.password[-3:]} )")
        packet = self._build_packet(0x00, self.password.encode('utf-8'))

        try:
            self.sock.send(packet)
            print("[RCON LOGIN] Pakiet wysłany, czekam na odpowiedź (6s timeout)")
            data = self.sock.recv(4096)
            print(f"[RCON LOGIN] Otrzymano {len(data)} bajtów")

            if not data.startswith(b'BE'):
                print("[RCON LOGIN] Brak nagłówka BE – niepoprawna odpowiedź")
                return False

            crc_received = data[2:6]
            payload = data[9:]   # od offset 9 (po header + crc + type)
            if crc_received != self._crc32(payload):
                print("[RCON LOGIN] Nieprawidłowy CRC")
                return False

            if payload and payload[0] == 0x01:
                self.logged_in = True
                print("[RCON LOGIN] SUKCES – zalogowano poprawnie!")
                return True
            else:
                print("[RCON LOGIN] Logowanie odrzucone (payload[0] != 0x01)")
                return False

        except socket.timeout:
            print("[RCON LOGIN] TIMEOUT 6s – serwer nie odpowiada (port otwarty? BattlEye działa?)")
        except Exception as e:
            print(f"[RCON LOGIN] Błąd: {type(e).__name__} → {e}")
        return False

    def send_command(self, command: str) -> str:
        print(f"[RCON CMD] Wysyłanie: {command}")
        if not self.logged_in:
            if not self.login():
                return "❌ Nie udało się zalogować do RCON"

        # Tutaj brakuje pełnej implementacji – tylko test
        # Prawidłowo: wyślij pakiet 0x01 + command, odbierz wielopakietowo
        return f"[TEST] Komenda '{command}' wysłana – brak pełnej obsługi odpowiedzi"

# ────────────────────────────────────────────────
# Inicjalizacja + natychmiastowy test
# ────────────────────────────────────────────────
rcon: Optional[BattlEyeRCon] = None

if RCON_IP and RCON_PORT and RCON_PASSWORD:
    rcon = BattlEyeRCon(RCON_IP, RCON_PORT, RCON_PASSWORD)
    
    print("\n===== NATYCHMIASTOWY TEST RCON =====")
    if rcon.login():
        print("===== TEST UDANY – RCON DZIAŁA =====")
    else:
        print("===== TEST NIEUDANY – sprawdź logi powyżej =====")
else:
    print("[RCON] Brakujące zmienne – RCON wyłączony")

# ────────────────────────────────────────────────
# Discord Bot
# ────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = False

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    print(f"[DISCORD] Bot zalogowany: {client.user}")
    try:
        await tree.sync()
        print("[DISCORD] Komendy zsynchronizowane")
    except Exception as e:
        print(f"[DISCORD] Błąd sync: {e}")
    asyncio.create_task(status_loop())

async def status_loop():
    print("[STATUS] Pętla wystartowana")
    await asyncio.sleep(10)

    while True:
        if rcon:
            try:
                resp = rcon.send_command("players")
                print(f"[STATUS] players → {resp}")
            except Exception as e:
                print(f"[STATUS] Błąd: {e}")
        else:
            print("[STATUS] rcon=None")
        await asyncio.sleep(60)

def run_discord_bot():
    if not DISCORD_TOKEN:
        print("[DISCORD] Brak tokena")
        return
    asyncio.run(client.start(DISCORD_TOKEN))

# ────────────────────────────────────────────────
# Główny start
# ────────────────────────────────────────────────
if __name__ == "__main__":
    print("[MAIN] Start Render")
    bot_thread = threading.Thread(target=run_discord_bot, daemon=True)
    bot_thread.start()
    time.sleep(4)

    port = int(os.environ.get("PORT", 5000))
    print(f"[MAIN] Flask na {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
