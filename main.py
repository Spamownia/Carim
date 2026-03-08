import os
import sys
from threading import Thread
from flask import Flask
import subprocess
import socket
import asyncio

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


def test_socket_resolve():
    host = os.environ.get('RCON_IP', '').strip()
    port_str = os.environ.get('RCON_PORT', '3705').strip()

    print(f"\n=== TEST SOCKET RESOLVE ===")
    print(f"Host raw: '{os.environ.get('RCON_IP')}'")
    print(f"Host cleaned: '{host}'")
    print(f"Port raw: '{os.environ.get('RCON_PORT')}'")
    print(f"Port cleaned: '{port_str}'")

    if not host or not port_str:
        print("BRAK IP lub PORT – test pominięty")
        return

    try:
        port = int(port_str)
    except ValueError:
        print(f"Błąd: port '{port_str}' nie jest liczbą")
        return

    # Test 1: gethostbyname (tylko IP)
    try:
        resolved_ip = socket.gethostbyname(host)
        print(f"gethostbyname({host}) → {resolved_ip}  (SUKCES)")
    except socket.gaierror as e:
        print(f"gethostbyname → BŁĄD: {e}")
        return

    # Test 2: getaddrinfo (IP + port)
    try:
        addr_info = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_DGRAM)
        print(f"getaddrinfo({host}, {port}) → SUKCES: {addr_info[0]}")
    except socket.gaierror as e:
        print(f"getaddrinfo → BŁĄD: {e}")
    except Exception as e:
        print(f"Inny błąd getaddrinfo: {e}")


if __name__ == '__main__':
    print("=== MAIN START – DEBUG ===")
    test_socket_resolve()
    print("=== KONIEC DEBUG ===\n")

    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive uruchomiony na porcie", os.environ.get("PORT", "nieznany"))

    cmd = ["carim-bot"]
    # cmd = ["carim-bot", "--verbose"]  # odkomentuj, jeśli chcesz pełne logi bota

    print("Uruchamiam carim-bot...")
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
        print("BŁĄD: 'carim-bot' nie znaleziono w PATH")
        sys.exit(1)
    except Exception as e:
        print(f"Błąd startu carim-bot: {e}")
        sys.exit(1)

    sys.exit(process.returncode)
