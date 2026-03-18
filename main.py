import os
import asyncio
import socket
import discord
from discord import app_commands
import zlib  # do CRC32
import time
import threading
from dotenv import load_dotenv

load_dotenv()

# ========================= KONFIGURACJA =========================
TOKEN = os.getenv("DISCORD_TOKEN")
RCON_IP = os.getenv("RCON_IP", "127.0.0.1")
RCON_PORT = int(os.getenv("RCON_PORT", "2302"))
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "")

if not TOKEN:
    print("❌ Brak DISCORD_TOKEN w zmiennych środowiskowych!")
    exit(1)
if not RCON_PASSWORD:
    print("❌ Brak RCON_PASSWORD – logowanie się nie uda")
    # ale nie wychodzimy – może ktoś chce tylko Discord bez RCON

# ========================= RCON IMPLEMENTACJA =========================
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
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(5.0)
        self.sock.connect((self.ip, self.port))
        print(f"[RCON] Utworzono socket → {self.ip}:{self.port}")

    def _crc32(self, data: bytes) -> bytes:
        """Oblicza 4-bajtowy CRC32 tak jak wymaga BattlEye"""
        crc = zlib.crc32(data) & 0xFFFFFFFF
        return crc.to_bytes(4, "little")

    def _build_packet(self, packet_type: int, payload: bytes = b"") -> bytes:
        body = bytes([packet_type]) + payload
        header = b"BE" + self._crc32(body) + b"\xFF"
        return header + body

    def login(self) -> bool:
        if not self.password:
            print("[RCON] Brak hasła → pomijam logowanie")
            return False

        print(f"[RCON] Próba logowania jako hasło: {self.password[:3]}***")

        packet = self._build_packet(0x00, self.password.encode("utf-8"))
        try:
            self.sock.send(packet)
            data = self.sock.recv(4096)
        except Exception as e:
            print(f"[RCON] Błąd podczas logowania: {e}")
            self.logged_in = False
            return False

        if len(data) < 12:
            print("[RCON] Zbyt krótka odpowiedź serwera")
            return False

        # BE + CRC + FF + 00 + 01/00
        if data[:9] == b"BE" + self._crc32(data[8:]) + b"\xFF\x00":
            if data[9] == 0x01:
                self.logged_in = True
                print("[RCON] Zalogowano pomyślnie do BattlEye RCON!")
                self.last_activity = time.time()
                return True
            else:
                print("[RCON] Nieprawidłowe hasło (serwer zwrócił 0x00)")
        else:
            print("[RCON] Nieprawidłowy format odpowiedzi logowania")

        self.logged_in = False
        return False

    def send_command(self, command: str) -> str:
        if not self.logged_in and not self.login():
            return "❌ Nie udało się zalogować do RCON"

        # keep-alive / odświeżenie połączenia
        if time.time() - self.last_activity > 35:
            self._send_keepalive()

        self.sequence = (self.sequence + 1) % 256

        packet = self._build_packet(0x01, bytes([self.sequence]) + command.encode("utf-8"))
        try:
            self.sock.send(packet)
            data = self.sock.recv(16384)  # większy bufor na listy graczy / banów
            self.last_activity = time.time()
        except socket.timeout:
            self.logged_in = False
            return "❌ Timeout – brak odpowiedzi"
        except Exception as e:
            self.logged_in = False
            return f"❌ Błąd komunikacji: {e}"

        if len(data) < 12:
            return "❌ Zbyt krótka odpowiedź"

        # Sprawdzenie nagłówka
        expected_crc = self._crc32(data[8:])
        if data[:8] != b"BE" + expected_crc:
            return "❌ Uszkodzony pakiet (zły CRC)"

        if data[9] != 0xFF:
            return "❌ Nieprawidłowy format pakietu"

        if data[10] != self.sequence:
            print(f"[RCON] Ostrzeżenie: sequence mismatch (oczekiwano {self.sequence}, dostałem {data[10]})")

        # Pomijamy nagłówek BE + CRC + FF + seq
        payload = data[11:]

        # Multi-packet support (bardzo uproszczony – tylko jeden pakiet)
        # Jeśli potrzebujesz pełnego wsparcia – trzeba parsować 0x00 na końcu i seq
        return payload.decode("utf-8", errors="replace").strip()

    def _send_keepalive(self):
        """Wysyła pusty pakiet komendy (tylko seq) – utrzymuje sesję"""
        try:
            self.sequence = (self.sequence + 1) % 256
            packet = self._build_packet(0x01, bytes([self.sequence]))
            self.sock.send(packet)
            self.last_activity = time.time()
            # nie odbieramy odpowiedzi – to tylko keep-alive
        except:
            pass

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass


