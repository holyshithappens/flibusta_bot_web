#!/usr/bin/env python3
import sqlite3
import os
from constants import FLIBUSTA_DB_SETTINGS_PATH, FLIBUSTA_DB_LOGS_PATH


def init_databases():
    # Создаем папку data если нет
    os.makedirs(os.path.dirname(FLIBUSTA_DB_SETTINGS_PATH), exist_ok=True)

    # Инициализируем БД настроек
    conn_settings = sqlite3.connect(FLIBUSTA_DB_SETTINGS_PATH)
    cursor_settings = conn_settings.cursor()
    cursor_settings.execute("""
        CREATE TABLE IF NOT EXISTS UserSettings (
            User_ID INTEGER NOT NULL UNIQUE,
            MaxBooks INTEGER NOT NULL DEFAULT 20,
            Lang VARCHAR(2) DEFAULT '',
            DateSortOrder VARCHAR(10) DEFAULT 'DESC',
            BookFormat VARCHAR(10) DEFAULT 'fb2',
            LastNewsDate VARCHAR(10) DEFAULT '2000-01-01',
            IsBlocked BOOLEAN DEFAULT FALSE,
            PRIMARY KEY(User_ID)
        );
    """)
    # Создаем индекс
    cursor_settings.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS IXUserSettings_User_ID 
        ON UserSettings (User_ID);
    """)
    conn_settings.commit()
    conn_settings.close()

    # Инициализируем БД логов
    conn_logs = sqlite3.connect(FLIBUSTA_DB_LOGS_PATH)
    cursor_logs = conn_logs.cursor()
    cursor_logs.execute("""
        CREATE TABLE IF NOT EXISTS UserLog (
            Timestamp VARCHAR(27) NOT NULL,
            UserID INTEGER NOT NULL,
            UserName VARCHAR(50),
            Action VARCHAR(50) COLLATE NOCASE,
            Detail VARCHAR(255) COLLATE NOCASE,
            PRIMARY KEY(Timestamp, UserID)
        );
    """)
    # Создаем индекс
    cursor_logs.execute("""
        CREATE INDEX IF NOT EXISTS IXUserLog_UserID_Timestamp 
        ON UserLog (UserID, Timestamp);
    """)
    conn_logs.commit()
    conn_logs.close()

    print("Базы данных инициализированы")

if __name__ == "__main__":
    init_databases()