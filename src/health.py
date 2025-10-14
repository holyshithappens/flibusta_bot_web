import psutil
import gc
import logging
from datetime import datetime

from telegram.ext import CallbackContext

from constants import CLEANUP_INTERVAL


def get_memory_usage():
    """Возвращает использование памяти в MB"""
    process = psutil.Process()
    return process.memory_info().rss / 1024 / 1024


def get_system_stats():
    """Возвращает системную статистику"""
    return {
        'memory_used': get_memory_usage(),
        'memory_percent': psutil.virtual_memory().percent,
        'cpu_percent': psutil.cpu_percent(interval=1),
        'open_files': len(psutil.Process().open_files()),
        'threads': psutil.Process().num_threads(),
        'timestamp': datetime.now().isoformat()
    }


def log_system_stats():
    """Логирует системную статистику"""
    stats = get_system_stats()
    logging.info(f"SYSTEM_STATS: {stats}")
    return stats


def cleanup_memory():
    """Принудительная очистка памяти"""
    before = get_memory_usage()
    gc.collect()
    after = get_memory_usage()
    logging.info(f"Memory cleanup: {before:.1f}MB -> {after:.1f}MB")

# ===== ОБРАБОТЧИКИ ТРИГГЕРОВ В job_queue =====

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
        app = context.application
        cleaned_count_private = 0
        cleaned_count_group = 0

        # Чистим пространство пользователя в личном чате с ботом
        if hasattr(context.application, 'user_data'):
            for user_id, user_data in app.user_data.items():
                if isinstance(user_data, dict):
                    last_activity = user_data.get('last_activity')
                    # print(f"DEBUG: user_id:{user_id}, user_data:{str(user_data[0:1000])}, last_activity:{last_activity}")
                    # Очищаем если неактивен более 1 часа
                    if isinstance(last_activity, datetime) and (
                            datetime.now() - last_activity).total_seconds() > CLEANUP_INTERVAL:
                        # Очищаем данные поиска УДАЛЕНИЕМ ключей
                        search_keys = [
                            'BOOKS', 'PAGES_OF_BOOKS', 'FOUND_BOOKS_COUNT',
                            'SERIES', 'PAGES_OF_SERIES', 'FOUND_SERIES_COUNT',
                            'last_activity'
                        ]

                        for key in search_keys:
                            if key in user_data:
                                del user_data[key]

                        cleaned_count_private += 1

            if cleaned_count_private > 0:
                print(f"🧹 Cleaned datasets of {cleaned_count_private} user(s)")

        # Чистим пространство групповых чатов бота
        if hasattr(context.application, 'bot_data'):
            # print(f"DEBUG: пространтсво bot_data: {str(app.bot_data)[0:1000]}")
            for group_id in list(app.bot_data.keys()):
                bot_data = app.bot_data[group_id]
                # print(f"DEBUG: group_id:{group_id}, bot_data:{str(bot_data)[0:1000]}")
                if isinstance(bot_data, dict):
                    last_activity = bot_data.get('last_activity')
                    # print(f"DEBUG: last_activity: {last_activity}")

                    # Очищаем если неактивен более 1 часа
                    if isinstance(last_activity, datetime) and (
                            datetime.now() - last_activity).total_seconds() > CLEANUP_INTERVAL:
                        # Очищаем данные поиска УДАЛЕНИЕМ ключей
                        del app.bot_data[group_id]
                        cleaned_count_group += 1

            if cleaned_count_group > 0:
                print(f"🧹 Cleaned datasets of {cleaned_count_group} group(s)")

        if cleaned_count_private > 0 or cleaned_count_group > 0:
            cleanup_memory()

    except Exception as e:
        print(f"❌ Cleanup error: {e}")