rcon = BattlEyeRCon(RCON_IP, RCON_PORT, RCON_PASSWORD)

# ========================= DISCORD BOT =========================
intents = discord.Intents.default()
intents.message_content = False  # nie potrzebujemy treści wiadomości

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot zalogowany jako {client.user}")
    asyncio.create_task(status_loop())


async def status_loop():
    while True:
        await asyncio.sleep(60)
        try:
            resp = rcon.send_command("players")
            if not resp or "players" not in resp.lower():
                continue

            lines = resp.splitlines()
            if len(lines) > 0 and lines[0].strip().isdigit():
                count = lines[0].strip()
            elif "players online" in resp.lower():
                count = resp.split("online")[0].strip()[-2:].strip()
            else:
                count = "?"

            await client.change_presence(
                activity=discord.Game(name=f"Graczy: {count} | DayZ")
            )
        except Exception as e:
            print(f"[status] Błąd: {e}")


# ========================= KOMENDY =========================
@tree.command(name="players", description="Lista graczy na serwerze")
async def cmd_players(interaction: discord.Interaction):
    await interaction.response.defer()
    resp = rcon.send_command("players")
    if not resp:
        resp = "Brak odpowiedzi / nie zalogowano"
    await interaction.followup.send(f"**Gracze online:**\n```{resp}```")


@tree.command(name="say", description="Wyślij wiadomość globalną na serwer")
async def cmd_say(interaction: discord.Interaction, tekst: str):
    await interaction.response.defer()
    resp = rcon.send_command(f"say -1 {tekst}")
    await interaction.followup.send(f"✅ Wiadomość: `{tekst}`\nOdpowiedź: ```{resp or 'OK'}```")


@tree.command(name="kick", description="Wyrzuca gracza po ID")
async def cmd_kick(interaction: discord.Interaction, player_id: int, reason: str = "Brak powodu"):
    await interaction.response.defer()
    resp = rcon.send_command(f"kick {player_id} {reason}")
    await interaction.followup.send(f"✅ Kick {player_id} → `{reason}`\nOdpowiedź: `{resp or 'OK'}`")


@tree.command(name="ban", description="Ban gracza po ID")
async def cmd_ban(interaction: discord.Interaction, player_id: int, reason: str = "Brak powodu"):
    await interaction.response.defer()
    resp = rcon.send_command(f"ban {player_id} {reason}")
    await interaction.followup.send(f"✅ Ban {player_id} → `{reason}`\nOdpowiedź: `{resp or 'OK'}`")


@tree.command(name="rcon", description="Dowolna komenda RCON (admin only)")
async def cmd_raw(interaction: discord.Interaction, komenda: str):
    await interaction.response.defer()
    resp = rcon.send_command(komenda)
    if len(resp) > 1900:
        resp = resp[:1900] + "... (skrócono)"
    await interaction.followup.send(f"**Komenda:** `{komenda}`\n**Odpowiedź:**\n```{resp or 'Brak odpowiedzi'}```")


# ========================= URUCHOMIENIE =========================
if __name__ == "__main__":
    print("🚀 Uruchamiam Carim Discord + RCon Bot...")
    print(f"   → RCON: {RCON_IP}:{RCON_PORT}   hasło: {RCON_PASSWORD[:3]}***")
    client.run(TOKEN)
