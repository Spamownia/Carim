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

print("[DEBUG] Skrypt uruchomiony")
print(f"[DEBUG] Zmienne środowiskowe: TOKEN={'tak' if os.getenv('DISCORD_TOKEN') else 'BRAK'}, "
      f"RCON_IP={os.getenv('RCON_IP')}, RCON_PORT={os.getenv('RCON_PORT')}, "
      f"RCON_PASSWORD={'tak' if os.getenv('RCON_PASSWORD') else 'BRAK'} (długość: {len(os.getenv('RCON_PASSWORD', ''))})")

# Flask
app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "bot_running": client.is_ready() if 'client' in globals() else False,
        "rcon_logged_in": rcon.logged_in if 'rcon' in globals() else False,
        "thread_alive": bot_thread.is_alive() if 'bot_thread' in globals() else False
    })

# ────────────────────────────────────────────────
# RCON z ekstremalnym debugowaniem
# ────────────────────────────────────────────────

class BattlEyeRCon:
    def __init__(self, ip: str, port: int, password: str):
        print(f"[RCON INIT] Tworzę instancję: {ip}:{port}, hasło długość={len(password)}")
        self.ip = ip
        self.port = port
        self.password = password
        self.sock = None
        self.sequence = 0
        self.logged_in = False
        self.last_activity = time.time()
        self._connect()

    def _connect(self):
        print("[RCON] Próba stworzenia socketa UDP...")
        if self.sock:
            try:
                self.sock.close()
                print("[RCON] Zamknięto stary socket")
            except Exception as e:
                print(f"[RCON] Błąd zamykania starego socketa: {e}")
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.ip, self.port))
            print(f"[RCON CONNECT] Socket utworzony i połączony → {self.ip}:{self.port}")
        except Exception as e:
            print(f"[RCON CONNECT ERROR] Nie udało się stworzyć socketa: {type(e).__name__}: {e}")
            self.sock = None

    def _crc32(self, data: bytes) -> bytes:
        crc = zlib.crc32(data) & 0xFFFFFFFF
        print(f"[RCON CRC] Obliczony CRC32 dla {len(data)} bajtów: {crc:08x}")
        return crc.to_bytes(4, "little")

    def _build_packet(self, packet_type: int, payload: bytes = b"") -> bytes:
        body = bytes([packet_type]) + payload
        header = b"BE" + self._crc32(body) + b"\xFF"
        packet = header + body
        print(f"[RCON PACKET BUILD] Typ={packet_type:02x}, długość payload={len(payload)}, "
              f"całkowity pakiet={len(packet)} bajtów, początek hex: {packet[:16].hex()}")
        return packet

    def login(self) -> bool:
        print("[RCON LOGIN] Rozpoczynam procedurę logowania")
        if not self.password:
            print("[RCON LOGIN] Brak hasła → pomijam")
            return False

        if not self.sock:
            print("[RCON LOGIN] Brak socketa → ponowne połączenie")
            self._connect()
            if not self.sock:
                print("[RCON LOGIN] Nadal brak socketa → abort")
                return False

        print(f"[RCON LOGIN] Hasło (długość): {len(self.password)}, ukryte: {self.password[:2]}***{self.password[-2:]}")

        packet = self._build_packet(0x00, self.password.encode("utf-8", errors="replace"))

        try:
            print("[RCON LOGIN] Wysyłam pakiet logowania...")
            sent = self.sock.send(packet)
            print(f"[RCON LOGIN] Wysyłanie OK – wysłano {sent} bajtów")

            print("[RCON LOGIN] Czekam na odpowiedź (timeout 4s)...")
            self.sock.settimeout(4.0)
            data = self.sock.recv(4096)

            print(f"[RCON LOGIN] Otrzymano {len(data)} bajtów")
            print(f"[RCON LOGIN] Odpowiedź hex (pierwsze 64 bajty): {data[:64].hex()}")
            print(f"[RCON LOGIN] Odpowiedź repr: {data!r}")

            if len(data) < 10:
                print("[RCON LOGIN] Zbyt krótka odpowiedź")
                return False

            if not data.startswith(b"BE"):
                print("[RCON LOGIN] Brak nagłówka BE → to nie BattlEye")
                return False

            received_crc = data[2:6]
            payload = data[8:]
            calc_crc = self._crc32(payload)
            print(f"[RCON LOGIN] CRC received: {received_crc.hex()}, calculated: {calc_crc.hex()}")

            if received_crc != calc_crc:
                print("[RCON LOGIN] Nieprawidłowy CRC")
                return False

            if data[9] != 0x00:
                print(f"[RCON LOGIN] Nieprawidłowy typ odpowiedzi: {data[9]:02x}")
                return False

            if len(payload) >= 1 and payload[0] == 0x01:
                self.logged_in = True
                self.last_activity = time.time()
                print("[RCON LOGIN] SUKCES – zalogowano pomyślnie!")
                return True
            else:
                print("[RCON LOGIN] Serwer odrzucił logowanie (status != 0x01)")
                return False

        except socket.timeout:
            print("[RCON LOGIN] TIMEOUT – serwer nie odpowiedział w 4 sekundy")
        except Exception as e:
            print(f"[RCON LOGIN] BŁĄD podczas logowania: {type(e).__name__}: {e}")

        self.logged_in = False
        return False

    def send_command(self, command: str) -> str:
        print(f"[RCON SEND] Próba wysłania komendy: '{command}'")
        if not self.logged_in:
            print("[RCON SEND] Nie zalogowany → próbuję login...")
            if not self.login():
                return "❌ Nie udało się zalogować (patrz logi powyżej)"

        # reszta metody send_command bez zmian – dodaj printy jeśli chcesz

        # ... (wklej resztę Twojej implementacji send_command)

        return "Odpowiedź (dodaj printy jeśli potrzeba)"

