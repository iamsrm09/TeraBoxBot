import os
import re
import html
import time
import logging
from urllib.parse import urlparse
import requests
import telebot
from telebot import types
from flask import Flask, request

# ==========================================
# CONFIGURATION
# ==========================================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
RENDER_URL = os.getenv("RENDER_URL", "").strip().rstrip("/")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@Film4You_Official").strip()
CHANNEL_LINK = os.getenv(
    "CHANNEL_LINK", "https://t.me/Film4You_Official"
).strip()
CONTACT_USERNAME = os.getenv(
    "CONTACT_USERNAME", "iamsrm0"
).strip().lstrip("@")

# Supports all three existing cookie variable names
RAW_COOKIE = (
    os.getenv("NDUS_COOKIE") or os.getenv("NDUS") or os.getenv("COOKIE") or ""
).strip()

PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing.")
if not RENDER_URL:
    raise RuntimeError("Set RENDER_URL to your public Render URL.")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("terabox_bot")

app = Flask(__name__)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
})

# ==========================================
# MENUS
# ==========================================
def main_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(
            "📥 How to Use", callback_data="help"
        ),
        types.InlineKeyboardButton("ℹ️ About", callback_data="about"),
    )
    kb.add(
        types.InlineKeyboardButton("📢 Updates Channel", url=CHANNEL_LINK),
        types.InlineKeyboardButton(
            "💬 Contact Us", url=f"https://t.me/{CONTACT_USERNAME}"
        ),
    )
    return kb

def join_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK)
    )
    kb.add(
        types.InlineKeyboardButton(
            "✅ Check Joined", callback_data="check_join"
        )
    )
    return kb

