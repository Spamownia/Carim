import os
import sys
import threading
import socket
import time
import struct
from flask import Flask

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
        self.password = password.strip()
        self.sock = None
        self.sequence = 0          # BattlEye wymaga zwiększania sekwencji
        self.connected = False
        self._create_socket()

    def _create_socket(self):
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(8.0)   # 8 sekund – rozsądny kompromis
        print(f"[RCon] Nowy socket UDP utworzony → {self.host}:{self.port}")

    def login(self):
        print("[RCon] Próba logowania...")
        try:
            # Pakiet logowania: header (0xFF 0x00) + hasło
            payload = self.password.encode('utf-8')
            packet = b'\xFF\x00' + payload

            self.sock.sendto(packet, (self.host, self.port))
            print(f"[RCon] Wysyłanie login (len={len(packet)}) → {packet!r}")

            data, addr = self.sock.recvfrom(1024)
            print(f"[RCon] Odpowiedź login (od {addr}, len={len(data)}): {data!r}")

            # Sukces: FF 00 00 01 00 ... (czasami z "Login successful" tekstem)
            if len(data) >= 9 and data.startswith(b'\xFF\x00') and data[7:9] == b'\x00\x01':
                print("[RCon] Zalogowano pomyślnie!")
                self.connected = True
                return True
            else:
                print(f"[RCon] Błąd logowania – odpowiedź: {data!r}")
                return False

        except socket.timeout:
            print("[RCon] Timeout podczas logowania")
        except Exception as e:
            print(f"[RCon] Błąd logowania: {type(e).__name__}: {e}")
        self.connected = False
        return False

    def send_command(self, command):
        if not self.connected:
            if not self.login():
                return "Nie udało się zalogować do RCon"

        try:
            self.sequence = (self.sequence + 1) % 256
            seq_byte = bytes([self.sequence])

            payload = seq_byte + command.encode('utf-8')
            packet = b'\xFF\x01' + payload

            print(f"[RCon] Wysyłam komendę '{command}' (seq={self.sequence}, len={len(packet)})")
            print(f"     Pakiet: {packet!r}")

            self.sock.sendto(packet, (self.host, self.port))

            data, addr = self.sock.recvfrom(4096)
            print(f"[RCon] Odpowiedź (od {addr}, len={len(data)}): {data!r}")

            if len(data) < 9 or not data.startswith(b'\xFF\x00'):
                print("[RCon] Nieprawidłowy format odpowiedzi")
                return "Nieprawidłowa odpowiedź od serwera"

            # Odpowiedź zaczyna się od FF 00 + seq + tekst
            response = data[9:].decode('utf-8', errors='replace').strip()  # pomijamy header + seq
            print(f"[RCon] Sukces – odpowiedź: {response}")
            return response

        except socket.timeout:
            print("[RCon] Timeout podczas oczekiwania na odpowiedź")
            self.connected = False
            return "Timeout"
        except Exception as e:
            print(f"[RCon] Błąd wysyłania komendy: {type(e).__name__}: {e}")
            self.connected = False
            return f"Błąd: {str(e)}"


def rcon_worker():
    host = os.environ.get('RCON_IP', '147.93.162.60').strip()
    port = os.environ.get('RCON_PORT', '3705').strip()
    password = os.environ.get('RCON_PASSWORD', '').strip()

    if not host or not port or not password:
        print("RCON nie skonfigurowany (brak IP/port/hasła) – pomijam pętlę")
        while True:
            time.sleep(3600)

    rcon = SimpleBattlEyeRCon(host, port, password)

    print("Start pętli RCon (co ~60 sekund wysyłane 'players')...")
    while True:
        try:
            response = rcon.send_command("players")
            print(f"[RCon] Odpowiedź na 'players': {response}")
        except Exception as e:
            print(f"[RCon] Nieoczekiwany błąd w pętli: {e}")
        time.sleep(60)  # co minutę


if __name__ == '__main__':
    print("=== BOT START ===")
    print(f"RCON_IP     : {os.environ.get('RCON_IP')}")
    print(f"RCON_PORT   : {os.environ.get('RCON_PORT')}")
    print(f"RCON_PASSWORD length: {len(os.environ.get('RCON_PASSWORD', ''))}")

    # Flask w osobnym wątku (keep-alive dla Render Web Service)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("Flask keep-alive uruchomiony")

    # RCON w osobnym wątku (bo blocking socket)
    rcon_thread = threading.Thread(target=rcon_worker, daemon=True)
    rcon_thread.start()

    # Główny wątek czeka na Ctrl+C
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("Wyłączanie bota...")
    except Exception as e:
        print(f"Główny błąd: {e}")
    finally:
        print("Koniec działania.")
        sys.exit(0)
