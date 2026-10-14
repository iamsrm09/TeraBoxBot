import os, re, requests, telebot
from telebot import types
from flask import Flask
import threading

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot is Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_flask).start()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@Film4You_Official"
CHANNEL_LINK = "https://t.me/Film4You_Official"
BOT_SHARE_LINK = "https://t.me/AllTeraBoxBot?start=share"

bot = telebot.TeleBot(BOT_TOKEN)

APIS = [
    "https://terabox-dl.hydraax.workers.dev/api?url={}",
    "https://terabox.hnn.workers.dev/api?url={}",
    "https://terabox-api.sirath.workers.dev/api?url={}"
]

def get_direct_link(tera_url):
    for api in APIS:
        try:
            r = requests.get(api.format(tera_url), timeout=20).json()
            link = r.get("direct_link") or r.get("download_link") or r.get("url") or r.get("link") or r.get("dlink")
            if link:
                return {
                    "title": r.get("title") or r.get("file_name") or "TeraBox File",
                    "size": r.get("size") or r.get("file_size") or "Unknown",
                    "thumb": r.get("thumbnail") or r.get("thumb"),
                    "direct": link
                }
        except:
            continue
    return None

def is_joined(user_id):
    try:
        m = bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in ['member','administrator','creator']
    except:
        return True

def parse_mb(size_str):
    try:
        s = str(size_str).lower()
        num = float(re.findall(r"[\d\.]+", s)[0])
        if "gb" in s: return num * 1024
        if "mb" in s: return num
        if "kb" in s: return num/1024
        return 0
    except:
        return 0

def welcome_btn():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📩 How to Use", callback_data="how_to"),
        types.InlineKeyboardButton("📢 Film4You Channel", url=CHANNEL_LINK)
    )
    markup.add(types.InlineKeyboardButton("🔗 Share Bot", url=BOT_SHARE_LINK))
    return markup

def main_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("📩 How to Use"), types.KeyboardButton("📢 Film4You Channel"))
    markup.add(types.KeyboardButton("🔗 Share Bot"), types.KeyboardButton("📞 Contact"))
    return markup

@bot.message_handler(commands=['start'])
def start(m):
    if not is_joined(m.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Join Film4You Official", url=CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("✅ I Joined", callback_data="check_join"))
        bot.send_message(m.chat.id, "⚠️ **Access Locked**\n\nPlease join @Film4You_Official to continue using the bot.", reply_markup=markup, parse_mode="Markdown")
        return
    txt = "📦 **Welcome to AllTeraBoxBot - Pro**\n\n🚀 **Fastest TeraBox Downloader**\nJust send me any TeraBox link.\n\n✨ **No Ads | No Waiting | Direct File**"
    bot.send_message(m.chat.id, txt, reply_markup=main_menu_keyboard(), parse_mode="Markdown")
    bot.send_message(m.chat.id, "👇 **Select an option:**", reply_markup=welcome_btn(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    if c.data == "check_join":
        if is_joined(c.from_user.id):
            bot.delete_message(c.message.chat.id, c.message.message_id)
            start(c.message)
        else:
            bot.answer_callback_query(c.id, "❌ Please join the channel first!", show_alert=True)
    if c.data == "how_to":
        bot.send_message(c.message.chat.id, "📩 **How to Use**\n\n1. Copy TeraBox link\n2. Send it here\n3. Get direct file / download link\n\nExample: `https://terasharelink.com/s/...`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📩 How to Use")
def howto_btn(m):
    bot.send_message(m.chat.id, "📩 **How to Use**\n\n1. Copy TeraBox link\n2. Send it here\n3. Get direct download link", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📢 Film4You Channel")
def channel_btn(m):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
    bot.send_message(m.chat.id, "📢 **Official Channel**", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🔗 Share Bot")
def share_btn(m):
    bot.send_message(m.chat.id, f"🔗 **Share this bot:**\n{BOT_SHARE_LINK}")

@bot.message_handler(func=lambda m: m.text == "📞 Contact")
def contact_btn(m):
    bot.send_message(m.chat.id, "📞 **Contact:** @Film4You_Official")

@bot.message_handler(func=lambda m: True)
def handle(m):
    if m.text in ["📩 How to Use", "📢 Film4You Channel", "🔗 Share Bot", "📞 Contact", "/start", "/help"]:
        return
    if not is_joined(m.from_user.id):
        start(m); return
    match = re.search(r'https?://[^\s]+', m.text)
    if not match: return
    url = match.group(0)
    if "tera" not in url.lower(): return
    wait = bot.send_message(m.chat.id, "⏳ **Processing...**")
    data = get_direct_link(url)
    if not data:
        bot.edit_message_text("❌ **Failed to fetch link.**\nPlease try again after 10 seconds.", m.chat.id, wait.message_id, parse_mode="Markdown")
        return
    title = data["title"]
    size_str = data["size"]
    thumb = data["thumb"]
    direct = data["direct"]
    mb = parse_mb(size_str)
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("▶️ Watch Online", url=direct), types.InlineKeyboardButton("⬇️ Fast Download", url=direct))
    markup.add(types.InlineKeyboardButton("📢 Film4You Channel", url=CHANNEL_LINK))
    caption = f"🎬 **{title}**\n\n📁 **Size:** {size_str}"
    if mb > 0 and mb < 500:
        try:
            bot.edit_message_text(f"{caption}\n\n⏳ **Uploading file...**", m.chat.id, wait.message_id, parse_mode="Markdown")
            r = requests.get(direct, stream=True, timeout=200)
            fname = f"{title[:30]}.mp4".replace("/","")
            with open(fname, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk: f.write(chunk)
            with open(fname, 'rb') as f:
                bot.send_document(m.chat.id, f, caption=caption, reply_markup=markup, parse_mode="Markdown", visible_file_name=fname)
            os.remove(fname)
            bot.delete_message(m.chat.id, wait.message_id)
            return
        except Exception as e:
            print(e)
    try:
        if thumb:
            bot.send_photo(m.chat.id, thumb, caption=caption, reply_markup=markup, parse_mode="Markdown")
            bot.delete_message(m.chat.id, wait.message_id)
        else:
            bot.edit_message_text(caption, m.chat.id, wait.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.edit_message_text(caption, m.chat.id, wait.message_id, reply_markup=markup, parse_mode="Markdown")

print("Bot Started - English Version")
bot.infinity_polling()
