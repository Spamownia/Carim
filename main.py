import os
import sys
from threading import Thread
from flask import Flask
import asyncio
import socket
import time

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


class SimpleBattlEyeRCon:
    def __init__(self, host, port, password):
        self.host = host
        self.port = int(port)
        self.password = password
        self.sock = None
        self.connected = False

    def connect(self):
        if self.connected:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(5)
            self.sock.connect((self.host, self.port))

            # Handshake / login
            login_packet = b'\xFF\x00' + self.password.encode('utf-8')
            self.sock.send(login_packet)
            data = self.sock.recv(1024)

            if data.startswith(b'\xFF\x00\x01'):
                print("RCon: zalogowano pomyślnie")
                self.connected = True
                return True
            else:
                print("RCon: błąd logowania (złe hasło?)")
                return False
        except Exception as e:
            print(f"RCon connect error: {e}")
            self.connected = False
            return False

    def send_command(self, command):
        if not self.connected:
            if not self.connect():
                return "Nie połączono z RCon"

        try:
            # Pakiet komendy: FF 01 + komenda
            packet = b'\xFF\x01' + command.encode('utf-8')
            self.sock.send(packet)
            data = self.sock.recv(4096)

            if data.startswith(b'\xFF\x00'):
                # Odpowiedź zaczyna się od FF 00, potem treść
                response = data[3:].decode('utf-8', errors='ignore').strip()
                return response
            else:
                return "Brak odpowiedzi"
        except socket.timeout:
            return "Timeout – brak odpowiedzi"
        except Exception as e:
            print(f"RCon send error: {e}")
            self.connected = False
            return str(e)


async def rcon_loop():
    host = os.environ.get('RCON_IP', '').strip()
    port = os.environ.get('RCON_PORT', '3705').strip()
    password = os.environ.get('RCON_PASSWORD', '')

    if not host or not port or not password:
        print("RCON nie skonfigurowany – pomijam")
        while True:
            await asyncio.sleep(3600)

    rcon = SimpleBattlEyeRCon(host, port, password)

    print("Start pętli RCon...")

    while True:
        try:
            if not rcon.connected:
                print("Próba ponownego połączenia...")
                rcon.connect()

            if rcon.connected:
                response = rcon.send_command("players")
                print(f"Odpowiedź RCon (players): {response}")

                # Możesz dodać tu wysyłanie na Discord / logowanie do pliku
                # np. await channel.send(f"Gracze: {response}")

            await asyncio.sleep(60)  # co minutę
        except Exception as e:
            print(f"Błąd w pętli RCon: {e}")
            await asyncio.sleep(10)  # krótszy sleep przy błędzie


if __name__ == '__main__':
    print("=== BOT START ===")
    print(f"RCON_IP:   {os.environ.get('RCON_IP')}")
    print(f"RCON_PORT: {os.environ.get('RCON_PORT')}")
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
        print("Wyłączanie bota...")
    except Exception as e:
        print(f"Główny błąd: {e}")
    finally:
        loop.close()
