import os
import sys
from threading import Thread
from flask import Flask
import asyncio
import socket
import struct
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


class BattlEyeRCon:
    def __init__(self, host, port, password):
        self.host = host
        self.port = int(port)
        self.password = password
        self.sock = None
        self.sequence = 0

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(5)
            self.sock.connect((self.host, self.port))

            # Login packet: header 0xFF 0x00 + password
            login = struct.pack('<I', 0) + b'\xFF\x00' + self.password.encode('utf-8')
            self.sock.send(login)
            data = self.sock.recv(1024)

            if len(data) > 9 and data[7:9] == b'\x00\x01':
                print("RCon: zalogowano pomyślnie")
                return True
            else:
                print(f"RCon login failed: {data}")
                return False
        except Exception as e:
            print(f"RCon connect error: {e}")
            return False

    def send_command(self, cmd):
        if not self.sock:
            if not self.connect():
                return "Nie połączono"

        try:
            self.sequence += 1
            # Command packet: header + sequence + command
            packet = struct.pack('<I', self.sequence) + b'\xFF\x01' + cmd.encode('utf-8')
            self.sock.send(packet)
            data = self.sock.recv(4096)

            if len(data) > 9 and data[7] == 0:
                response = data[9:].decode('utf-8', errors='ignore').strip()
                return response
            else:
                return "Brak odpowiedzi"
        except socket.timeout:
            return "Timeout"
        except Exception as e:
            print(f"RCon command error: {e}")
            return str(e)


async def rcon_loop():
    host = os.environ.get('RCON_IP', '147.93.162.60').strip()
    port = int(os.environ.get('RCON_PORT', '3705'))
    password = os.environ.get('RCON_PASSWORD', '')

    if not password:
        print("Brak hasła RCon – wyłączam RCon")
        while True:
            await asyncio.sleep(3600)

    rcon = BattlEyeRCon(host, port, password)

    print("Start pętli RCon...")

    while True:
        try:
            response = rcon.send_command("players")
            print(f"Odpowiedź RCon: {response}")
            await asyncio.sleep(60)
        except Exception as e:
            print(f"Błąd w pętli: {e}")
            await asyncio.sleep(10)  # krótszy wait przy błędzie


if __name__ == '__main__':
    print("=== BOT START ===")
    print(f"RCON_IP:   {os.environ.get('RCON_IP')}")
    print(f"RCON_PORT: {os.environ.get('RCON_PORT')}")
    print(f"RCON_PASSWORD length: {len(os.environ.get('RCON_PASSWORD', ''))}")

    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive uruchomiony")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(rcon_loop())
    except KeyboardInterrupt:
        print("Wyłączanie...")
    except Exception as e:
        print(f"Główny błąd: {e}")
    finally:
        loop.close()
