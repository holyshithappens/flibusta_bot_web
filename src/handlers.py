import os
import zipfile
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import TimedOut, BadRequest
from telegram.ext import CallbackContext, ConversationHandler

from database import DatabaseBooks, DatabaseSettings
from constants import FLIBUSTA_BASE_URL, DEFAULT_BOOK_FORMAT, BOT_NEWS, \
    SETTING_MAX_BOOKS, SETTING_LANG_SEARCH, SETTING_SORT_ORDER, SETTING_SIZE_LIMIT, \
    SETTING_BOOK_FORMAT, SETTING_SEARCH_TYPE, SETTING_OPTIONS, SETTING_TITLES
from utils import format_size, extract_cover_from_fb2, extract_metadata_from_fb2, format_metadata_message, \
    get_platform_recommendations, download_book_with_filename, upload_to_tmpfiles
from logger import logger


DB_BOOKS = DatabaseBooks()
DB_SETTINGS = DatabaseSettings()

BOOKS = 'BOOKS'
PAGES_OF_BOOKS = 'PAGES_OF_BOOKS'
FOUND_BOOKS_COUNT = 'FOUND_BOOKS_COUNT'
USER_PARAMS = 'USER_PARAMS'
SERIES = 'SERIES'
PAGES_OF_SERIES = 'PAGES_OF_SERIES'
FOUND_SERIES_COUNT = 'FOUND_SERIES_COUNT'

CONTACT_INFO = {'email': os.getenv("FEEDBACK_EMAIL", "не указан"), 'pikabu': os.getenv("FEEDBACK_PIKABU", ""),
                'pikabu_username': os.getenv("FEEDBACK_PIKABU_USERNAME", "не указан")}

SEARCH_CONTEXT = 'SEARCH_CONTEXT'
SEARCH_TYPE_BOOKS = 'books'
SEARCH_TYPE_SERIES = 'series'

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====

def create_back_button() -> list:
    """Создает кнопку возврата в настройки"""
    return [[InlineKeyboardButton("⬅ Назад в настройки", callback_data="back_to_settings")]]


def form_header_books(page, max_books, found_count, search_type='книг', series_name=None):
    # return f"Показываю с {max_books * page + 1} по {min(max_books * (page + 1), found_count)} из {found_count} найденных {search_type}:"
    start = max_books * page + 1
    end = min(max_books * (page + 1), found_count)

    header = f"Показываю с {start} по {end} из {found_count} найденных {search_type}"

    if series_name:
        header += f" в серии '{series_name}'"

    return header


def create_books_keyboard(page, pages_of_books, search_context=SEARCH_TYPE_BOOKS):
    # reply_markup = None
    keyboard = []

    if pages_of_books:
        books_in_page = pages_of_books[page]

        if books_in_page:
            # keyboard = []
            for book in books_in_page:
                text = f"{book.Title} ({book.LastName} {book.FirstName}) {format_size(book.BookSize)}/{book.Genre}"
                if book.SearchYear != 0:
                    text += f"/{str(book.SearchYear)}"
                keyboard.append([InlineKeyboardButton(
                    text,
                    callback_data=f"send_file:{book.Folder}:{book.FileName}:{book.Ext}"
                )])

            # Добавляем кнопки для навигации
            navigation_buttons = []
            if page > 0:
                navigation_buttons.append(InlineKeyboardButton("⬆ В начало", callback_data=f"page_0"))
                navigation_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"page_{page - 1}"))
            if page < len(pages_of_books) - 1:
                navigation_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"page_{page + 1}"))
                navigation_buttons.append(InlineKeyboardButton("В конец ⬇️️️", callback_data=f"page_{len(pages_of_books) - 1}"))
            if navigation_buttons:
                keyboard.append(navigation_buttons)

            # Добавляем кнопку "Назад к сериям" только при поиске по сериям
            if search_context == SEARCH_TYPE_SERIES:
                keyboard.append([InlineKeyboardButton("⤴️ Назад к сериям", callback_data="back_to_series")])

            # reply_markup = InlineKeyboardMarkup(keyboard)

    # return reply_markup
    return keyboard


def create_series_keyboard(page, pages_of_series):
    # reply_markup = None
    keyboard = []

    if pages_of_series:
        series_in_page = pages_of_series[page]

        if series_in_page:
            # keyboard = []
            for idx, (series_name, search_series, book_count) in enumerate(series_in_page):
                text = f"{series_name} ({book_count})"
                keyboard.append([InlineKeyboardButton(
                    text,
                    callback_data=f"show_series:{page}:{idx}"
                )])

            # Добавляем кнопки для навигации
            navigation_buttons = []
            if page > 0:
                navigation_buttons.append(InlineKeyboardButton("⬆ В начало", callback_data=f"series_page_0"))
                navigation_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"series_page_{page - 1}"))
            if page < len(pages_of_series) - 1:
                navigation_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"series_page_{page + 1}"))
                navigation_buttons.append(
                    InlineKeyboardButton("В конец ⬇️️️", callback_data=f"series_page_{len(pages_of_series) - 1}"))
            if navigation_buttons:
                keyboard.append(navigation_buttons)

            # reply_markup = InlineKeyboardMarkup(keyboard)

    return keyboard


