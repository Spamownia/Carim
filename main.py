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
        self.host = host.strip()
        self.port = int(port)
        self.password = password
        self.sock = None
        self.connected = False

    def connect(self):
        if self.connected and self.sock:
            print("[RCon] Już połączony – używam istniejącego socketu")
            return True

        print(f"[RCon] Tworzę nowe połączenie: {self.host}:{self.port}")

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.settimeout(10)
            print("[RCon] Socket utworzony (UDP)")

            self.sock.connect((self.host, self.port))
            print("[RCon] connect() OK – socket podłączony")

            # Pakiet login: FF 00 + hasło
            login_packet = b'\xFF\x00' + self.password.encode('utf-8')
            print(f"[RCon] Wysyłam pakiet login (długość: {len(login_packet)} bajtów)")
            self.sock.send(login_packet)

            print("[RCon] Czekam na odpowiedź login (timeout 10s)...")
            data = self.sock.recv(1024)
            print(f"[RCon] Otrzymano dane (długość {len(data)} bajtów): {data!r}")

            # BattlEye login success: zaczyna się od FF 00 01
            if len(data) >= 9 and data[7:9] == b'\x00\x01':
                print("RCon: zalogowano pomyślnie!")
                self.connected = True
                return True
            else:
                print(f"RCon: błąd logowania – odpowiedź: {data!r}")
                return False

        except socket.timeout:
            print("RCon: timeout podczas oczekiwania na odpowiedź login")
            return False
        except ConnectionRefusedError:
            print("RCon: połączenie odrzucone (serwer nie słucha lub firewall)")
            return False
        except OSError as e:
            print(f"RCon: błąd systemu (OSError): {e}")
            return False
        except Exception as e:
            print(f"RCon: nieoczekiwany błąd: {type(e).__name__}: {e}")
            return False

    def send_command(self, command):
        print(f"[RCon] Wysyłam komendę: '{command}'")

        if not self.connected:
            if not self.connect():
                return "Nie udało się połączyć z RCon"

        try:
            packet = b'\xFF\x01' + command.encode('utf-8')
            print(f"[RCon] Pakiet komendy (długość: {len(packet)} bajtów)")
            self.sock.send(packet)

            print("[RCon] Czekam na odpowiedź...")
            data = self.sock.recv(4096)
            print(f"[RCon] Otrzymano odpowiedź (długość {len(data)} bajtów): {data!r}")

            if len(data) >= 3 and data[0:1] == b'\xFF':
                response = data[3:].decode('utf-8', errors='ignore').strip()
                print(f"[RCon] Sukces – odpowiedź: {response}")
                return response
            else:
                print("[RCon] Nieprawidłowy format odpowiedzi")
                return "Nieprawidłowa odpowiedź"
        except socket.timeout:
            print("[RCon] Timeout odpowiedzi na komendę")
            return "Timeout"
        except Exception as e:
            print(f"[RCon] Błąd wysyłania komendy: {type(e).__name__}: {e}")
            self.connected = False
            return str(e)


async def rcon_loop():
    host = os.environ.get('RCON_IP', '147.93.162.60').strip()
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
            response = rcon.send_command("players")
            print(f"Odpowiedź RCon (players): {response}")
            await asyncio.sleep(60)
        except Exception as e:
            print(f"Błąd w pętli RCon: {e}")
            await asyncio.sleep(15)  # krótszy wait przy błędzie


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
        print(f"Główny błąd asyncio: {e}")
    finally:
        loop.close()
