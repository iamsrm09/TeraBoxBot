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
        types.InlineKeyboardButton("📥 How to Use", callback_data="help"),
        types.InlineKeyboardButton("ℹ️ About", callback_data="about"),
    )
    kb.add(
        types.InlineKeyboardButton("📢 Updates Channel", url=CHANNEL_LINK),
        types.InlineKeyboardButton("💬 Contact Us", url=f"https://t.me/{CONTACT_USERNAME}"),
    )
    return kb

def join_menu():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
    kb.add(types.InlineKeyboardButton("✅ Check Joined", callback_data="check_join"))
    return kb

# ==========================================
# CHANNEL MEMBERSHIP
# ==========================================
def is_joined(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as exc:
        log.warning("Membership check failed: %s", type(exc).__name__)
        return False

def require_join(message):
    if is_joined(message.from_user.id):
        return True
    bot.send_message(
        message.chat.id,
        "🔒 <b>Join our updates channel first!</b>\n\nJoin the channel, then tap Check Joined.",
        reply_markup=join_menu(),
    )
    return False

# ==========================================
# LINK VALIDATION
# ==========================================
ALLOWED_DOMAINS = ("terabox.com", "terabox.app", "terasharelink.com", "1024tera.com", "teraboxshare.com")

def extract_link(text):
    if not text:
        return None
    match = re.search(r"https?://[^\s<>]+", text)
    if not match:
        return None
    url = match.group(0).rstrip(".,!?)]}")
    host = (urlparse(url).hostname or "").lower()
    valid = any(host == domain or host.endswith("." + domain) for domain in ALLOWED_DOMAINS)
    return url if valid else None

# ==========================================
# DIRECT LINK FETCHING - FIXED VERSION
# ==========================================
API_ENDPOINTS = (
    "https://terabox-dl.hnn.workers.dev/api",
    "https://wdzone-terabox-api.vercel.app/api",
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
        data.get("direct_link") or data.get("download_link") or data.get("dlink")
        or data.get("downloadUrl") or data.get("download_url") or data.get("link")
    )
    if not direct and isinstance(data.get("files"), list) and data["files"]:
        direct = data["files"][0].get("download_link") or data["files"][0].get("url") or data["files"][0].get("dlink")
    if not direct and isinstance(data.get("list"), list) and data["list"]:
        direct = data["list"][0].get("dlink") or data["list"][0].get("download_link")

    if isinstance(direct, str) and direct.startswith("http"):
        return {
            "title": str(data.get("title") or data.get("filename") or data.get("server_filename") or "TeraBox File")[:200],
            "direct": direct,
            "size": str(data.get("size") or "Unknown"),
        }
    for key in ("data", "result", "file", "info", "response"):
        if isinstance(data.get(key), (dict, list)):
            result = parse_result(data[key])
            if result:
                return result
    return None

def get_link(url):
    # 1. Try Public APIs
    for endpoint in API_ENDPOINTS:
        try:
            # GET try
            r = session.get(endpoint, params={"url": url}, timeout=15)
            if r.status_code == 200:
                try:
                    result = parse_result(r.json())
                    if result:
                        log.info("Got result from %s", urlparse(endpoint).hostname)
                        return result
                except: pass
            # POST try
            r = session.post(endpoint, json={"url": url}, timeout=15)
            if r.status_code == 200:
                try:
                    result = parse_result(r.json())
                    if result:
                        log.info("Got result from %s POST", urlparse(endpoint).hostname)
                        return result
                except: pass
        except Exception as e:
            log.warning("API %s failed: %s", urlparse(endpoint).hostname, type(e).__name__)

    # 2. Cookie fallback - FIXED for errno 105
    if RAW_COOKIE:
        try:
            m = re.search(r"/s/([A-Za-z0-9_-]+)", url) or re.search(r"[?&]surl=([A-Za-z0-9_-]+)", url)
            if not m:
                log.warning("Could not extract share ID")
                return None
            share_id = m.group(1)
            log.info("Cookie fallback share_id: %s", share_id)

            cookie_val = RAW_COOKIE
            if "ndus=" not in cookie_val.lower():
                cookie_val = f"ndus={cookie_val}"
            if "lang=" not in cookie_val.lower():
                cookie_val += "; lang=en"

            # FIXED PARAMS to avoid 105
            resp = session.get(
                "https://www.terabox.com/share/list",
                params={
                    "app_id": "250528",
                    "shorturl": share_id,
                    "root": "1",
                    "dir": "/",
                    "order": "time",
                    "desc": "1",
                    "web": "1",
                    "channel": "dubox",
                    "clienttype": "0",
                },
                headers={"Cookie": cookie_val, "Referer": "https://www.terabox.com/"},
                timeout=15,
            )
            log.info("Cookie status %s", resp.status_code)
            data = resp.json()
            log.info("Cookie errno %s", data.get("errno"))

            if data.get("errno") == 105:
                log.warning("NDUS invalid/expired - need fresh NDUS")
                return None
            if data.get("errno")!= 0:
                log.warning("Terabox error %s %s", data.get("errno"), data.get("errmsg"))
                return None

            files = data.get("list") or []
            if files and isinstance(files[0], dict):
                item = files[0]
                dlink = item.get("dlink")
                if dlink:
                    return {
                        "title": str(item.get("server_filename") or "TeraBox File"),
                        "direct": dlink,
                        "size": str(item.get("size") or "Unknown"),
                    }
        except Exception as exc:
            log.warning("Cookie fallback failed: %s", type(exc).__name__)
    return None

# ==========================================
# HANDLERS
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
        "👋 <b>Welcome to TeraBox Link Bot!</b>\n\n📦 Send a supported public TeraBox share link.\n\n⚡ I'll try to fetch the available file information.\n\n⚠️ Results depend on link permissions and external service availability.\n\n👇 Choose an option below:",
        reply_markup=main_menu(),
    )

