import os
import asyncio
import threading
import time
import socket
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

# ========================= KONFIGURACJA =========================
TOKEN = os.getenv("DISCORD_TOKEN")
RCON_IP = os.getenv("RCON_IP", "127.0.0.1")
RCON_PORT = int(os.getenv("RCON_PORT", "2302"))
RCON_PASSWORD = os.getenv("RCON_PASSWORD", "")

if not TOKEN or not RCON_PASSWORD:
    print("❌ Brak DISCORD_TOKEN lub RCON_PASSWORD w zmiennych środowiskowych!")
    exit(1)

# ========================= RCON KLASA =========================
class BattlEyeRCon:
    def __init__(self):
        self.sock = None
        self.sequence = 0
        self.connected = False
        self._connect()

    def _connect(self):
        if self.sock:
            self.sock.close()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(8)
        self.sock.connect((RCON_IP, RCON_PORT))
        print(f"[RCON] Połączono z {RCON_IP}:{RCON_PORT}")

    def login(self):
        packet = b'\xFF\x00' + RCON_PASSWORD.encode('utf-8')
        self.sock.send(packet)
        try:
            data = self.sock.recv(1024)
            if len(data) >= 9 and data[7:9] == b'\x00\x01':
                self.connected = True
                print("[RCON] Zalogowano pomyślnie!")
                return True
        except:
            pass
        print("[RCON] Logowanie nieudane")
        return False

    def send(self, command: str) -> str:
        if not self.connected and not self.login():
            return "❌ Nie połączono z RCon"

        self.sequence = (self.sequence + 1) % 256
        packet = b'\xFF\x01' + bytes([self.sequence]) + command.encode('utf-8')
        self.sock.send(packet)

        try:
            data = self.sock.recv(4096)
            if data.startswith(b'\xFF\x00'):
                return data[9:].decode('utf-8', errors='replace').strip()
        except:
            self.connected = False
        return "❌ Brak odpowiedzi (timeout)"

rcon = BattlEyeRCon()

# ========================= DISCORD BOT =========================
intents = discord.Intents.default()
intents.message_content = False
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

@client.event
async def on_ready():
    await tree.sync()
    print(f"✅ Bot zalogowany jako {client.user}")
    asyncio.create_task(update_status_loop())

async def update_status_loop():
    """Co 60 sekund aktualizuje status bota na liczbę graczy"""
    while True:
        try:
            response = rcon.send("players")
            if "players" in response.lower() or response:
                # prosty parsing – bierzemy pierwszą liczbę
                players = response.splitlines()[0].split()[0] if response else "0"
                await client.change_presence(
                    activity=discord.Game(name=f"Graczy: {players} | DayZ")
                )
        except:
            pass
        await asyncio.sleep(60)

# ========================= KOMENDY =========================
@tree.command(name="players", description="Lista graczy na serwerze")
async def players(interaction: discord.Interaction):
    await interaction.response.defer()
    resp = rcon.send("players")
    await interaction.followup.send(f"**Gracze online:**\n```{resp or 'Brak odpowiedzi'}```")

@tree.command(name="say", description="Wiadomość na serwer (say -1 tekst)")
async def say(interaction: discord.Interaction, tekst: str):
    await interaction.response.defer()
    resp = rcon.send(f"say -1 {tekst}")
    await interaction.followup.send(f"✅ Wiadomość wysłana:\n`{tekst}`\nOdpowiedź: `{resp}`")

@tree.command(name="kick", description="Wyrzuć gracza")
async def kick(interaction: discord.Interaction, id: int, powód: str = "Brak powodu"):
    await interaction.response.defer()
    resp = rcon.send(f"kick {id} {powód}")
    await interaction.followup.send(f"✅ Kick {id} wysłany\nOdpowiedź: `{resp}`")

@tree.command(name="ban", description="Ban gracza")
async def ban(interaction: discord.Interaction, id: int, powód: str = "Brak powodu"):
    await interaction.response.defer()
    resp = rcon.send(f"ban {id} {powód}")
    await interaction.followup.send(f"✅ Ban {id} wysłany\nOdpowiedź: `{resp}`")

@tree.command(name="rcon", description="Dowolna komenda RCon (dla adminów)")
async def raw_rcon(interaction: discord.Interaction, komenda: str):
    await interaction.response.defer()
    resp = rcon.send(komenda)
    await interaction.followup.send(f"**Wysłano:** `{komenda}`\n**Odpowiedź:**\n```{resp or 'Brak odpowiedzi'}```")

# ========================= URUCHOMIENIE =========================
if __name__ == "__main__":
    print("🚀 Uruchamiam Carim Discord + RCon Bot...")
    client.run(TOKEN)
