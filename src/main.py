#import configparser
from datetime import datetime
import os

from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, \
    ConversationHandler, CallbackContext
from telegram.request import HTTPXRequest
from telegram.error import Forbidden, BadRequest, TimedOut

from handlers import handle_message, button_callback, start_cmd, genres_cmd, langs_cmd, settings_cmd, donate_cmd, \
    help_cmd, about_cmd, news_cmd
from admin import admin_cmd, cancel_auth, auth_password, AUTH_PASSWORD, handle_admin_buttons, ADMIN_BUTTONS
from constants import FLIBUSTA_DB_BOOKS_PATH   # , FLIBUSTA_DB_SETTINGS_PATH
from health import log_system_stats

MONITORING_INTERVAL=1800
CLEANUP_INTERVAL=3600

async def log_stats(context: CallbackContext):
    """Только логирование статистики"""
    stats = log_system_stats()
    print(f"📊 Stats: {stats['memory_used']:.1f}MB memory")

# async def perform_cleanup(context: CallbackContext):
#     """Периодическая очистка и мониторинг"""
#     try:
#         cleanup_memory()
#     except Exception as e:
#         print(f"Error in periodic cleanup: {e}")

async def cleanup_old_sessions(context: CallbackContext):
    """Очистка данных поиска у неактивных пользователей"""
    try:
        if hasattr(context, 'application') and hasattr(context.application, 'user_data'):
            app = context.application
            cleaned_count = 0

            for user_id, user_data in app.user_data.items():
                if isinstance(user_data, dict):
                    last_activity = user_data.get('last_activity')

                    # Очищаем если неактивен более 1 часа
                    if isinstance(last_activity, datetime) and (datetime.now() - last_activity).total_seconds() > CLEANUP_INTERVAL:
                        # Очищаем данные поиска УДАЛЕНИЕМ ключей
                        search_keys = [
                            'BOOKS', 'PAGES_OF_BOOKS', 'FOUND_BOOKS_COUNT',
                            'SERIES', 'PAGES_OF_SERIES', 'FOUND_SERIES_COUNT'
                        ]

                        for key in search_keys:
                            if key in user_data:
                                del user_data[key]

                        cleaned_count += 1

            if cleaned_count > 0:
                print(f"🧹 Cleaned datasets of {cleaned_count} user(s)")

    except Exception as e:
        print(f"❌ Cleanup error: {e}")


async def error_handler(update: Update, context: CallbackContext):
    """Глобальный обработчик ошибок"""
    error = context.error

    # Пользователь заблокировал бота
    if isinstance(error, Forbidden) and "bot was blocked by the user" in str(error):
        print(f"Пользователь заблокировал бота: {update.effective_user.id if update.effective_user else 'Unknown'}")
        return

    # Устаревший callback query
    if isinstance(error, BadRequest) and "Query is too old" in str(error):
        print(f"Устаревший callback query: {error}")
        return

    # Таймаут
    if isinstance(error, TimedOut):
        print(f"Таймаут запроса: {error}")
        return

    # Другие ошибки
    print(f"Необработанная ошибка: {error}")
    if update and update.effective_user:
        print(f"User: {update.effective_user.id}")


def check_files():
    # Проверяем доступность файлов и БД
    required_paths = [
        FLIBUSTA_DB_BOOKS_PATH
#        FLIBUSTA_DB_SETTINGS_PATH
    ]
    for path in required_paths:
        if not os.path.exists(path):
            print(f"Ошибка: путь {path} недоступен в контейнере.")
            return False
    return True


async def set_commands(application: Application):
    """Устанавливает меню команд"""
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("news", "Новости и обновления"),
        BotCommand("about", "Инфа о боте и библиотеке"),
        BotCommand("help", "Помощь по запросам"),
        BotCommand("genres", "Список жанров"),
        BotCommand("langs", "Доступные языки"),
        BotCommand("set", "Настройки поиска"),
        BotCommand("donate", "Поддержать разработчика")
        #        BotCommand("search", "Поиск книг"),
    ]
    await application.bot.set_my_commands(commands)


def main():
    if not check_files():
        raise RuntimeError("Необходимые файлы или БД недоступны в контейнере.")

    # Получаем токен из переменной окружения
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        raise ValueError("Токен бота не найден в переменной окружения BOT_TOKEN.")
#        # Загрузка конфигурации из INI-файла
#        config = configparser.ConfigParser()
#        config.read("config.ini")
#        TOKEN = config.get("Bot", "token", fallback=None)
#        if not TOKEN:
#            raise ValueError("Токен бота не найден в config.ini.")

    request = HTTPXRequest(connect_timeout=60, read_timeout=60)
    #application = Application.builder().token(TOKEN).read_timeout(60).build()
    application = Application.builder().token(TOKEN).request(request).build()

    application.add_error_handler(error_handler)

    # В первкю очередь добавляем обработчики администратора
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('admin', admin_cmd)],
        states={
            AUTH_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, auth_password)]
        },
        fallbacks=[CommandHandler('cancel', cancel_auth)]
    )
    application.add_handler(conv_handler)

    # Регулярное выражение для фильтрации админских кнопок
    ADMIN_BUTTONS_REGEX = r'^(' + '|'.join(ADMIN_BUTTONS.values()) + ')$'
    # Обработчик для админских кнопок
    application.add_handler(MessageHandler(filters.Regex(ADMIN_BUTTONS_REGEX), handle_admin_buttons))
    # # Добавляем обработчик callback для админских действий
    # application.add_handler(CallbackQueryHandler(handle_admin_callback))

    # application.add_handler(CommandHandler("whoami", admin_whoami))
    # application.add_handler(CommandHandler("stats", admin_user_stats))
    # application.add_handler(CommandHandler("broadcast", admin_broadcast))
    # application.add_handler(CommandHandler("logs", admin_logs))
    # application.add_handler(CommandHandler("logout", admin_logout))

    # Команды пользователя
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("news", news_cmd))
    application.add_handler(CommandHandler("about", about_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("genres", genres_cmd))
    application.add_handler(CommandHandler("langs", langs_cmd))
    application.add_handler(CommandHandler("set", settings_cmd))
    application.add_handler(CommandHandler("donate", donate_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))

    # Устанавливаем меню команд
    application.post_init = set_commands

    # Добавляем периодическую очистку сессий (каждые 5 минут)
    #job_queue = application.job_queue
    #job_queue.run_repeating(cleanup_admin_sessions, interval=300, first=10)
    # Добавляем периодические задачи
    job_queue = application.job_queue
    if job_queue:
        # Периодический мониторинг
        job_queue.run_repeating(log_stats, interval=MONITORING_INTERVAL, first=10)
        # Периодическая очистка старых пользовательских сессий
        job_queue.run_repeating(cleanup_old_sessions, interval=CLEANUP_INTERVAL, first=CLEANUP_INTERVAL)

    application.run_polling()

if __name__ == '__main__':
    main()