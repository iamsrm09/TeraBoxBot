import os, re, requests, telebot, time
from telebot import types
from flask import Flask
import threading

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot Running"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask).start()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@Film4You_Official"
CHANNEL_LINK = "https://t.me/Film4You_Official"
BOT_SHARE_LINK = "https://t.me/AllTeraBoxBot?start=share"

bot = telebot.TeleBot(BOT_TOKEN)
# IMPORTANT FIX FOR 409 ERROR
bot.remove_webhook()
time.sleep(2)

def get_direct_link(tera_url):
    headers = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

    # POST APIs - New
    apis = [
        ("https://teraboxdl.com/api", {"url": tera_url}),
        ("https://teraboxdownloader.online/api/fetch", {"link": tera_url}),
    ]
    for api_url, data in apis:
        try:
            r = requests.post(api_url, json=data, headers=headers, timeout=25)
            # Fix: check if response is json
            try:
                j = r.json()
            except:
                continue
            link = j.get("direct_link") or j.get("dlink") or j.get("downloadLink") or j.get("url") or (j.get("data", {}).get("dlink") if isinstance(j.get("data"), dict) else None)
            if link:
                return {"title": j.get("title") or "TeraBox File", "size": j.get("size") or "Unknown", "thumb": j.get("thumb",""), "direct": link}
        except Exception as e:
            print(f"Fail {api_url}: {e}")
            continue

    # GET APIs - Fallback
    get_apis = [
        f"https://terabox-dl.hydraax.workers.dev/api?url={tera_url}",
        f"https://teraboxdl.site/api?url={tera_url}",
    ]
    for api_url in get_apis:
        try:
            r = requests.get(api_url, timeout=20)
            j = r.json()
            link = j.get("direct_link") or j.get("download_link") or j.get("dlink")
            if link:
                return {"title": j.get("title","TeraBox File"), "size": j.get("size","Unknown"), "thumb": j.get("thumbnail",""), "direct": link}
        except:
            continue
    return None

def is_joined(user_id):
    try:
        m = bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in ['member','administrator','creator']
    except:
        return True

def parse_mb(s):
    try:
        s = str(s).lower()
        n = float(re.findall(r"[\d\.]+", s)[0])
        return n*1024 if "gb" in s else n
    except:
        return 0

def welcome_btn():
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(types.InlineKeyboardButton("📩 How to Use", callback_data="how_to"), types.InlineKeyboardButton("📢 Film4You Channel", url=CHANNEL_LINK))
    mk.add(types.InlineKeyboardButton("🔗 Share Bot", url=BOT_SHARE_LINK))
    return mk

def main_menu_keyboard():
    mk = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add(types.KeyboardButton("📩 How to Use"), types.KeyboardButton("📢 Film4You Channel"))
    mk.add(types.KeyboardButton("🔗 Share Bot"), types.KeyboardButton("📞 Contact"))
    return mk

@bot.message_handler(commands=['start'])
def start(m):
    if not is_joined(m.from_user.id):
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton("📢 Join Film4You Official", url=CHANNEL_LINK))
        mk.add(types.InlineKeyboardButton("✅ I Joined", callback_data="check_join"))
        bot.send_message(m.chat.id, "⚠️ **Access Locked**\n\nPlease join @Film4You_Official to continue.", reply_markup=mk, parse_mode="Markdown")
        return
    bot.send_message(m.chat.id, "📦 **Welcome to AllTeraBoxBot - Pro**\n\n🚀 **Fastest TeraBox Downloader**\nJust send me any TeraBox link.", reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    bot.send_message(m.chat.id, "👇 **Select an option:**", reply_markup=welcome_btn(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    if c.data == "check_join":
        if is_joined(c.from_user.id):
            bot.delete_message(c.message.chat.id, c.message.message_id)
            start(c.message)
        else:
            bot.answer_callback_query(c.id, "❌ Please join first!", show_alert=True)
    if c.data == "how_to":
        bot.send_message(c.message.chat.id, "📩 **How to Use**\n\n1. Copy TeraBox link\n2. Send it here\n3. Get direct file", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text in ["📩 How to Use","📢 Film4You Channel","🔗 Share Bot","📞 Contact"])
def menu_handler(m):
    if m.text == "📩 How to Use":
        bot.send_message(m.chat.id, "📩 1. Copy link\n2. Send here\n3. Get file")
    elif m.text == "📢 Film4You Channel":
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
        bot.send_message(m.chat.id, "📢 **Official Channel**", reply_markup=mk)
    elif m.text == "🔗 Share Bot":
        bot.send_message(m.chat.id, f"🔗 **Share:**\n{BOT_SHARE_LINK}")
    else:
        bot.send_message(m.chat.id, "📞 **Contact:** @Film4You_Official")

@bot.message_handler(func=lambda m: True)
def handle(m):
    if m.text.startswith("/"):
        return
    if not is_joined(m.from_user.id):
        start(m)
        return
    match = re.search(r'https?://[^\s]+', m.text)
    if not match:
        return
    url = match.group(0)
    if "tera" not in url.lower():
        return
    wait = bot.send_message(m.chat.id, "⏳ **Processing...**")
    data = get_direct_link(url)
    if not data or not data.get("direct"):
        bot.edit_message_text("❌ **Failed to fetch. Please try again after 10 seconds.**", m.chat.id, wait.message_id, parse_mode="Markdown")
        return

    title, size_str, thumb, direct = data["title"], data["size"], data["thumb"], data["direct"]
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(types.InlineKeyboardButton("▶️ Watch Online", url=direct), types.InlineKeyboardButton("⬇️ Fast Download", url=direct))
    mk.add(types.InlineKeyboardButton("📢 Film4You Channel", url=CHANNEL_LINK))
    caption = f"🎬 **{title}**\n\n📁 **Size:** {size_str}"

    mb = parse_mb(size_str)
    if 0 < mb < 500:
        try:
            bot.edit_message_text(f"{caption}\n\n⏳ **Uploading...**", m.chat.id, wait.message_id, parse_mode="Markdown")
            r = requests.get(direct, stream=True, timeout=200)
            fname = f"{title[:30]}.mkv".replace("/","")
            with open(fname, 'wb') as f:
                for ch in r.iter_content(1024*1024):
                    if ch: f.write(ch)
            with open(fname, 'rb') as f:
                bot.send_document(m.chat.id, f, caption=caption, reply_markup=mk, parse_mode="Markdown", visible_file_name=fname)
            os.remove(fname)
            bot.delete_message(m.chat.id, wait.message_id)
            return
        except Exception as e:
            print(e)

    try:
        if thumb:
            bot.send_photo(m.chat.id, thumb, caption=caption, reply_markup=mk, parse_mode="Markdown")
            bot.delete_message(m.chat.id, wait.message_id)
        else:
            bot.edit_message_text(caption, m.chat.id, wait.message_id, reply_markup=mk, parse_mode="Markdown")
    except:
        bot.edit_message_text(caption, m.chat.id, wait.message_id, reply_markup=mk, parse_mode="Markdown")

print("Bot Started - No Login Needed - Fixed 409")
bot.infinity_polling(skip_pending=True)