async def edit_or_reply_message(query, text, reply_markup=None):
    """Редактирует существующее сообщение или отправляет новое"""
    if hasattr(query.message, 'message_id'):
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await query.message.reply_text(text, reply_markup=reply_markup)


async def process_book_download(query, book_id, book_format, file_name, file_ext):
    """Обрабатывает скачивание и отправку книги"""
    processing_msg = await query.message.reply_text(
        "⏰ <i>Ожидайте, отправляю книгу...</i>",
        parse_mode=ParseMode.HTML,
        disable_notification=True
    )

    try:
        url = f"{FLIBUSTA_BASE_URL}/b/{book_id}/{book_format}"
        book_data, original_filename = await download_book_with_filename(url)
        public_filename = original_filename if original_filename else f"{book_id}.{book_format}"

        if book_data:
            if book_format == DEFAULT_BOOK_FORMAT:
                await extract_and_send_metadata(book_data, query)

            await query.message.reply_document(
                document=book_data,
                filename=public_filename,
                disable_notification=True
            )
        else:
            await query.message.reply_text(
                "😞 Не удалось скачать книгу в этом формате",
                disable_notification=True
            )

        await processing_msg.delete()
        return public_filename

    except TimedOut:
        await handle_timeout_error(processing_msg, book_data, file_name, file_ext, query)
    except Exception as e:
        #await handle_download_error(processing_msg, url, e, query)
        """Обрабатывает ошибку загрузки"""
        print(f"Общая ошибка при отправке книги: {e}")
        await processing_msg.edit_text(
            f"❌ Произошла ошибка при подготовке книги {url}. Возможно она доступна только в локальной базе"
        )
        logger.log_user_action(query.from_user.id, "error sending book direct", url)

    return None


async def extract_and_send_metadata(book_data, query):
    """Извлекает и отправляет метаданные книги"""
    with zipfile.ZipFile(BytesIO(book_data), 'r') as zip_file:
        for file_info in zip_file.infolist():
            file_data = zip_file.read(file_info.filename)
            file_io = BytesIO(file_data)
            file_io.seek(0)

            cover_bytes = extract_cover_from_fb2(file_io)
            metadata = extract_metadata_from_fb2(file_io)
            caption = format_metadata_message(metadata)

            if cover_bytes:
                await query.message.reply_photo(
                    photo=cover_bytes,
                    caption=caption or "",
                    disable_notification=True
                )
            elif caption:
                await query.message.reply_text(caption, disable_notification=True)


async def handle_timeout_error(processing_msg, book_data, file_name, file_ext, query):
    """Обрабатывает ошибку таймаута"""
    await processing_msg.edit_text(
        "⏳ Книга большая, использую внешний сервис...",
        parse_mode=ParseMode.HTML
    )

    try:
        download_url = await upload_to_tmpfiles(book_data, f"{file_name}{file_ext}")
        if download_url:
            direct_download_url = download_url.replace(
                "https://tmpfiles.org/",
                "https://tmpfiles.org/dl/",
                1
            )
            message = (
                f"<a href='{direct_download_url}'>📥 Скачать книгу</a>\n"
                "⏳ Ссылка действительна 15 минут"
            )
            await query.message.reply_text(
                text=message,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
                disable_notification=True
            )
    except Exception as upload_error:
        print(f"Ошибка загрузки на tmpfiles: {upload_error}")
        await processing_msg.edit_text("❌ Не удалось отправить книгу. Попробуйте позже.")
        logger.log_user_action(query.from_user.id, "error sending book cloud", f"{file_name}{file_ext}")


# ===== ОСНОВНЫЕ ОБРАБОТЧИКИ КОМАНД =====

async def start_cmd(update: Update, context: CallbackContext):
    """Обработка команды /start с deep linking"""
    user = update.effective_user

    # Сохраняем настройки пользователя
    user_params = DB_SETTINGS.get_user_settings(user.id)
    context.user_data[USER_PARAMS] = user_params

    #Вывод приглашения и помощи по поиску книг
    welcome_text = """
📚 <b>Привет! Я помогу тебе искать и скачивать книги непосредственно из библиотеки Флибуста.</b> 

<u>Управление</u>
<code>/news</code> - новости и обновления бота
<code>/about</code> - информация о боте и библиотеке 
<code>/help</code> - помощь в составлении поисковых запросов
<code>/genres</code> - посмотреть доступные жанры
<code>/langs</code> - посмотреть доступные языки книг по убыванию их количества
<code>/set</code> - установка настроек поиска и вывода книг
<code>/donate</code> - поддержать разработчика
    """
    await update.message.reply_text(welcome_text, parse_mode='HTML')

    user = update.message.from_user
    user_params = DB_SETTINGS.get_user_settings(user.id)
    context.user_data[USER_PARAMS] = user_params

    logger.log_user_action(user, "started bot")


