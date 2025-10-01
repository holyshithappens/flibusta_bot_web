import sqlite3
import re
from collections import Counter

# Подключение к базе данных
def connect_to_db(db_path):
    conn = sqlite3.connect(db_path)
    return conn

# Функция для разделения строк на слова
def split_into_words(text):
    # Используем регулярное выражение для разделения строки на слова
    words = re.findall(r'\b\w+\b', text.lower())  # Приводим к нижнему регистру
    return words

# Основная функция для обработки данных
def process_titles(db_path):
    conn = connect_to_db(db_path)
    cursor = conn.cursor()

    # Выбираем все заголовки из таблицы Books
    #cursor.execute("SELECT SearchTitle FROM Books")
    cursor.execute("SELECT SearchName FROM Authors")
    titles = cursor.fetchall()

    # Собираем все слова в один список
    all_words = []
    for title in titles:
        if title[0]:  # Проверяем, что заголовок не пустой
            words = split_into_words(title[0])
            all_words.extend(words)

    # Подсчитываем количество каждого слова
    word_counts = Counter(all_words)

    # Сортируем слова по количеству (по убыванию)
    sorted_word_counts = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)

    # Выводим результаты
    for word, count in sorted_word_counts:
        print(f"{word}: {count}")

    # Закрываем соединение с базой данных
    conn.close()

# Путь к базе данных
db_path = '/media/sf_FlibustaBot/Flibusta_FB2_local.hlc2'

# Запуск обработки
process_titles(db_path)