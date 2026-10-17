import os
import re
import logging
import asyncio
import requests
from urllib.parse import urlparse
from threading import Thread
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ---------------- CONFIGURATION ----------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
FORCE_JOIN_CHANNEL = os.getenv("FORCE_JOIN_CHANNEL", "").strip()
FORCE_JOIN_URL = os.getenv("FORCE_JOIN_URL", "").strip()
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
}

# Professional API Configuration
TERABOX_API_URL = os.getenv("TERABOX_DL_API_URL", "https://api.teraboxdl.site/v1/api").strip()
TERABOX_API_KEY = os.getenv("TERABOX_DL_API_KEY", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("terabox_bot")

URL_PATTERN = re.compile(r"https?://[^\s<>]+")
TERABOX_HOSTS = {
    "terabox.com", "www.terabox.com",
    "1024terabox.com", "www.1024terabox.com",
    "teraboxapp.com", "www.teraboxapp.com",
    "teraboxlink.com", "www.teraboxlink.com",
    "terabox.fun", "www.terabox.fun",
}
VIDEO_EXTENSIONS = (".mp4", ".m4v", ".mov", ".webm", ".mkv", ".avi")

def get_host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""

def is_valid_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.hostname)
    except ValueError:
        return False

def is_terabox_url(url: str) -> bool:
    host = get_host(url)
    return any(host == domain or host.endswith("." + domain) for domain in TERABOX_HOSTS)

# ---------------- FORCE JOIN LOGIC ----------------
async def is_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False
    if user.id in ADMIN_IDS:
        return True
    if not FORCE_JOIN_CHANNEL:
        return True
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_JOIN_CHANNEL, user_id=user.id)
        return member.status in ("creator", "administrator", "member")
    except TelegramError as exc:
        logger.warning("Membership check failed: %s", exc)
        return False

def join_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    if FORCE_JOIN_URL:
        buttons.append([InlineKeyboardButton("📢 Join Promotion Channel", url=FORCE_JOIN_URL)])
    buttons.append([InlineKeyboardButton("✅ I've Joined — Check Again", callback_data="check_join")])
    return InlineKeyboardMarkup(buttons)

async def require_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if await is_member(update, context):
        return True
    text = "🔒 <b>Join Required</b>\n\nPlease join our promotion channel first to use the bot."
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, reply_markup=join_keyboard(), parse_mode="HTML")
    elif update.effective_message:
        await update.effective_message.reply_text(text, reply_markup=join_keyboard(), parse_mode="HTML")
    return False

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()
    if await is_member(update, context):
        await query.message.reply_text("✅ Membership verified! Now send your TeraBox link.")
    else:
        await query.message.reply_text("❌ Not joined yet. Please join and try again.", reply_markup=join_keyboard())