async def genres_cmd(update: Update, context: CallbackContext):
    """Показывает родительские жанры"""
    results = DB_BOOKS.get_parent_genres()
    keyboard = [[InlineKeyboardButton(genre[0], callback_data=f"show_genres:{genre[0]}")] for genre in results]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Посмотреть жанры:", reply_markup=reply_markup)

    user = update.message.from_user
    logger.log_user_action(user, "viewed parent genres")


async def langs_cmd(update: Update, context: CallbackContext):
    """Показывает доступные языки"""
    results = DB_BOOKS.get_langs()
    langs = ", ".join([f"<code>{lang[0].strip()}</code>" for lang in results])
    await update.message.reply_text(
        langs,
        parse_mode=ParseMode.HTML,
        disable_notification=True
    )

    user = update.message.from_user
    logger.log_user_action(user, "viewed langs of books")


def create_settings_menu():
    """Создает главное меню настроек"""
    settings = [
        ("Ограничение максимального вывода", SETTING_MAX_BOOKS),
        ("Язык поиска книг", SETTING_LANG_SEARCH),
        ("Сортировку выдачи", SETTING_SORT_ORDER),
        ("Ограничение на размер книг", SETTING_SIZE_LIMIT),
        ("Формат скачивания книг", SETTING_BOOK_FORMAT),
        ("Тип поиска (книги/серии)", SETTING_SEARCH_TYPE),
    ]

    keyboard = [[InlineKeyboardButton(text, callback_data=f"set_{key}")] for text, key in settings]
    return InlineKeyboardMarkup(keyboard)


async def show_settings_menu(update_or_query, context, from_callback=False):
    """Показывает главное меню настроек"""
    reply_markup = create_settings_menu()

    if from_callback:
        await update_or_query.edit_message_text("Настроить:", reply_markup=reply_markup)
        user = update_or_query.from_user
    else:
        await update_or_query.message.reply_text("Настроить:", reply_markup=reply_markup)
        user = update_or_query.message.from_user

    logger.log_user_action(user, "showed settings menu")


async def handle_back_to_series(query, context, action, params):
    """Возвращает к результатам поиска серий"""
    try:
        # Восстанавливаем последнюю позицию
        page_num = context.user_data.get('last_series_page', 0)

        pages_of_series = context.user_data.get(PAGES_OF_SERIES)
        if not pages_of_series:
            await query.edit_message_text("❌ Не удалось восстановить результаты поиска")
            return

        keyboard = create_series_keyboard(page_num, pages_of_series)
        reply_markup = InlineKeyboardMarkup(keyboard)

        if reply_markup:
            found_series_count = context.user_data.get(FOUND_SERIES_COUNT)
            user_params = context.user_data.get(USER_PARAMS)
            header_found_text = form_header_books(page_num, user_params.MaxBooks, found_series_count, 'серий')
            await query.edit_message_text(header_found_text, reply_markup=reply_markup)
        else:
            await query.edit_message_text("❌ Не удалось восстановить результаты поиска")

    except Exception as e:
        print(f"Ошибка при возврате к сериям: {e}")
        await query.edit_message_text("❌ Ошибка при возврате к результатам поиска")


async def handle_back_to_settings(query, context, action, params):
    """Возвращает в главное меню настроек"""
    await show_settings_menu(query, context, from_callback=True)


async def settings_cmd(update: Update, context: CallbackContext):
    """Показывает главное меню настроек"""
    await show_settings_menu(update, context, from_callback=False)



async def handle_message(update: Update, context: CallbackContext):
    """Обрабатывает текстовые сообщения (поиск книг или серий)"""
    search_type = context.user_data.get(SETTING_SEARCH_TYPE, 'books')

    if search_type == 'series':
        await handle_search_series(update, context)
    else:
        await handle_search_books(update, context)


async def handle_search_books(update: Update, context: CallbackContext):
    """Обрабатывает текстовые сообщения (поиск книг)"""
    query = update.message.text
    user = update.message.from_user

    processing_msg = await update.message.reply_text(
        "⏰ <i>Ищу книги, ожидайте...</i>",
        parse_mode=ParseMode.HTML,
        disable_notification=True
    )

    size_limit = context.user_data.get(SETTING_SIZE_LIMIT)
    user_params = DB_SETTINGS.get_user_settings(user.id)
    context.user_data[USER_PARAMS] = user_params
    context.user_data[SEARCH_CONTEXT] = SEARCH_TYPE_BOOKS  # Сохраняем контекст

    books, found_books_count = DB_BOOKS.search_books(
        query, user_params.MaxBooks, user_params.Lang,
        user_params.DateSortOrder, size_limit
    )

    # Проверяем, найдены ли книги
    if books or found_books_count > 0:
        pages_of_books = [books[i:i + user_params.MaxBooks] for i in range(0, len(books), user_params.MaxBooks)]

        await processing_msg.delete()

        page = 0
        keyboard = create_books_keyboard(page, pages_of_books)
        reply_markup = InlineKeyboardMarkup(keyboard)
        if reply_markup:
            header_found_text = form_header_books(page, user_params.MaxBooks, found_books_count)
            await update.message.reply_text(header_found_text, reply_markup=reply_markup)

        context.user_data[BOOKS] = books
        context.user_data[PAGES_OF_BOOKS] = pages_of_books
        context.user_data[FOUND_BOOKS_COUNT] = found_books_count
    else:
        await update.message.reply_text("😞 Не нашёл подходящих книг. Попробуйте другие критерии поиска")

    logger.log_user_action(user, "searched for books", f"{query}; count:{found_books_count}")


