import os
import sqlite3
import logging
from html import escape

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")
DB_PATH = os.getenv("DB_PATH", "kartonyar_welcome.db")

DEFAULT_WELCOME = """👋 سلام {mention} عزیز، به گروه «{group}» خوش آمدید.
🌱 به جمع خانواده کارتن‌یار خوش آمدی.
📦 این گروه برای تبادل اطلاعات، ارتباطات و فرصت‌های صنعت کاغذ، مقوا و کارتن ایجاد شده است.

لطفاً قوانین گروه را رعایت کنید و با احترام با سایر اعضا گفتگو کنید. 🙏

🟢 کارتن‌یار | همراه صنعت سلولزی"""

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS welcomes "
        "(chat_id INTEGER PRIMARY KEY, text TEXT NOT NULL)"
    )
    conn.commit()
    return conn


def get_welcome(chat_id: int):
    conn = db()
    row = conn.execute(
        "SELECT text FROM welcomes WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def set_welcome(chat_id: int, text: str):
    conn = db()
    conn.execute(
        "INSERT INTO welcomes(chat_id, text) VALUES(?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET text=excluded.text",
        (chat_id, text),
    )
    conn.commit()
    conn.close()


def reset_welcome(chat_id: int):
    conn = db()
    conn.execute("DELETE FROM welcomes WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()


def render(text: str, user, group_name: str) -> str:
    mention = user.mention_html()
    return (
        text.replace("{mention}", mention)
        .replace("{name}", escape(user.full_name))
        .replace("{username}", escape(user.username or ""))
        .replace("{group}", escape(group_name))
    )


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_chat or not update.effective_user:
        return False

    member = await context.bot.get_chat_member(
        update.effective_chat.id, update.effective_user.id
    )
    return member.status in ("administrator", "creator")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        "🤖 ربات خوشامدگوی کارتن‌یار فعال است.\n\n"
        "📝 برای این گروه، اولین پیام متنی مدیر گروه به‌عنوان متن خوشامدگویی ذخیره می‌شود.\n\n"
        "تغییر دستی متن:\n"
        "/setwelcome متن شما\n\n"
        "نمایش متن فعلی:\n"
        "/welcome\n\n"
        "پاک کردن متن اختصاصی و شروع دوباره:\n"
        "/resetwelcome"
    )


async def welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.effective_message.reply_text(
            "این دستور را داخل گروه اجرا کنید."
        )
        return

    text = get_welcome(update.effective_chat.id)
    if text:
        await update.effective_message.reply_text(
            "📝 متن فعلی خوشامدگویی:\n\n" + text
        )
    else:
        await update.effective_message.reply_text(
            "📝 هنوز متن اختصاصی برای این گروه ثبت نشده است.\n"
            "اولین پیام متنی مدیر گروه به‌عنوان متن خوشامدگویی ذخیره می‌شود."
        )


async def setwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.effective_message.reply_text(
            "این دستور را داخل گروه اجرا کنید."
        )
        return

    if not await is_admin(update, context):
        await update.effective_message.reply_text(
            "⛔ فقط مدیران گروه می‌توانند متن خوشامدگویی را تغییر دهند."
        )
        return

    text = update.effective_message.text.partition(" ")[2].strip()
    if not text:
        await update.effective_message.reply_text(
            "مثال:\n/setwelcome 👋 سلام {mention} عزیز، به گروه «{group}» خوش آمدی!"
        )
        return

    set_welcome(update.effective_chat.id, text)
    await update.effective_message.reply_text(
        "✅ متن خوشامدگویی این گروه ذخیره شد."
    )


async def resetwelcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.effective_message.reply_text(
            "این دستور را داخل گروه اجرا کنید."
        )
        return

    if not await is_admin(update, context):
        await update.effective_message.reply_text(
            "⛔ فقط مدیران گروه می‌توانند این تنظیم را تغییر دهند."
        )
        return

    reset_welcome(update.effective_chat.id)
    await update.effective_message.reply_text(
        "✅ متن اختصاصی این گروه پاک شد.\n"
        "پیام متنی بعدی که توسط مدیر گروه ارسال شود، متن خوشامدگویی جدید خواهد بود."
    )


async def capture_first_admin_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    if not update.effective_chat or update.effective_chat.type not in (
        "group",
        "supergroup",
    ):
        return

    if not update.effective_message or not update.effective_message.text:
        return

    # Commands are handled separately and should not become the welcome text.
    if update.effective_message.text.startswith("/"):
        return

    # Only the first normal text message from an administrator can initialize
    # the welcome text for a group.
    if not await is_admin(update, context):
        return

    chat_id = update.effective_chat.id

    if get_welcome(chat_id) is not None:
        return

    set_welcome(chat_id, update.effective_message.text.strip())

    try:
        await update.effective_message.reply_text(
            "✅ اولین پیام شما به‌عنوان مدیر گروه، به‌عنوان متن خوشامدگویی این گروه ذخیره شد."
        )
    except Exception:
        logger.exception("Could not confirm welcome template")


async def new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type not in (
        "group",
        "supergroup",
    ):
        return

    group_name = update.effective_chat.title or "کارتن‌یار"
    template = get_welcome(update.effective_chat.id) or DEFAULT_WELCOME

    for user in update.effective_message.new_chat_members:
        try:
            message = render(template, user, group_name)
            await update.effective_message.reply_text(
                message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
        except Exception:
            logger.exception("Could not send welcome message")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Unhandled bot error", exc_info=context.error)


def main():
    if not TOKEN:
        raise RuntimeError(
            "BOT_TOKEN تنظیم نشده است. توکن BotFather را به صورت متغیر محیطی BOT_TOKEN قرار دهید."
        )

    db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("welcome", welcome_command))
    app.add_handler(CommandHandler("setwelcome", setwelcome))
    app.add_handler(CommandHandler("resetwelcome", resetwelcome))

    # First normal text from a group admin becomes that group's welcome text.
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS,
            capture_first_admin_message,
        )
    )

    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_members)
    )

    app.add_error_handler(error_handler)

    print("KartonYar Welcome Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
