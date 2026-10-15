import os
import re
import logging
from threading import Thread
from urllib.parse import urlparse

from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ==================== CONFIGURATION ====================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
FORCE_JOIN_CHANNEL = os.getenv("FORCE_JOIN_CHANNEL", "").strip()
FORCE_JOIN_URL = os.getenv("FORCE_JOIN_URL", "").strip()

ADMIN_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_IDS", "").split(",")
    if value.strip().isdigit()
}

PORT = int(os.getenv("PORT", "10000"))

# ==================== LOGGING ====================

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger("terabox_bot")

# Reduce noisy HTTP logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

# ==================== URL CONFIGURATION ====================

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)

TERABOX_HOSTS = {
    "terabox.com",
    "1024terabox.com",
    "teraboxapp.com",
    "teraboxlink.com",
    "terabox.fun",
    "teraboxshare.com",
}

VIDEO_EXTENSIONS = (
    ".mp4",
    ".m4v",
    ".mov",
    ".webm",
)

# ==================== FLASK HEALTH SERVER ====================

health_app = Flask(__name__)


@health_app.route("/")
def home():
    return "TeraBox Bot is running!", 200


@health_app.route("/health")
def health():
    return {"status": "ok"}, 200


def run_health_server():
    health_app.run(
        host="0.0.0.0",
        port=PORT,
        use_reloader=False,
        threaded=True,
    )


# ==================== URL HELPERS ====================

def get_host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except (ValueError, TypeError):
        return ""


def is_valid_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)

        return (
            parsed.scheme.lower() in ("http", "https")
            and bool(parsed.hostname)
            and not parsed.username
            and not parsed.password
        )
    except (ValueError, TypeError):
        return False


def is_terabox_url(url: str) -> bool:
    host = get_host(url)

    return any(
        host == domain or host.endswith("." + domain)
        for domain in TERABOX_HOSTS
    )


def is_direct_video_url(url: str) -> bool:
    if not is_valid_http_url(url):
        return False

    path = urlparse(url).path.lower()
    return path.endswith(VIDEO_EXTENSIONS)


def extract_urls(message) -> list:
    """Extract URLs from text, captions and Telegram text-link entities."""
    content = message.text or message.caption or ""
    urls = URL_PATTERN.findall(content)

    entities = message.entities or []
    caption_entities = message.caption_entities or []

    for entity in entities + caption_entities:
        if entity.type == "text_link" and entity.url:
            urls.append(entity.url)

    # Remove duplicates while preserving order.
    result = []
    seen = set()

    for raw_url in urls:
        url = raw_url.rstrip(".,!?;:)]}")
        if url not in seen:
            seen.add(url)
            result.append(url)

    return result


# ==================== MEMBERSHIP ====================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def is_member(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    user = update.effective_user

    if not user:
        return False

    # Configured admins can use the bot without joining.
    if is_admin(user.id):
        return True

    # Force join is disabled if no channel is configured.
    if not FORCE_JOIN_CHANNEL:
        return True

    try:
        member = await context.bot.get_chat_member(
            chat_id=FORCE_JOIN_CHANNEL,
            user_id=user.id,
        )

        if member.status in ("creator", "administrator", "member"):
            return True

        # A restricted user may still be a channel member.
        return (
            member.status == "restricted"
            and getattr(member, "is_member", False)
        )

    except TelegramError:
        logger.exception("Channel membership check failed")
        return False


def join_keyboard() -> InlineKeyboardMarkup:
    buttons = []

    if FORCE_JOIN_URL:
        buttons.append([
            InlineKeyboardButton(
                "Join Channel",
                url=FORCE_JOIN_URL,
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "I Have Joined - Check Again",
            callback_data="check_join",
        )
    ])

    return InlineKeyboardMarkup(buttons)