async def handle_search_series(update: Update, context: CallbackContext):
    """Обрабатывает текстовые сообщения (поиск книг)"""
    query_text = update.message.text
    user = update.message.from_user

    processing_msg = await update.message.reply_text(
        "⏰ <i>Ищу книжные серии, ожидайте...</i>",
        parse_mode=ParseMode.HTML,
        disable_notification=True
    )

    size_limit = context.user_data.get(SETTING_SIZE_LIMIT)
    user_params = DB_SETTINGS.get_user_settings(user.id)
    context.user_data[USER_PARAMS] = user_params
    context.user_data[SEARCH_CONTEXT] = SEARCH_TYPE_SERIES  # Сохраняем контекст

    # Ищем серии
    series, found_series_count = DB_BOOKS.search_series(
        query_text, user_params.MaxBooks, user_params.Lang, size_limit
    )

    if series or found_series_count > 0:
        pages_of_series = [series[i:i + user_params.MaxBooks] for i in range(0, len(series), user_params.MaxBooks)]

        await processing_msg.delete()

        page = 0
        keyboard = create_series_keyboard(page, pages_of_series)
        reply_markup = InlineKeyboardMarkup(keyboard)

        if reply_markup:
            header_found_text = form_header_books(page, user_params.MaxBooks, found_series_count, 'серий')
            await update.message.reply_text(header_found_text, reply_markup=reply_markup)

        context.user_data[SERIES] = series
        context.user_data[PAGES_OF_SERIES] = pages_of_series
        context.user_data[FOUND_SERIES_COUNT] = found_series_count
        context.user_data['series_search_query'] = query_text  # Сохраняем поисковый запрос
        context.user_data['last_series_page'] = page  # Сохраняем текущую страницу
    else:
        await update.message.reply_text("😞 Не нашёл подходящих книжных серий. Попробуйте другие критерии поиска")

    logger.log_user_action(user, "searched for series", f"{query_text}; count:{found_series_count}")


async def handle_search_series_books(query, context, action, params):
    """Показывает книги выбранной серии"""
    try:
        page_num = int(params[0])
        series_idx = int(params[1])

        # Получаем серию из контекста
        pages_of_series = context.user_data.get(PAGES_OF_SERIES)
        if not pages_of_series or page_num >= len(pages_of_series) or series_idx >= len(pages_of_series[page_num]):
            await query.edit_message_text("❌ Ошибка: не удалось найти серию")
            return

        series_name, search_series_name, book_count = pages_of_series[page_num][series_idx]
        context.user_data['current_series_name'] = series_name  # Сохраняем название серии

        user = query.from_user
        user_params = DB_SETTINGS.get_user_settings(user.id)
        size_limit = context.user_data.get(SETTING_SIZE_LIMIT)

        # Ищем книги серии в комбинации с предыдущим запросом
        query_text = f"{context.user_data['series_search_query']}, серия: '{search_series_name}'"
        #query_text = f"серия: '{search_series_name}'"

        # #debug
        # print(query_text)

        books, found_books_count = DB_BOOKS.search_books(
            query_text, user_params.MaxBooks, user_params.Lang,
            user_params.DateSortOrder, size_limit
        )

        if books:
            pages_of_books = [books[i:i + user_params.MaxBooks] for i in range(0, len(books), user_params.MaxBooks)]
            context.user_data[BOOKS] = books
            context.user_data[PAGES_OF_BOOKS] = pages_of_books
            context.user_data[FOUND_BOOKS_COUNT] = found_books_count

            page = 0
            keyboard = create_books_keyboard(page, pages_of_books, SEARCH_TYPE_SERIES)

            # Добавляем кнопку возврата к сериям
            if keyboard:
                # keyboard.append([InlineKeyboardButton("⬅ Назад к сериям", callback_data="back_to_series")])
                reply_markup = InlineKeyboardMarkup(keyboard)

                # header_text = f"Книги серии '{series_name}' ({book_count}):"
                header_text = form_header_books(page, user_params.MaxBooks, found_books_count, 'книг', series_name)
                await query.edit_message_text(header_text, reply_markup=reply_markup)
        else:
            await query.edit_message_text(f"Не найдено книг в серии '{series_name}'")

    except (ValueError, IndexError) as e:
        print(f"Ошибка при обработке серии: {e}")
        await query.edit_message_text("❌ Ошибка при загрузке серии")


# ===== УНИФИЦИРОВАННЫЕ ФУНКЦИИ ДЛЯ НАСТРОЕК =====

