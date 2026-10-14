import os, re, requests, telebot, time, threading
from telebot import types
from flask import Flask, request

# ================= CONFIG =================
app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
NDUS_COOKIE = os.getenv("NDUS_COOKIE") or os.getenv("TERABOX_COOKIE") or os.getenv("COOKIE") # <-- naya add kiya
CHANNEL_ID = "@Film4You_Official"
CHANNEL_LINK = "https://t.me/Film4You_Official"
BOT_SHARE_LINK = "https://t.me/AllTeraBoxBot?start=share"
RENDER_URL = "https://teraboxbot-25lo.onrender.com"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

try:
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{RENDER_URL}/webhook")
except:
    pass

# ================= HELPERS =================
def escape(t): return t.replace("<","").replace(">","") if t else ""

def auto_delete(chat_id, msg_ids, delay=2700):
    def job():
        time.sleep(delay)
        for mid in msg_ids:
            try: bot.delete_message(chat_id, mid)
            except: pass
        try: bot.send_message(chat_id, "🗑️ <b>File Expired</b>\n\nThis file was automatically deleted after 45 minutes due to copyright restrictions.", parse_mode="HTML")
        except: pass
    threading.Thread(target=job).start()

def get_direct_link_cookie(tera_url):
    """Naya function - NDUS cookie se direct link"""
    if not NDUS:
        return None
    try:
        # short url nikalna
        m = re.search(r'/s/([A-Za-z0-9_-]+)', tera_url)
        if not m:
            return None
        surl = m.group(1)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Cookie": f"ndus={NDUS}",
            "Referer": "https://www.terabox.com/"
        }

        # 1. Get share list to get fs_id
        list_url = f"https://www.terabox.com/share/list?app_id=250528&shorturl={surl}&root=1"
        r = requests.get(list_url, headers=headers, timeout=15).json()

        if r.get("errno")!= 0 or not r.get("list"):
            return None

        file_info = r["list"][0]
        fs_id = file_info.get("fs_id")
        file_name = file_info.get("server_filename")

        # 2. Get dlink
        dlink_url = f"https://www.terabox.com/share/list?app_id=250528&shorturl={surl}&fs_id={fs_id}&type=dlink"
        # Actually correct endpoint for download is different, using share api
        dl_api = "https://www.terabox.com/api/download?app_id=250528&shorturl=" + surl
        # Try another endpoint
        params = {
            "app_id": "250528",
            "shorturl": surl,
            "fs_id": fs_id
        }
        r2 = requests.get("https://www.terabox.com/share/list", params=params, headers=headers, timeout=15).json()
        # fallback - use dlink from first response if available
        dlink = file_info.get("dlink")
        if not dlink and "dlink" in str(r2):
            dlink = r2.get("dlink") or r2.get("list", [{}])[0].get("dlink")

        if dlink:
            return {
                "title": file_name or "TeraBox File",
                "size": str(file_info.get("size", "Unknown")),
                "thumb": "",
                "direct": dlink
            }
    except Exception as e:
        print(f"Cookie method error: {e}")
    return None

def get_direct_link(tera_url):
    # PEHLE COOKIE METHOD TRY KARO
    data = get_direct_link_cookie(tera_url)
    if data:
        print("Success with NDUS cookie")
        return data

    # FAIL HUA TOH PURANE APIS
    headers = {"User-Agent": "Mozilla/5.0"}
    apis = [
        f"https://terabox-dl.hnn.workers.dev/api?url={tera_url}",
        f"https://teraboxdl.site/api?url={tera_url}",
    ]
    for api_url in apis:
        try:
            j = requests.get(api_url, headers=headers, timeout=25).json()
            link = j.get("direct_link") or j.get("download_link") or j.get("dlink") or j.get("url")
            if link:
                return {"title": j.get("title") or "TeraBox File", "size": j.get("size") or "Unknown", "thumb": j.get("thumb") or "", "direct": link}
        except: continue
    return None

def is_joined(user_id):
    try:
        m = bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in ['member','administrator','creator']
    except: return True

def parse_mb(s):
    try:
        s=str(s).lower(); n=float(re.findall(r"[\d\.]+",s)[0]); return n*1024 if "gb" in s else n
    except: return 0

