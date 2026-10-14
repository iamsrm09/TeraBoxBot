import os, re, requests, telebot, time, threading
from telebot import types
from flask import Flask, request

# ================= CONFIG =================
app = Flask(__name__)
BOT_TOKEN = os.getenv("BOT_TOKEN")
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

def get_direct_link(tera_url):
    headers = {"User-Agent": "Mozilla/5.0"}
    apis = [
        f"https://terabox-dl.hnn.workers.dev/api?url={tera_url}",
        f"https://teraboxdl.site/api?url={tera_url}",
        f"https://teraboxdownloader.pro/api?url={tera_url}",
    ]
    for api_url in apis:
        try:
            j = requests.get(api_url, headers=headers, timeout=25).json()
            link = j.get("direct_link") or j.get("download_link") or j.get("dlink") or j.get("url") or j.get("downloadLink")
            if link:
                return {"title": j.get("title") or j.get("file_name") or "TeraBox File", "size": j.get("size") or j.get("file_size") or "Unknown", "thumb": j.get("thumb") or j.get("thumbnail") or "", "direct": link}
        except: continue
    try:
        j = requests.post("https://teraboxdownloader.online/api/fetch", json={"link": tera_url}, headers={"Content-Type":"application/json","User-Agent":"Mozilla/5.0"}, timeout=25).json()
        link = j.get("direct_link") or j.get("dlink")
        if link: return {"title": j.get("title") or "TeraBox File", "size": j.get("size") or "Unknown", "thumb": j.get("thumb",""), "direct": link}
    except: pass
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

# ================= KEYBOARDS =================
def pro_welcome_keyboard():
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(types.InlineKeyboardButton("📖 How to Use", callback_data="how_to"),
           types.InlineKeyboardButton("📢 Official Channel", url=CHANNEL_LINK))
    mk.add(types.InlineKeyboardButton("🔗 Share Bot", url=BOT_SHARE_LINK),
           types.InlineKeyboardButton("🆘 Support", url=CHANNEL_LINK))
    return mk

def pro_file_keyboard(direct_link):
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(types.InlineKeyboardButton("▶️ Watch Online", url=direct_link),
           types.InlineKeyboardButton("⬇️ Fast Download", url=direct_link))
    mk.add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
    return mk

def main_menu():
    mk = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add(types.KeyboardButton("📖 How to Use"), types.KeyboardButton("📢 Channel"))
    mk.add(types.KeyboardButton("🔗 Share Bot"), types.KeyboardButton("🆘 Support"))
    return mk

# ================= FLASK =================
@app.route('/')
def home(): return "AllTeraBoxBot Pro - Live & Professional"

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
        bot.send_message(m.chat.id,
            "<b>⚠️ Access Restricted</b>\n\n"
            "To use this bot, please join our official channel first.\n\n"
            "<b>Benefits:</b>\n"
            "• Unlimited Downloads\n"
            "• Fastest Servers\n"
            "• 24/7 Support",
            reply_markup=mk, parse_mode="HTML")
        return

    welcome_text = (
        "<b>📦 Welcome to AllTeraBox Pro</b>\n\n"
        "<b>🚀 The Fastest & Most Reliable TeraBox Downloader</b>\n\n"
        "Just send me any TeraBox link and get instant direct download link.\n\n"
        "<b>✨ Features:</b>\n"
        "• ⚡ Super Fast Download\n"
        "• 🎬 Online Streaming Support\n"
        "• 📁 Up to 4K Quality\n"
        "• 🔒 Secure & Private\n\n"
        "<i>👇 Send your TeraBox link now</i>"
    )
    bot.send_message(m.chat.id, welcome_text, reply_markup=main_menu(), parse_mode="HTML")
    bot.send_message(m.chat.id, "<b>🔧 Quick Access Menu:</b>", reply_markup=pro_welcome_keyboard(), parse_mode="HTML")

@bot.callback_query_handler(func=lambda c: True)
def callback_handler(c):
    if c.data == "check_join":
        if is_joined(c.from_user.id):
            try: bot.delete_message(c.message.chat.id, c.message.message_id)
            except: pass
            start_handler(c.message)
        else: bot.answer_callback_query(c.id, "❌ You haven't joined yet! Please join @Film4You_Official", show_alert=True)

    elif c.data == "how_to":
        bot.send_message(c.message.chat.id,
            "<b>📖 How to Use AllTeraBox Pro</b>\n\n"
            "<b>Step 1:</b> Copy any TeraBox link (e.g. terabox.com/s/...)\n"
            "<b>Step 2:</b> Paste it here in chat\n"
            "<b>Step 3:</b> Get instant Download & Streaming links\n\n"
            "<b>💡 Supported Links:</b>\n"
            "• terabox.com / 1024terabox.com\n"
            "• teraboxapp.com / freeterabox.com\n\n"
            "<i>Need help? Contact @Film4You_Official</i>",
            parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text in ["📖 How to Use", "📢 Channel", "🔗 Share Bot", "🆘 Support"])