def create_settings_keyboard(setting_type, current_value, options):
    """
    Создает клавиатуру для настроек с галочками и кнопкой назад
    :param setting_type: тип настройки (для callback_data)
    :param current_value: текущее значение настройки
    :param options: список опций в формате [(value, display_text), ...]
    """
    keyboard = []

    if setting_type == SETTING_LANG_SEARCH:
        # Особый случай для языка - добавляем кнопку сброса
        if current_value:
            keyboard.append([
                InlineKeyboardButton(
                    f"✔ {current_value} - сбросить",
                    callback_data=f"set_{setting_type}_to_"
                )
            ])

        # Создаем кнопки языков
        buttons = []
        for value, display_text in options:
            buttons.append(InlineKeyboardButton(
                f"{display_text}",
                callback_data=f"set_{setting_type}_to_{value}"
            ))

        # Группируем по 8 кнопок в строку
        keyboard.extend([buttons[i:i + 8] for i in range(0, len(buttons), 8)])

    else:
        # Для остальных настроек - кнопки в строку
        row = []
        for value, display_text in options:
            row.append(InlineKeyboardButton(
                f"{'✔️ ' if str(value) == str(current_value) else ''}{display_text}",
                callback_data=f"set_{setting_type}_to_{value}"
            ))
        keyboard.append(row)

    # Добавляем кнопку "Назад"
    keyboard += create_back_button()

    return InlineKeyboardMarkup(keyboard)


# ===== ОБРАБОТЧИКИ CALLBACK =====

async def button_callback(update: Update, context: CallbackContext):
    """УНИВЕРСАЛЬНЫЙ обработчик callback-запросов"""
    query = update.callback_query
    user = query.from_user
    user_params = DB_SETTINGS.get_user_settings(user.id)
    context.user_data[USER_PARAMS] = user_params

    await query.answer()

    data = query.data.split(':')
    action, *params = data

    # Сначала проверяем АДМИНСКИЕ действия
    if action in ['users_list', 'user_detail', 'toggle_block', 'recent_searches',
                 'recent_downloads', 'top_downloads', 'top_searches', 'back_to_stats',
                 'refresh_stats']:
        # Перенаправляем в админский обработчик
        from admin import handle_admin_callback
        await handle_admin_callback(update, context)
        return

    # Затем проверяем ПОЛЬЗОВАТЕЛЬСКИЕ действия
    action_handlers = {
        'send_file': handle_send_file,
        'show_genres': handle_show_genres,
        'back_to_settings': handle_back_to_settings,
        f'set_{SETTING_MAX_BOOKS}': handle_set_max_books,
        f'set_{SETTING_LANG_SEARCH}': handle_set_lang_search,
        f'set_{SETTING_SORT_ORDER}': handle_set_sort_order,
        f'set_{SETTING_SIZE_LIMIT}': handle_set_size_limit,
        f'set_{SETTING_BOOK_FORMAT}': handle_set_book_format,
        f'set_{SETTING_SEARCH_TYPE}': handle_set_search_type,
        'show_series': handle_search_series_books,
        'back_to_series': handle_back_to_series,
    }

    # Прямой поиск обработчика в словаре
    if action in action_handlers:
        handler = action_handlers[action]
        await handler(query, context, action, params)
        return

    # Затем проверяем префиксы
    if action.startswith('page_'):
        await handle_page_change(query, context, action, params)
        return

    if action.startswith('series_page_'):
        await handle_series_page_change(query, context, action, params)
        return

    # Обработка set_ действий
    if action.startswith('set_'):
        await handle_set_actions(query, context, action, params)
        return

    # Если ничего не найдено
    print(f"Unknown action: {action}")
    await query.edit_message_text("❌ Неизвестное действие")

async def handle_send_file(query, context, action, params):
    """Обрабатывает отправку файла"""
    file_path, file_name, file_ext = params
    book_id = file_name
    user_params = context.user_data.get(USER_PARAMS)
    book_format = user_params.BookFormat or DEFAULT_BOOK_FORMAT

    public_filename = await process_book_download(query, book_id, book_format, file_name, file_ext)

    log_detail = f"{file_name}{file_ext}"
    log_detail += ":" + public_filename if public_filename else ""
    logger.log_user_action(query.from_user, "send file", log_detail)


async def handle_show_genres(query, context, action, params):
    """Показывает жанры выбранной категории"""
    parent_genre = params[0]
    genres = DB_BOOKS.get_genres(parent_genre)

    if genres:
        genres_html = f"<b><code>{parent_genre}</code></b>\n\n"
        for genre in genres:
            genres_html += f"<code>{genre}</code>\n"
        await query.message.reply_text(genres_html, parse_mode=ParseMode.HTML)
    else:
        await query.message.reply_text("❌ Жанры не найдены для этой категории", parse_mode=ParseMode.HTML)

    logger.log_user_action(query.from_user, "show genre", parent_genre)


# ===== ОБНОВЛЕННЫЕ ОБРАБОТЧИКИ НАСТРОЕК =====

