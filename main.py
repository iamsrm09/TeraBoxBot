import os, requests, re
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

FREE_APIS = [
    "https://terabox-dl.hydraax.workers.dev/api?url={}",
    "https://terabox-api-eta.vercel.app/api?url={}"
]

def get_direct_link(tera_url):
    for api_template in FREE_APIS:
        try:
            r = requests.get(api_template.format(tera_url), timeout=20).json()
            link = r.get("direct_link") or r.get("download_link") or r.get("url")
            if link:
                return r
        except:
            continue
    return None

@bot.message_handler(commands=['start'])
def start_msg(m):
    bot.reply_to(m, "📦 *Welcome to AllTeraBoxBot*\n\nSend any TeraBox link and I'll give you direct link instantly.", parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle_all(m):
    text = m.text
    match = re.search(r'https?://[^\s]+', text)
    if not match: return
    tera_link = match.group(0)
    if "tera" not in tera_link.lower(): return
    
    wait = bot.reply_to(m, "⏳ Processing...")
    data = get_direct_link(tera_link)
    if not data:
        bot.edit_message_text("❌ Failed. API busy, try after 2 mins.", wait.chat.id, wait.message_id)
        return
    direct = data.get("direct_link") or data.get("download_link") or data.get("url")
    title = data.get("title", "Your File")
    bot.edit_message_text(f"✅ *{title}*\n\nDirect Link:", wait.chat.id, wait.message_id, parse_mode="Markdown")
    bot.send_message(m.chat.id, direct)

print("Bot Started...")
bot.infinity_polling()
