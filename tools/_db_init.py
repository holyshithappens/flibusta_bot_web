import sqlite3
import os
from src.constants import (
    FLIBUSTA_DB_LOGS_PATH,
    FLIBUSTA_DB_SETTINGS_PATH,
    PREFIX_WORK_PATH,
    PREFIX_LOG_PATH,
    PREFIX_TMP_PATH
)


def ensure_directories_exist():
    """Создает необходимые рабочие директории, если они не существуют"""
    os.makedirs(PREFIX_WORK_PATH, exist_ok=True)
    os.makedirs(PREFIX_LOG_PATH, exist_ok=True)
    os.makedirs(PREFIX_TMP_PATH, exist_ok=True)
    os.makedirs(os.path.dirname(FLIBUSTA_DB_LOGS_PATH) or '.', exist_ok=True)
    os.makedirs(os.path.dirname(FLIBUSTA_DB_SETTINGS_PATH) or '.', exist_ok=True)


def init_logs_db():
    """Инициализирует БД логов с точной структурой таблицы"""
    if not os.path.exists(FLIBUSTA_DB_LOGS_PATH):
        print(f"Создаем новую БД логов: {FLIBUSTA_DB_LOGS_PATH}")
        conn = sqlite3.connect(FLIBUSTA_DB_LOGS_PATH)
        cursor = conn.cursor()

        # Создаем таблицу логов с точным соответствием DDL
        cursor.execute("""
        CREATE TABLE "UserLog" (
            "Timestamp" VARCHAR(27) NOT NULL,
            "UserID" INTEGER NOT NULL,
            "UserName" VARCHAR(50),
            "Action" VARCHAR(50) COLLATE NOCASE,
            "Detail" VARCHAR(255) COLLATE NOCASE,
            PRIMARY KEY("Timestamp","UserID")
        )
        """)

        # Создаем индекс для ускорения поиска
        cursor.execute("""
        CREATE INDEX "IXUserLog_UserID_Timestamp" ON "UserLog" (
            "UserID",
            "Timestamp"
        )
        """)

        conn.commit()
        conn.close()
        print("БД логов успешно инициализирована с правильной структурой")


def init_settings_db():
    """Инициализирует БД настроек с точной структурой таблицы"""
    if not os.path.exists(FLIBUSTA_DB_SETTINGS_PATH):
        print(f"Создаем новую БД настроек: {FLIBUSTA_DB_SETTINGS_PATH}")
        conn = sqlite3.connect(FLIBUSTA_DB_SETTINGS_PATH)
        cursor = conn.cursor()

        # Создаем таблицу настроек с точным соответствием DDL
        cursor.execute("""
        CREATE TABLE "UserSettings" (
            "User_ID" INTEGER NOT NULL UNIQUE,
            "MaxBooks" INTEGER NOT NULL DEFAULT 20,
            "Lang" VARCHAR(2) DEFAULT '',
            "DateSortOrder" VARCHAR(10) DEFAULT 'DESC',
            PRIMARY KEY("User_ID")
        )
        """)

        # Создаем уникальный индекс
        cursor.execute("""
        CREATE UNIQUE INDEX "IXUserSettings_User_ID" ON "UserSettings" (
            "User_ID"
        )
        """)

        conn.commit()
        conn.close()
        print("БД настроек успешно инициализирована с правильной структурой")


def check_and_init_dbs():
    """Проверяет и инициализирует все необходимые БД с точными структурами"""
    try:
        # Создаем директории если их нет
        ensure_directories_exist()

        # Инициализируем БД с точными DDL
        init_logs_db()
        init_settings_db()

        print("Все БД проверены и инициализированы с правильными структурами")
        return True
    except Exception as e:
        print(f"Критическая ошибка при инициализации БД: {str(e)}")
        return False


if __name__ == "__main__":
    # При запуске модуля напрямую выполняем проверку и инициализацию
    check_and_init_dbs()
