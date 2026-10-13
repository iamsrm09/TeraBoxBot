import os
import re
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📦 **AllTeraBoxBot** me swagat hai!\n\n"
        "Bas TeraBox ka link bhejo aur main direct file de dunga.\n\n"
        "Example: https://terabox.com/s/xxxxx",
        parse_mode="Markdown"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if "terabox" not in text.lower() and "1024tera" not in text.lower():
        await update.message.reply_text("❌ Ye TeraBox link nahi lag raha. Sahi link bhejo.")
        return
    
    msg = await update.message.reply_text("⏳ Link process ho raha hai...")

    try:
        # Yaha tumhara TeraBox API lagega
        # Abhi ke liye demo reply
        # Tum isko kisi free API se replace kar sakte ho jaise terabox-dl API
        api_url = f"https://terabox-dl-api.vercel.app/api?url={text}"
        res = requests.get(api_url, timeout=30).json()
        
        if res.get("direct_link"):
            await msg.edit_text(f"✅ Ho gaya!\n\nDirect Link: {res['direct_link']}")
        else:
            await msg.edit_text("❌ File nahi mili. Link check karo ya private file hai.")
            
    except Exception as e:
        await msg.edit_text(f"❌ Error: {e}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    print("Bot Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
