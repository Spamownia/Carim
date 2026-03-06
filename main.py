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
    # Flask w tle – żeby Render nie uśpił instancji na free planie
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive started on port", os.environ.get("PORT", "nieznany"))
    print("Starting CARIM bot via 'carim-bot' command...")

    # Najważniejsza część – uruchamiamy bot tak, jak normalnie z terminala
    cmd = ["carim-bot"]

    # Jeśli chcesz więcej informacji w logach Render → odkomentuj poniższą linię
    # cmd = ["carim-bot", "--verbose"]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
            bufsize=1,                  # line buffered – logi na bieżąco
            universal_newlines=True
        )
        
        # Czekamy na proces (bot powinien działać w nieskończoność)
        process.wait()
        
    except FileNotFoundError:
        print("BŁĄD: komenda 'carim-bot' nie znaleziona w PATH.")
        print("Sprawdź czy pakiet carim-discord-bot zainstalował się poprawnie.")
        sys.exit(1)
    except Exception as e:
        print(f"Błąd podczas uruchamiania bota: {e}")
        sys.exit(1)

    # Jeśli bot sam się zakończy (rzadko) – Render to wykryje i zrestartuje
    sys.exit(process.returncode)
