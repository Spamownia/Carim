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
    # Uruchamiamy Flask w tle
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive started on port", os.environ.get("PORT", "nieznany"))
    print("Starting CARIM Discord bot via subprocess...")

    # Symulujemy uruchomienie carim-bot (jakbyś wpisał w terminalu: carim-bot)
    # Dodajemy --verbose jeśli chcesz więcej logów do debugu
    cmd = [sys.executable, "-m", "carim_discord_bot", "--verbose"]  # lub bez --verbose

    # Uruchamiamy i czekamy (blokuje główny wątek, ale to OK – bot ma działać non-stop)
    process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr, text=True)

    # Czekamy na zakończenie (w praktyce bot nigdy nie kończy, chyba że błąd)
    process.wait()

    # Jeśli bot padnie – Flask też padnie (Render to wykryje i zrestartuje)
    sys.exit(process.returncode)