# ---------------- COMMANDS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_membership(update, context):
        return
    await update.effective_message.reply_text(
        "👋 Welcome to TeraBox Pro Bot!\n\n"
        "📥 Just send any TeraBox link and I'll generate a direct download link for you.\n\n"
        "Commands:\n"
        "/start - Start bot\n"
        "/help - How to use\n"
        "/id - Get your Telegram ID"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_membership(update, context):
        return
    await update.effective_message.reply_text(
        "📌 How to use\n\n"
        "1. Copy your TeraBox share link\n"
        "2. Paste it here\n"
        "3. Bot will fetch the direct link via API\n"
        "4. Download or stream instantly"
    )

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user:
        await update.effective_message.reply_text(f"Your Telegram ID: {update.effective_user.id}")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or update.effective_user.id not in ADMIN_IDS:
        await update.effective_message.reply_text("⛔ Admin only.")
        return
    await update.effective_message.reply_text(
        f"✅ Admin access active.\n"
        f"Force Join: {FORCE_JOIN_CHANNEL or 'Disabled'}\n"
        f"API URL: {TERABOX_API_URL}\n"
        f"API Key Configured: {'Yes' if TERABOX_API_KEY else 'No'}"
    )

# ---------------- CORE API FUNCTION ----------------
def get_direct_link_from_api(terabox_url: str) -> str | None:
    if not TERABOX_API_URL or not TERABOX_API_KEY:
        logger.error("API URL or KEY is missing in environment variables")
        return None
    try:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": TERABOX_API_KEY,
            "Authorization": f"Bearer {TERABOX_API_KEY}",
        }
        payload = {"url": terabox_url}
        logger.info(f"Calling API: {TERABOX_API_URL} for {terabox_url}")
        response = requests.post(TERABOX_API_URL, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        logger.info(f"API Response received: {data}")
        if isinstance(data, dict):
            if data.get("direct_link"):
                return data["direct_link"]
            if data.get("download_link"):
                return data["download_link"]
            if data.get("downloadUrl"):
                return data["downloadUrl"]
            if isinstance(data.get("data"), dict):
                nested = data["data"]
                return nested.get("direct_link") or nested.get("download_link") or nested.get("url")
            if isinstance(data.get("data"), list) and len(data["data"]) > 0:
                first = data["data"][0]
                if isinstance(first, dict):
                    return first.get("direct_link") or first.get("download_link") or first.get("url")
        return None
    except requests.exceptions.HTTPError as http_err:
        logger.error(f"API HTTP Error: {http_err} - Response: {http_err.response.text if http_err.response else 'No response'}")
        return None
    except Exception as e:
        logger.error(f"API call failed: {e}")
        return None

# ---------------- LINK PROCESSING ----------------
async def process_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_membership(update, context):
        return
    message = update.effective_message
    if not message or not message.text:
        return
    urls = URL_PATTERN.findall(message.text)
    if not urls:
        await message.reply_text("Please send a valid HTTP/HTTPS link.")
        return
    url = urls[0].rstrip(".,!?)\"]}'")
    if not is_valid_http_url(url):
        await message.reply_text("❌ Invalid URL format.")
        return
    if not is_terabox_url(url):
        await message.reply_text("❌ Please send only a valid TeraBox link.")
        return
    status_msg = await message.reply_text("⏳ Processing... Fetching direct link via API, please wait.")
    direct_link = get_direct_link_from_api(url)
    if not direct_link:
        await status_msg.edit_text(
            "❌ Failed to generate direct link.\n\n"
            "Possible reasons:\n"
            "- API key invalid or expired\n"
            "- TeraBox link is private or expired\n"
            "- API server is down\n\n"
            "Please try again later or contact admin."
        )
        return
    try:
        await message.reply_video(
            video=direct_link,
            caption="✅ Here is your video",
            supports_streaming=True,
            read_timeout=90,
            write_timeout=90,
        )
        await status_msg.delete()
    except TelegramError as exc:
        logger.warning(f"Telegram video send failed, sending as link: {exc}")
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📥 Download / Watch", url=direct_link)]])
        await status_msg.edit_text(
            "✅ Direct link generated successfully!\n\n"
            "Telegram cannot stream this file directly (too large or format issue). "
            "Click below to download.",
            reply_markup=keyboard,
        )

# ---------------- ERROR HANDLER ----------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception", exc_info=context.error)

# ---------------- HEALTH SERVER + WEBHOOK ----------------
health_app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("id", id_command))
application.add_handler(CommandHandler("admin", admin_command))
application.add_handler(CallbackQueryHandler(check_join, pattern="^check_join$"))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_link))
application.add_error_handler(error_handler)

@health_app.route("/")
def home():
    return "TeraBox Bot is running!", 200

@health_app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Initialize only once
        try:
            loop.run_until_complete(application.initialize())
        except Exception:
            pass # Already initialized
        loop.run_until_complete(application.process_update(update))
        loop.close()
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
    return "ok", 200

@health_app.route("/set-webhook")
def set_webhook_route():
    if not WEBHOOK_URL:
        return "WEBHOOK_URL env missing. Add https://teraboxbot-251o.onrender.com/webhook", 400
    try:
        requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=True", timeout=10)
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={WEBHOOK_URL}", timeout=10)
        return r.text, 200
    except Exception as e:
        return str(e), 500

def run_health_server():
    port = int(os.getenv("PORT", "10000"))
    health_app.run(host="0.0.0.0", port=port, use_reloader=False)

# ---------------- MAIN ----------------
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing.")
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    if WEBHOOK_URL:
        logger.info(f"Starting in WEBHOOK mode: {WEBHOOK_URL}")
        port = int(os.getenv("PORT", "10000"))
        health_app.run(host="0.0.0.0", port=port, use_reloader=False)
    else:
        Thread(target=run_health_server, daemon=True).start()
        logger.info("Starting Telegram bot polling...")
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
