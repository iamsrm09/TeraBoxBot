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
        "📦 *AllTeraBoxBot*\n\n"
        "TeraBox / 1024Tera ka link bhejo, main direct download link de dunga.\n\n"
        "Support: terabox.com | teraboxapp.com | 1024terabox.com",
        parse_mode="Markdown"
    )

def get_direct_link(tera_url):
    for api_template in FREE_APIS:
        try:
            url = api_template.format(tera_url)
            r = requests.get(url, timeout=20).json()
            # API ka response alag alag hota hai, common fields check
            link = r.get("direct_link") or r.get("download_link") or r.get("url") or r.get("link")
            if link:
                return r
        except:
            continue
    return None

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "terabox" not in text.lower() and "tera" not in text.lower():
        return
    
    m = re.search(r'https?://[^\s]+', text)
    if not m: return
    tera_link = m.group(0)
    
    wait = await update.message.reply_text("⏳ Fetching... 5 sec")

    data = get_direct_link(tera_link)
    if not data:
        await wait.edit_text("❌ API down hai, 2 min baad try karo. Ya link private to nahi hai?")
        return

    title = data.get("title", "File")
    size = data.get("size", "")
    direct = data.get("direct_link") or data.get("download_link") or data.get("url")

    await wait.edit_text(
        f"✅ *{title}*\n"
        f"📁 Size: {size}\n\n"
        f"🔗 Direct Link niche hai, Telegram pe forward karne ke liye bolna:",
        parse_mode="Markdown"
    )
    await update.message.reply_text(direct)

    # Agar chhota file hai to bot direct bhej bhi dega
    # (Render free me 500MB tak kar deta hai)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("AllTeraBoxBot Started")
    app.run_polling()

if __name__ == "__main__":
    main()
