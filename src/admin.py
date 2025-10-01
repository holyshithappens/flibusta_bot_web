import datetime
import os
import time

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, ConversationHandler

from database import DatabaseSettings, DatabaseLogs

# Добавляем константы для пагинации
USERS_PER_PAGE = 10

# Создаем экземпляр базы данных логов
DB_LOGS = DatabaseLogs()

# Админские кнопки: ключ - имя обработчика, значение - текст кнопки
# Добавляем новые админские кнопки
ADMIN_BUTTONS = {
    "admin_user_stats": "📊 Статистика",
    "admin_users": "👥 Пользователи",
    "admin_broadcast": "📢 Рассылка",
    "admin_logs": "📋 Логи",
    "admin_system": "⚙️ Система",
    "admin_whoami": "👤 Кто я",
    "admin_logout": "🚪 Выход",
    "admin_recent_activity": "🔍 Последняя активность"
}

# Обратное mapping: текст кнопки -> имя обработчика
ADMIN_BUTTONS_REVERSE = {v: k for k, v in ADMIN_BUTTONS.items()}

# Глобальный словарь для хранения сессий администраторов
# Format: {user_id: {"admin_until": timestamp, "permissions": {...}}}
admin_sessions = {}

# Константы
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_SESSION_TIMEOUT = 1800  # 30 минут

DB_SETTINGS = DatabaseSettings()


# ===== АДМИНИСТРИРОВАНИЕ =====

AUTH_PASSWORD = 1

def authenticate_admin(password: str) -> bool:
    """Проверяет пароль администратора"""
    return password == ADMIN_PASSWORD and ADMIN_PASSWORD != ""


def grant_admin_access(user_id: int, duration: int = ADMIN_SESSION_TIMEOUT):
    """Дает права администратора на указанное время"""
    admin_until = int(time.time()) + duration
    admin_sessions[user_id] = {
        "admin_until": admin_until,
        "permissions": {
            "view_stats": True,
            "broadcast": True,
            "manage_users": True,
            "view_logs": True
        }
    }


def revoke_admin_access(user_id: int):
    """Забирает права администратора"""
    admin_sessions.pop(user_id, None)


def is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    # Сначала очищаем просроченные сессии
    cleanup_expired_sessions()

    session = admin_sessions.get(user_id)
    if session and session["admin_until"] > time.time():
        return True
    # Автоматически очищаем просроченные сессии
    if session:
        revoke_admin_access(user_id)
    return False


def cleanup_expired_sessions():
    """Очищает просроченные админские сессии"""
    current_time = time.time()
    expired_users = [
        user_id for user_id, session in admin_sessions.items()
        if session["admin_until"] <= current_time
    ]
    for user_id in expired_users:
        revoke_admin_access(user_id)
    return len(expired_users)


async def cleanup_admin_sessions(context: CallbackContext):
    """Периодическая очистка просроченных админских сессий"""
    cleaned = cleanup_expired_sessions()
    if cleaned > 0:
        print(f"Очищено {cleaned} просроченных админских сессий")


async def cancel_auth(update: Update, context: CallbackContext):
    """Отмена аутентификации"""
    await update.message.reply_text("❌ Аутентификация отменена")
    return ConversationHandler.END


async def show_admin_panel(update: Update, context: CallbackContext):
    """Показывает панель администратора"""
    # Клавиатура админ-панели
    ADMIN_KEYBOARD = [
        [ADMIN_BUTTONS["admin_user_stats"], ADMIN_BUTTONS["admin_recent_activity"]],
        [ADMIN_BUTTONS["admin_users"], ADMIN_BUTTONS["admin_logs"]],
        [ADMIN_BUTTONS["admin_broadcast"], ADMIN_BUTTONS["admin_system"]],
        [ADMIN_BUTTONS["admin_whoami"], ADMIN_BUTTONS["admin_logout"]]
    ]

    reply_markup = ReplyKeyboardMarkup(ADMIN_KEYBOARD, resize_keyboard=True)

    await update.message.reply_text(
        "👑 <b>Панель администратора</b>\n\n"
        "Выберите действие:",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )


