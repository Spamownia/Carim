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
    # Flask w tle – keep-alive dla Render free plan
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive started on port", os.environ.get("PORT", "nieznany"))
    print("Starting CARIM bot via 'carim-bot' command...")

    # Uruchamiamy dokładnie tak, jak w README: carim-bot
    # Dodaj --verbose jeśli chcesz więcej logów do debugu
    cmd = ["carim-bot"]  # lub ["carim-bot", "--verbose"]

    # Uruchamiamy i przekierowujemy output do logów Render
    try:
        process = subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
            bufsize=1,          # line buffered
            universal_newlines=True
        )
        process.wait()  # blokuje – bot działa non-stop, chyba że crash
    except FileNotFoundError:
        print("ERROR: 'carim-bot' command not found in PATH. Check if package installed correctly.")
        sys.exit(1)

    # Jeśli bot padnie – Render zrestartuje
    sys.exit(process.returncode)
