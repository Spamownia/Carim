import os
import sys
from threading import Thread
from flask import Flask
import asyncio
import socket
import struct
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


# Prosty BattlEye RCon client (UDP)
class SimpleRCon:
    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        self.password = password.encode('utf-8')
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(5)
        self.connected = False

    def connect(self):
        try:
            # BattlEye handshake (login)
            packet = b'\xFF\x00' + self.password
            self.sock.sendto(packet, (self.host, self.port))
            data, addr = self.sock.recvfrom(1024)
            if data.startswith(b'\xFF\x00\x01'):
                print("RCon login OK")
                self.connected = True
            else:
                print("RCon login failed")
        except Exception as e:
            print(f"RCon connect error: {e}")
            self.connected = False

    def send_command(self, cmd):
        if not self.connected:
            self.connect()
            if not self.connected:
                return "Not connected"

        try:
            # BattlEye command packet: FF 01 + cmd
            packet = b'\xFF\x01' + cmd.encode('utf-8')
            self.sock.sendto(packet, (self.host, self.port))
            data, addr = self.sock.recvfrom(4096)
            if data.startswith(b'\xFF\x00'):
                response = data[3:].decode('utf-8', errors='ignore').strip()
                print(f"RCon response: {response}")
                return response
            else:
                return "No response"
        except Exception as e:
            print(f"RCon send error: {e}")
            return str(e)


async def rcon_task():
    host = os.environ.get('RCON_IP', '147.93.162.60').strip()
    port = int(os.environ.get('RCON_PORT', '3705'))
    password = os.environ.get('RCON_PASSWORD', '')

    if not password:
        print("Brak RCON_PASSWORD – RCon wyłączony")
        return

    rcon = SimpleRCon(host, port, password)
    rcon.connect()

    if rcon.connected:
        print("RCon połączony – start loop")
        while True:
            await asyncio.sleep(60)
            try:
                response = rcon.send_command("players")
                print(f"Odpowiedź RCon: {response}")
                # Tutaj możesz wysłać response na Discord – dodaj poniżej
            except Exception as e:
                print(f"Błąd w loopie RCon: {e}")
    else:
        print("Nie udało się połączyć z RCon")


if __name__ == '__main__':
    print("=== START MAIN ===")
    print(f"RCON_IP   : {os.environ.get('RCON_IP')}")
    print(f"RCON_PORT : {os.environ.get('RCON_PORT')}")
    print(f"RCON_PASSWORD length: {len(os.environ.get('RCON_PASSWORD', ''))}")

    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive uruchomiony")

    # Uruchamiamy asyncio loop dla RCon
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(rcon_task())
    except KeyboardInterrupt:
        print("Wyłączanie...")
    except Exception as e:
        print(f"Błąd asyncio: {e}")
    finally:
        loop.close()
