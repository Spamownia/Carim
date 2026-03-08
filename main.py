import os
import sys
from threading import Thread
from flask import Flask
import subprocess
import socket

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
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        use_reloader=False
    )


if __name__ == '__main__':
    # ==============================================
    # SUPER DEBUG – sprawdzamy IP i PORT osobno
    # ==============================================
    print("=== SUPER DEBUG – IP i PORT osobno ===")
    print(f"Python version: {sys.version}")
    print(f"Current working dir: {os.getcwd()}")

    # Pobieramy i czyścimy wartości
    rcon_ip_raw    = os.environ.get('RCON_IP', 'BRAK')
    rcon_ip        = rcon_ip_raw.strip() if rcon_ip_raw else 'BRAK'
    rcon_port_raw  = os.environ.get('RCON_PORT', 'BRAK')
    rcon_port      = rcon_port_raw.strip() if rcon_port_raw else 'BRAK'

    print(f"RCON_IP   raw    : '{rcon_ip_raw}'")
    print(f"RCON_IP   cleaned: '{rcon_ip}'")
    print(f"RCON_PORT raw    : '{rcon_port_raw}'")
    print(f"RCON_PORT cleaned: '{rcon_port}'")

    # Test 1: resolve samego IP
    if rcon_ip != 'BRAK':
        try:
            resolved_ip = socket.gethostbyname(rcon_ip)
            print(f"socket.gethostbyname(IP) → {resolved_ip}  (OK)")
        except socket.gaierror as e:
            print(f"socket.gethostbyname(IP) → BŁĄD: {e}")
        except Exception as e:
            print(f"Błąd resolve IP: {e}")

    # Test 2: getaddrinfo(IP, PORT) – dokładnie to co robi biblioteka RCon
    if rcon_ip != 'BRAK' and rcon_port != 'BRAK':
        try:
            port_int = int(rcon_port)
            addr_info = socket.getaddrinfo(rcon_ip, port_int, family=socket.AF_INET, type=socket.SOCK_DGRAM)
            print(f"socket.getaddrinfo(IP, PORT) → SUKCES: {addr_info[0]}")
        except ValueError as e:
            print(f"Błąd konwersji PORT na int: {e}")
        except socket.gaierror as e:
            print(f"socket.getaddrinfo(IP, PORT) → BŁĄD: {e}")
        except Exception as e:
            print(f"Inny błąd getaddrinfo(IP, PORT): {e}")
    else:
        print("Brak IP lub PORT – pomijam test getaddrinfo z portem")

    print("=== KONIEC DEBUG ===\n")

    # Flask w tle
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive started on port", os.environ.get("PORT", "nieznany"))
    print("Starting CARIM bot via 'carim-bot' command...")

    cmd = ["carim-bot"]
    # cmd = ["carim-bot", "--verbose"]   # odkomentuj jeśli chcesz pełne logi bota

    try:
        process = subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        process.wait()
    except FileNotFoundError:
        print("BŁĄD: komenda 'carim-bot' nie znaleziona.")
        sys.exit(1)
    except Exception as e:
        print(f"Błąd uruchamiania bota: {e}")
        sys.exit(1)

    sys.exit(process.returncode)