rcon = BattlEyeRCon(RCON_IP, RCON_PORT, RCON_PASSWORD)

# ────────────────────────────────────────────────
# DISCORD + wątek
# ────────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = False

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    print(f"[DISCORD] Bot zalogowany jako {client.user} (ID: {client.user.id})")
    print("[DISCORD] Synchronizuję slash commands...")
    try:
        await tree.sync()
        print("[DISCORD] Slash commands zsynchronizowane")
    except Exception as e:
        print(f"[DISCORD] Błąd synchronizacji komend: {e}")
    asyncio.create_task(status_loop())

async def status_loop():
    print("[STATUS LOOP] Uruchamiam pętlę statusu...")
    while True:
        print("[STATUS LOOP] Kolejna iteracja...")
        try:
            resp = rcon.send_command("players")
            print(f"[STATUS LOOP] Odpowiedź na 'players': {resp[:100] if resp else 'Brak odpowiedzi'}")
            # ... reszta parsowania i change_presence
        except Exception as e:
            print(f"[STATUS LOOP] Błąd: {type(e).__name__}: {e}")
        await asyncio.sleep(60)

# Twoje komendy (dodaj printy jeśli chcesz)
# @tree.command(...) ...

# ────────────────────────────────────────────────
# Uruchomienie
# ────────────────────────────────────────────────

def run_discord_bot():
    print("[THREAD] Start wątku Discorda")
    try:
        asyncio.run(client.start(TOKEN))
    except Exception as e:
        print(f"[THREAD] Błąd w wątku Discorda: {e}")

if __name__ == "__main__":
    print("[MAIN] Start aplikacji Render")
    print(f"[MAIN] PORT z env: {os.environ.get('PORT', 'brak')}")

    bot_thread = threading.Thread(target=run_discord_bot, daemon=True, name="DiscordThread")
    bot_thread.start()
    print("[MAIN] Wątek Discorda uruchomiony")

    # Czekamy chwilę, żeby zobaczyć czy wątek ruszył
    time.sleep(5)
    print(f"[MAIN] Status po 5s: thread alive = {bot_thread.is_alive()}")

    port = int(os.environ.get("PORT", 5000))
    print(f"[MAIN] Start Flask na {port}")
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