def menu_handler(m):
    txt = m.text
    if "How to Use" in txt:
        callback_handler(type('obj',(object,),{'data':"how_to", 'message':m, 'from_user':m.from_user, 'id':0})())
    elif "Channel" in txt:
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton("📢 Join Film4You Official", url=CHANNEL_LINK))
        bot.send_message(m.chat.id, "<b>📢 Our Official Channel</b>\n\nJoin for latest movies & updates.", reply_markup=mk, parse_mode="HTML")
    elif "Share" in txt:
        bot.send_message(m.chat.id, f"<b>🔗 Share AllTeraBox Pro</b>\n\n{ BOT_SHARE_LINK}\n\n<i>Share with friends & enjoy unlimited downloads!</i>", parse_mode="HTML")
    else:
        bot.send_message(m.chat.id, "<b>🆘 Support</b>\n\nContact us: @Film4You_Official\nWe reply within 1 hour.", parse_mode="HTML")

@bot.message_handler(func=lambda m: True)
def file_handler(m):
    if m.text.startswith("/"): return
    if m.text in ["📖 How to Use","📢 Channel","🔗 Share Bot","🆘 Support"]: return
    if not is_joined(m.from_user.id): start_handler(m); return

    match = re.search(r'https?://[^\s]+', m.text)
    if not match: return
    url = match.group(0)
    if "tera" not in url.lower(): return

    wait_msg = bot.send_message(m.chat.id, "⏳ <b>Processing your link...</b>\n\n<i>Please wait, fetching file info</i>", parse_mode="HTML")
    data = get_direct_link(url)

    if not data or not data.get("direct"):
        bot.edit_message_text(
            "❌ <b>Failed to Fetch File</b>\n\n"
            "Possible reasons:\n"
            "• Invalid or expired link\n"
            "• Server overloaded - Try again after 30 seconds\n\n"
            "<i>Contact support if issue persists.</i>",
            m.chat.id, wait_msg.message_id, parse_mode="HTML")
        return

    title, size_str, thumb, direct = escape(data["title"]), escape(data["size"]), data["thumb"], data["direct"]
    mk = pro_file_keyboard(direct)
    caption = (
        f"<b>🎬 {title}</b>\n\n"
        f"<b>📁 Size:</b> {size_str}\n"
        f"<b>⚡ Quality:</b> Original\n\n"
        f"<b>⏳ Note:</b> <i>This file will be auto-deleted after 45 minutes due to copyright policy.</i>\n\n"
        f"<b>🚀 Powered by AllTeraBox Pro</b>"
    )

    mb = parse_mb(size_str)
    if 0 < mb < 500:
        try:
            bot.edit_message_text(f"{caption}\n\n⏳ <b>Uploading to Telegram...</b>", m.chat.id, wait_msg.message_id, parse_mode="HTML")
            r = requests.get(direct, stream=True, timeout=200)
            fname = f"{title[:40]}.mkv".replace("/","")
            with open(fname,'wb') as f:
                for ch in r.iter_content(1024*1024):
                    if ch: f.write(ch)
            with open(fname,'rb') as f:
                sent = bot.send_document(m.chat.id, f, caption=caption, reply_markup=mk, parse_mode="HTML", visible_file_name=fname)
            os.remove(fname)
            bot.delete_message(m.chat.id, wait_msg.message_id)
            auto_delete(m.chat.id, [sent.message_id], 2700)
            return
        except Exception as e:
            print(f"Upload error: {e}")

    try:
        if thumb:
            sent = bot.send_photo(m.chat.id, thumb, caption=caption, reply_markup=mk, parse_mode="HTML")
            bot.delete_message(m.chat.id, wait_msg.message_id)
        else:
            sent = bot.edit_message_text(caption, m.chat.id, wait_msg.message_id, reply_markup=mk, parse_mode="HTML")
        auto_delete(m.chat.id, [sent.message_id], 2700)
    except:
        bot.edit_message_text(caption, m.chat.id, wait_msg.message_id, reply_markup=mk, parse_mode="HTML")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
