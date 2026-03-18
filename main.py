import os
import sys
import threading
import socket
import time
from flask import Flask

app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True


@app.route('/')
def home():
    return "CARIM DayZ Bot działa (tylko keep-alive) 🚀"


@app.route('/health')
@app.route('/ping')
def health_check():
    return "OK", 200


def run_flask_keepalive():
    port = int(os.environ.get("PORT", 10000))
    print(f"[KEEP-ALIVE] Flask startuje na porcie {port}")
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        use_reloader=False,
        threaded=True
    )


class SimpleBattlEyeRCon:
    def __init__(self, host, port, password):
        self.host = host.strip()
        self.port = int(port)
        self.password = password.strip()
        self.sock = None
        self.sequence = 0
        self.connected = False
        self._create_socket()

    def _create_socket(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(10.0)
        print(f"[RCON] Utworzono socket → {self.host}:{self.port}")

    def login(self):
        print("[RCON] Próba logowania...")
        try:
            packet = b'\xFF\x00' + self.password.encode('utf-8')
            self.sock.sendto(packet, (self.host, self.port))
            data, _ = self.sock.recvfrom(1024)

            if len(data) >= 9 and data.startswith(b'\xFF\x00') and data[7:9] == b'\x00\x01':
                print("[RCON] Logowanie UDANE")
                self.connected = True
                return True
            else:
                print(f"[RCON] Logowanie NIEUDANE – odpowiedź: {data!r}")
                return False
        except Exception as e:
            print(f"[RCON] Błąd logowania: {e}")
            return False

    def send_command(self, command):
        if not self.connected:
            if not self.login():
                time.sleep(8)
                return None

        try:
            self.sequence = (self.sequence + 1) % 256
            packet = b'\xFF\x01' + bytes([self.sequence]) + command.encode('utf-8')
            self.sock.sendto(packet, (self.host, self.port))
            data, _ = self.sock.recvfrom(4096)

            if not data.startswith(b'\xFF\x00'):
                raise ValueError("Zła odpowiedź serwera")

            response = data[9:].decode('utf-8', errors='replace').strip()
            return response
        except Exception as e:
            print(f"[RCON] Błąd wysyłania komendy '{command}': {e}")
            self.connected = False
            return None


def rcon_worker():
    host = os.environ.get('RCON_IP', '').strip()
    port_str = os.environ.get('RCON_PORT', '2302').strip()  # 2302 to domyślny BattlEye
    password = os.environ.get('RCON_PASSWORD', '').strip()

    if not host or not password:
        print("!!! BRAK RCON_IP LUB RCON_PASSWORD – bot w trybie uśpienia !!!")
        while True:
            time.sleep(1800)

    try:
        port = int(port_str)
    except ValueError:
        print("!!! Nieprawidłowy RCON_PORT – używam domyślnego 2302 !!!")
        port = 2302

    print(f"[START] RCON → {host}:{port} (hasło: {len(password)} znaków)")

    rcon = SimpleBattlEyeRCon(host, port, password)

    while True:
        try:
            resp = rcon.send_command("players")
            if resp is not None:
                print(f"[PLAYERS] {resp}")
            else:
                print("[PLAYERS] Brak odpowiedzi – ponawiam za 60s")
        except Exception as e:
            print(f"[RCON LOOP] Błąd: {e}")
        time.sleep(60)


if __name__ == '__main__':
    print("══════════════════════════════════════════")
    print("     CARIM DayZ RCon Bot – START")
    print(f"PORT (keep-alive) : {os.environ.get('PORT', '10000 (domyślny)')}")
    print(f"RCON_IP           : {os.environ.get('RCON_IP')}")
    print(f"RCON_PORT         : {os.environ.get('RCON_PORT')}")
    print(f"RCON_PASSWORD len : {len(os.environ.get('RCON_PASSWORD', ''))}")
    print("══════════════════════════════════════════")

    flask_thread = threading.Thread(target=run_flask_keepalive, daemon=True)
    flask_thread.start()

    rcon_thread = threading.Thread(target=rcon_worker, daemon=True)
    rcon_thread.start()

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("Bot wyłączany (Ctrl+C)")
    finally:
        print("Koniec działania bota.")
        sys.exit(0)
