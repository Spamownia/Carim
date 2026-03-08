import os
import sys
from threading import Thread
from flask import Flask
import asyncio
import socket

# Importujemy tylko to, co naprawdę istnieje w carim-discord-bot 2.2.5
from carim_discord_bot.rcon.rcon_protocol import RconProtocol
from carim_discord_bot.rcon.rcon_service import RconService

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


async def rcon_loop():
    host = os.environ.get('RCON_IP', '').strip()
    port_str = os.environ.get('RCON_PORT', '3705').strip()
    password = os.environ.get('RCON_PASSWORD', '')

    if not host or not port_str or not password:
        print("BRAK RCON_IP / RCON_PORT / RCON_PASSWORD – pomijam RCon")
        return

    try:
        port = int(port_str)
    except ValueError:
        print(f"Błąd: RCON_PORT '{port_str}' nie jest liczbą")
        return

    print(f"Próba RCon: {host}:{port} (hasło: {'ustawione' if password else 'BRAK'})")

    # Ręczny resolve IP + port
    loop = asyncio.get_running_loop()
    try:
        addr_info = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_DGRAM)
        if not addr_info:
            print("getaddrinfo zwróciło pustą listę")
            return
        sockaddr = addr_info[0][4]  # ('147.93.162.60', 3705)

        print(f"Resolved: {sockaddr}")

        # Tworzymy endpoint ręcznie (używamy RconProtocol z biblioteki)
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: RconProtocol(password),
            local_addr=('0.0.0.0', 0),
            remote_addr=sockaddr
        )

        print("RCon transport utworzony pomyślnie!")

        # Przykładowy loop – co 30 s wysyłamy "players" (możesz zmienić)
        while True:
            await asyncio.sleep(30)
            try:
                protocol.send_command("players")
                print("Wysłano komendę: players")
            except Exception as e:
                print(f"Błąd wysyłania komendy: {e}")

    except Exception as e:
        print(f"Błąd RCon: {e}")


if __name__ == '__main__':
    print("=== START MAIN ===")
    print(f"RCON_IP   : {os.environ.get('RCON_IP')}")
    print(f"RCON_PORT : {os.environ.get('RCON_PORT')}")
    print(f"RCON_PASSWORD length: {len(os.environ.get('RCON_PASSWORD', ''))}")

    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive uruchomiony")

    # Główna pętla asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(rcon_loop())
    except KeyboardInterrupt:
        print("Wyłączanie...")
    except Exception as e:
        print(f"Błąd w pętli: {e}")
    finally:
        loop.close()
