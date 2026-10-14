import os, re, requests, telebot, time
from telebot import types
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
RAW_COOKIE = os.getenv("NDUS") or os.getenv("COOKIE") or ""
CHANNEL_ID = os.getenv("CHANNEL_ID") or "@Film4You_Official"
CHANNEL_LINK = os.getenv("CHANNEL_LINK") or "https://t.me/Film4You_Official"
RENDER_URL = os.getenv("RENDER_URL") or "https://teraboxbot-261o.onrender.com"
RENDER_URL = RENDER_URL.rstrip('/')

bot = telebot.TeleBot(BOT_TOKEN)

try:
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{RENDER_URL}/webhook")
    print(f"Webhook set: {RENDER_URL}/webhook")
except Exception as e:
    print(e)

# ====== DIRECT LINK LOGIC (Same as that bot) ======
def get_link(url):
    # 1. Try Public APIs (No cookie needed) - Yehi uss bot ka secret hai
    apis = [
        f"https://terabox-dl.hnn.workers.dev/api?url={url}",
        f"https://wdzone-terabox-api.vercel.app/api?url={url}",
        f"https://teraboxdl.site/api?url={url}"
    ]
    headers = {"User-Agent": "Mozilla/5.0"}
    for api in apis:
        try:
            r = requests.get(api, headers=headers, timeout=20).json()
            direct = r.get("direct_link") or r.get("download_link") or r.get("dlink") or r.get("url") or r.get("downloadUrl")
            if direct:
                print(f"Success from API: {api}")
                return {"title": r.get("title") or r.get("filename") or "TeraBox File", "direct": direct, "size": r.get("size") or "Unknown"}
        except Exception as e:
            print(f"API fail {api}: {e}")
            continue

    # 2. Cookie method as backup
    if RAW_COOKIE:
        try:
            m = re.search(r'/s/([A-Za-z0-9_-]+)', url) or re.search(r'surl=([A-Za-z0-9_-]+)', url)
            if not m: return None
            surl = m.group(1)
            cookie_str = RAW_COOKIE if "ndus=" in RAW_COOKIE else f"ndus={RAW_COOKIE}"
            h = {"User-Agent": "Mozilla/5.0", "Cookie": cookie_str, "Referer": "https://www.terabox.com/"}
            api_url = f"https://www.terabox.com/share/list?app_id=250528&shorturl={surl}&root=1"
            j = requests.get(api_url, headers=h, timeout=15).json()
            if j.get("list") and j["list"][0].get("dlink"):
                f = j["list"][0]
                return {"title": f.get("server_filename"), "direct": f.get("dlink"), "size": f.get("size")}
        except Exception as e:
            print(f"Cookie method error: {e}")
    return None

def is_joined(uid):
    try:
        m = bot.get_chat_member(CHANNEL_ID, uid)
        return m.status in ['member','administrator','creator']
    except:
        return False

@app.route('/')
def home():
    return "Bot Live - OK"

@app.route('/webhook', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
    bot.process_new_updates([update])
    return 'ok'

@bot.message_handler(commands=['start'])
def start(m):
    if not is_joined(m.from_user.id):
        mk = types.InlineKeyboardMarkup()
        mk.add(types.InlineKeyboardButton("📢 Join Bots XP", url=CHANNEL_LINK))
        mk.add(types.InlineKeyboardButton("✅ Check Joined", callback_data="chk"))
        bot.send_message(m.chat.id, "To use this bot, please join our updates channel.\n\nAfter joining, tap Check Joined.", reply_markup=mk)
        return
    bot.send_message(m.chat.id, "📦 Send any TeraBox link now...")

@bot.callback_query_handler(func=lambda c: c.data=="chk")
def chk(c):
    if is_joined(c.from_user.id):
        bot.delete_message(c.message.chat.id, c.message.message_id)
        bot.send_message(c.message.chat.id, "✅ Joined! Now send TeraBox link.")
    else:
        bot.answer_callback_query(c.id, "❌ You haven't joined yet!", show_alert=True)

@bot.message_handler(func=lambda m: True)
def handle(m):
    if m.text.startswith("/"): return
    match = re.search(r'https?://[^\s]+', m.text)
    if not match: return
    url = match.group(0)
    if "tera" not in url and "terashare" not in url: return

    if not is_joined(m.from_user.id):
        start(m)
        return

    wait = bot.send_message(m.chat.id, "⏳ Processing... Getting direct link")
    data = get_link(url)
    if not data:
        bot.edit_message_text("❌ Failed to Fetch\n\nTerabox is blocking. Try with another link or wait 30 sec.", m.chat.id, wait.message_id)
        return

    mk = types.InlineKeyboardMarkup()
    mk.add(types.InlineKeyboardButton("▶️ Watch / Download", url=data["direct"]))
    mk.add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
    bot.edit_message_text(f"🎬 <b>{data['title']}</b>\n\n📁 Size: {data['size']}\n\n🚀 <b>Powered by Film4You</b>", m.chat.id, wait.message_id, reply_markup=mk, parse_mode="HTML")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