async def handle_set_max_books(query, context, action, params):
    """Показывает настройки максимального вывода"""
    user_params = DB_SETTINGS.get_user_settings(query.from_user.id)
    current_value = user_params.MaxBooks

    options = SETTING_OPTIONS[SETTING_MAX_BOOKS]
    reply_markup = create_settings_keyboard(SETTING_MAX_BOOKS, current_value, options)

    await edit_or_reply_message(query, SETTING_TITLES[SETTING_MAX_BOOKS], reply_markup)
    logger.log_user_action(query.from_user, "showed max books setting for user")


async def handle_set_lang_search(query, context, action, params):
    """Показывает настройки языка поиска"""
    user_params = DB_SETTINGS.get_user_settings(query.from_user.id)
    current_value = user_params.Lang

    # Получаем языки из БД и преобразуем в нужный формат
    langs = DB_BOOKS.get_langs()
    options = [(lang[0], lang[0]) for lang in langs if lang[0]]

    reply_markup = create_settings_keyboard(SETTING_LANG_SEARCH, current_value, options)

    await edit_or_reply_message(query, SETTING_TITLES[SETTING_LANG_SEARCH], reply_markup)
    logger.log_user_action(query.from_user, "showed langs of books setting for user")


async def handle_set_sort_order(query, context, action, params):
    """Показывает настройки сортировки"""
    user_params = DB_SETTINGS.get_user_settings(query.from_user.id)
    current_value = user_params.DateSortOrder

    options = SETTING_OPTIONS[SETTING_SORT_ORDER]
    reply_markup = create_settings_keyboard(SETTING_SORT_ORDER, current_value, options)

    await edit_or_reply_message(query, SETTING_TITLES[SETTING_SORT_ORDER], reply_markup)
    logger.log_user_action(query.from_user, "showed sort order setting for user")


async def handle_set_size_limit(query, context, action, params):
    """Показывает настройки ограничения размера"""
    current_value = context.user_data.get('size_limit', '')

    options = SETTING_OPTIONS[SETTING_SIZE_LIMIT]
    reply_markup = create_settings_keyboard(SETTING_SIZE_LIMIT, current_value, options)

    await edit_or_reply_message(query, SETTING_TITLES[SETTING_SIZE_LIMIT], reply_markup)
    logger.log_user_action(query.from_user, "showed size limit setting for user")


async def handle_set_book_format(query, context, action, params):
    """Показывает настройки формата книг"""
    user_params = DB_SETTINGS.get_user_settings(query.from_user.id)
    current_value = user_params.BookFormat

    options = SETTING_OPTIONS[SETTING_BOOK_FORMAT]
    reply_markup = create_settings_keyboard(SETTING_BOOK_FORMAT, current_value, options)

    await edit_or_reply_message(query, SETTING_TITLES[SETTING_BOOK_FORMAT], reply_markup)
    logger.log_user_action(query.from_user, "showed book format setting for user")


async def handle_set_search_type(query, context, action, params):
    """Показывает настройки типа поиска"""
    current_value = context.user_data.get(SETTING_SEARCH_TYPE, 'books')

    options = SETTING_OPTIONS[SETTING_SEARCH_TYPE]
    reply_markup = create_settings_keyboard(SETTING_SEARCH_TYPE, current_value, options)

    await edit_or_reply_message(query, SETTING_TITLES[SETTING_SEARCH_TYPE], reply_markup)
    logger.log_user_action(query.from_user, "showed search type setting")


async def handle_page_change(query, context, action, params):
    """Обрабатывает смену страницы"""
    page = int(action.removeprefix('page_'))
    pages_of_books = context.user_data.get(PAGES_OF_BOOKS)
    # Определяем контекст поиска
    search_context = context.user_data.get(SEARCH_CONTEXT, SEARCH_TYPE_BOOKS)
    keyboard = create_books_keyboard(page, pages_of_books, search_context)
    reply_markup = InlineKeyboardMarkup(keyboard)

    if reply_markup:
        found_books_count = context.user_data.get(FOUND_BOOKS_COUNT)
        user_params = context.user_data.get(USER_PARAMS)
        # Формируем заголовок в зависимости от контекста
        series_name = None
        if search_context == SEARCH_TYPE_SERIES:
            series_name = context.user_data.get('current_series_name', None)
        header_text = form_header_books(page, user_params.MaxBooks, found_books_count, 'книг', series_name)
        await query.edit_message_text(header_text, reply_markup=reply_markup)

    logger.log_user_action(query.from_user, "changed page of books", page)


async def handle_series_page_change(query, context, action, params):
    """Обрабатывает смену страницы"""
    page = int(action.removeprefix('series_page_'))
    pages_of_series = context.user_data.get(PAGES_OF_SERIES)
    keyboard = create_series_keyboard(page, pages_of_series)
    reply_markup = InlineKeyboardMarkup(keyboard)

    if reply_markup:
        found_series_count = context.user_data.get(FOUND_SERIES_COUNT)
        user_params = context.user_data.get(USER_PARAMS)
        header_found_text = form_header_books(page, user_params.MaxBooks, found_series_count)
        await query.edit_message_text(header_found_text, reply_markup=reply_markup)

    context.user_data['last_series_page'] = page  # Сохраняем текущую страницу

    logger.log_user_action(query.from_user, "changed page of series", page)


