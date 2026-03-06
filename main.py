import os
from threading import Thread
from flask import Flask
import subprocess
import sys

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
    # Flask w tle – żeby Render nie uśpił instancji
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive started on port", os.environ.get("PORT", "nieznany"))
    print("Starting CARIM bot via 'carim-bot' command...")

    # Najważniejsze – uruchamiamy bota
    cmd = ["carim-bot"]

    # Jeśli chcesz więcej logów do debugowania:
    # cmd = ["carim-bot", "--verbose"]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
            bufsize=1,                  # logi na bieżąco
            universal_newlines=True
        )
        process.wait()              # czekamy – bot powinien działać w nieskończoność
    except FileNotFoundError:
        print("BŁĄD: komenda 'carim-bot' nie znaleziona w PATH.")
        print("Sprawdź instalację pakietu carim-discord-bot.")
        sys.exit(1)
    except Exception as e:
        print(f"Błąd podczas uruchamiania bota: {e}")
        sys.exit(1)

    # Jeśli bot sam padnie – Render powinien zrestartować instancję
    sys.exit(process.returncode)
