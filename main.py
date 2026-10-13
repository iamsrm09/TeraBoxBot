import os, re, requests, telebot
from telebot import types

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = "@Film4You_Official"
CHANNEL_LINK = "https://t.me/Film4You_Official"

bot = telebot.TeleBot(BOT_TOKEN)

FREE_APIS = [
    "https://terabox-dl.hydraax.workers.dev/api?url={}",
    "https://terabox-api-eta.vercel.app/api?url={}"
]

def get_direct_link(tera_url):
    for api_template in FREE_APIS:
        try:
            r = requests.get(api_template.format(tera_url), timeout=30).json()
            link = r.get("direct_link") or r.get("download_link") or r.get("url") or r.get("link")
            if link:
                return r
        except:
            continue
    return None

def is_joined(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return True

def parse_size_to_mb(size_str):
    try:
        size_str = size_str.lower()
        if "gb" in size_str:
            num = float(re.findall(r"[\d\.]+", size_str)[0])
            return num * 1024
        if "mb" in size_str:
            return float(re.findall(r"[\d\.]+", size_str)[0])
        return 0
    except:
        return 0

@bot.message_handler(commands=['start'])
def start(m):
    if not is_joined(m.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Join Film4You Official", url=CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("✅ I Joined", callback_data="check_join"))
        bot.send_message(m.chat.id, "⚠️ **Access Locked**\n\nJoin @Film4You_Official to continue.", reply_markup=markup, parse_mode="Markdown")
        return
    bot.send_message(m.chat.id, "📦 **AllTeraBoxBot PRO**\n\nSend me any TeraBox link.", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    if call.data == "check_join":
        if is_joined(call.from_user.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Please join @Film4You_Official first!", show_alert=True)

@bot.message_handler(func=lambda m: True)
def handle(m):
    if not is_joined(m.from_user.id):
        start(m)
        return
    match = re.search(r'https?://[^\s]+', m.text)
    if not match: return
    tera_link = match.group(0)
    if "tera" not in tera_link.lower(): return

    wait = bot.send_message(m.chat.id, "⏳ **Processing...**")
    data = get_direct_link(tera_link)

    if not data:
        bot.edit_message_text("❌ Failed to fetch link.", m.chat.id, wait.message_id)
        return

    title = data.get("title", "TeraBox File")
    size_str = data.get("size", "Unknown")
    thumb = data.get("thumbnail") or data.get("thumb")
    direct = data.get("direct_link") or data.get("download_link") or data.get("url")
    size_mb = parse_size_to_mb(size_str)

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("▶️ Watch Online", url=direct),
        types.InlineKeyboardButton("⬇️ Fast Download", url=direct)
    )
    markup.add(types.InlineKeyboardButton("📢 Join Film4You", url=CHANNEL_LINK))

    caption = f"🎬 **{title}**\n\n📁 **Size:** {size_str}\n\n👇 **Select Option**"

    # If < 450MB -> send file
    if size_mb > 0 and size_mb < 450:
        try:
            bot.edit_message_text(f"{caption}\n\n⏳ Uploading...", m.chat.id, wait.message_id, parse_mode="Markdown")
            r = requests.get(direct, stream=True, timeout=180)
            file_name = f"{title[:50]}.mp4"
            with open(file_name, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk: f.write(chunk)
            with open(file_name, 'rb') as f:
                bot.send_document(m.chat.id, f, caption=caption, parse_mode="Markdown", reply_markup=markup, visible_file_name=file_name)
            os.remove(file_name)
            bot.delete_message(m.chat.id, wait.message_id)
            return
        except:
            pass

    # > 450MB -> only buttons + size
    try:
        if thumb:
            bot.send_photo(m.chat.id, thumb, caption=caption, reply_markup=markup, parse_mode="Markdown")
            bot.delete_message(m.chat.id, wait.message_id)
        else:
            bot.edit_message_text(caption, m.chat.id, wait.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.edit_message_text(caption, m.chat.id, wait.message_id, reply_markup=markup, parse_mode="Markdown")

print("Bot Started Clean - @Film4You_Official")
bot.infinity_polling()