async def handle_admin_buttons(update: Update, context: CallbackContext):
    """Обрабатывает нажатия кнопок в админ-панели"""
    user = update.effective_user

    if not is_admin(user.id):
        await update.message.reply_text("❌ Права администратора истекли",
                                        #parse_mode=ParseMode.HTML,
                                        reply_markup=ReplyKeyboardRemove()
        )
        revoke_admin_access(user.id)
        return

    text = update.message.text
    handler_name = ADMIN_BUTTONS_REVERSE.get(text)

    if handler_name:
        handler = globals().get(handler_name)
        if handler and callable(handler):
            await handler(update, context)
        else:
            await update.message.reply_text(
                f"❌ Обработчик {handler_name} не найден",
                parse_mode=ParseMode.HTML
            )
    else:
        await show_admin_panel(update, context)


async def admin_cmd(update: Update, context: CallbackContext):
    """Главная команда администратора"""
    user = update.effective_user

    if is_admin(user.id):
        await show_admin_panel(update, context)
        return

    # Запрашиваем пароль
    await update.message.reply_text(
        "🔐 <b>Введите пароль администратора:</b>",
        parse_mode=ParseMode.HTML
    )
    return AUTH_PASSWORD


async def auth_password(update: Update, context: CallbackContext):
    """Обработка ввода пароля"""
    user = update.effective_user
    password = update.message.text

    if authenticate_admin(password):
        grant_admin_access(user.id)
        await update.message.reply_text(
            "✅ <b>Доступ предоставлен!</b>\n"
            f"Права администратора активны до {time.strftime('%H:%M:%S', time.localtime(admin_sessions[user.id]['admin_until']))}",
            parse_mode=ParseMode.HTML
        )
        await show_admin_panel(update, context)
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ <b>Неверный пароль</b>\n"
            "Попробуйте еще раз или отмените командой /cancel",
            parse_mode=ParseMode.HTML
        )
        return AUTH_PASSWORD