# ===== ОБНОВЛЕННЫЙ ОБРАБОТЧИК SET_ACTIONS =====

async def handle_set_actions(query, context, action, params):
    """Обрабатывает все set_ действия"""
    user = query.from_user

    # Определяем тип настройки из action
    if action.startswith(f'set_{SETTING_MAX_BOOKS}_to_'):
        setting_type = SETTING_MAX_BOOKS
        new_value = int(action.removeprefix(f'set_{SETTING_MAX_BOOKS}_to_'))
        DB_SETTINGS.update_user_settings(user.id, maxbooks=new_value)

    elif action.startswith(f'set_{SETTING_LANG_SEARCH}_to_'):
        setting_type = SETTING_LANG_SEARCH
        new_value = action.removeprefix(f'set_{SETTING_LANG_SEARCH}_to_')
        DB_SETTINGS.update_user_settings(user.id, lang=new_value)

    elif action.startswith(f'set_{SETTING_SORT_ORDER}_to_'):
        setting_type = SETTING_SORT_ORDER
        new_value = action.removeprefix(f'set_{SETTING_SORT_ORDER}_to_')
        DB_SETTINGS.update_user_settings(user.id, datesortorder=new_value)

    elif action.startswith(f'set_{SETTING_SIZE_LIMIT}_to_'):
        setting_type = SETTING_SIZE_LIMIT
        new_value = action.removeprefix(f'set_{SETTING_SIZE_LIMIT}_to_')
        context.user_data[SETTING_SIZE_LIMIT] = new_value

    elif action.startswith(f'set_{SETTING_BOOK_FORMAT}_to_'):
        setting_type = SETTING_BOOK_FORMAT
        new_value = action.removeprefix(f'set_{SETTING_BOOK_FORMAT}_to_')
        DB_SETTINGS.update_user_settings(user.id, BookFormat=new_value)

    elif action.startswith(f'set_{SETTING_SEARCH_TYPE}_to_'):
        setting_type = SETTING_SEARCH_TYPE
        new_value = action.removeprefix(f'set_{SETTING_SEARCH_TYPE}_to_')
        context.user_data[SETTING_SEARCH_TYPE] = new_value

    else:
        return

    # Обновляем контекст пользователя
    if setting_type != SETTING_SEARCH_TYPE and setting_type != SETTING_SIZE_LIMIT:
        context.user_data[USER_PARAMS] = DB_SETTINGS.get_user_settings(user.id)

    # Создаем обновленную клавиатуру
    if setting_type == 'lang_search':
        langs = DB_BOOKS.get_langs()
        options = [(lang[0], lang[0]) for lang in langs if lang[0]]
    else:
        options = SETTING_OPTIONS[setting_type]

    reply_markup = create_settings_keyboard(setting_type, new_value, options)

    # Debug
    print(f"{setting_type} {new_value}")

    # Обновляем сообщение
    try:
        await query.edit_message_text(SETTING_TITLES[setting_type], reply_markup=reply_markup)
    except BadRequest as e:
        if "Message is not modified" not in str(e):
            raise e
    # else: игнорируем ошибку "не изменено"

    # Логируем действие
    logger.log_user_action(user, f"set {setting_type} to {new_value}")


# ===== ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ =====

