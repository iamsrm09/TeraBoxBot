from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp
import os
import requests
from PIL import Image

API_ID = 123456 # apna daal
API_HASH = "apna hash"
BOT_TOKEN = "apna token"

app = Client("songbot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def download_thumb(url):
    try:
        r = requests.get(url, timeout=10)
        with open("thumb.jpg", "wb") as f:
            f.write(r.content)
        # webp ko jpg me convert
        im = Image.open("thumb.jpg")
        im = im.convert("RGB")
        im.save("thumb.jpg", "JPEG")
        return "thumb.jpg"
    except:
        return None

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("🎵 **Song4You Bot**\n\nBas gaane ka naam bhejo, mai mp3 player bana ke dunga.\nEx: `Kesariya Arijit`")

@app.on_message(filters.text & ~filters.command(["start"]))
async def player(client, message):
    query = message.text
    status = await message.reply(f"🔍 `'{query}'` search kar raha hu...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'outtmpl': '%(id)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            data = info['entries'][0]
            title = data.get('title', query)
            artist = data.get('uploader', 'Unknown Artist')
            thumb_url = data.get('thumbnail')
            
            # file ka naam find karo
            mp3_file = f"{data['id']}.mp3"
            
            thumb_file = None
            if thumb_url:
                thumb_file = download_thumb(thumb_url)

            await status.edit(f"📤 **{title}** upload ho raha hai...")

            await client.send_audio(
                chat_id=message.chat.id,
                audio=mp3_file,
                title=title[:60],
                performer=artist[:30],
                thumb=thumb_file,
                caption=f"🎧 **{title}**\n👤 {artist}\n\n@film4youofficial",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Share", switch_inline_query=title),
                     InlineKeyboardButton("📢 Film4You", url="https://t.me/film4youofficial")]
                ])
            )

            await status.delete()
            if os.path.exists(mp3_file): os.remove(mp3_file)
            if thumb_file and os.path.exists(thumb_file): os.remove(thumb_file)

    except Exception as e:
        await status.edit(f"❌ Error: {e}")

app.run()
