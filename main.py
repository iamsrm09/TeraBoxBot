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
            r = requests.get(api_template.format(tera_url), timeout=25).json()
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

@bot.message_handler(commands=['start'])
def start(m):
    if not is_joined(m.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Join Film4You Official", url=CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("✅ I Joined, Check Again", callback_data="check_join"))
        bot.send_message(m.chat.id, "⚠️ **Access Locked**\n\nTo use this bot, you must join @Film4You_Official first.", reply_markup=markup, parse_mode="Markdown")
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📥 How To Use", callback_data="how"),
        types.InlineKeyboardButton("📢 Channel", url=CHANNEL_LINK)
    )
    bot.send_message(m.chat.id, "📦 **AllTeraBoxBot - PRO**\n\nSend any TeraBox link and get instant Download + Watch buttons.", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    if call.data == "check_join":
        if is_joined(call.from_user.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ Join @Film4You_Official first!", show_alert=True)
    if call.data == "how":
        bot.send_message(call.message.chat.id, "1. Copy TeraBox link\n2. Paste here\n3. Click Watch or Download", parse_mode="Markdown")

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
        bot.edit_message_text("❌ Link expired/private or API down. Try again.", m.chat.id, wait.message_id)
        return

    title = data.get("title", "TeraBox File")
    size = data.get("size", "Unknown")
    thumb = data.get("thumbnail") or data.get("thumb")
    direct = data.get("direct_link") or data.get("download_link") or data.get("url")

    # PROFESSIONAL 2 BUTTON LAYOUT
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("▶️ Watch Online", url=direct),
        types.InlineKeyboardButton("⬇️ Fast Download", url=direct)
    )
    markup.add(types.InlineKeyboardButton("📢 Join Film4You", url=CHANNEL_LINK))

    caption = f"✅ **File Ready**\n\n📄 **Name:** `{title}`\n📁 **Size:** {size}\n\n👇 **Choose option:**\n▶️ Watch = Online Stream\n⬇️ Download = Save in Gallery"

    try:
        if thumb:
            bot.send_photo(m.chat.id, thumb, caption=caption, reply_markup=markup, parse_mode="Markdown")
            bot.delete_message(m.chat.id, wait.message_id)
            bot.send_message(m.chat.id, f"🔗 **Direct Link:**\n`{direct}`", parse_mode="Markdown")
        else:
            bot.edit_message_text(caption, m.chat.id, wait.message_id, reply_markup=markup, parse_mode="Markdown")
    except:
        bot.edit_message_text(f"{caption}\n\n{direct}", m.chat.id, wait.message_id, reply_markup=markup, parse_mode="Markdown")

print("Bot Started - @Film4You_Official Force Join + Watch/Download")
bot.infinity_polling()
