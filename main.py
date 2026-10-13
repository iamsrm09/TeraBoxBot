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
    except Exception as e:
        print(f"Join check error: {e}")
        return True # Agar bot admin nahi hai to error na de

@bot.message_handler(commands=['start'])
def start(m):
    if not is_joined(m.from_user.id):
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📢 Join Film4You Official", url=CHANNEL_LINK))
        markup.add(types.InlineKeyboardButton("✅ Joined, Try Again", callback_data="check_join"))
        bot.send_message(m.chat.id, 
            "⚠️ *Access Denied*\n\n"
            "To use @AllTeraBoxBot, you must join our main channel first.\n\n"
            "👇 Join and then click 'Joined' button.",
            reply_markup=markup, parse_mode="Markdown")
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📥 How to Use", callback_data="how"),
        types.InlineKeyboardButton("📢 Film4You Channel", url=CHANNEL_LINK),
        types.InlineKeyboardButton("🔗 Share Bot", switch_inline_query="Best TeraBox Downloader Bot - Fast & Free")
    )
    
    bot.send_message(m.chat.id,
        "📦 *Welcome to AllTeraBoxBot - Pro*\n\n"
        "🚀 *Fastest TeraBox Downloader*\n"
        "Just send me any TeraBox link.\n\n"
        "✨ *No Ads | No Waiting | Direct File*",
        reply_markup=markup, parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: True)
def callbacks(call):
    if call.data == "check_join":
        if is_joined(call.from_user.id):
            bot.delete_message(call.message.chat.id, call.message.message_id)
            start(call.message)
        else:
            bot.answer_callback_query(call.id, "❌ You haven't joined @Film4You_Official yet. Please join first.", show_alert=True)
    
    elif call.data == "how":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,
            "📥 *How to Use:*\n\n"
            "1. Copy TeraBox link\n"
            "2. Send it here\n"
            "3. Get direct link instantly\n\n"
            "Example: `https://terabox.com/s/1abc...`", parse_mode="Markdown")

@bot.message_handler(func=lambda m: True)
def handle(m):
    if not is_joined(m.from_user.id):
        start(m)
        return

    match = re.search(r'https?://[^\s]+', m.text)
    if not match: return
    tera_link = match.group(0)
    if "tera" not in tera_link.lower(): return

    wait = bot.send_message(m.chat.id, "⏳ *Processing your link...* ⏳", parse_mode="Markdown")
    data = get_direct_link(tera_link)
    
    if not data:
        bot.edit_message_text("❌ *Failed to fetch.*\n\nLink is private/expired or API busy. Try again.", m.chat.id, wait.message_id, parse_mode="Markdown")
        return

    title = data.get("title", "Your File")
    size = data.get("size", "Unknown")
    thumb = data.get("thumbnail") or data.get("thumb")
    direct = data.get("direct_link") or data.get("download_link") or data.get("url")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬇️ Direct Download", url=direct))
    markup.add(types.InlineKeyboardButton("📢 Join Film4You", url=CHANNEL_LINK))
    
    caption = f"✅ *File Found!*\n\n📄 *Name:* `{title}`\n📁 *Size:* {size}\n\n🔗 *Ready to download*"
    
    try:
        if thumb:
            bot.send_photo(m.chat.id, thumb, caption=caption, reply_markup=markup, parse_mode="Markdown")
            bot.delete_message(m.chat.id, wait.message_id)
        else:
            bot.edit_message_text(caption, m.chat.id, wait.message_id, reply_markup=markup, parse_mode="Markdown")
        bot.send_message(m.chat.id, f"`{direct}`", parse_mode="Markdown")
    except:
        bot.edit_message_text(f"{caption}\n\n{direct}", m.chat.id, wait.message_id, parse_mode="Markdown", reply_markup=markup)

print("Bot Started with Force Join @Film4You_Official")
bot.infinity_polling()
