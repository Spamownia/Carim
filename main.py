import os
from threading import Thread
from flask import Flask
from carim_discord_bot import main as carim_main

app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True   # pomaga przy błędach w wątkach

@app.route('/')
def home():
    return "CARIM DayZ Bot is running! 🚀"

@app.route('/health')
@app.route('/ping')
def health_check():
    return "OK", 200

def run_flask():
    # Render SAM przypisuje zmienną PORT – nie hardkoduj!
    port = int(os.environ.get("PORT", 10000))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        use_reloader=False
    )

if __name__ == '__main__':
    # Uruchamiamy Flask w osobnym wątku (daemon → zginie z głównym procesem)
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("Flask keep-alive started on port", os.environ.get("PORT", "nieznany"))
    print("Starting CARIM Discord bot...")

    # Start właściwego bota CARIM
    carim_main()