# ================= KEYBOARDS (same) =================
def pro_welcome_keyboard():
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(types.InlineKeyboardButton("📖 How to Use", callback_data="how_to"), types.InlineKeyboardButton("📢 Official Channel", url=CHANNEL_LINK))
    mk.add(types.InlineKeyboardButton("🔗 Share Bot", url=BOT_SHARE_LINK), types.InlineKeyboardButton("🆘 Support", url=CHANNEL_LINK))
    return mk

def pro_file_keyboard(direct_link):
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(types.InlineKeyboardButton("▶️ Watch Online", url=direct_link), types.InlineKeyboardButton("⬇️ Fast Download", url=direct_link))
    mk.add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
    return mk

def main_menu():
    mk = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add(types.KeyboardButton("📖 How to Use"), types.KeyboardButton("📢 Channel"))
    mk.add(types.KeyboardButton("🔗 Share Bot"), types.KeyboardButton("🆘 Support"))
    return mk

# ================= FLASK =================
@app.route('/')
def home():
    status = "NDUS Set ✅" if NDUS else "NDUS Missing ❌"
    return f"AllTeraBoxBot Pro - Live & Professional - {status}"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
    return 'ok'

# ================= BOT HANDLERS =================
@bot.message_handler(commands=['start'])
def start_handler(m):
    if not is_joined(m.from_user.id):
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton("📢 Join Channel - Unlock Access", url=CHANNEL_LINK))
        mk.add(types.InlineKeyboardButton("✅ I Joined - Continue", callback_data="check_join"))
        bot.send_message(m.chat.id, "<b>⚠️ Access Restricted</b>\n\nTo use this bot, please join our official channel first.", reply_markup=mk, parse_mode="HTML")
        return
    welcome_text = "<b>📦 Welcome to AllTeraBox Pro</b>\n\n<b>🚀 The Fastest & Most Reliable TeraBox Downloader</b>\n\nJust send me any TeraBox link and get instant direct download link."
    bot.send_message(m.chat.id, welcome_text, reply_markup=main_menu(), parse_mode="HTML")
    bot.send_message(m.chat.id, "<b>🔧 Quick Access Menu:</b>", reply_markup=pro_welcome_keyboard(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: True)
def callback_handler(c):
    if c.data == "check_join":
        if is_joined(c.from_user.id):
            try: bot.delete_message(c.message.chat.id, c.message.message_id)
            except: pass
            start_handler(c.message)
        else:
            bot.answer_callback_query(c.id, "❌ You haven't joined yet!", show_alert=True)
    elif c.data == "how_to":
        bot.send_message(c.message.chat.id, "<b>📖 How to Use</b>\n\nCopy link > Paste here > Get link", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text in ["📖 How to Use", "📢 Channel", "🔗 Share Bot", "🆘 Support"])
def menu_handler(m):
    if "Channel" in m.text:
        mk = types.InlineKeyboardMarkup(); mk.add(types.InlineKeyboardButton("📢 Join Film4You Official", url=CHANNEL_LINK))
        bot.send_message(m.chat.id, "<b>📢 Our Official Channel</b>", reply_markup=mk, parse_mode="HTML")

@bot.message_handler(func=lambda m: True)
def file_handler(m):
    if m.text.startswith("/"): return
    if m.text in ["📖 How to Use","📢 Channel","🔗 Share Bot","🆘 Support"]: return
    if not is_joined(m.from_user.id): start_handler(m); return
    match = re.search(r'https?://[^\s]+', m.text)
    if not match: return
    url = match.group(0)
    if "tera" not in url.lower(): return
    wait_msg = bot.send_message(m.chat.id, "⏳ <b>Processing...</b>", parse_mode="HTML")
    data = get_direct_link(url)
    if not data or not data.get("direct"):
        bot.edit_message_text("❌ <b>Failed to Fetch</b>\n\nTry again after 30s or check NDUS in Render Env.", m.chat.id, wait_msg.message_id, parse_mode="HTML")
        return
    title, size_str, thumb, direct = escape(data["title"]), escape(data["size"]), data["thumb"], data["direct"]
    mk = pro_file_keyboard(direct)
    caption = f"<b>🎬 {title}</b>\n\n<b>📁 Size:</b> {size_str}\n\n<b>⏳ Note:</b> <i>Auto-delete after 45 mins</i>\n\n<b>🚀 Powered by AllTeraBox Pro</b>"
    try:
        bot.edit_message_text(caption, m.chat.id, wait_msg.message_id, reply_markup=mk, parse_mode="HTML")
    except:
        bot.send_message(m.chat.id, caption, reply_markup=mk, parse_mode="HTML")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