async def admin_whoami(update: Update, context: CallbackContext):
    """Показывает информацию о текущей сессии"""
    user = update.effective_user
    session = admin_sessions.get(user.id)

    if session and session["admin_until"] > time.time():
        expires = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(session["admin_until"]))
        await update.message.reply_text(
            f"👑 <b>Вы администратор</b>\n\n"
            f"• ID: {user.id}\n"
            f"• Имя: {user.first_name}\n"
            f"• Сессия действительна до: {expires}\n"
            f"• Осталось: {session['admin_until'] - time.time():.0f} секунд",
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text(
            "❌ <b>Вы не администратор</b>\n\n"
            "Используйте /admin для входа",
            parse_mode=ParseMode.HTML
        )


# async def admin_stats(update: Update, context: CallbackContext):
#     """Статистика системы"""
#     if not is_admin(update.effective_user.id):
#         await update.message.reply_text("❌ Недостаточно прав")
#         return
#
#     # Очищаем просроченные сессии
#     cleaned = cleanup_expired_sessions()
#     if cleaned > 0:
#         print(f"Очищено {cleaned} просроченных админских сессий")
#
#     stats = DB_SETTINGS.get_user_stats()
#
#     # Добавляем информацию о текущих админских сессиях
#     active_admins = len([uid for uid in admin_sessions if admin_sessions[uid]["admin_until"] > time.time()])
#
#     stats_text = f"""
# 📊 <b>Статистика системы</b>
#
# 👥 <b>Пользователи:</b>
# • Всего: {stats['total_users']}
# • Заблокированы: {stats['blocked_users']}
# • Активные: {stats['active_users']}
# • Активные админы: {active_admins}
#
# 🕒 <b>Админские сессии:</b>
# """
#
#     for user_id, session in admin_sessions.items():
#         if session["admin_until"] > time.time():
#             expires = time.strftime('%H:%M:%S', time.localtime(session["admin_until"]))
#             stats_text += f"• ID {user_id}: до {expires}\n"
#
#     await update.message.reply_text(stats_text, parse_mode=ParseMode.HTML)


async def admin_broadcast(update: Update, context: CallbackContext):
    """Массовая рассылка"""
    if not is_admin(update.effective_user.id):
        return

    if context.args:
        message = " ".join(context.args)
        # ... код рассылки ...
    else:
        await update.message.reply_text(
            "📢 <b>Массовая рассылка</b>\n\n"
            "Использование: /broadcast Ваше сообщение",
            parse_mode=ParseMode.HTML
        )


async def admin_logs(update: Update, context: CallbackContext):
    """Просмотр логов"""
    if not is_admin(update.effective_user.id):
        return

    # Можно реализовать просмотр последних логов
    await update.message.reply_text(
        "📋 <b>Просмотр логов</b>\n\n"
        "Функция в разработке...",
        parse_mode=ParseMode.HTML
    )


async def admin_logout(update: Update, context: CallbackContext):
    """Выход из режима администратора"""
    revoke_admin_access(update.effective_user.id)
    await update.message.reply_text(
        "🚪 <b>Режим администратора завершен</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove()
    )


async def admin_users(update: Update, context: CallbackContext):
    """Управление пользователями"""
    if not is_admin(update.effective_user.id):
        return

    # TODO: реализовать управление пользователями
    await update.message.reply_text(
        "👥 <b>Управление пользователями</b>\n\n"
        "Функция в разработке...",
        parse_mode=ParseMode.HTML
    )


async def admin_system(update: Update, context: CallbackContext):
    """Системные команды"""
    if not is_admin(update.effective_user.id):
        return

    # TODO: реализовать системные команды
    await update.message.reply_text(
        "⚙️ <b>Системные команды</b>\n\n"
        "Функция в разработке...",
        parse_mode=ParseMode.HTML
    )


async def admin_user_stats(update: Update, context: CallbackContext, from_callback=False):
    """Универсальная функция для показа статистики пользователей"""
    if from_callback:
        query = update.callback_query
        user = query.from_user
        message_func = query.edit_message_text
    else:
        user = update.effective_user
        message_func = update.message.reply_text

    if not is_admin(user.id):
        if from_callback:
            await query.edit_message_text("❌ Недостаточно прав")
        else:
            await update.message.reply_text("❌ Недостаточно прав")
        return

    # Получаем общую статистику
    stats = DB_LOGS.get_user_stats_summary()

    # Получаем статистику по дням
    daily_stats = DB_LOGS.get_daily_user_stats(7)

    stats_text = f"""
📈 <b>Статистика пользователей</b>

👥 <b>Общая статистика:</b>
• Всего пользователей: <code>{stats['total_users']:,}</code>
• Новых за неделю: <code>{stats['new_users_week']:,}</code>
• Активных за неделю: <code>{stats['active_users_week']:,}</code>

📊 <b>Активность за неделю:</b>
• Поисковых запросов: <code>{stats['searches_week']:,}</code>
• Скачиваний книг: <code>{stats['downloads_week']:,}</code>

📅 <b>Статистика по дням (последние 7 дней):</b>
"""

    # Добавляем статистику по дням в виде таблицы
    stats_text += "\n<pre>"
    stats_text += "Дата       | Новые | Активные | Поиски | Скачивания\n"
    stats_text += "───────────┼───────┼──────────┼────────┼───────────\n"

    for i in range(len(daily_stats['dates'])):
        date = daily_stats['dates'][i]
        new_users = daily_stats['new_users'][i]
        active_users = daily_stats['active_users'][i]
        searches = daily_stats['searches'][i]
        downloads = daily_stats['downloads'][i]

        # Форматируем дату (только день.месяц)
        date_formatted = datetime.datetime.strptime(date, '%Y-%m-%d').strftime('%d.%m')

        stats_text += f"{date_formatted:9} | {new_users:5} | {active_users:8} | {searches:6} | {downloads:9}\n"

    stats_text += "</pre>"

    # Добавляем графики в виде emoji-визуализации
    stats_text += "\n📊 <b>Визуализация активности:</b>\n\n"

    # График новых пользователей
    max_new = max(daily_stats['new_users']) or 1
    stats_text += "👥 Новые пользователи:\n"
    for count in daily_stats['new_users']:
        bar_length = int((count / max_new) * 10)
        stats_text += "🟢" * bar_length + "⚪" * (10 - bar_length) + f" {count}\n"

    # График активных пользователей
    max_active = max(daily_stats['active_users']) or 1
    stats_text += "\n🔥 Активные пользователи:\n"
    for count in daily_stats['active_users']:
        bar_length = int((count / max_active) * 10)
        stats_text += "🔵" * bar_length + "⚪" * (10 - bar_length) + f" {count}\n"

    # График поисков
    max_searches = max(daily_stats['searches']) or 1
    stats_text += "\n🔍 Поисковые запросы:\n"
    for count in daily_stats['searches']:
        bar_length = int((count / max_searches) * 10)
        stats_text += "🟡" * bar_length + "⚪" * (10 - bar_length) + f" {count}\n"

    # График скачиваний
    max_downloads = max(daily_stats['downloads']) or 1
    stats_text += "\n📥 Скачивания книг:\n"
    for count in daily_stats['downloads']:
        bar_length = int((count / max_downloads) * 10)
        stats_text += "🟣" * bar_length + "⚪" * (10 - bar_length) + f" {count}\n"

    # Кнопки действий
    keyboard = [
        [InlineKeyboardButton("📋 Детальный список пользователей", callback_data="users_list:0")],
        [InlineKeyboardButton("🔍 Топ поисковых запросов", callback_data="top_searches")],
        [InlineKeyboardButton("📥 Топ скачиваний", callback_data="top_downloads")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Используем правильный метод в зависимости от контекста
    await message_func(stats_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def show_top_searches(query, context: CallbackContext):
    """Показывает топ поисковых запросов"""
    top_searches = DB_LOGS.get_top_searches(15)

    searches_text = "🔍 <b>Топ поисковых запросов</b>\n\n"

    for i, search in enumerate(top_searches, 1):
        # Обрезаем длинные запросы
        query_text = search['query'][:50] + "..." if len(search['query']) > 50 else search['query']

        searches_text += f"{i}. {query_text}\n"
        searches_text += f"   👥 {search['count']} раз ({search['unique_users']} пользователей)\n\n"

    keyboard = [[InlineKeyboardButton("⬅️ Назад в статистику", callback_data="back_to_stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(searches_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def admin_recent_activity(update: Update, context: CallbackContext):
    """Последняя активность"""
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Недостаточно прав")
        return

    # Получаем последние действия
    activities = []
    recent_searches = DB_LOGS.get_recent_searches(10)
    recent_downloads = DB_LOGS.get_recent_downloads(10)

    activity_text = "🔍 <b>Последняя активность</b>\n\n"

    if recent_searches:
        activity_text += "📚 <b>Последние поиски:</b>\n"
        for search, timestamp, username in recent_searches:
            activity_text += f"• {username}: {search} ({timestamp})\n"
        activity_text += "\n"

    if recent_downloads:
        activity_text += "📥 <b>Последние скачивания:</b>\n"
        for filename, timestamp, username in recent_downloads:
            activity_text += f"• {username}: {filename} ({timestamp})\n"

    keyboard = [
        [InlineKeyboardButton("📋 Полный список пользователей", callback_data="users_list:0")],
        [InlineKeyboardButton("⬅️ Назад в статистику", callback_data="back_to_stats")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(activity_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def show_users_list(query, context: CallbackContext, page=0):
    """Показывает список пользователей"""
    users = DB_LOGS.get_users_list(USERS_PER_PAGE, page * USERS_PER_PAGE)
    total_users = DB_LOGS.get_user_stats_summary()['total_users']

    users_text = f"👥 <b>Список пользователей</b>\n\n"
    users_text += f"Страница {page + 1} из {((total_users - 1) // USERS_PER_PAGE) + 1}\n\n"

    keyboard = []

    for user in users:
        # Сокращаем информацию для кнопки
        user_info = f"{user['username']}"
        user_info += f" | 📅{user['first_seen'].split()[0]}"
        user_info += f" | 🔍{user['total_searches']} | 📥{user['total_downloads']}"

        keyboard.append([InlineKeyboardButton(
            user_info,
            callback_data=f"user_detail:{user['user_id']}"
        )])

    # Кнопки навигации
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"users_list:{page - 1}"))
    if (page + 1) * USERS_PER_PAGE < total_users:
        nav_buttons.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"users_list:{page + 1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("⬅️ Назад в статистику", callback_data="back_to_stats")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(users_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def show_user_detail(query, context: CallbackContext, user_id):
    """Показывает детальную информацию о пользователе"""
    # Получаем информацию о пользователе напрямую по ID
    user = DB_LOGS.get_user_by_id(user_id)

    if not user:
        await query.edit_message_text("❌ Пользователь не найден")
        return

    # Получаем историю действий
    activities = DB_LOGS.get_user_activity(user_id, 10)

    # Проверяем статус блокировки
    user_settings = DB_SETTINGS.get_user_settings(user_id)
    is_blocked = user_settings.IsBlocked

    user_text = f"👤 <b>Информация о пользователе</b>\n\n"
    user_text += f"<b>Имя:</b> {user['username']}\n"
    user_text += f"<b>ID:</b> {user_id}\n"
    user_text += f"<b>Первый визит:</b> {user['first_seen']}\n"
    user_text += f"<b>Последний визит:</b> {user['last_seen']}\n"
    user_text += f"<b>Всего поисков:</b> {user['total_searches']}\n"
    user_text += f"<b>Всего скачиваний:</b> {user['total_downloads']}\n"
    user_text += f"<b>Статус:</b> {'❌ Заблокирован' if is_blocked else '✅ Активен'}\n\n"

    user_text += "📋 <b>Последние действия:</b>\n"
    for activity in activities:
        action_desc = activity['action']
        if 'searched for' in activity['action']:
            # Убираем часть с count из деталей поиска
            detail = activity['detail'].split(';')[0] if ';' in activity['detail'] else activity['detail']
            action_desc = f"🔍 Поиск: {detail}"
        elif 'send file' in activity['action']:
            action_desc = f"📥 Скачал: {activity['detail']}"
        elif 'started bot' in activity['action']:
            action_desc = "🚀 Запустил бота"

        user_text += f"• {activity['timestamp']}: {action_desc}\n"

    keyboard = [
        [InlineKeyboardButton(
            "🚫 Заблокировать" if not is_blocked else "✅ Разблокировать",
            callback_data=f"toggle_block:{user_id}"
        )],
        [InlineKeyboardButton("⬅️ Назад к списку", callback_data="users_list:0")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(user_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def toggle_user_block(query, context: CallbackContext, user_id):
    """Блокирует/разблокирует пользователя с проверками"""
    user_settings = DB_SETTINGS.get_user_settings(user_id)
    current_block_status = user_settings.IsBlocked
    new_block_status = not current_block_status

    # Проверяем, не пытаемся ли заблокировать самого себя
    if user_id == query.from_user.id and new_block_status:
        await query.answer("❌ Нельзя заблокировать самого себя")
        return

    # Проверяем, не пытаемся ли заблокировать другого администратора
    if is_admin(user_id) and new_block_status:
        await query.answer("❌ Нельзя заблокировать администратора")
        return

    DB_SETTINGS.update_user_settings(user_id, IsBlocked=new_block_status)

    action = "заблокирован" if new_block_status else "разблокирован"
    await query.answer(f"Пользователь {action}")

    # Возвращаемся к деталям пользователя
    await show_user_detail(query, context, user_id)


async def show_recent_searches(query, context: CallbackContext):
    """Показывает последние поисковые запросы"""
    searches = DB_LOGS.get_recent_searches(20)

    searches_text = "🔍 <b>Последние поисковые запросы</b>\n\n"

    for search, timestamp, username in searches:
        searches_text += f"<b>{username}</b> ({timestamp}):\n{search}\n\n"

    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(searches_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def show_recent_downloads(query, context: CallbackContext):
    """Показывает последние скачивания"""
    downloads = DB_LOGS.get_recent_downloads(20)

    downloads_text = "📥 <b>Последние скачивания</b>\n\n"

    for filename, timestamp, username in downloads:
        downloads_text += f"<b>{username}</b> ({timestamp}):\n{filename}\n\n"

    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(downloads_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def show_top_downloads(query, context: CallbackContext):
    """Показывает топ скачанных книг"""
    top_downloads = DB_LOGS.get_top_downloads(20)

    top_text = "🏆 <b>Топ скачанных книг</b>\n\n"

    for filename, count in top_downloads:
        top_text += f"<b>{count} раз</b>: {filename}\n"

    keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(top_text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)


async def handle_admin_callback(update: Update, context: CallbackContext):
    """Обработчик callback для админских действий"""
    query = update.callback_query
    await query.answer()

    data = query.data.split(':')
    action = data[0]

    try:
        if action == "users_list":
            page = int(data[1]) if len(data) > 1 else 0
            await show_users_list(query, context, page)

        elif action == "user_detail":
            user_id = int(data[1])
            await show_user_detail(query, context, user_id)

        elif action == "toggle_block":
            user_id = int(data[1])
            await toggle_user_block(query, context, user_id)

        elif action == "recent_searches":
            await show_recent_searches(query, context)

        elif action == "recent_downloads":
            await show_recent_downloads(query, context)

        elif action == "top_downloads":
            await show_top_downloads(query, context)

        elif action == "top_searches":
            await show_top_searches(query, context)

        elif action == "back_to_stats":
            await admin_user_stats(update, context, from_callback=True)

        elif action == "refresh_stats":
            await admin_user_stats(update, context, from_callback=True)

    except Exception as e:
        print(f"Error in admin callback: {e}")
        await query.edit_message_text("❌ Произошла ошибка при обработке запроса")