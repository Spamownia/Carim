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

# Konwersja portu na int + fallback
try:
    RCON_PORT = int(RCON_PORT_RAW) if RCON_PORT_RAW else 2302
except (ValueError, TypeError):
    print("!!! Błąd: RCON_PORT nie jest prawidłową liczbą → używam domyślnego 2302 !!!")
    RCON_PORT = 2302

print("[START] Skrypt uruchomiony")
print(f"  DISCORD_TOKEN  → {'obecny' if DISCORD_TOKEN else 'BRAK'}")
print(f"  RCON_IP        → {RCON_IP or 'BRAK'}")
print(f"  RCON_PORT      → {RCON_PORT}")
print(f"  RCON_PASSWORD  → {'obecne' if RCON_PASSWORD else 'BRAK'} (dł. {len(RCON_PASSWORD or '')})")

# ────────────────────────────────────────────────
# Flask – healthcheck
# ────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "bot_running": client.is_ready() if 'client' in globals() else False,
        "rcon_connected": rcon.logged_in if 'rcon' in globals() and rcon is not None else False,
        "thread_alive": bot_thread.is_alive() if 'bot_thread' in globals() else False
    })

# ────────────────────────────────────────────────
# Klasa BattlEye RCON
# ────────────────────────────────────────────────
class BattlEyeRCon:
    def __init__(self, ip: str, port: int, password: str):
        print(f"[RCON] Inicjalizacja: {ip}:{port}  (hasło: {len(password)} znaków)")
        self.ip = ip
        self.port = port
        self.password = password
        self.sock: Optional[socket.socket] = None
        self.sequence = 0
        self.logged_in = False
        self.last_activity = time.time()
        self._connect()

    def _connect(self) -> None:
        print("[RCON] Tworzenie socketa UDP...")
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.ip, self.port))
            print(f"[RCON] Socket połączony → {self.ip}:{self.port}")
        except Exception as e:
            print(f"[RCON] Błąd połączenia: {type(e).__name__}: {e}")
            self.sock = None

    def _crc32(self, data: bytes) -> bytes:
        crc = zlib.crc32(data) & 0xFFFFFFFF
        return crc.to_bytes(4, "little")

    def _build_packet(self, packet_type: int, payload: bytes = b"") -> bytes:
        body = bytes([packet_type]) + payload
        header = b"BE" + self._crc32(body) + b"\xFF"
        return header + body

    def login(self) -> bool:
        if not self.password or not self.sock:
            print("[RCON LOGIN] Brak hasła lub socketa")
            return False

        print("[RCON LOGIN] Wysyłanie loginu...")
        packet = self._build_packet(0x00, self.password.encode("utf-8", errors="replace"))

        try:
            self.sock.send(packet)
            self.sock.settimeout(4.0)
            data = self.sock.recv(4096)

            if len(data) < 10 or not data.startswith(b"BE"):
                return False

            received_crc = data[2:6]
            payload = data[8:]
            if received_crc != self._crc32(payload):
                print("[RCON LOGIN] Błędny CRC")
                return False

            if data[9] == 0x00 and len(payload) >= 1 and payload[0] == 0x01:
                self.logged_in = True
                self.last_activity = time.time()
                print("[RCON LOGIN] Zalogowano pomyślnie")
                return True
            else:
                print("[RCON LOGIN] Odrzucono logowanie")
                return False

        except socket.timeout:
            print("[RCON LOGIN] Timeout")
        except Exception as e:
            print(f"[RCON LOGIN] Błąd: {type(e).__name__}: {e}")

        self.logged_in = False
        return False

    def send_command(self, command: str) -> str:
        if not self.logged_in:
            if not self.login():
                return "❌ Nie udało się zalogować do RCON"

        # Tutaj wstaw swoją pełną implementację wysyłania komend i odbierania odpowiedzi
        # (obecnie placeholder – dodaj swoją logikę)
        print(f"[RCON CMD] Wysyłanie: {command}")
        return f"[placeholder] Odpowiedź na: {command}"

# ────────────────────────────────────────────────
# Inicjalizacja RCON (jeśli dane są poprawne)
# ────────────────────────────────────────────────
rcon: Optional[BattlEyeRCon] = None

if RCON_IP and RCON_PORT and RCON_PASSWORD:
    try:
        rcon = BattlEyeRCon(RCON_IP, RCON_PORT, RCON_PASSWORD)
    except Exception as e:
        print(f"[RCON] Krytyczny błąd przy tworzeniu obiektu: {e}")
        rcon = None
else:
    print("[RCON] Pomijam inicjalizację – brakuje wymaganych zmiennych")

# ────────────────────────────────────────────────
# Discord Bot
# ────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = False  # wyłączamy, jeśli nie potrzebujesz czytać treści wiadomości

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
    print(f"[DISCORD] Zalogowano jako {client.user} ({client.user.id})")
    try:
        await tree.sync()
        print("[DISCORD] Komendy slash zsynchronizowane")
    except Exception as e:
        print(f"[DISCORD] Błąd synchronizacji komend: {e}")

    asyncio.create_task(status_loop())


async def status_loop():
    while True:
        await asyncio.sleep(60)
        if rcon is None:
            print("[STATUS] RCON wyłączony – pomijam")
            continue

        try:
            resp = rcon.send_command("players")
            print(f"[STATUS] Odpowiedź players: {resp[:120]}...")
            # tutaj możesz zmienić status / presence bota
        except Exception as e:
            print(f"[STATUS] Błąd: {type(e).__name__}: {e}")


def run_discord_bot():
    if not DISCORD_TOKEN:
        print("[DISCORD] Brak tokena → bot nie zostanie uruchomiony")
        return

    print("[DISCORD] Uruchamiam klienta...")
    try:
        asyncio.run(client.start(DISCORD_TOKEN))
    except Exception as e:
        print(f"[DISCORD] Błąd uruchamiania: {e}")


# ────────────────────────────────────────────────
# Główna część programu
# ────────────────────────────────────────────────
if __name__ == "__main__":
    print("[MAIN] Start aplikacji")

    # Uruchamiamy bota w osobnym wątku
    bot_thread = threading.Thread(
        target=run_discord_bot,
        daemon=True,
        name="DiscordBotThread"
    )
    bot_thread.start()

    time.sleep(2)  # dajemy chwilę na start wątku

    # Uruchamiamy Flask (Render tego oczekuje)
    port = int(os.environ.get("PORT", 5000))
    print(f"[MAIN] Uruchamiam Flask na porcie {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