@bot.message_handler(commands=["help"])
def help_command(message):
    bot.send_message(
        message.chat.id,
        "📥 <b>HOW TO USE</b>\n\n1. Copy a TeraBox share link.\n2. Send it to this bot.\n3. Wait while the link is checked.\n4. If fetching succeeds, use the provided button.\n\n❌ If fetching fails, the link may be unsupported, expired, protected, or the external APIs may be down.",
        reply_markup=main_menu(),
    )

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    if call.data == "check_join":
        if is_joined(call.from_user.id):
            bot.answer_callback_query(call.id, "✅ Membership verified!")
            try:
                bot.edit_message_text("✅ <b>You're all set!</b>\n\nSend a supported TeraBox link now.", call.message.chat.id, call.message.message_id, reply_markup=main_menu())
            except Exception:
                bot.send_message(call.message.chat.id, "✅ Send a supported TeraBox link now.", reply_markup=main_menu())
        else:
            bot.answer_callback_query(call.id, "❌ Please join the channel first.", show_alert=True)
    elif call.data == "help":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "📥 <b>How to use</b>\n\nSend a supported public TeraBox share link. Fetching is not guaranteed for every link.", reply_markup=main_menu())
    elif call.data == "about":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, f"ℹ️ <b>ABOUT THIS BOT</b>\n\nA Telegram helper for supported TeraBox links.\n\n💬 Contact: @{html.escape(CONTACT_USERNAME)}", reply_markup=main_menu())
    else:
        bot.answer_callback_query(call.id)

@bot.message_handler(content_types=["text"])
def handle_message(message):
    text = message.text or ""
    if text.startswith("/"):
        return
    url = extract_link(text)
    if not url:
        bot.send_message(message.chat.id, "🔗 Please send a supported TeraBox share link.\n\nUse /help for instructions.")
        return
    if not require_join(message):
        return
    status = bot.send_message(message.chat.id, "⏳ <b>Processing your link...</b>\nPlease wait.")
    try:
        result = get_link(url)
        if not result:
            bot.edit_message_text(
                "❌ <b>Failed to fetch this link.</b>\n\nPossible reasons:\n• Link expired or unsupported\n• File requires permission\n• External APIs down\n• NDUS cookie expired (check logs for errno 105)\n\nGet fresh NDUS from terabox.com > F12 > Application > Cookies > ndus",
                message.chat.id, status.message_id, reply_markup=main_menu(),
            )
            return
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("▶️ Open / Download", url=result["direct"]))
        kb.add(types.InlineKeyboardButton("📢 Updates Channel", url=CHANNEL_LINK))
        title = html.escape(result["title"])
        size = html.escape(result["size"])
        bot.edit_message_text(
            f"✅ <b>LINK PROCESSED</b>\n\n📄 <b>File:</b> {title}\n📦 <b>Size:</b> {size}\n\nUse the button below if you have permission to access the file.",
            message.chat.id, status.message_id, reply_markup=kb, disable_web_page_preview=True,
        )
    except Exception as exc:
        log.exception("Link processing failed: %s", type(exc).__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    if WEBHOOK_SECRET:
        supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if supplied!= WEBHOOK_SECRET:
            return "Forbidden", 403
    try:
        update = telebot.types.Update.de_json(request.get_data(as_text=True))
        bot.process_new_updates([update])
        return "ok", 200
    except Exception as exc:
        log.exception("Webhook processing failed: %s", type(exc).__name__)
        return "error", 500

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
