import os
from threading import Thread
from flask import Flask
import subprocess
import sys
import socket  # do testu resolve IP

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
    # DEBUG – wypiszmy wszystko co ważne przed startem bota
    # ==============================================
    print("=== DEBUG START – RENDER ENV VARS I ŚRODOWISKO ===")
    print(f"Python version: {sys.version}")
    print(f"Current working dir: {os.getcwd()}")
    print(f"PATH: {os.environ.get('PATH', 'brak')[:200]}...")  # skracamy, bo długie

    print("\nKluczowe zmienne CARIM:")
    print(f"RCON_IP       : '{os.environ.get('RCON_IP', 'BRAK')}'")
    print(f"RCON_PORT     : '{os.environ.get('RCON_PORT', 'BRAK')}'")
    print(f"RCON_PASSWORD : {'ustawione (długość ' + str(len(os.environ.get('RCON_PASSWORD', ''))) + ')' if 'RCON_PASSWORD' in os.environ else 'BRAK'}")
    print(f"DISCORD_TOKEN : {'ustawione (długość ' + str(len(os.environ.get('DISCORD_TOKEN', ''))) + ')' if 'DISCORD_TOKEN' in os.environ else 'BRAK'}")
    print(f"DISCORD_CHANNEL_ID : '{os.environ.get('DISCORD_CHANNEL_ID', 'BRAK')}'")
    print(f"LOG_CHANNEL_ID     : '{os.environ.get('LOG_CHANNEL_ID', 'BRAK')}'")
    print(f"COMMAND_PREFIX     : '{os.environ.get('COMMAND_PREFIX', 'BRAK')}'")

    # Test resolve IP – sprawdzamy, czy system widzi ten adres
    rcon_ip = os.environ.get('RCON_IP')
    if rcon_ip:
        try:
            resolved = socket.gethostbyname(rcon_ip.strip())
            print(f"socket.gethostbyname('{rcon_ip}') → {resolved}  (OK)")
        except socket.gaierror as e:
            print(f"socket.gethostbyname('{rcon_ip}') → BŁĄD: {e}")
        except Exception as e:
            print(f"Błąd podczas resolve IP: {e}")
    else:
        print("RCON_IP jest pusty – nie da się przetestować resolve")

    print("=== KONIEC DEBUGU ===\n")

    # Flask w tle
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive started on port", os.environ.get("PORT", "nieznany"))
    print("Starting CARIM bot via 'carim-bot' command...")

    cmd = ["carim-bot"]
    # cmd = ["carim-bot", "--verbose"]   # odkomentuj jeśli chcesz bardzo szczegółowe logi

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
        print("BŁĄD: komenda 'carim-bot' nie znaleziona w PATH.")
        print("Sprawdź instalację pakietu carim-discord-bot.")
        sys.exit(1)
    except Exception as e:
        print(f"Błąd podczas uruchamiania bota: {e}")
        sys.exit(1)

    sys.exit(process.returncode)
