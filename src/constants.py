#import os

# Пути к базам данных и файлам
#CONNECT_DB_AUX = "/media/sf_FlibustaBot/FlibustaAux.sqlite"
#PREFIX_FILE_PATH = "/media/sf_FlibustaFiles/" #WEB
PREFIX_FILE_PATH = "./data"
#PREFIX_WORK_PATH = "/media/sf_FlibustaBot/"
#PREFIX_LOG_PATH = f"{PREFIX_WORK_PATH}/logs"
#PREFIX_TMP_PATH = f"{PREFIX_WORK_PATH}/tmp"
#DEFAULT_PATH_DB_BOOKS = "./data/Flibusta_FB2_local.hlc2"
#DEFAULT_PATH_DB_SETTINGS = "./data/FlibustaSettings.sqlite"
#DEFAULT_PATH_DB_LOGS = "./data/FlibustaLogs.sqlite"

FLIBUSTA_DB_BOOKS_PATH = f"{PREFIX_FILE_PATH}/Flibusta_FB2_local.hlc2"
FLIBUSTA_LOG_PATH = './logs'
FLIBUSTA_DB_SETTINGS_PATH = f"{PREFIX_FILE_PATH}/FlibustaSettings.sqlite"
FLIBUSTA_DB_LOGS_PATH = f"{PREFIX_FILE_PATH}/FlibustaLogs.sqlite"

# Максимальное количество книг для поиска, это же значение задано по умолчанию для поля UserSettings.MaxBooks
MAX_BOOKS_SEARCH = 20
#WEB
FLIBUSTA_BASE_URL = "https://flibusta.is"
DEFAULT_BOOK_FORMAT = 'fb2'  # По умолчанию формат не установлен

# Интервалы мониторинга загрузки и очистки ресурсов
# MONITORING_INTERVAL=1800 # каждые полчаса мониторим потребление памяти
CLEANUP_INTERVAL=3600 # каждый час очищаем старые сохранённые контексты поисков

# Критерии поиска: русское название -> поле в БД
SEARCH_CRITERIA = {
    "автор": "Author",
    "название": "SearchTitle",
    "жанр": "GenreUpper",
    "язык": "SearchLang",
    "серия": "SearchSeriesTitle",
    "год": "SearchYear",
    "город": "SearchCity",
    "издательство": "SearchPublisher",
    "рейтинг": "LibRate",
    "полный": "FullSearch"
}

# Регулярное выражение для извлечения критериев
CRITERIA_PATTERN_SERIES_QUOTED = r"(серия)\s*:\s*('[^']*'|\"[^\"]*\")"
CRITERIA_PATTERN = r"(автор|название|жанр|язык|серия|год|город|издательство|рейтинг|полный)\s*:\s*([^,;\n]+)"

# Константы для типов настроек
SETTING_MAX_BOOKS = 'max_books'
SETTING_LANG_SEARCH = 'lang_search'
SETTING_SORT_ORDER = 'sort_order'
SETTING_SIZE_LIMIT = 'size_limit'
SETTING_BOOK_FORMAT = 'book_format'
SETTING_SEARCH_TYPE = 'search_type'
# Константа для типа настройки рейтинга
SETTING_RATING_FILTER = 'rating_filter'

# Словарь соответствия setting_type -> заголовок
SETTING_TITLES = {
    SETTING_MAX_BOOKS: 'Вывод максимум:',
    SETTING_LANG_SEARCH: 'Язык книг:',
    SETTING_SORT_ORDER: 'Порядок сортировки по дате публикации:',
    SETTING_SIZE_LIMIT: 'Ограничение на размер книги:',
    SETTING_BOOK_FORMAT: 'Формат скачивания книг:',
    SETTING_SEARCH_TYPE: 'Тип поиска:',
    SETTING_RATING_FILTER: 'Фильтр по рейтингу:'
}

# Словарь опций для настроек
SETTING_OPTIONS = {
    SETTING_MAX_BOOKS: [
        (20, '20'),
        (40, '40')
    ],
    SETTING_SORT_ORDER: [
        ('asc', 'По возрастанию'),
        ('desc', 'По убыванию')
    ],
    SETTING_SIZE_LIMIT: [
        ('less800', '<800K'),
        ('more800', '>800K'),
        ('', 'Сбросить')
    ],
    SETTING_BOOK_FORMAT: [
        ('fb2', 'FB2'),
        ('mobi', 'MOBI'),
        ('epub', 'EPUB')
    ],
    SETTING_SEARCH_TYPE: [
        ('books', 'По книгам'),
        ('series', 'По сериям')
    ],
    SETTING_RATING_FILTER: [
        (0, '⚪️ Без рейтинга (0)'),
        (1, '🔴 Нечитаемо (1)'),
        (2, '🟠 Плохо (2)'),
        (3, '🟡 Неплохо (3)'),
        (4, '🟢 Хорошо (4)'),
        (5, '🔵 Отлично (5)')
    ]
}

# Рейтинги книг с эмодзи
BOOK_RATINGS = {
    0: ("⚪️", "Без рейтинга (0)"),
    1: ("🔴", "Нечитаемо (1)"),
    2: ("🟠", "Плохо (2)"),
    3: ("🟡", "Неплохо (3)"),
    4: ("🟢", "Хорошо (4)"),
    5: ("🔵", "Отлично (5)")
}

# Путь к файлу с новостями (теперь Python файл)
BOT_NEWS_FILE_PATH = "./data/bot_news.py"

