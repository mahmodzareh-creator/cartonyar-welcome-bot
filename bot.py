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
        "(chat_id INTEGER PRIMARY KEY, text TEXT, source_message_id INTEGER)"
    )
    conn.commit()
    return conn


def get_welcome(chat_id: int):
    conn = db()
    row = conn.execute(
        "SELECT text, source_message_id FROM welcomes WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()
    conn.close()

    if not row:
        return {"text": DEFAULT_WELCOME, "source_message_id": None}

    return {"text": row[0], "source_message_id": row[1]}


def set_welcome(chat_id: int, text: str, source_message_id=None):
    conn = db()
    conn.execute(
        "INSERT INTO welcomes(chat_id, text, source_message_id) VALUES(?, ?, ?) "
        "ON CONFLICT(chat_id) DO UPDATE SET "
        "text=excluded.text, source_message_id=excluded.source_message_id",
        (chat_id, text, source_message_id),
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
        "برای استفاده از پیام اول گروه:\n"
        "1️⃣ روی پیام موردنظر Reply کنید.\n"
        "2️⃣ سپس /setwelcome را بفرستید.\n\n"
        "روش قدیمی با متن مستقیم:\n"
        "/setwelcome متن شما\n\n"
        "نمایش متن فعلی:\n"
        "/welcome\n\n"
        "بازگشت به متن پیش‌فرض:\n"
        "/resetwelcome"
    )


async def welcome_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.effective_message.reply_text(
            "این دستور را داخل گروه اجرا کنید."
        )
        return

    setting = get_welcome(update.effective_chat.id)

    if setting["source_message_id"]:
        await update.effective_message.reply_text(
            "📝 برای این گروه یک پیام ذخیره شده است.\n"
            "برای تغییر آن، روی پیام موردنظر Reply کنید و /setwelcome بفرستید."
        )
    else:
        await update.effective_message.reply_text(
            "📝 متن فعلی خوشامدگویی:\n\n" + setting["text"]
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

    # روش جدید: Reply روی پیام موردنظر و ارسال /setwelcome
    replied = update.effective_message.reply_to_message
    if replied:
        source_text = replied.text or replied.caption or ""
        set_welcome(
            update.effective_chat.id,
            source_text,
            replied.message_id,
        )
        await update.effective_message.reply_text(
            "✅ این پیام به‌عنوان پیام خوشامدگویی گروه ذخیره شد."
        )
        return

    # روش قبلی: /setwelcome متن
    text = update.effective_message.text.partition(" ")[2].strip()
    if not text:
        await update.effective_message.reply_text(
            "برای استفاده از پیام اول گروه:\n"
            "روی پیام موردنظر Reply کنید و /setwelcome را بفرستید.\n\n"
            "یا متن را مستقیم وارد کنید:\n"
            "/setwelcome 👋 سلام {mention} عزیز، خوش آمدی!"
        )
        return

    set_welcome(update.effective_chat.id, text, None)
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
        "✅ متن گروه به پیام پیش‌فرض کارتن‌یار برگشت."
    )


async def new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type not in (
        "group",
        "supergroup",
    ):
        return

    group_name = update.effective_chat.title or "کارتن‌یار"
    setting = get_welcome(update.effective_chat.id)

    for user in update.effective_message.new_chat_members:
        try:
            # اگر پیام مشخصی ذخیره شده باشد، همان پیام را کپی می‌کنیم.
            if setting["source_message_id"]:
                await context.bot.copy_message(
                    chat_id=update.effective_chat.id,
                    from_chat_id=update.effective_chat.id,
                    message_id=setting["source_message_id"],
                )
            else:
                message = render(setting["text"], user, group_name)
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
    app.add_handler(
        MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, new_members)
    )
    app.add_error_handler(error_handler)

    print("KartonYar Welcome Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