async def donate_cmd(update: Update, context: CallbackContext):
    """Команда /donate с HTML сообщением"""
    addresses = {
        '₿ Bitcoin (BTC)': os.getenv('DONATE_BTC'),
        'Ξ Ethereum & Poligon (ETH & POL)': os.getenv('DONATE_ETH'),
        '◎ Solana (SOL & USDC)': os.getenv('DONATE_SOL'),
        '🔵 Sui (SUI)': os.getenv('DONATE_SUI'),
        '₮ Toncoin (TON & USDT)': os.getenv('DONATE_TON'),
        '🔴 Tron (TRX & USDT)': os.getenv('DONATE_TRX')
    }

    donate_html = "💰 <b>Поддержать разработчика крипто-копеечкой</b>"
    for crypto_name, address in addresses.items():
        if address:
            donate_html += f"\n{crypto_name}:\n<code>{address}</code>\n"

    await update.message.reply_text(
        donate_html,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

    user = update.message.from_user
    logger.log_user_action(user, "viewed donate page")


async def help_cmd(update: Update, context: CallbackContext):
    """Команда помощи со списком всех команд"""
    help_text = """
    <b>Помощь в поиске книг.</b>

    📚 <i>Запрос может содержать слова из ФИО автора, названия книги, её жанра, серии и языка. В слове можно указывать символ % для подмены любого количества символов.</i> 
    <u>Обычный поиск:</u>
    ✏️ <code>Лев Толстой Война и мир</code>
    ✏️ <code>фантастика звёзды</code>
    ✏️ <code>harry potter fr</code>
    ✏️ <code>математич%</code>

    <i>Есть вариант более быстрого поиска по отдельным критериям: названию книги, автору, жанру, серии, году издания. Комбинировать критерии можно, например, через запятую. В одном критерии можно комбинировать слова через символ |</i>
    <u>Поиск по критериям:</u>
    🔎 <code>название: =психология</code>
    🔎 <code>название: монах|монаш|монастыр</code>
    🔎 <code>автор: Лев Толстой, название: !Война, язык: ru</code>
    🔎 <code>автор: Лукьяненко, жанр: !фантастика</code>
    🔎 <code>серия: жизнь замечательных людей, год: -1991</code>

    <u>Поиск по году:</u>
    🕰 <code>год: 1950</code> - книги 1950 года издания
    🕰 <code>год: 1924-1953</code> - книги с 1924 по 1953 годы издания
    🕰 <code>год: -1991</code> - книги до 1991 года издания включительно
    🕰 <code>год: 1991-</code> - книги 1991 года издания и новее

    <u>Новые критерии:</u>
    🏙️ <code>город: Красноярск</code> - поиск по городу издания
    🏢 <code>издательство: Наука</code> - поиск по издательству
    
    <u>Управляющие символы в начале слова:</u>
    🚦 <code>!слово</code> - исключить слово, например, <code>Распутин !Валентин</code> - ищем слово Распутин и исключаем слово Валентин
    🚦 <code>=слово</code> - точное соответствие критерию, например, <code>название: =монах</code>
    """
    await update.message.reply_text(help_text, parse_mode='HTML')
    logger.log_user_action(update.message.from_user, "showed help")


async def about_cmd(update: Update, context: CallbackContext):
    """Команда /about - информация о боте и библиотеке"""
    try:
        stats = DB_BOOKS.get_library_stats()
        last_update = stats['last_update']
        #last_update_str = last_update.strftime('%d.%m.%Y') if hasattr(last_update, 'strftime') else "неизвестно"
        last_update_str = last_update

        #debug
        #print(f"{last_update}, {last_update_str}")

        reader_recommendations = get_platform_recommendations()

        about_text = f"""
<b>Flibusta Bot</b> - телеграм бот для поиска и скачивания книг непосредственно с сайта библиотеки Флибуста.

📊 <b>Статистика БД библиотеки бота:</b>
• 📚 Книг: <code>{stats['books_count']:,}</code>
• 👥 Авторов: <code>{stats['authors_count']:,}</code>
• 🏷️ Жанров: <code>{stats['genres_count']:,}</code>
• 📖 Серий: <code>{stats['series_count']:,}</code>
• 🌐 Языков: <code>{stats['languages_count']:,}</code>
• 📅 Обновлено: <code>{last_update_str}</code>
• 🔢 Максимальный ID файла книги: <code>{stats['max_filename']}</code>

⚡ <b>Возможности бота:</b>
• 🔍 Поиск книг по названию, автору, жанру, серии, языку и году издания
• 📚 Поиск с группировкой по сериям 
• 📖 Скачивание в форматах fb2, epub, mobi
• ⚙️ Пользовательские настройки поиска
• 📊 Информация о книгах (при выборе fb2 формата)
{reader_recommendations}
📞 <b>Обратная связь:</b>
• 📧 Email: <code>{CONTACT_INFO['email']}</code>
• 🎮 Пикабу: <a href="{CONTACT_INFO['pikabu']}">{CONTACT_INFO['pikabu_username']}</a>

🛠 <b>Технологии:</b>
• Python 3.11
• python-telegram-bot
• SQLite
• Flibusta database
        """

        await update.message.reply_text(
            about_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

        logger.log_user_action(update.message.from_user, "viewed about")

    except Exception as e:
        print(f"Error in about command: {e}")
        await update.message.reply_text(
            "❌ Не удалось получить информацию о библиотеке",
            parse_mode=ParseMode.HTML
        )


async def news_cmd(update: Update, context: CallbackContext):
    """Команда /news - показывает последние новости бота"""
    try:
        if not BOT_NEWS:
            await update.message.reply_text(
                "📢 Пока нет новостей. Следите за обновлениями!",
                parse_mode=ParseMode.HTML
            )
            return

        # Берем последние 3 новости
        latest_news = BOT_NEWS[:3]

        news_text = "📢 <b>Последние новости бота:</b>\n\n"

        for i, news_item in enumerate(latest_news, 1):
            news_text += f"📅 <b>{news_item['date']}</b>\n"
            news_text += f"<b>{news_item['title']}</b>\n"
            news_text += f"{news_item['content']}\n"

            # Добавляем разделитель между новостями (кроме последней)
            if i < len(latest_news):
                news_text += "─" * 30 + "\n\n"

        await update.message.reply_text(
            news_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

        # Логируем действие
        user = update.message.from_user
        logger.log_user_action(user, "viewed news")

    except Exception as e:
        print(f"Error in news command: {e}")
        await update.message.reply_text(
            "❌ Не удалось загрузить новости",
            parse_mode=ParseMode.HTML
        )