# ==========================================
# CHANNEL MEMBERSHIP
# ==========================================
def is_joined(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in (
            "member",
            "administrator",
            "creator",
        )
    except Exception as exc:
        log.warning("Membership check failed: %s", type(exc).__name__)
        return False

def require_join(message):
    if is_joined(message.from_user.id):
        return True
    bot.send_message(
        message.chat.id,
        "🔒 <b>Join our updates channel first!</b>\n\n"
        "Join the channel, then tap Check Joined.",
        reply_markup=join_menu(),
    )
    return False

# ==========================================
# LINK VALIDATION
# ==========================================
ALLOWED_DOMAINS = (
    "terabox.com",
    "terabox.app",
    "terasharelink.com",
    "1024tera.com",
    "teraboxshare.com",
)

def extract_link(text):
    if not text:
        return None
    match = re.search(r"https?://[^\s<>]+", text)
    if not match:
        return None
    url = match.group(0).rstrip(".,!?)]}")
    host = (urlparse(url).hostname or "").lower()
    valid = any(
        host == domain or host.endswith("." + domain)
        for domain in ALLOWED_DOMAINS
    )
    return url if valid else None

# ==========================================
# DIRECT LINK FETCHING - FIXED
# ==========================================
API_ENDPOINTS = (
    "https://terabox-dl.hnn.workers.dev/api",
    "https://wdzone-terabox-api.vercel.app/api",
    "https://teraboxdl.site/api",
    "https://terabox.hnn.workers.dev/api",
)

def parse_result(data):
    if isinstance(data, list):
        for item in data:
            result = parse_result(item)
            if result:
                return result
        return None
    if not isinstance(data, dict):
        return None
    direct = (
        data.get("direct_link")
        or data.get("download_link")
        or data.get("dlink")
        or data.get("downloadUrl")
        or data.get("download_url")
        or data.get("link")
        or data.get("url")
    )
    # For APIs returning files array
    if not direct and isinstance(data.get("files"), list) and data["files"]:
        direct = data["files"][0].get("download_link") or data["files"][0].get("url") or data["files"][0].get("dlink")
    if not direct and isinstance(data.get("list"), list) and data["list"]:
        direct = data["list"][0].get("dlink") or data["list"][0].get("download_link")

    if isinstance(direct, str) and direct.startswith("http"):
        return {
            "title": str(
                data.get("title")
                or data.get("filename")
                or data.get("server_filename")
                or data.get("file_name")
                or "TeraBox File"
            )[:200],
            "direct": direct,
            "size": str(data.get("size") or data.get("file_size") or "Unknown"),
        }
    # Handle APIs that wrap results in nested objects
    for key in ("data", "result", "file", "info", "response"):
        if isinstance(data.get(key), (dict, list)):
            result = parse_result(data[key])
            if result:
                return result
    return None

def get_link(url):
    # FIX 1: Try all public APIs with both GET and POST
    for endpoint in API_ENDPOINTS:
        try:
            # Try GET
            response = session.get(
                endpoint, params={"url": url}, timeout=18
            )
            if response.status_code == 200:
                try:
                    data = response.json()
                    result = parse_result(data)
                    if result:
                        log.info("Result received from %s (GET)", urlparse(endpoint).hostname)
                        return result
                except: pass

            # Try POST fallback for same endpoint
            response = session.post(
                endpoint, json={"url": url}, timeout=18
            )
            if response.status_code == 200:
                try:
                    data = response.json()
                    result = parse_result(data)
                    if result:
                        log.info("Result received from %s (POST)", urlparse(endpoint).hostname)
                        return result
                except: pass

        except requests.Timeout:
            log.warning("API timeout: %s", urlparse(endpoint).hostname)
        except requests.RequestException as exc:
            log.warning("API request failed: %s", type(exc).__name__)

    # FIX 2: Cookie fallback - FIXED FOR terasharelink long IDs
    if RAW_COOKIE:
        try:
            # Support both /s/ID and?surl=ID - FIXED REGEX for long IDs like 1SJTgxJ_rtQMDojbrJdg3dg
            match = (
                re.search(r"/s/([A-Za-z0-9_-]+)", url)
                or re.search(r"[?&]surl=([A-Za-z0-9_-]+)", url)
            )
            if not match:
                log.warning("Could not extract share ID from %s", url)
                return None
            share_id = match.group(1)
            log.info("Trying cookie fallback with share_id: %s", share_id)

            cookie_header = RAW_COOKIE
            if "ndus=" not in cookie_header.lower():
                cookie_header = f"ndus={cookie_header}"
            # Add lang cookie if not present
            if "lang=" not in cookie_header.lower():
                cookie_header += "; lang=en"

            response = session.get(
                "https://www.terabox.com/share/list",
                params={
                    "app_id": "250528",
                    "shorturl": share_id,
                    "root": "1",
                    "dir": "/",
                },
                headers={
                    "Cookie": cookie_header,
                    "Referer": "https://www.terabox.com/",
                },
                timeout=15,
            )
            log.info("Cookie fallback status: %s", response.status_code)
            if response.status_code!= 200:
                log.warning("Cookie fallback HTTP %s", response.status_code)
                return None
            data = response.json()
            log.info("Cookie resp errno: %s", data.get("errno"))
            if data.get("errno") == 2:
                log.warning("NDUS EXPIRED - Need fresh ndus")
                return None

            files = data.get("list") or []
            if files and isinstance(files[0], dict):
                item = files[0]
                direct = item.get("dlink")
                if direct:
                    return {
                        "title": str(
                            item.get("server_filename") or "TeraBox File"
                        ),
                        "direct": direct,
                        "size": str(item.get("size") or "Unknown"),
                    }
            log.warning("Cookie fallback returned no downloadable file. Data: %s", str(data)[:500])
        except Exception as exc:
            log.warning("Cookie fallback failed: %s - %s", type(exc).__name__, str(exc)[:200])
    else:
        log.warning("No RAW_COOKIE set, skipping cookie fallback")
    return None

# ==========================================
# START / HELP COMMANDS
# ==========================================
@app.route("/", methods=["GET", "HEAD"])
def home():
    return "TeraBox Bot is running!", 200

@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200

@bot.message_handler(commands=["start"])
def start(message):
    if not require_join(message):
        return
    bot.send_message(
        message.chat.id,
        "👋 <b>Welcome to TeraBox Link Bot!</b>\n\n"
        "📦 Send a supported public TeraBox share link.\n\n"
        "⚡ I'll try to fetch the available file information.\n\n"
        "⚠️ Results depend on link permissions and "
        "external service availability.\n\n"
        "👇 Choose an option below:",
        reply_markup=main_menu(),
    )

@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "📥 <b>HOW TO USE</b>\n\n"
        "1. Copy a TeraBox share link.\n"
        "2. Send it to this bot.\n"
        "3. Wait while the link is checked.\n"
        "4. If fetching succeeds, use the provided button.\n\n"
        "❌ If fetching fails, the link may be unsupported, "
        "expired, protected, or the external APIs may be down.",
        reply_markup=main_menu(),
    )

