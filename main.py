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

try:
    RCON_PORT = int(RCON_PORT_RAW) if RCON_PORT_RAW else 3705
except (ValueError, TypeError):
    print("!!! Nieprawidłowy RCON_PORT → używam domyślnego 3705 !!!")
    RCON_PORT = 3705

print("[START] Skrypt uruchomiony")
print(f"  DISCORD_TOKEN  → {'obecny' if DISCORD_TOKEN else 'BRAK'}")
print(f"  RCON_IP        → {RCON_IP or 'BRAK'}")
print(f"  RCON_PORT      → {RCON_PORT}")
print(f"  RCON_PASSWORD  → {'obecne' if RCON_PASSWORD else 'BRAK'} (dł. {len(RCON_PASSWORD or '')})")


# ────────────────────────────────────────────────
# Prosty test outbound UDP – czy Render pozwala odbierać odpowiedzi UDP
# ────────────────────────────────────────────────
def test_udp_outbound():
    print("\n===== TEST: Czy Render pozwala na outbound UDP + odpowiedź? =====")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(6.0)
        # Wysyłamy cokolwiek do Google DNS – liczy się tylko czy wraca odpowiedź
        sock.sendto(b"\x00\x00\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x03www\x06google\x03com\x00\x00\x01\x00\x01",
                    ("8.8.8.8", 53))
        data, addr = sock.recvfrom(512)
        print(f"[UDP TEST] SUKCES – otrzymano {len(data)} bajtów od {addr}")
    except socket.timeout:
        print("[UDP TEST] TIMEOUT → Render najprawdopodobniej blokuje odpowiedzi UDP")
    except Exception as e:
        print(f"[UDP TEST] Błąd: {type(e).__name__} → {e}")
    finally:
        sock.close()


test_udp_outbound()


# ────────────────────────────────────────────────
# Flask – healthcheck
# ────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "bot_running": 'client' in globals() and client.is_ready(),
        "rcon_logged_in": 'rcon' in globals() and rcon is not None and rcon.logged_in,
        "thread_alive": 'bot_thread' in globals() and bot_thread.is_alive()
    })


# ────────────────────────────────────────────────
# Klasa BattlEye RCON
# ────────────────────────────────────────────────
class BattlEyeRCon:
    def __init__(self, ip: str, port: int, password: str):
        print(f"[RCON INIT] {ip}:{port}  (hasło: {len(password)} znaków)")
        self.ip = ip
        self.port = port
        self.password = (password or "").strip()
        self.sock: Optional[socket.socket] = None
        self.logged_in = False
        self._connect()

    def _connect(self) -> None:
        print(f"[RCON] Tworzenie socketa UDP → {self.ip}:{self.port}")
        if self.sock:
            try:
                self.sock.close()
            except:
                pass

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(10.0)
            self.sock.connect((self.ip, self.port))
            print("[RCON] connect() OK")
        except Exception as e:
            print(f"[RCON] connect() NIEUDANE: {type(e).__name__} → {e}")
            self.sock = None

    def _crc32(self, data: bytes) -> bytes:
        return zlib.crc32(data).to_bytes(4, 'little')

    def _build_packet(self, packet_type: int, payload: bytes = b'') -> bytes:
        body = bytes([packet_type]) + payload
        return b'BE' + self._crc32(body) + b'\xff' + body

    def login(self) -> bool:
        if not self.password:
            print("[RCON LOGIN] Brak hasła")
            return False

        if not self.sock:
            self._connect()
            if not self.sock:
                return False

        for attempt in range(1, 3):
            print(f"[RCON LOGIN] Próba {attempt}/2")
            packet = self._build_packet(0x00, self.password.encode('utf-8', errors='replace'))

            try:
                self.sock.send(packet)
                print("[RCON LOGIN] Pakiet wysłany, czekam na odpowiedź...")
                data = self.sock.recv(4096)
                print(f"[RCON LOGIN] Otrzymano {len(data)} bajtów")

                if not data.startswith(b'BE'):
                    print("[RCON LOGIN] Brak nagłówka BE")
                    return False

                received_crc = data[2:6]
                payload_start = 9
                payload = data[payload_start:]
                if received_crc != self._crc32(payload):
                    print("[RCON LOGIN] Błędny CRC")
                    return False

                if len(payload) >= 1 and payload[0] == 0x01:
                    self.logged_in = True
                    print("[RCON LOGIN] ZALOGOWANO POMYŚLNIE")
                    return True
                else:
                    print(f"[RCON LOGIN] Odrzucono (status: {payload[0] if payload else 'brak'})")
                    return False

            except socket.timeout:
                print(f"[RCON LOGIN] Timeout (10s) – próba {attempt}")
                time.sleep(1.5)
                continue
            except Exception as e:
                print(f"[RCON LOGIN] Błąd: {type(e).__name__} → {e}")
                break

        print("[RCON LOGIN] Wszystkie próby nieudane")
        return False

    def send_command(self, command: str) -> str:
        if not self.logged_in and not self.login():
            return "❌ Nie udało się zalogować do RCON"

        # Tutaj brakuje jeszcze pełnej implementacji wysyłania komend i odbierania odpowiedzi
        # Na razie tylko placeholder
        print(f"[RCON CMD] Wysyłanie (placeholder): {command}")
        return f"[PLACEHOLDER] Komenda '{command}' wysłana – implementacja niekompletna"


# ────────────────────────────────────────────────
# Inicjalizacja RCON + natychmiastowy test
# ────────────────────────────────────────────────
rcon: Optional[BattlEyeRCon] = None

if RCON_IP and RCON_PORT and RCON_PASSWORD:
    rcon = BattlEyeRCon(RCON_IP, RCON_PORT, RCON_PASSWORD)
    print("\n===== AUTOMATYCZNY TEST LOGOWANIA =====")
    if rcon.login():
        print("===== TEST UDANY – RCON DZIAŁA =====")
    else:
        print("===== TEST NIEUDANY – patrz logi powyżej =====")
else:
    print("[RCON] Brakujące zmienne → RCON wyłączony")


# ────────────────────────────────────────────────
# Discord Bot
# ────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = False

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
    print(f"[DISCORD] Zalogowano jako {client.user}")
    try:
        await tree.sync()
        print("[DISCORD] Komendy zsynchronizowane")
    except Exception as e:
        print(f"[DISCORD] Błąd sync: {e}")
    asyncio.create_task(status_loop())


async def status_loop():
    print("[STATUS] Pętla statusu uruchomiona")
    await asyncio.sleep(10)

    while True:
        if rcon:
            try:
                resp = rcon.send_command("players")
                print(f"[STATUS] Odpowiedź: {resp}")
            except Exception as e:
                print(f"[STATUS] Błąd: {e}")
        await asyncio.sleep(60)


def run_discord_bot():
    if not DISCORD_TOKEN:
        print("[DISCORD] Brak tokena → bot nie wystartuje")
        return
    asyncio.run(client.start(DISCORD_TOKEN))


# ────────────────────────────────────────────────
# Główna część
# ────────────────────────────────────────────────
if __name__ == "__main__":
    print("[MAIN] Start aplikacji")
    bot_thread = threading.Thread(target=run_discord_bot, daemon=True)
    bot_thread.start()
    time.sleep(4)

    port = int(os.environ.get("PORT", 5000))
    print(f"[MAIN] Flask na porcie {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
