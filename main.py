import os
import re
import logging
import requests
from urllib.parse import urlparse
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
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

# API ADDED HERE
TERABOX_DL_API_KEY = os.getenv("TERABOX_DL_API_KEY", "").strip()
TERABOX_DL_API_URL = os.getenv("TERABOX_DL_API_URL", "").strip()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("terabox_bot")

URL_PATTERN = re.compile(r"https?://[^\s<>]+")
TERABOX_HOSTS = {
    "terabox.com",
    "www.terabox.com",
    "1024terabox.com",
    "www.1024terabox.com",
    "teraboxapp.com",
    "www.teraboxapp.com",
    "teraboxlink.com",
    "www.teraboxlink.com",
}
VIDEO_EXTENSIONS = (".mp4", ".m4v", ".mov", ".webm")

def get_host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""

def is_valid_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )
    except ValueError:
        return False

def is_terabox_url(url: str) -> bool:
    host = get_host(url)
    return any(host == domain or host.endswith("." + domain) for domain in TERABOX_HOSTS)

def is_direct_video_url(url: str) -> bool:
    if not is_valid_http_url(url):
        return False
    path = urlparse(url).path.lower()
    return path.endswith(VIDEO_EXTENSIONS)

# ---------------- FORCE JOIN ----------------
async def is_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    if not user:
        return False
    if user.id in ADMIN_IDS:
        return True
    if not FORCE_JOIN_CHANNEL:
        return True
    try:
        member = await context.bot.get_chat_member(
            chat_id=FORCE_JOIN_CHANNEL,
            user_id=user.id,
        )
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
    text = (
        "🔒 <b>Join Required</b>\n\n"
        "Bot use karne se pehle hamara promotion channel join karein. "
        "Join karne ke baad neeche diye button par tap karein."
    )
    if update.callback_query:
        await update.callback_query.answer()
        if update.callback_query.message:
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
        await query.message.reply_text("✅ Membership verified!\n\nAb apna TeraBox link bhejein.")
    else:
        await query.message.reply_text("❌ Membership verify nahi hui. Channel join karke phir try karein.", reply_markup=join_keyboard())

# ---------------- BOT COMMANDS ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_membership(update, context):
        return
    await update.effective_message.reply_text(
        "👋 Welcome to TeraBox Link Bot!\n\n"
        "📥 TeraBox shared link bhejein.\n"
        "Bot API se direct link nikalne ki koshish karega.\n\n"
        "Commands:\n"
        "/start — Start bot\n"
        "/help — Help\n"
        "/id — Apni Telegram ID dekhein"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_membership(update, context):
        return
    await update.effective_message.reply_text(
        "📌 How to use\n\n"
        "1. TeraBox share link bhejein.\n"
        "2. Bot API se direct download link generate karega.\n"
        "3. Agar link valid hua to video bhej dega."
    )

async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user and update.effective_message:
        await update.effective_message.reply_text(f"Your Telegram ID: {user.id}")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or user.id not in ADMIN_IDS:
        await update.effective_message.reply_text("⛔ Admin only command.")
        return
    await update.effective_message.reply_text(
        f"✅ Admin access active.\nForce Join: {FORCE_JOIN_CHANNEL or 'Disabled'}\n"
        f"API Configured: {'Yes' if TERABOX_DL_API_KEY else 'No'}"
    )

# ---------------- API CALL FUNCTION ----------------
def get_direct_link_from_api(terabox_url: str):
    if not TERABOX_DL_API_URL or not TERABOX_DL_API_KEY:
        logger.error("API URL or KEY missing")
        return None
    try:
        headers = {"x-api-key": TERABOX_DL_API_KEY, "Authorization": f"Bearer {TERABOX_DL_API_KEY}"}
        # Most APIs use GET with ?url= or ?link=
        resp = requests.get(TERABOX_DL_API_URL, params={"url": terabox_url}, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        # Adjust as per your API response - common keys: direct_link, download_link, url
        return data.get("direct_link") or data.get("download_link") or data.get("url") or data.get("directlink")
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
        await message.reply_text("Please ek valid HTTP/HTTPS link bhejein.")
        return
    url = urls[0].rstrip(".,!?)\"]}'")
    if not is_valid_http_url(url):
        await message.reply_text("❌ Invalid URL.")
        return

    if is_terabox_url(url):
        status = await message.reply_text("⏳ TeraBox link mila, API se direct link nikal raha hoon...")
        direct_link = get_direct_link_from_api(url)
        if not direct_link:
            await status.edit_text(
                "❌ API se direct link nahi mila. API key / URL check karo ya link private hai.",
                disable_web_page_preview=True
            )
            return
        try:
            await message.reply_video(video=direct_link, caption="▶️ Video", supports_streaming=True)
            await status.delete()
        except TelegramError as exc:
            logger.warning(f"Video delivery failed: {exc}")
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📥 Direct Download", url=direct_link)]])
            await status.edit_text(
                f"✅ Direct link ready hai. Telegram pe direct play nahi ho paya, button se download karo.",
                reply_markup=keyboard
            )
        return

    if is_direct_video_url(url):
        status = await message.reply_text("⏳ Direct video URL detected, bhej raha hoon...")
        try:
            await message.reply_video(video=url, caption="▶️ Video", supports_streaming=True)
            await status.delete()
        except TelegramError as exc:
            logger.warning(f"Video delivery failed: {exc}")
            await status.edit_text("❌ Telegram is URL se video fetch nahi kar saka.")
        return

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Open Link", url=url)]])
    await message.reply_text("Link mil gaya, lekin supported format me nahi hai.", reply_markup=keyboard, disable_web_page_preview=True)

# ---------------- ERROR HANDLING ----------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled bot error", exc_info=context.error)

from flask import Flask
from threading import Thread

health_app = Flask(__name__)

@health_app.route("/")
def home():
    return "TeraBox Bot is running!", 200

@health_app.route("/health")
def health():
    return {"status": "ok"}, 200

def run_health_server():
    port = int(os.getenv("PORT", "10000"))
    health_app.run(host="0.0.0.0", port=port, use_reloader=False)

import asyncio

if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is missing.")

    # Fix for Python 3.14 - event loop banana padega
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    Thread(target=run_health_server, daemon=True).start()
    
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CallbackQueryHandler(check_join, pattern="^check_join$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_link))
    application.add_error_handler(error_handler)
    
    logger.info("Starting Telegram bot polling...")
    application.run_polling()
