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
    # SUPER DEBUG – wszystko co może pomóc
    # ==============================================
    print("=== SUPER DEBUG – START ===")
    print(f"Python version: {sys.version}")
    print(f"Current working dir: {os.getcwd()}")
    print(f"PATH (skrócone): {os.environ.get('PATH', 'brak')[:300]}...")

    print("\nKluczowe zmienne CARIM (raw i stripped):")
    keys = [
        'RCON_IP', 'RCON_PORT', 'RCON_PASSWORD',
        'DISCORD_TOKEN', 'DISCORD_CHANNEL_ID', 'LOG_CHANNEL_ID',
        'COMMAND_PREFIX'
    ]
    for key in keys:
        raw = os.environ.get(key, 'BRAK')
        stripped = raw.strip() if raw else 'BRAK'
        length = len(raw) if raw else 0
        print(f"{key:18}: raw='{raw}' | stripped='{stripped}' | length={length}")

    # Test resolve IP – sprawdzamy, czy system widzi ten adres
    rcon_ip_raw = os.environ.get('RCON_IP')
    if rcon_ip_raw:
        rcon_ip = rcon_ip_raw.strip()
        print(f"\nTest resolve IP: '{rcon_ip}'")
        try:
            resolved = socket.gethostbyname(rcon_ip)
            print(f"→ socket.gethostbyname → {resolved} (SUKCES)")
            try:
                addr_info = socket.getaddrinfo(rcon_ip, 0)
                print(f"→ getaddrinfo → {addr_info[:2]}... (OK)")
            except Exception as e:
                print(f"→ getaddrinfo błąd: {e}")
        except socket.gaierror as e:
            print(f"→ BŁĄD resolve: {e}")
        except Exception as e:
            print(f"→ Inny błąd podczas resolve: {e}")
    else:
        print("\nRCON_IP jest pusty – nie da się przetestować resolve")

    print("=== KONIEC SUPER DEBUG ===\n")

    # Flask w tle – żeby Render nie uśpił instancji
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive started on port", os.environ.get("PORT", "nieznany"))
    print("Starting CARIM bot via 'carim-bot' command...")

    # Najważniejsze – uruchamiamy bota
    cmd = ["carim-bot"]
    # cmd = ["carim-bot", "--verbose"]  # odkomentuj jeśli chcesz więcej logów

    try:
        process = subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        process.wait()  # czekamy – bot powinien działać w nieskończoność
    except FileNotFoundError:
        print("BŁĄD: komenda 'carim-bot' nie znaleziona w PATH.")
        print("Sprawdź instalację pakietu carim-discord-bot.")
        sys.exit(1)
    except Exception as e:
        print(f"Błąd podczas uruchamiania bota: {e}")
        sys.exit(1)

    # Jeśli bot sam padnie – Render powinien zrestartować
    sys.exit(process.returncode)
