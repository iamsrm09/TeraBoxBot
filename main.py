import os, requests, re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

FREE_APIS = [
    "https://terabox-dl.hydraax.workers.dev/api?url={}",
    "https://terabox-api-eta.vercel.app/api?url={}",
    "https://teraboxdownloader.com/api?url={}"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 *Welcome to AllTeraBoxBot*\n\n"
        "Just send me any TeraBox link and I'll give you the direct download link instantly.\n\n"
        "Supported:\n"
        "• terabox.com\n"
        "• teraboxapp.com\n"
        "• 1024terabox.com\n\n"
        "Send link now 👇",
        parse_mode="Markdown"
    )

def get_direct_link(tera_url):
    for api_template in FREE_APIS:
        try:
            url = api_template.format(tera_url)
            r = requests.get(url, timeout=20).json()
            link = r.get("direct_link") or r.get("download_link") or r.get("url") or r.get("link")
            if link:
                return r
        except:
            continue
    return None

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    m = re.search(r'https?://[^\s]+', text)
    if not m:
        return
    tera_link = m.group(0)
    
    if "tera" not in tera_link.lower():
        await update.message.reply_text("❌ Please send a valid TeraBox link.")
        return
    
    wait = await update.message.reply_text("⏳ Processing your link... Please wait 5 seconds.")
    data = get_direct_link(tera_link)
    
    if not data:
        await wait.edit_text("❌ Failed to fetch. API is busy or link is private. Try again after 2 mins.")
        return

    title = data.get("title", "Your File")
    size = data.get("size", "Unknown")
    direct = data.get("direct_link") or data.get("download_link") or data.get("url")

    await wait.edit_text(
        f"✅ *{title}*\n"
        f"📁 Size: {size}\n\n"
        f"Your direct download link is ready:",
        parse_mode="Markdown"
    )
    await update.message.reply_text(direct)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("AllTeraBoxBot Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
