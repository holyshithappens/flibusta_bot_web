import re
import sqlite3
from datetime import datetime

#DB_PATH_META = "/media/sf_FlibustaBot/FlibustaMeta.sqlite"
DB_PATH_META = "/media/sf_FlibustaBot/data/Flibusta_FB2_local.hlc2"


def clean_year(year_str):
    """Очищает и преобразует строку с годом в целое число.
    Возвращает 0 если год не распознан."""
    if not year_str or str(year_str).strip() == "":
        return 0

    year_str = str(year_str).strip()

    # 1. Проверка текстовых дат формата "June 28th 2011" → 2011
    text_date_match = re.search(
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?\s+(\d{4})",
        year_str,
        re.IGNORECASE
    )
    if text_date_match:
        year = int(text_date_match.group(1))
        if 1000 <= year <= datetime.now().year:
            return year

    # 2. Проверка формата DD.MM.YYYY ("12.01.2009" → 2009)
    date_match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", year_str)
    if date_match:
        year = int(date_match.group(3))
        if 1000 <= year <= datetime.now().year:
            return year

    # 3. Извлечение 4-значного года из начала строки ("2005 г." → 2005)
    match = re.search(r"^(18|19|20)\d{2}", year_str)
    if match:
        year = int(match.group())
        if 1000 <= year <= datetime.now().year:
            return year

    # 4. Обработка диапазонов ("2013-2014" → 2013)
    range_match = re.search(r"(?P<first_year>(18|19|20)\d{2})\s*[-–]\s*(18|19|20)\d{2}", year_str)
    if range_match:
        first_year = int(range_match.group("first_year"))
        if 1000 <= first_year <= datetime.now().year:
            return first_year

    # 5. Извлечение года из строк с мусором ("ISBN2005" → 2005)
    digits_only = re.sub(r"[^0-9]", "", year_str)
    if len(digits_only) == 4:
        year = int(digits_only)
        if 1000 <= year <= datetime.now().year:
            return year

    return 0  # Возвращаем 0 для нераспознанных годов

def clean_years_in_db(db_path):
    """Очищает и обновляет года в базе данных"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Включаем оптимизации
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA synchronous = OFF;")
    cursor.execute("PRAGMA cache_size = 10000;")
    cursor.execute("PRAGMA temp_store = MEMORY;")

    try:
        # Сначала получаем общее количество записей
        cursor.execute("""
            SELECT COUNT(*) FROM Books_Meta where SearchYear is null and Year is not null;
        """)
        total_rows = cursor.fetchone()[0]
        print(f"Всего записей для обработки: {total_rows}")

        # Обрабатываем пачками
        batch_size = 10000
        offset = 0
        processed = 0

        # Подготавливаем обновления
        while True:
            # Получаем данные для обработки
            cursor.execute(f"""
                SELECT BookID, Year FROM Books_Meta where SearchYear is null and Year is not null
                LIMIT {batch_size} --OFFSET {offset}
                """)

            rows = cursor.fetchall()
            if not rows:
                break

            updates = []
            for bookid, year_str in rows:
                cleaned_year = clean_year(year_str)
                updates.append((cleaned_year, bookid))

            # Выполняем массовое обновление в транзакции
            with conn:
                cursor.executemany(
                    "UPDATE Books_Meta SET SearchYear = ? WHERE BookID = ?;",
                    updates
                )

            conn.commit()

            processed += len(rows)
            offset += batch_size

            print(f"Обработано: {processed}/{total_rows} ({processed / total_rows * 100:.1f}%)")

    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
        conn.rollback()
    finally:
        # Восстанавливаем нормальные настройки
        cursor.execute("PRAGMA journal_mode = DELETE;")
        cursor.execute("PRAGMA synchronous = FULL;")
        conn.close()

if __name__ == "__main__":
    clean_years_in_db(db_path=DB_PATH_META)