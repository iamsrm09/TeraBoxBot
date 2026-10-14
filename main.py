import os, re, requests, telebot
from telebot import types
from flask import Flask
import threading

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask).start()

# --- iske neeche tera wahi purana code ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
... (baaki sab same jo maine diya tha)
