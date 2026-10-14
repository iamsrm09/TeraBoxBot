import os, re, requests, telebot
from telebot import types
from flask import Flask
import threading

app = Flask(__name__)
@app.route('/')
def home(): return "Bot Running"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
threading.Thread(target=run_flask).start()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TERABOX_COOKIE = os.getenv("TERABOX_COOKIE") # Yaha se cookie lega
CHANNEL_ID = "@Film4You_Official"
CHANNEL_LINK = "https://t.me/Film4You_Official"
BOT_SHARE_LINK = "https://t.me/AllTeraBoxBot?start=share"

bot = telebot.TeleBot(BOT_TOKEN)

# --- NEW 100% WORKING METHOD ---
def get_direct_link(tera_url):
    # Method 1: Try with cookie (Most Powerful)
    if TERABOX_COOKIE:
        try:
            surl = tera_url.split("/s/")[1].split("/")[0].split("?")[0]
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Cookie": f"ndus={TERABOX_COOKIE}",
            }
            # Get file info
            info_url = f"https://www.1024terabox.com/api/shorturl/info?shorturl={surl}&root=1"
            r = requests.get(info_url, headers=headers, timeout=20).json()
            if r.get("list") and len(r["list"]) > 0:
                file = r["list"][0]
                fs_id = file.get("fs_id")
                # Get dlink
                dlink_url = f"https://www.1024terabox.com/share/list?shorturl={surl}&dir=%2F&root=1&fs_id={fs_id}"
                r2 = requests.get(dlink_url, headers=headers, timeout=20).json()
                if r2.get("list") and r2["list"][0].get("dlink"):
                    dlink = r2["list"][0]["dlink"]
                    # Resolve dlink to direct link
                    res = requests.head(dlink, headers=headers, allow_redirects=True, timeout=20)
                    return {
                        "title": file.get("server_filename", "TeraBox File"),
                        "size": str(file.get("size", "Unknown")),
                        "thumb": file.get("thumbs", {}).get("url3", ""),
                        "direct": res.url
                    }
        except Exception as e:
            print(f"Cookie method fail: {e}")

    # Method 2: Fallback Public APIs
    apis = [
        f"https://terabox-dl.hydraax.workers.dev/api?url={tera_url}",
        f"https://terabox.hnn.workers.dev/api?url={tera_url}",
        f"https://terabox-api.sirath.workers.dev/api?url={tera_url}",
    ]
    for api_url in apis:
        try:
            r = requests.get(api_url, timeout=20).json()
            link = r.get("direct_link") or r.get("download_link") or r.get("url")
            if link:
                return {"title": r.get("title","TeraBox File"), "size": r.get("size","Unknown"), "thumb": r.get("thumbnail",""), "direct": link}
        except: continue
    return None

def is_joined(user_id):
    try:
        m = bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in ['member','administrator','creator']
    except: return True

def parse_mb(size_str):
    try:
        s=str(size_str).lower(); num=float(re.findall(r"[\d\.]+",s)[0])
        if "gb" in s: return num*1024
        if "mb" in s: return num
        return 0
    except: return 0

def welcome_btn():
    markup=types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("📩 How to Use",callback_data="how_to"),types.InlineKeyboardButton("📢 Film4You Channel",url=CHANNEL_LINK))
    markup.add(types.InlineKeyboardButton("🔗 Share Bot",url=BOT_SHARE_LINK))
    return markup

def main_menu_keyboard():
    markup=types.ReplyKeyboardMarkup(resize_keyboard=True,row_width=2)
    markup.add(types.KeyboardButton("📩 How to Use"),types.KeyboardButton("📢 Film4You Channel"))
    markup.add(types.KeyboardButton("🔗 Share Bot"),types.KeyboardButton("📞 Contact"))
    return markup

@bot.message_handler(commands=['start'])
def start(m):
    if not is_joined(m.from_user.id):
        markup=types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Join Film4You Official",url=CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("✅ I Joined",callback_data="check_join"))
        bot.send_message(m.chat.id,"⚠️ **Access Locked**\n\nPlease join @Film4You_Official to continue.",reply_markup=markup,parse_mode="Markdown")
        return
    txt="📦 **Welcome to AllTeraBoxBot - Pro**\n\n🚀 **Fastest TeraBox Downloader**\nJust send me any TeraBox link.\n\n✨ **No Ads | No Waiting | Direct File**"
    bot.send_message(m.chat.id,txt,reply_markup=main_menu_keyboard(),parse_mode="Markdown")
    bot.send_message(m.chat.id,"👇 **Select an option:**",reply_markup=welcome_btn(),parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: True)
