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
    return "CARIM DayZ Bot is running! (keep-alive only) 🚀"


@app.route('/health')
@app.route('/ping')
def health_check():
    return "OK", 200


def run_flask_keepalive():
    # Flask tylko do utrzymania procesu przy życiu – NIE używany przez Fly proxy
    port = int(os.environ.get("PORT", 10000))           # fallback na 10000
    print(f"[Keep-alive] Uruchamiam Flask dummy server na 0.0.0.0:{port}")
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
        print(f"[RCon] Nowy socket → {self.host}:{self.port}")

    def login(self):
        print("[RCon] Próba logowania...")
        try:
            payload = self.password.encode('utf-8')
            packet = b'\xFF\x00' + payload
            self.sock.sendto(packet, (self.host, self.port))
            data, _ = self.sock.recvfrom(1024)

            if len(data) >= 9 and data.startswith(b'\xFF\x00') and data[7:9] == b'\x00\x01':
                print("[RCon] Zalogowano pomyślnie")
                self.connected = True
                return True
            else:
                print(f"[RCon] Błąd logowania – odpowiedź: {data!r}")
                return False
        except socket.timeout:
            print("[RCon] Timeout logowania")
        except Exception as e:
            print(f"[RCon] Błąd logowania: {e}")
        self.connected = False
        return False

    def send_command(self, command):
        if not self.connected:
            if not self.login():
                print("[RCon] Nie udało się zalogować – reconnect za 10s")
                time.sleep(10)
                return None

        try:
            self.sequence = (self.sequence + 1) % 256
            packet = b'\xFF\x01' + bytes([self.sequence]) + command.encode('utf-8')
            self.sock.sendto(packet, (self.host, self.port))
            data, _ = self.sock.recvfrom(4096)

            if not data.startswith(b'\xFF\x00'):
                raise ValueError("Nieprawidłowy header odpowiedzi")

            # Pomijamy header + sequence byte
            response = data[9:].decode('utf-8', errors='replace').strip()
            return response
        except socket.timeout:
            print("[RCon] Timeout komendy → reconnect")
            self.connected = False
        except Exception as e:
            print(f"[RCon] Błąd komendy: {e}")
            self.connected = False
        return None


def rcon_worker():
    host = os.environ.get('RCON_IP', '147.93.162.60').strip()
    port_str = os.environ.get('RCON_PORT', '3705').strip()
    password = os.environ.get('RCON_PASSWORD', '').strip()

    if not host or not port_str or not password:
        print("!!! RCON_IP / RCON_PORT / RCON_PASSWORD nie ustawione – bot idle !!!")
        while True:
            time.sleep(3600)

    port = int(port_str)
    print(f"[RCON] Konfiguracja → {host}:{port} (hasło: {len(password)} znaków)")

    rcon = SimpleBattlEyeRCon(host, port, password)

    while True:
        try:
            response = rcon.send_command("players")
            if response is not None:
                print(f"[RCon players] {response}")
            else:
                print("[RCon] Komenda zwróciła None – czekam")
        except Exception as e:
            print(f"[RCon worker] Nieoczekiwany błąd: {e}")

        time.sleep(60)


if __name__ == '__main__':
    print("=== CARIM DayZ RCon Bot START ===")
    print(f"PORT (keep-alive)   : {os.environ.get('PORT', 'nie ustawiony (użyje 10000)')}")
    print(f"RCON_IP             : {os.environ.get('RCON_IP')}")
    print(f"RCON_PORT           : {os.environ.get('RCON_PORT')}")
    print(f"RCON_PASSWORD len   : {len(os.environ.get('RCON_PASSWORD', ''))}")

    # Wątek z dummy Flask (tylko keep-alive)
    flask_thread = threading.Thread(target=run_flask_keepalive, daemon=True)
    flask_thread.start()

    # Główny worker RCON
    rcon_thread = threading.Thread(target=rcon_worker, daemon=True)
    rcon_thread.start()

    # Trzymamy główny wątek żywy
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("Wyłączanie bota (Ctrl+C)")
    except Exception as e:
        print(f"Główny wątek błąd: {e}")
    finally:
        print("Koniec działania.")
        sys.exit(0)
