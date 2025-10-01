import sqlite3
import unicodedata

#DB_PATH_META = "/media/sf_FlibustaBot/FlibustaMeta.sqlite"
DB_PATH_META = "/media/sf_FlibustaBot/data/Flibusta_FB2_local.hlc2"


def process_city(city):
    """
    Обрабатывает поле city согласно требованиям:
    1) Если содержит цифры - возвращает None
    2) Удаляет все символы кроме букв (включая диакритические), пробелов, точки, запятой, минуса, дефиса
    3) Удаляет пробелы справа и слева
    4) Переводит в верхний регистр
    """
    if city is None:
        return None

    # 1) Проверяем наличие цифр
    if any(char.isdigit() for char in city):
        return None

    # 2) Удаляем все символы кроме букв (включая диакритические), пробелов, точки, запятой, минуса, дефиса
    # Используем Unicode свойства для идентификации букв (включая диакритические)
    processed_chars = []
    for char in city:
        # Проверяем, является ли символ буквой (включая диакритические)
        if unicodedata.category(char).startswith('L'):
            processed_chars.append(char)
        # Разрешаем пробелы, точку, запятую, минус, дефис
        #elif char in ' \t\n\r\f\v.,-\–—':  # пробелы, точка, запятая, разные типы дефисов
        elif char in ' \t\n\r\f\v-\–—':  # пробелы, разные типы дефисов
            processed_chars.append(char)
        # Все остальные символы игнорируем

    processed_city = ''.join(processed_chars)

    # 3) Удаляем пробелы справа и слева
    processed_city = processed_city.strip()

    # 4) Переводим в верхний регистр
    processed_city = processed_city.upper()

    return processed_city if processed_city else None


def upper_search_in_db_batch(db_path):
    """Очищает и обновляет года в базе данных с пагинацией"""
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
            SELECT COUNT(*) FROM Books_Meta 
            WHERE NOT (Publisher IS NULL AND City IS NULL)
            AND SearchPublisher IS NULL AND SearchCity IS NULL
        """)
        total_rows = cursor.fetchone()[0]
        print(f"Всего записей для обработки: {total_rows}")

        # Обрабатываем пачками
        batch_size = 10000
        offset = 0
        processed = 0

        while True:
            # Получаем данные пачками
            cursor.execute(f"""
                SELECT BookID, Publisher, City FROM Books_Meta 
                WHERE NOT (Publisher IS NULL AND City IS NULL)
                AND SearchPublisher IS NULL AND SearchCity IS NULL
                LIMIT {batch_size} OFFSET {offset}
            """)

            rows = cursor.fetchall()
            if not rows:
                break

            # Подготавливаем обновления
            updates = []
            for bookid, publisher, city in rows:
                publisher_upper = publisher.strip().upper() if publisher else '' #None
                city_upper = process_city(city) if city else '' #None
                updates.append((publisher_upper, city_upper, bookid))

            # Выполняем массовое обновление
            with conn:
                cursor.executemany(
                    "UPDATE Books_Meta SET SearchPublisher = ?, SearchCity = ? WHERE BookID = ?",
                    updates
                )

            conn.commit()

            processed += len(rows)
            offset += batch_size

            print(f"Обработано: {processed}/{total_rows} ({processed / total_rows * 100:.1f}%)")

            # Делаем паузу чтобы не перегружать систему
            #if processed % 100000 == 0:
            #    conn.commit()
            #    time.sleep(1)

        print(f"Успешно обновлено {processed} записей.")

    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
        conn.rollback()
    finally:
        # Восстанавливаем нормальные настройки
        cursor.execute("PRAGMA journal_mode = DELETE;")
        cursor.execute("PRAGMA synchronous = FULL;")
        conn.close()


def upper_search_in_db(db_path):
    """Очищает и обновляет года в базе данных"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Получаем данные для обработки
        cursor.execute("""
            SELECT BookID, Publisher, City FROM Books_Meta where not (Publisher is null and City is null )
               and SearchPublisher is null and SearchCity is null ;
"""
        )
        rows = cursor.fetchall()

        # Подготавливаем обновления
        updates = []
        for bookid, publisher, city  in rows:
            publisher_upper = publisher.upper() if publisher else None
            city_upper = city.upper() if city else None
            updates.append((publisher_upper, city_upper, bookid))

        # Выполняем массовое обновление в транзакции
        with conn:
            cursor.executemany(
                "UPDATE Books_Meta SET SearchPublisher = ?, SearchCity = ? WHERE BookID = ?",
                updates
            )

        print(f"Успешно обновлено {len(updates)} записей.")

    except sqlite3.Error as e:
        print(f"Ошибка базы данных: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    upper_search_in_db_batch(db_path=DB_PATH_META)