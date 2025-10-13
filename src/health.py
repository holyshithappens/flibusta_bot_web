import psutil
import gc
import logging
from datetime import datetime

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

# def cleanup_memory():
#     """Принудительная очистка памяти"""
#     before = get_memory_usage()
#     gc.collect()
#     after = get_memory_usage()
#     logging.info(f"Memory cleanup: {before:.1f}MB -> {after:.1f}MB")