# ==========================================
# BUTTON CALLBACKS
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    if call.data == "check_join":
        if is_joined(call.from_user.id):
            bot.answer_callback_query(
                call.id, "✅ Membership verified!"
            )
            try:
                bot.edit_message_text(
                    "✅ <b>You're all set!</b>\n\n"
                    "Send a supported TeraBox link now.",
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=main_menu(),
                )
            except Exception:
                bot.send_message(
                    call.message.chat.id,
                    "✅ Send a supported TeraBox link now.",
                    reply_markup=main_menu(),
                )
        else:
            bot.answer_callback_query(
                call.id, "❌ Please join the channel first.", show_alert=True
            )
    elif call.data == "help":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "📥 <b>How to use</b>\n\n"
            "Send a supported public TeraBox share link. "
            "Fetching is not guaranteed for every link.",
            reply_markup=main_menu(),
        )
    elif call.data == "about":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "ℹ️ <b>ABOUT THIS BOT</b>\n\n"
            "A Telegram helper for supported TeraBox links.\n\n"
            f"💬 Contact: @{html.escape(CONTACT_USERNAME)}",
            reply_markup=main_menu(),
        )
    else:
        bot.answer_callback_query(call.id)

# ==========================================
# PROCESS TERA BOX LINKS
# ==========================================
@bot.message_handler(content_types=["text"])
def handle_message(message):
    text = message.text or ""
    if text.startswith("/"):
        return
    url = extract_link(text)
    if not url:
        bot.send_message(
            message.chat.id,
            "🔗 Please send a supported TeraBox share link.\n\n"
            "Use /help for instructions.",
        )
        return
    if not require_join(message):
        return
    status = bot.send_message(
        message.chat.id, "⏳ <b>Processing your link...</b>\n" "Please wait."
    )
    try:
        result = get_link(url)
        if not result:
            bot.edit_message_text(
                "❌ <b>Failed to fetch this link.</b>\n\n"
                "Possible reasons:\n"
                "• Link expired or unsupported\n"
                "• File requires permission or verification\n"
                "• External APIs are unavailable\n"
                "• NDUS cookie expired (check Render logs)\n\n"
                "Please try again later or use another "
                "authorized public link.",
                message.chat.id,
                status.message_id,
                reply_markup=main_menu(),
            )
            return
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton(
                "▶️ Open / Download", url=result["direct"]
            )
        )
        kb.add(
            types.InlineKeyboardButton(
                "📢 Updates Channel", url=CHANNEL_LINK
            )
        )
        title = html.escape(result["title"])
        size = html.escape(result["size"])
        bot.edit_message_text(
            "✅ <b>LINK PROCESSED</b>\n\n"
            f"📄 <b>File:</b> {title}\n"
            f"📦 <b>Size:</b> {size}\n\n"
            "Use the button below if you have permission "
            "to access the file.",
            message.chat.id,
            status.message_id,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
    except Exception as exc:
        log.exception("Link processing failed: %s", type(exc).__name__)
        try:
            bot.edit_message_text(
                "⚠️ <b>Something went wrong.</b>\n\n"
                "Please try again later. Check Render logs "
                "for the technical error.",
                message.chat.id,
                status.message_id,
                reply_markup=main_menu(),
            )
        except Exception:
            pass

# ==========================================
# RENDER WEBHOOK
# ==========================================
@app.route("/webhook", methods=["POST"])
def webhook():
    if WEBHOOK_SECRET:
        supplied = request.headers.get(
            "X-Telegram-Bot-Api-Secret-Token", ""
        )
        if supplied!= WEBHOOK_SECRET:
            return "Forbidden", 403
    try:
        update = telebot.types.Update.de_json(
            request.get_data(as_text=True)
        )
        bot.process_new_updates([update])
        return "ok", 200
    except Exception as exc:
        log.exception(
            "Webhook processing failed: %s", type(exc).__name__
        )
        return "error", 500

# Configure webhook once when the app starts.
def configure_webhook():
    webhook_url = RENDER_URL + "/webhook"
    try:
        info = bot.get_webhook_info()
        if info.url!= webhook_url:
            bot.delete_webhook(drop_pending_updates=False)
            time.sleep(0.5)
            bot.set_webhook(url=webhook_url)
        log.info("Webhook configured successfully: %s", webhook_url)
    except Exception:
        log.exception("Webhook configuration failed.")
        raise

configure_webhook()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
