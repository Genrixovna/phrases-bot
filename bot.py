import logging
import random
import sqlite3
from datetime import datetime, time
import pytz
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TARGET_CHAT_IDS = [-618165838, -4057163344, -4510385399]

# ✅ ВЕРНУЛИ нормальное время рассылки
TIMEZONE = pytz.timezone('Europe/Moscow')
SEND_TIME = time(hour=14, minute=32, tzinfo=TIMEZONE)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# 🆕 SQLite БАЗА ДАННЫХ
db_conn = None

def init_db():
    global db_conn
    db_conn = sqlite3.connect('phrases.db')
    cursor = db_conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS phrases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            phrase TEXT,
            created_at TEXT
        )
    ''')
    db_conn.commit()
    logger.info("✅ SQLite база данных готова")

def add_phrase(user_id, username, text):
    global db_conn
    if not db_conn: return False
    try:
        cursor = db_conn.cursor()
        cursor.execute(
            "INSERT INTO phrases (user_id, username, phrase, created_at) VALUES (?, ?, ?, ?)",
            (user_id, username, text, datetime.now().strftime("%d.%m.%Y %H:%M"))
        )
        db_conn.commit()
        logger.info(f"✅ Фраза добавлена: {username}")
        return True
    except Exception as e:
        logger.error(f"Ошибка БД: {e}")
        return False

def get_all_phrases():
    global db_conn
    if not db_conn: return []
    try:
        cursor = db_conn.cursor()
        cursor.execute("SELECT phrase FROM phrases")
        return [row[0] for row in cursor.fetchall()]
    except:
        return []

# 🔥 ГЛАВНОЕ МЕНЮ С КНОПКАМИ
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("➕ Добавить фразу"), KeyboardButton("🎲 Случайная фраза")],
        [KeyboardButton("📈 Статистика"), KeyboardButton("🧪 Тест рассылки")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM phrases")
    count = cursor.fetchone()[0]
    
    await update.message.reply_text(
        f"🚀 **Бот с SQLite и кнопками!**\n\n"
        f"📊 **В базе:** {count} фраз\n\n"
        f"👇 **Выбери действие:**",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

# 🔥 ОБРАБОТЧИК КНОПОК
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == "➕ Добавить фразу":
        context.user_data['waiting_for_phrase'] = True
        await update.message.reply_text(
            "✍️ **Напиши свою фразу!**\n\n"
            "Или: `/add Твоя супер фраза`",
            parse_mode='Markdown'
        )
    
    elif text == "🎲 Случайная фраза":
        await sendphrase(update, context)
    
    elif text == "📈 Статистика":
        await stats(update, context)
    
    elif text == "🧪 Тест рассылки":
        await test_daily_send(update, context)
    
    elif text == "ℹ️ Помощь":
        await update.message.reply_text(
            "📋 **КОМАНДЫ:**\n"
            "• `/start` — меню\n"
            "• `/add фраза` — добавить\n"
            "• `/sendphrase` — случайная\n"
            "• `/stats` — статистика\n"
            "• `/test_send` — тест рассылки",
            parse_mode='Markdown'
        )

# 🔥 ОБРАБОТЧИК ТЕКСТА (фраза от пользователя)
async def handle_phrase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name or "Аноним"
    
    if context.user_data.get('waiting_for_phrase'):
        context.user_data['waiting_for_phrase'] = False
        
        if add_phrase(user_id, username, update.message.text):
            await update.message.reply_text(
                f"✅ **{username}**, добавлено!\n\n"
                f"{update.message.text}\n\n"
                f"🎉 База пополнена!",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text("❌ Ошибка добавления")
        return
    
    await start(update, context)

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or user.first_name or "Аноним"
    
    text = ' '.join(context.args)
    if not text:
        await update.message.reply_text("❌ Укажи фразу: `/add Твоя фраза`", parse_mode='Markdown')
        return
    
    if add_phrase(user_id, username, text):
        await update.message.reply_text(
            f"✅ **{username}**, добавлено!\n\n"
            f"{text}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Ошибка добавления")

async def sendphrase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phrases = get_all_phrases()
    if not phrases:
        await update.message.reply_text("📭 База пуста")
        return
    phrase = random.choice(phrases)
    await update.message.reply_text(f"🎲 **Случайная фраза:**\n\n{phrase}")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global db_conn
    if not db_conn:
        await update.message.reply_text("❌ База не подключена")
        return
    
    cursor = db_conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM phrases")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT username, COUNT(*) FROM phrases GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 3")
    top_users = cursor.fetchall()
    
    stats_text = f"📊 **СТАТИСТИКА:**\n\n"
    stats_text += f"**Всего фраз:** {total}\n\n"
    stats_text += f"**🏆 Топ-3:**\n"
    
    for i, (user, cnt) in enumerate(top_users, 1):
        stats_text += f"{i}. **{user}**: {cnt}\n"
    
    keyboard = [[InlineKeyboardButton("🔄 Обновить", callback_data='refresh_stats')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(stats_text, reply_markup=reply_markup, parse_mode='Markdown')

# 🧪 ТЕСТ РАССЫЛКИ
async def test_daily_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phrases = get_all_phrases()
    if not phrases:
        await update.message.reply_text("📭 Нет фраз")
        return
    
    phrase = random.choice(phrases)
    message = f"🧪 ТЕСТ РАССЫЛКИ ({datetime.now().strftime('%H:%M')}):\n\n{phrase}"
    success = 0
    
    for chat_id in TARGET_CHAT_IDS:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
            success += 1
            logger.info(f"✅ Тест: {chat_id}")
        except Exception as e:
            logger.error(f"❌ Тест {chat_id}: {e}")
    
    await update.message.reply_text(
        f"🧪 **Тест завершён!**\n"
        f"✅ Отправлено: {success}/3 чата\n\n"
        f"{phrase}",
        parse_mode='Markdown'
    )

# 🔥 INLINE КНОПКИ
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'refresh_stats':
        await stats(query, context)

# ✅ ИСПРАВЛЕННАЯ РАССЫЛКА БЕЗ Markdown
async def daily_send(context: ContextTypes.DEFAULT_TYPE):
    phrases = get_all_phrases()
    if not phrases: return
    
    phrase = random.choice(phrases)
    message = f"🌅 Утренняя мудрость:\n\n{phrase}"
    
    for chat_id in TARGET_CHAT_IDS:
        try:
            await context.bot.send_message(chat_id=chat_id, text=message)
            logger.info(f"✅ Рассылка: {chat_id}")
        except Exception as e:
            logger.error(f"❌ Рассылка {chat_id}: {e}")

def main():
    if not TELEGRAM_TOKEN:
        logger.error("❌ TELEGRAM_TOKEN не найден")
        return
    
    init_db()
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("sendphrase", sendphrase))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("test_send", test_daily_send))
    
    # Кнопки и текст
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))
    application.add_handler(MessageHandler(filters.TEXT, handle_phrase))
    
    # Inline кнопки
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Рассылка завтра в 10:30
    application.job_queue.run_daily(
        daily_send, time=SEND_TIME, days=(0,1,2,3,4,5,6), name="daily_phrase_job"
    )
    
    logger.info("🚀 БОТ С КНОПКАМИ И РАССЫЛКОЙ ГОТОВ!")
    application.run_polling()

if __name__ == '__main__':
    main()