async def require_membership(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    if await is_member(update, context):
        return True

    text = (
        "🔒 <b>Channel Membership Required</b>\n\n"
        "Please join our channel before using this bot.\n"
        "After joining, press the verification button below."
    )

    message = update.effective_message

    if message:
        await message.reply_text(
            text,
            reply_markup=join_keyboard(),
            parse_mode="HTML",
        )

    return False


async def check_join(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    query = update.callback_query

    if not query:
        return

    await query.answer()

    if await is_member(update, context):
        if query.message:
            await query.message.reply_text(
                "Membership verified successfully!\n\n"
                "Send a TeraBox share link or a supported "
                "public direct video URL."
            )
    else:
        if query.message:
            await query.message.reply_text(
                "Membership not verified. Please join the channel "
                "and try again.",
                reply_markup=join_keyboard(),
            )


# ==================== BOT COMMANDS ====================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await require_membership(update, context):
        return

    message = update.effective_message

    if message:
        await message.reply_text(
            "Welcome to TeraBox Link Bot!\n\n"
            "Send a TeraBox shared link to get an option "
            "to open the original link.\n\n"
            "You can also send a public direct video URL "
            "in a supported format.\n\n"
            "Important: TeraBox share links are not "
            "automatically converted into direct downloads "
            "by this bot.\n\n"
            "Available commands:\n"
            "/start - Start the bot\n"
            "/help - Usage instructions\n"
            "/id - Show your Telegram ID\n"
            "/admin - Show admin status"
        )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await require_membership(update, context):
        return

    message = update.effective_message

    if message:
        await message.reply_text(
            "HOW TO USE THIS BOT\n\n"
            "1. Send a TeraBox shared link.\n"
            "2. Press the Open TeraBox Link button.\n"
            "3. For a public direct video URL, the bot will "
            "attempt to send the video through Telegram.\n\n"
            "Private links, expired links, login-required files "
            "and unsupported URLs may not work.\n\n"
            "The bot does not guarantee direct-link conversion "
            "or successful delivery for every URL."
        )


async def id_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    message = update.effective_message

    if user and message:
        await message.reply_text(
            f"Your Telegram ID: {user.id}"
        )


async def admin_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    user = update.effective_user
    message = update.effective_message

    if not message:
        return

    if not user or not is_admin(user.id):
        await message.reply_text("Admin-only command.")
        return

    await message.reply_text(
        "Admin access is active.\n"
        f"Force join: {FORCE_JOIN_CHANNEL or 'Disabled'}\n"
        f"Configured admins: {len(ADMIN_IDS)}"
    )


# ==================== LINK PROCESSING ====================

async def process_link(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not await require_membership(update, context):
        return

    message = update.effective_message

    if not message:
        return

    urls = extract_urls(message)

    if not urls:
        await message.reply_text(
            "Please send a valid HTTP or HTTPS link."
        )
        return

    # Process one URL per message.
    url = urls[0]

    if not is_valid_http_url(url):
        await message.reply_text("Invalid URL.")
        return

    # TeraBox shared links are opened in the original service.
    if is_terabox_url(url):
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "Open TeraBox Link",
                    url=url,
                )
            ]
        ])

        await message.reply_text(
            "TeraBox link detected.\n\n"
            "The original shared link is ready to open.\n\n"
            "Automatic direct-download conversion requires "
            "a compatible, authorized integration. This bot "
            "does not currently perform that conversion.",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
        return

    # Attempt to send supported public direct video URLs.
    if is_direct_video_url(url):
        status = await message.reply_text(
            "Direct video URL detected. Trying to send the video..."
        )

        try:
            await message.reply_video(
                video=url,
                caption="Video",
                supports_streaming=True,
                read_timeout=60,
                write_timeout=60,
                connect_timeout=30,
                pool_timeout=30,
            )

            await status.delete()

        except TelegramError as exc:
            logger.warning("Video delivery failed: %s", exc)

            await status.edit_text(
                "Telegram could not fetch this video URL.\n\n"
                "The link may be private, expired, unsupported, "
                "or inaccessible to Telegram's servers."
            )

        except Exception:
            logger.exception("Unexpected video delivery error")

            await status.edit_text(
                "An unexpected error occurred while sending the video."
            )

        return

    # Any other valid URL gets an open-link button.
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "Open Link",
                url=url,
            )
        ]
    ])

    await message.reply_text(
        "Link received, but it is not a supported direct video URL.\n\n"
        "Use the button below to open the original link.",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


# ==================== ERROR HANDLING ====================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    error = context.error

    if error:
        logger.error(
            "Unhandled bot error",
            exc_info=(
                type(error),
                error,
                error.__traceback__,
            ),
        )
    else:
        logger.error("An unknown bot error occurred")


# ==================== APPLICATION STARTUP ====================

def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Set it in Render Environment Variables."
        )

    # Start the web health server for Render.
    Thread(
        target=run_health_server,
        daemon=True,
        name="health-server",
    ).start()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("id", id_command))
    application.add_handler(CommandHandler("admin", admin_command))

    application.add_handler(
        CallbackQueryHandler(
            check_join,
            pattern=r"^check_join$",
        )
    )

    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.CAPTION) & ~filters.COMMAND,
            process_link,
        )
    )

    application.add_error_handler(error_handler)

    logger.info("Starting Telegram bot polling...")

    application.run_polling(
        drop_pending_updates=False,
        allowed_updates=Update.ALL_TYPES,
    )


if __name__ == "__main__":
    main()
