import sqlite3

def transfer_genres(source_db_path, target_db_path):
    """
    Переносит записи из таблицы genres одной БД в таблицу genres другой БД.
    Поле genreAlias преобразуется в верхний регистр и записывается в searchgenre.
    """
    try:
        # Подключаемся к исходной базе данных
        source_conn = sqlite3.connect(source_db_path)
        source_cursor = source_conn.cursor()

        # Подключаемся к целевой базе данных
        target_conn = sqlite3.connect(target_db_path)
        target_cursor = target_conn.cursor()

        # Выбираем все записи из таблицы genres исходной БД
        source_cursor.execute("SELECT GenreCode, ParentCode, FB2Code, GenreAlias FROM Genres")
        rows = source_cursor.fetchall()

        # Переносим записи в целевую БД
        for row in rows:
            GenreCode, ParentCode, FB2Code, GenreAlias = row
            SearchGenre = GenreAlias.upper()  # Преобразуем genreAlias в верхний регистр

            # Вставляем запись в целевую БД
            target_cursor.execute("""
                INSERT INTO genres (GenreCode, ParentCode, FB2Code, GenreAlias, SearchGenre)
                VALUES (?, ?, ?, ?, ?)
            """, (GenreCode, ParentCode, FB2Code, GenreAlias, SearchGenre))

        # Сохраняем изменения в целевой БД
        target_conn.commit()

        print(f"Перенос завершён. Перенесено {len(rows)} записей.")

    except sqlite3.Error as e:
        print(f"Ошибка при работе с базой данных: {e}")
    finally:
        # Закрываем соединения
        if source_conn:
            source_conn.close()
        if target_conn:
            target_conn.close()

def update_genres(target_db_path):
    """
    Копируем из поля GenreAlias в поле SearchGenre с преобразованием в верхний регистр
    :param target_db_path:
    :return:
    """
    # Подключаемся к целевой базе данных
    target_conn = sqlite3.connect(target_db_path)
    target_cursor = target_conn.cursor()

    # Выбираем все записи из таблицы genres исходной БД
    target_cursor.execute("SELECT GenreCode, GenreAlias FROM Genres")
    rows = target_cursor.fetchall()

    #обновляем записи в целевой БД
    for row in rows:
        GenreCode, GenreAlias = row
        SearchGenre = GenreAlias.upper()  # Преобразуем genreAlias в верхний регистр

        # Вставляем запись в целевую БД
        target_cursor.execute("""
            UPDATE Genres SET SearchGenre = ?
            WHERE GenreCode = ?
        """, (SearchGenre, GenreCode))

    # Сохраняем изменения в целевой БД
    target_conn.commit()

    print(f"Перенос завершён. обновлено {len(rows)} записей.")


# Пример использования
#source_db_path = "/media/sf_FlibustaRun/Data/Flibusta_FB2_local.hlc2"  # Путь к исходной базе данных
#target_db_path = "/media/sf_FlibustaBot/FlibustaAux.sqlite"  # Путь к целевой базе данных

#transfer_genres(source_db_path, target_db_path)

update_db_path = "/media/sf_FlibustaBot/Flibusta_FB2_local.hlc2"  # Путь к целевой базе данных
update_genres(update_db_path)