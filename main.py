import os
from threading import Thread
from flask import Flask
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
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive started on port", os.environ.get("PORT", "nieznany"))
    print("Starting CARIM Discord bot...")

    # ────────────────────────────────────────────────
    # Tutaj poprawka – uruchamiamy CLI entrypoint
    # ────────────────────────────────────────────────
    from carim_discord_bot.cli import main as carim_cli_main
    sys.argv = ['carim-bot']                     # symulujemy komendę carim-bot
    # sys.argv = ['carim-bot', '--verbose']      # jeśli chcesz więcej logów

    carim_cli_main()
