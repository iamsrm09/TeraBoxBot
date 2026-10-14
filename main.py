import os, re, requests, telebot, time, threading
from telebot import types
from flask import Flask, request

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
# NDUS kisi bhi naam se chalega
RAW_COOKIE = os.getenv("NDUS") or os.getenv("NDUS_COOKIE") or os.getenv("TERABOX_COOKIE") or ""

# Agar full cookie bheja hai to usme se ndus nikal le
def extract_ndus(cookie_str):
    if not cookie_str: return ""
    m = re.search(r'ndus=([A-Za-z0-9_-]+)', cookie_str)
    if m: return m.group(1)
    # Agar sirf value hai to wahi return
    return cookie_str.strip().split()[0]

NDUS = extract_ndus(RAW_COOKIE)
FULL_COOKIE = RAW_COOKIE if "ndus=" in RAW_COOKIE else f"ndus={NDUS}"

CHANNEL_ID = "@Film4You_Official"
CHANNEL_LINK = "https://t.me/Film4You_Official"
RENDER_URL = os.getenv("RENDER_URL") or os.getenv("WEBHOOK_URL") or "https://teraboxbot-261o.onrender.com"
RENDER_URL = RENDER_URL.rstrip('/')

if not BOT_TOKEN:
    print("BOT_TOKEN Missing!")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)

# Webhook sahi se set karo
try:
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f"{RENDER_URL}/webhook")
    print(f"Webhook set: {RENDER_URL}/webhook")
except Exception as e:
    print(f"Webhook error: {e}")

def get_direct_link_cookie(tera_url):
    if not NDUS:
        print("NDUS Empty")
        return None
    try:
        m = re.search(r'/s/([A-Za-z0-9_-]+)', tera_url)
        if not m:
            m = re.search(r'surl=([A-Za-z0-9_-]+)', tera_url)
        if not m: return None
        surl = m.group(1)

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Cookie": FULL_COOKIE,
            "Referer": "https://www.terabox.com/",
            "Host": "www.terabox.com"
        }
        list_url = f"https://www.terabox.com/share/list?app_id=250528&shorturl={surl}&root=1"
        r = requests.get(list_url, headers=headers, timeout=15)
        print(r.text[:500])
        j = r.json()
        if j.get("errno")!= 0 or not j.get("list"):
            return None
        file_info = j["list"][0]
        dlink = file_info.get("dlink")
        if dlink:
            return {
                "title": file_info.get("server_filename") or "TeraBox File",
                "size": str(file_info.get("size", "Unknown")),
                "direct": dlink
            }
    except Exception as e:
        print(f"Cookie method error: {e}")
    return None

def get_direct_link(tera_url):
    data = get_direct_link_cookie(tera_url)
    if data:
        print("Success with NDUS cookie")
        return data

    # Fallback APIs
    apis = [
        f"https://terabox-dl.hnn.workers.dev/api?url={tera_url}",
        f"https://teraboxdl.site/api?url={tera_url}",
    ]
    for api_url in apis:
        try:
            j = requests.get(api_url, timeout=25).json()
            link = j.get("direct_link") or j.get("download_link") or j.get("dlink") or j.get("url")
            if link:
                return {"title": j.get("title") or "TeraBox File", "size": j.get("size") or "Unknown", "direct": link}
        except: continue
    return None

def is_joined(user_id):
    try:
        m = bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in ['member','administrator','creator']
    except: return True

def pro_file_keyboard(direct_link):
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(types.InlineKeyboardButton("▶️ Watch Online", url=direct_link), types.InlineKeyboardButton("⬇️ Fast Download", url=direct_link))
    mk.add(types.InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
    return mk

@app.route('/')
def home():
    status = "NDUS Set ✅" if NDUS else "NDUS Missing ❌"
    return f"AllTeraBoxBot Pro - Live & {status} | URL: {RENDER_URL}"

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
        bot.process_new_updates([update])
        return 'ok'
    return 'ok'

@bot.message_handler(commands=['start'])
def start_handler(m):
    bot.send_message(m.chat.id, f"<b>📦 Welcome to AllTeraBox Pro</b>\n\nJust send TeraBox link.\n\nStatus: {'✅ NDUS OK' if NDUS else '❌ NDUS Missing'}", parse_mode="HTML")

@bot.message_handler(func=lambda m: True)
def file_handler(m):
    if m.text.startswith("/"): return
    match = re.search(r'https?://[^\s]+', m.text)
    if not match: return
    url = match.group(0)
    if "tera" not in url.lower(): return

    wait_msg = bot.send_message(m.chat.id, "⏳ <b>Processing...</b>", parse_mode="HTML")
    data = get_direct_link(url)
    if not data or not data.get("direct"):
        bot.edit_message_text("❌ <b>Failed to Fetch</b>\n\n1. Check NDUS in Render Env\n2. Link expire to nahi hai?\n3. Try after 30s", m.chat.id, wait_msg.message_id, parse_mode="HTML")
        return

    mk = pro_file_keyboard(data["direct"])
    caption = f"<b>🎬 {data['title']}</b>\n\n<b>📁 Size:</b> {data['size']}"
    try:
        bot.edit_message_text(caption, m.chat.id, wait_msg.message_id, reply_markup=mk, parse_mode="HTML")
    except:
        bot.send_message(m.chat.id, caption, reply_markup=mk, parse_mode="HTML")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
