import os
import sys
from threading import Thread
from flask import Flask
import asyncio
import socket
from carim_discord_bot import config
from carim_discord_bot.rcon.rcon_protocol import RconProtocol
from carim_discord_bot.rcon.rcon_connection import RconConnection
import discord
from discord.ext import commands

app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True


@app.route('/')
def home():
    return "CARIM DayZ Bot is running! 🚀"


@app.route('/health')
@app.route('/ping')
def health_check():
    return "OK", 200


def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)


async def create_rcon_connection():
    host = os.environ.get('RCON_IP', '').strip()
    port_str = os.environ.get('RCON_PORT', '').strip()
    password = os.environ.get('RCON_PASSWORD', '')

    if not host or not port_str or not password:
        print("BRAK RCON_IP / RCON_PORT / RCON_PASSWORD – pomijam RCon")
        return None

    try:
        port = int(port_str)
    except ValueError:
        print(f"Błąd: RCON_PORT '{port_str}' nie jest liczbą")
        return None

    print(f"Próba połączenia RCon: {host}:{port} (hasło: {'ustawione' if password else 'BRAK'})")

    # Najpierw ręcznie resolve IP + port
    try:
        addr_info = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_DGRAM)
        if not addr_info:
            print("getaddrinfo zwróciło pustą listę")
            return None
        family, socktype, proto, canonname, sockaddr = addr_info[0]
        print(f"Resolved: {sockaddr}")
    except Exception as e:
        print(f"Błąd resolve IP:port → {e}")
        return None

    # Tworzymy transport i protokół ręcznie
    loop = asyncio.get_running_loop()
    try:
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: RconProtocol(password),
            local_addr=('0.0.0.0', 0),
            remote_addr=sockaddr
        )
        print("RCon transport utworzony pomyślnie")
        return RconConnection(transport, protocol)
    except Exception as e:
        print(f"Błąd create_datagram_endpoint: {e}")
        return None


async def main_bot_loop():
    # Ładujemy config z env vars (CARIM to obsługuje)
    config.load_from_env()

    # Tworzymy RCon connection ręcznie
    rcon_conn = await create_rcon_connection()
    if rcon_conn:
        print("RCon połączony – gotowy do wysyłania komend")
        # Tu możesz dodać logikę wysyłania/odbierania – np. co 30 s ping
        while True:
            await asyncio.sleep(30)
            # Przykład: wysłanie komendy
            # await rcon_conn.send_command("players")
    else:
        print("RCon nie udało się połączyć – bot działa tylko z Discordem")

    # Uruchamiamy Discord bota (jeśli masz token)
    token = os.environ.get('DISCORD_TOKEN')
    if token:
        intents = discord.Intents.default()
        bot = commands.Bot(command_prefix=os.environ.get('COMMAND_PREFIX', '!'), intents=intents)

        @bot.event
        async def on_ready():
            print(f"Discord zalogowany jako {bot.user}")

        await bot.start(token)
    else:
        print("Brak DISCORD_TOKEN – pomijam Discord")
        await asyncio.sleep(3600)  # śpij godzinę


if __name__ == '__main__':
    print("=== START MAIN ===")
    print(f"RCON_IP: {os.environ.get('RCON_IP')}")
    print(f"RCON_PORT: {os.environ.get('RCON_PORT')}")
    print(f"RCON_PASSWORD length: {len(os.environ.get('RCON_PASSWORD', ''))}")
    print(f"DISCORD_TOKEN length: {len(os.environ.get('DISCORD_TOKEN', ''))}")

    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive uruchomiony")

    # Uruchamiamy główną pętlę asyncio
    try:
        asyncio.run(main_bot_loop())
    except KeyboardInterrupt:
        print("Wyłączanie bota...")
    except Exception as e:
        print(f"Błąd w main_bot_loop: {e}")
        sys.exit(1)
