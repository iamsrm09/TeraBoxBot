import os
import re
import logging
import requests
from urllib.parse import urlparse
from flask import Flask, request

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
FORCE_JOIN_CHANNEL = os.getenv("FORCE_JOIN_CHANNEL", "").strip()
FORCE_JOIN_URL = os.getenv("FORCE_JOIN_URL", "").strip()
TERABOX_API_URL = os.getenv("TERABOX_DL_API_URL", "https://api.teraboxdl.site/v1/api").strip()
TERABOX_API_KEY = os.getenv("TERABOX_DL_API_KEY", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()  # Add this in Render: https://teraboxbot-251o.onrender.com/webhook

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("terabox_bot")

URL_PATTERN = re.compile(r"https?://[^\s<>]+")
TERABOX_HOSTS = {"terabox.com", "1024terabox.com", "teraboxapp.com", "teraboxlink.com", "terabox.fun"}

health_app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

def is_terabox_url(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in TERABOX_HOSTS)

def get_direct_link_from_api(terabox_url: str):
    try:
        headers = {"Content-Type": "application/json", "x-api-key": TERABOX_API_KEY, "Authorization": f"Bearer {TERABOX_API_KEY}"}
        resp = requests.post(TERABOX_API_URL, json={"url": terabox_url}, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data.get("direct_link") or data.get("download_link") or data.get("url") or data.get("data", {}).get("direct_link") if isinstance(data.get("data"), dict) else data.get("data", [{}])[0].get("url") if isinstance(data.get("data"), list) else None
    except Exception as e:
        logger.error(f"API failed: {e}")
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("👋 Send your TeraBox link, I will give you direct link.")

async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if not message or not message.text: return
    urls = URL_PATTERN.findall(message.text)
    if not urls: return
    url = urls[0].rstrip(".,!?)\"]}'")
    if not is_terabox_url(url):
        await message.reply_text("❌ Please send only TeraBox link.")
        return
    status = await message.reply_text("⏳ Fetching direct link...")
    direct = get_direct_link_from_api(url)
    if not direct:
        await status.edit_text("❌ Failed to get direct link. Check API key or link.")
        return
    try:
        await message.reply_video(video=direct, caption="✅ Here is your video", supports_streaming=True)
        await status.delete()
    except Exception:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download", url=direct)]])
        await status.edit_text("✅ Direct link ready:", reply_markup=keyboard)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_link))

@health_app.route("/")
def home():
    return "Bot is running!", 200

@health_app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok", 200

@health_app.route("/set-webhook")
def set_webhook():
    if not WEBHOOK_URL:
        return "WEBHOOK_URL env missing", 400
    # Delete old polling and set webhook
    requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=True")
    r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}")
    return r.text, 200

if __name__ == "__main__":
    import asyncio
    # For local testing you can still use polling, but on Render use webhook
    if os.getenv("USE_POLLING", "false").lower() == "true":
        application.run_polling(drop_pending_updates=True)
    else:
        port = int(os.getenv("PORT", "10000"))
        health_app.run(host="0.0.0.0", port=port)