def cb(c):
    if c.data=="check_join":
        if is_joined(c.from_user.id):
            bot.delete_message(c.message.chat.id,c.message.message_id); start(c.message)
        else: bot.answer_callback_query(c.id,"❌ Please join first!",show_alert=True)
    if c.data=="how_to": bot.send_message(c.message.chat.id,"📩 **How to Use**\n\n1. Copy TeraBox link\n2. Send it here\n3. Get direct file",parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text=="📩 How to Use")
def howto_btn(m): bot.send_message(m.chat.id,"📩 **How to Use**\n\n1. Copy link\n2. Send here\n3. Get file",parse_mode="Markdown")
@bot.message_handler(func=lambda m: m.text=="📢 Film4You Channel")
def channel_btn(m):
    markup=types.InlineKeyboardMarkup(); markup.add(types.InlineKeyboardButton("📢 Join Channel",url=CHANNEL_LINK))
    bot.send_message(m.chat.id,"📢 **Official Channel**",reply_markup=markup)
@bot.message_handler(func=lambda m: m.text=="🔗 Share Bot")
def share_btn(m): bot.send_message(m.chat.id,f"🔗 **Share:**\n{BOT_SHARE_LINK}")
@bot.message_handler(func=lambda m: m.text=="📞 Contact")
def contact_btn(m): bot.send_message(m.chat.id,"📞 **Contact:** @Film4You_Official")

@bot.message_handler(func=lambda m: True)
def handle(m):
    if m.text in ["📩 How to Use","📢 Film4You Channel","🔗 Share Bot","📞 Contact","/start"]: return
    if not is_joined(m.from_user.id): start(m); return
    match=re.search(r'https?://[^\s]+',m.text)
    if not match: return
    url=match.group(0)
    if "tera" not in url.lower(): return
    wait=bot.send_message(m.chat.id,"⏳ **Processing your link...**")
    data=get_direct_link(url)
    if not data or not data.get("direct"):
        bot.edit_message_text("❌ **Failed to fetch link.**\nPlease check if TERABOX_COOKIE is added in Render.",m.chat.id,wait.message_id,parse_mode="Markdown")
        return
    title,size_str,thumb,direct=data["title"],data["size"],data["thumb"],data["direct"]
    mb=parse_mb(size_str)
    markup=types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton("▶️ Watch Online",url=direct),types.InlineKeyboardButton("⬇️ Fast Download",url=direct))
    markup.add(types.InlineKeyboardButton("📢 Film4You Channel",url=CHANNEL_LINK))
    caption=f"🎬 **{title}**\n\n📁 **Size:** {size_str}"
    if mb>0 and mb<500:
        try:
            bot.edit_message_text(f"{caption}\n\n⏳ **Uploading...**",m.chat.id,wait.message_id,parse_mode="Markdown")
            r=requests.get(direct,stream=True,timeout=200)
            fname=f"{title[:30]}.mkv".replace("/","")
            with open(fname,'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk: f.write(chunk)
            with open(fname,'rb') as f: bot.send_document(m.chat.id,f,caption=caption,reply_markup=markup,parse_mode="Markdown",visible_file_name=fname)
            os.remove(fname); bot.delete_message(m.chat.id,wait.message_id); return
        except Exception as e: print(e)
    try:
        if thumb: bot.send_photo(m.chat.id,thumb,caption=caption,reply_markup=markup,parse_mode="Markdown"); bot.delete_message(m.chat.id,wait.message_id)
        else: bot.edit_message_text(caption,m.chat.id,wait.message_id,reply_markup=markup,parse_mode="Markdown")
    except: bot.edit_message_text(caption,m.chat.id,wait.message_id,reply_markup=markup,parse_mode="Markdown")

print("Bot Started - Cookie Version")
bot.infinity_polling()
