import telebot
from telebot import types
import json
import sqlite3
import pytz
import config
import html
import os
from datetime import datetime


# ================= ВЛАДЕЛЕЦ =================
OWNER_ID = 6635821466
ARCHIVE_GROUP_ID = -1003702155877
# ================= НАСТРОЙКИ =================
tz = pytz.timezone('Asia/Krasnoyarsk')
bot = telebot.TeleBot(config.TOKEN)

# ================= ЗАГРУЗКА ДАННЫХ =================
with open('single.json', encoding='utf-8') as f:
    pizzas = json.load(f)['pizzas']

with open('combo_sets.json', encoding='utf-8') as f:
    combos = json.load(f)['combos']

with open('zakuski.json', encoding='utf-8') as f:
    zakuski_menu = json.load(f)['zakuski']

with open('napitki.json', encoding='utf-8') as f:
    drinks_list = json.load(f)['napitki']

with open('shaurma.json', encoding='utf-8') as f:
    shaurma_data = json.load(f)

with open('additives.json', encoding='utf-8') as f:
    additives_data = json.load(f)

shaurma_list = shaurma_data['shaurma']
additives = additives_data['additives']

# ================= БАЗА ДАННЫХ =================
DB_PATH = '/data/orders.db'
os.makedirs('/data', exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()


cursor.execute('PRAGMA journal_mode=WAL;')
cursor.execute('PRAGMA synchronous=NORMAL;')

cursor.execute('''
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    phone TEXT,
    delivery_type TEXT,
    delivery_zone TEXT,
    address TEXT,
    delivery_time TEXT,
    payment_method TEXT,
    cash_change TEXT,
    comment TEXT,
    order_text TEXT,
    order_status TEXT,
    created_at TEXT,
    is_archived INTEGER DEFAULT 0,
    is_sent_to_group INTEGER DEFAULT 0  -- Добавляем запятую перед этим полем
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY
)
''')

conn.commit()

# ================= ПАМЯТЬ =================
user_carts = {}
user_order_data = {}
DRINK_GROUPS = {}

# ================= ПАМЯТЬ АРХИВА =================
archive_month_state = {}

DISTRICT_PRICES = {
    'Чечеул': 350,
    'Ашкаул': 450,
    'Бражное': 550,
    'Подояйск': 350,
    'Анцирь': 400,
    'Левобережное': 250,
    'Иланск': 650,
    'Сотниково': 500,
    'Ловать': 300,
    'Карапсель': 400,
    'Рассвет': 200,
    'Бережки': 200,
    'Филимоново': 500,
    'Красный маяк': 600,
    'Сухая речка': 800,
    'Шахтинский': 250,
    'Новый путь': 100,
    'Зеленый луг': 200
}

MONTHS_RU = {
    1: 'ЯНВАРЬ',
    2: 'ФЕВРАЛЬ',
    3: 'МАРТ',
    4: 'АПРЕЛЬ',
    5: 'МАЙ',
    6: 'ИЮНЬ',
    7: 'ИЮЛЬ',
    8: 'АВГУСТ',
    9: 'СЕНТЯБРЬ',
    10: 'ОКТЯБРЬ',
    11: 'НОЯБРЬ',
    12: 'ДЕКАБРЬ'
}

ORDER_STATUSES = {
    'accepted': '👨‍🍳 Принят',
    'cooking': '🔥 Готовится',
    'delivery': '🚗 В пути',
    'done': '   🟢 Завершён',
    'canceled': '❌ Отменён'
}


CATEGORY_TITLES = {
    'pizza': '🍕 Одиночные',
    'combo': '📦 Комбо наборы',
    'zakuska': '🍟 Закуски',
    'drink': '🥤 Напитки',
    'shaurma': '🌯 Шаурма',
    'additive': '➕ Добавки'
}

DRINK_CATEGORIES = {
    'cola': {
        'button': '🥤 Кола',
        'match': 'Кола',
        'title': 'Кола',
        'description': None
    },
    'orange_yuzu': {
        'button': '🍊 Дикий апельсин и юдзу',
        'match': 'Дикий апельсин и юдзу',
        'title': 'Дикий апельсин и юдзу',
        'description': None
    },
    'cosmos': {
        'button': '🚀 Энергетик космос Яркая энергия',
        'match': 'Энергетик космос Яркая энергия',
        'title': 'Энергетик космос Яркая энергия',
        'description': None
    },
    'lemonade': {
        'button': '🍃 Лимонад Черноголовка',
        'match': 'Лимонад Черноголовка',
        'title': 'Лимонад Черноголовка',
        'description': 'Мохито со вкусом лайма и мяты'
    },
    'tea_green': {
        'button': '🧃 Холодный чай зелёный',
        'match': 'Холодный чай зеленый',
        'title': 'Холодный чай зелёный',
        'description': 'Мята – лайм (для детей)'
    },
    'tea_black': {
        'button': '🧃 Холодный чай чёрный',
        'match': 'Холодный чай черный',
        'title': 'Холодный чай чёрный',
        'description': 'Лимон – лайм (для детей)'
    },
    'water': {
        'button': '💧 Черноголовка вода питьевая',
        'match': 'вода питьевая',
        'title': 'Черноголовка',
        'description': 'Вода питьевая газированная'
    },
    'energy': {
        'button': '⚡ Энергетик X TURBO',
        'match': 'X - TURBO',
        'title': 'Энергетик X TURBO',
        'description': 'Вкус персик – сакура'
    }
}

# ================= АДМИН =================
def is_admin(chat_id: int) -> bool:
    if chat_id == OWNER_ID:
        return True

    cursor.execute('SELECT 1 FROM admins WHERE user_id = ?', (chat_id,))
    return cursor.fetchone() is not None

def is_owner(chat_id: int) -> bool:
    return chat_id == OWNER_ID

def admin_manage_menu(chat_id):
    if not is_owner(chat_id):
        return

    admins = get_all_admins()

    kb = types.InlineKeyboardMarkup(row_width=1)

    # Всегда показываем кнопку назначения администратора
    kb.add(types.InlineKeyboardButton('Назначить администратора', callback_data='admin_add'))

    # Если есть администраторы, выводим их список
    if admins:
        for admin_id in admins:
            kb.add(
                types.InlineKeyboardButton(f'Удалить администратора {admin_id}', callback_data=f'remove_admin_{admin_id}')
            )

    kb.add(types.InlineKeyboardButton('Назад', callback_data='back_main'))

    bot.send_message(
        chat_id,
        'Управление администраторами:',
        reply_markup=kb
    )
def admin_add_handler(message):
    chat_id = message.chat.id

    if not is_owner(chat_id):
        bot.send_message(chat_id, '❌ Только владелец может назначать администраторов')
        return

    try:
        user_id = int(message.text)

        if user_id == OWNER_ID:
            bot.send_message(chat_id, 'ℹ️ Владелец уже имеет все права')
            return

        cursor.execute(
            'INSERT OR IGNORE INTO admins (user_id) VALUES (?)',
            (user_id,)
        )
        conn.commit()

        bot.send_message(chat_id, f'✅ Пользователь {user_id} назначен администратором')

    except ValueError:
        bot.send_message(chat_id, '❌ Введите корректный Telegram ID')

def admin_remove_handler(message):
    chat_id = message.chat.id

    if not is_owner(chat_id):
        bot.send_message(chat_id, '❌ Только владелец может удалять администраторов')
        return

    try:
        user_id = int(message.text)

        if user_id == OWNER_ID:
            bot.send_message(chat_id, '🚫 Нельзя удалить владельца')
            return

        cursor.execute(
            'DELETE FROM admins WHERE user_id = ?',
            (user_id,)
        )
        conn.commit()

        bot.send_message(chat_id, f'🗑 Администратор {user_id} удалён')

    except ValueError:
        bot.send_message(chat_id, '❌ Введите корректный Telegram ID')

def register_admin(admin_id):
    cursor.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (admin_id,))
    conn.commit()
def get_all_admins():
    cursor.execute('SELECT user_id FROM admins')
    admins = [row[0] for row in cursor.fetchall()]
    if OWNER_ID not in admins:
        admins.append(OWNER_ID)
    return admins


def search_archive(message):
    chat_id = message.chat.id
    query = message.text.strip()

    cursor.execute('''
        SELECT id, created_at, name
        FROM orders
        WHERE is_archived = 1
        AND (
            CAST(id AS TEXT) LIKE ?
            OR created_at LIKE ?
        )
        ORDER BY created_at DESC
    ''', (f'%{query}%', f'%{query}%'))

    rows = cursor.fetchall()

    if not rows:
        bot.send_message(chat_id, '❌ Ничего не найдено')
        return

    kb = types.InlineKeyboardMarkup(row_width=1)

    for oid, created_at, name in rows:
        kb.add(
            types.InlineKeyboardButton(
                f'📦 №{oid} | {created_at} | {name}',
                callback_data=f'admin_order_{oid}'
            )
        )

    kb.add(
        types.InlineKeyboardButton('◀️ Назад к архиву', callback_data='admin_archive')
    )

    bot.send_message(
        chat_id,
        '🔍 <b>Результаты поиска:</b>',
        parse_mode='HTML',
        reply_markup=kb
    )

def format_status(status):
    if status == 'Готовится':
        return '🔥 Готовится'
    elif status == 'В пути':
        return '🚗 В пути'
    return status


def show_all_orders_admin(chat_id):
    if not is_admin(chat_id):
        return

    cursor.execute('''
        SELECT id, created_at, order_status, name
        FROM orders
        WHERE is_archived = 0
        AND order_status NOT IN (?, ?)
        ORDER BY
            substr(created_at, 7, 4) ||
            substr(created_at, 4, 2) ||
            substr(created_at, 1, 2) ||
            substr(created_at, 14, 2) ||
            substr(created_at, 17, 2) DESC
    ''', (
        ORDER_STATUSES['done'],
        ORDER_STATUSES['canceled']
    ))

    rows = cursor.fetchall()

    if not rows:
        bot.send_message(chat_id, '📭 Нет активных заказов')
        return

    kb = types.InlineKeyboardMarkup(row_width=1)

    for oid, created_at, status, name in rows:
        kb.add(
            types.InlineKeyboardButton(
                f'📦 №{oid} | {format_status(status)} | {name}',
                callback_data=f'admin_order_{oid}'
            )
        )

    kb.add(types.InlineKeyboardButton('◀️ Назад', callback_data='back_main'))

    bot.send_message(
        chat_id,
        '🛠 <b>Новые заказы</b>',
        parse_mode='HTML',
        reply_markup=kb
    )

def show_archive_orders_admin(chat_id):
    if not is_admin(chat_id):
        return

    archive_month_state.setdefault(chat_id, {})

    cursor.execute('''
        SELECT id, created_at, name
        FROM orders
        WHERE is_archived = 1
        ORDER BY
            substr(created_at, 7, 4) || substr(created_at, 4, 2) DESC,
            substr(created_at, 1, 2) DESC
    ''')

    rows = cursor.fetchall()

    if not rows:
        bot.send_message(chat_id, '📦 Архив заказов пуст')
        return

    kb = types.InlineKeyboardMarkup(row_width=1)

    last_month = None

    for oid, created_at, name in rows:
        dt = datetime.strptime(created_at, '%d/%m/%Y - %H:%M')
        month_key = f'{dt.year}-{dt.month:02d}'
        month_title = f'{MONTHS_RU[dt.month]} {dt.year}'

        is_open = archive_month_state[chat_id].get(month_key, True)

        # 📅 Заголовок месяца
        if month_key != last_month:
            arrow = '▾' if is_open else '▸'
            kb.add(
                types.InlineKeyboardButton(
                    f'📅 {month_title} {arrow}',
                    callback_data=f'archive_toggle_{month_key}'
                )
            )
            last_month = month_key

        # 📦 Заказы месяца
        if is_open:
            kb.add(
                types.InlineKeyboardButton(
                    f'📦 №{oid} | {dt.strftime("%d.%m %H:%M")} | {name}',
                    callback_data=f'admin_order_{oid}'
                )
            )
    kb.add(types.InlineKeyboardButton('🗑 Удалить', callback_data='archive_delete'))
    kb.add(types.InlineKeyboardButton('🔍 Поиск', callback_data='archive_search'))
    kb.add(types.InlineKeyboardButton('◀️ Назад', callback_data='back_main'))

    bot.send_message(
        chat_id,
        '<b>📦 Архив заказов</b>',
        parse_mode='HTML',
        reply_markup=kb
    )

def archive_delete_menu(chat_id):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton('🗓 Удалить месяц целиком', callback_data='archive_delete_month'),
        types.InlineKeyboardButton('📦 Удалить заказ по номеру', callback_data='archive_delete_order'),
        types.InlineKeyboardButton('◀️ Назад', callback_data='admin_archive')
    )

    bot.send_message(
        chat_id,
        '🗑 <b>Удаление архива</b>\nВыберите действие:',
        parse_mode='HTML',
        reply_markup=kb
    )

def archive_delete_month_menu(chat_id):
    cursor.execute('''
        SELECT DISTINCT substr(created_at, 7, 4) || '-' || substr(created_at, 4, 2)
        FROM orders
        WHERE is_archived = 1
        ORDER BY 1 DESC
    ''')
    months = cursor.fetchall()

    if not months:
        bot.send_message(chat_id, '📦 Архив пуст')
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    for (month_key,) in months:
        year, month = month_key.split('-')
        title = f'{MONTHS_RU[int(month)]} {year}'
        kb.add(types.InlineKeyboardButton(
            f'🗓 {title}',
            callback_data=f'archive_delete_month_{month_key}'
        ))

    kb.add(types.InlineKeyboardButton('◀️ Назад', callback_data='archive_delete'))

    bot.send_message(
        chat_id,
        '🗓 <b>Выберите месяц для удаления:</b>',
        parse_mode='HTML',
        reply_markup=kb
    )
def delete_archive_month(chat_id, month_key):
    year, month = month_key.split('-')

    cursor.execute('''
        DELETE FROM orders
        WHERE is_archived = 1
        AND substr(created_at, 7, 4) = ?
        AND substr(created_at, 4, 2) = ?
    ''', (year, month))
    conn.commit()

    bot.send_message(
        chat_id,
        f'🗑 Архив за {MONTHS_RU[int(month)]} {year} удалён'
    )

    show_archive_orders_admin(chat_id)

def ask_delete_order_id(message):
    chat_id = message.chat.id
    try:
        order_id = int(message.text)

        cursor.execute(
            'DELETE FROM orders WHERE id = ? AND is_archived = 1',
            (order_id,)
        )

        if cursor.rowcount == 0:
            bot.send_message(chat_id, '❌ Заказ не найден в архиве')
        else:
            conn.commit()
            bot.send_message(chat_id, f'🗑 Заказ №{order_id} удалён')

        show_archive_orders_admin(chat_id)

    except ValueError:
        bot.send_message(chat_id, '❌ Введите корректный номер заказа')


def show_order_detail_admin(chat_id, order_id):
    """Показать детали заказа администратору"""
    if not is_admin(chat_id):
        return

    text = build_admin_order_text(order_id)
    if not text:
        bot.send_message(chat_id, '❌ Заказ не найден')
        return

    # Получаем данные заказа
    cursor.execute(
        'SELECT is_archived, user_id FROM orders WHERE id = ?',
        (order_id,)
    )
    row = cursor.fetchone()
    if not row:
        bot.send_message(chat_id, '❌ Заказ не найден')
        return

    is_archived, user_id = row

    kb = types.InlineKeyboardMarkup()

    # 🔗 КНОПКА ОТКРЫТИЯ ПРОФИЛЯ КЛИЕНТА
    if user_id:
        try:
            chat = bot.get_chat(user_id)
            if chat.username:
                kb.add(
                    types.InlineKeyboardButton(
                        '🔗 Открыть профиль',
                        url=f'https://t.me/{chat.username}'
                    )
                )
            else:
                kb.add(
                    types.InlineKeyboardButton(
                        '🔗 Открыть профиль',
                        url=f'tg://user?id={user_id}'
                    )
                )
        except Exception as e:
            print(f'Ошибка получения профиля пользователя {user_id}: {e}')

    # 👉 Кнопки статусов только для активных заказов
    if not is_archived:
        status_kb = operator_status_keyboard(order_id)

        # переносим кнопки статусов в основную клавиатуру
        for row in status_kb.keyboard:
            kb.row(*row)

        kb.add(types.InlineKeyboardButton('◀️ Назад', callback_data='admin_orders'))
    else:
        kb.add(types.InlineKeyboardButton('◀️ Назад', callback_data='admin_archive'))

    bot.send_message(
        chat_id,
        text,
        parse_mode='HTML',
        reply_markup=kb
    )

def operator_status_keyboard(order_id):
    cursor.execute('SELECT order_status, is_archived, user_id, is_sent_to_group FROM orders WHERE id = ?', (order_id,))
    row = cursor.fetchone()
    if not row:
        return None

    current_status, is_archived, user_id, is_sent_to_group = row

    kb = types.InlineKeyboardMarkup(row_width=2)
    for key, text in ORDER_STATUSES.items():
        is_active = (text == current_status)
        btn_text = f'✅ {text}' if is_active else text
        kb.add(
            types.InlineKeyboardButton(
                btn_text,
                callback_data=f'status_{order_id}_{key}'
            )
        )
    return kb

# ================= ВСПОМОГАТЕЛЬНОЕ =================
def send_item_with_image(chat_id, image_url, text, kb=None):
    if image_url:
        bot.send_photo(
            chat_id,
            photo=image_url,
            caption=text,
            parse_mode='HTML',
            reply_markup=kb
        )
    else:
        bot.send_message(
            chat_id,
            text,
            parse_mode='HTML',
            reply_markup=kb
        )

def get_cart_total(chat_id):
    return sum(
        i['item']['price'] * i['quantity']
        for i in user_carts.get(chat_id, [])
    )
def show_order_history(chat_id):
    cursor.execute('SELECT id, created_at, order_status FROM orders WHERE user_id = ? ORDER BY created_at DESC',
                   (chat_id,))
    orders = cursor.fetchall()

    if not orders:
        bot.send_message(chat_id, '📭 У вас пока нет оформленных заказов.')
        return

    kb = types.InlineKeyboardMarkup(row_width=1)

    for order_id, created_at, status in orders:
        btn_text = f'Заказ №{order_id} — {created_at.split(" ")[0]} — {status}'
        kb.add(types.InlineKeyboardButton(btn_text, callback_data=f'order_detail_{order_id}'))

    kb.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='back_main'))

    bot.send_message(chat_id, '📜 <b>История ваших заказов:</b>', parse_mode='HTML', reply_markup=kb)


def build_admin_order_text(order_id):
    cursor.execute('''
        SELECT
            id, created_at, name, phone, user_id,
            delivery_type, delivery_zone, address,
            delivery_time, payment_method, cash_change,
            comment, order_status, order_text
        FROM orders
        WHERE id = ?
    ''', (order_id,))
    row = cursor.fetchone()

    if not row:
        return None

    (
        oid, created_at, name, phone, user_id,
        delivery_type, delivery_zone, address,
        delivery_time, payment_method, cash_change,
        comment, status, order_text
    ) = row

    # ===== TELEGRAM =====
    tg_line = ''
    tg_username = None
    try:
        chat = bot.get_chat(user_id)
        if chat.username:
            tg_username = chat.username
            tg_line += f'💬 <b>Telegram:</b> @{chat.username}\n'
        tg_line += f'🆔 <b>ID пользователя:</b> <code>{user_id}</code>\n'
    except:
        tg_line += f'🆔 <b>ID пользователя:</b> <code>{user_id}</code>\n'


    # ===== ДОСТАВКА =====
    if delivery_type == 'Самовывоз':
        delivery_line = '🏠 Самовывоз'
    else:
        zone = delivery_zone or '—'
        delivery_line = f'🚚 Доставка ({zone})'

    # ===== ОСНОВНОЙ ТЕКСТ =====
    text = (
        f'📦 <b>Заказ №{oid}</b>\n\n'  # ← 1 пустая строка
        f'📌 <b>Статус:</b> {status}\n'
        f'🕒 <b>Дата:</b> {created_at}\n'# ← 1 пустая строка
        f'👤 <b>Клиент:</b> {html.escape(name or "—")}\n'
        f'📞 <b>Телефон:</b> {html.escape(phone or "—")}\n'
        f'{tg_line}'  # ← БЕЗ дополнительного \n
        f'{delivery_line}\n'
    )

    if address and delivery_type != 'Самовывоз':
        text += f'📍 <b>Адрес:</b> {html.escape(address)}\n'

    if delivery_time and delivery_time != '—':
        text += f'⏰ <b>Время:</b> {delivery_time}\n'  # ← без пустой строки

    text += f'💳 <b>Оплата:</b> {payment_method or "—"}\n'

    if cash_change and cash_change not in ['—', '', None]:
        text += f'💵 <b>Сдача:</b> {cash_change}\n'

    if comment and comment not in ['—', '', None]:
        text += f'📝 <b>Комментарий:</b> {html.escape(comment)}\n'

    text += f'\n{order_text}'

    return text

def show_order_detail_user(chat_id, order_id):
    cursor.execute('''
        SELECT order_text, order_status, created_at
        FROM orders
        WHERE id = ? AND user_id = ?
    ''', (order_id, chat_id))

    row = cursor.fetchone()
    if not row:
        bot.send_message(chat_id, '❌ Заказ не найден')
        return

    order_text, status, created_at = row

    text = (
        f'📦 <b>Ваш заказ №{order_id}</b>\n\n'
        f'📅 Дата: {created_at}\n'
        f'📌 Статус: {status}\n\n'
        f'{order_text}'
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton(
            '◀️ Назад к истории заказов',
            callback_data='order_history'
        )
    )
    kb.add(
        types.InlineKeyboardButton(
            '🏠 Главное меню',
            callback_data='back_main'
        )
    )

    bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=kb)

def build_item_card(item_type, item):
    text = f'<b>{item["name"]}</b>\n💰 Цена: {item["price"]} ₽'

    if item_type == 'pizza':
        diameter = f'{item["diameter"]} см' if item.get("diameter") else '—'
        grams = f'{item["grams"]} г' if item.get("grams") and item["grams"] != "null" else '—'
        text += f'\n📏 Диаметр: {diameter}'
        text += f'\n🧾 Состав: {item["ingredients"]}'

    elif item_type == 'combo':
        text += f'\n📦 {item.get("description", "")}'

    elif item_type == 'zakuska':
        if item.get("kolichestvo"):
            text += f'\n📦 Количество: {item["kolichestvo"]} шт.'

    elif item_type == 'drink':
        if item.get("liters"):
            text += f'\n🥤 Объём: {item["liters"]} л'

    elif item_type == 'shaurma':
        pass

    elif item_type == 'additive':
        pass

    return text

def build_order_text(chat_id):
    data = user_order_data.get(chat_id, {})
    cart = user_carts.get(chat_id, [])

    if not cart:
        return '🛒 Корзина пуста'

    # группируем товары по типу
    grouped = {}
    for item in cart:
        grouped.setdefault(item['type'], []).append(item)

    text = '🛒 <b>Состав заказа:</b>\n\n'
    total_items_price = 0

    for item_type, items in grouped.items():
        title = CATEGORY_TITLES.get(item_type, item_type)
        text += f'<b>{title}:</b>\n'

        for i, e in enumerate(items, 1):
            item_total = e['item']['price'] * e['quantity']
            total_items_price += item_total

            text += (
                f'{i}. {e["card_text"]}\n'
                f'Количество: {e["quantity"]} шт.\n'
                f'Цена: {item_total} ₽\n\n'
            )

    # ===== СУММЫ =====
    text += f'💰 <b>Сумма корзины:</b> {total_items_price} ₽\n'

    delivery_type = data.get('delivery_type')
    delivery_zone = data.get('delivery_zone')
    delivery_price = data.get('delivery_price')

    # самовывоз / город
    if delivery_type == 'Самовывоз' or delivery_zone == 'Город':
        text += '🚚 <b>Доставка:</b> 0 ₽\n'
        text += f'💳 <b>Итого:</b> {total_items_price} ₽\n'
        return text

    # район
    if delivery_price is None:
        text += '🚚 <b>Доставка:</b> уточняет администратор\n'
        text += f'💳 <b>Итого:</b> {total_items_price} ₽\n'
    else:
        text += f'🚚 <b>Доставка:</b> {delivery_price} ₽\n'
        text += f'💳 <b>Итого:</b> {total_items_price + delivery_price} ₽\n'

    return text

def manual_district(message):
    chat_id = message.chat.id
    district = message.text.strip()

    # Сохраняем адрес вручную
    user_order_data[chat_id] = {
        'delivery_type': 'Доставка',
        'delivery_zone': 'Район',
        'address': district,
        'delivery_price': None  # цену уточнит оператор
    }

    cart_total = get_cart_total(chat_id)
    bot.send_message(
        chat_id,
        f'📍 Населённый пункт: <b>{district}</b>\n'
        f'🛒 Сумма заказа: {cart_total} ₽\n'
        f'🚚 Доставка: —\n'
        f'💰 <b>Итого: {cart_total} ₽</b>',
        parse_mode='HTML'
    )

    # 🔥 Запускаем оформление заказа
    start_order(chat_id)


def back_button(kb: types.InlineKeyboardMarkup, callback):
    kb.add(types.InlineKeyboardButton('◀️ Назад', callback_data=callback))
    return kb


def home_button(kb: types.InlineKeyboardMarkup):
    kb.add(types.InlineKeyboardButton('🏠 Главное меню', callback_data='back_main'))
    return kb


def add_card_navigation(kb: types.InlineKeyboardMarkup, back_callback: str):
    kb.add(
        types.InlineKeyboardButton('◀️ Назад', callback_data=back_callback)
    )
    kb.add(
        types.InlineKeyboardButton('🏠 Главное меню', callback_data='back_main')
    )

# ================= КОРЗИНА =================
def add_to_cart(chat_id, item_type, item, call_id=None):
    card_text = build_item_card(item_type, item)
    user_carts.setdefault(chat_id, [])

    # Определяем уникальный ключ для позиции
    item_key = f'{item["id"]}_{item.get("diameter", 0)}'

    # Проверяем, есть ли уже такой товар в корзине
    for cart_item in user_carts[chat_id]:
        existing_key = f'{cart_item["item"]["id"]}_{cart_item["item"].get("diameter", 0)}'
        if cart_item['type'] == item_type and existing_key == item_key:
            cart_item['quantity'] += 1
            if call_id:
                bot.answer_callback_query(call_id, f'✅ Количество {item["name"]} увеличено')
            return

    # Если товара еще нет — добавляем с количеством 1
    user_carts[chat_id].append({
        'type': item_type,
        'item': item,
        'card_text': card_text,
        'quantity': 1
    })

    if call_id:
        bot.answer_callback_query(call_id, f'✅ {item["name"]} ({item.get("diameter", "—")} см) добавлено в корзину')


def show_cart(chat_id):
    cart = user_carts.get(chat_id, [])
    if not cart:
        bot.send_message(chat_id, '🛒 Корзина пуста')
        return

    categories = {}
    for i, e in enumerate(cart):
        categories.setdefault(e['type'], []).append((i, e))

    text = '🛒 <b>Ваша корзина:</b>\n\n'
    total_items_price = 0

    for cat, items in categories.items():
        cat_name = {
            'pizza': '🍕 Одиночные',
            'combo': '📦 Комбо наборы',
            'zakuska': '🍟 Закуски',
            'drink': '🥤 Напитки',
            'shaurma': '🌯 Шаурма',
            'additive': '➕ Добавки'
        }.get(cat, cat)

        text += f'<b>{cat_name}:</b>\n'

        for idx, cart_item in items:
            price = cart_item['item']['price'] * cart_item['quantity']
            total_items_price += price
            text += (
                f'{cart_item["card_text"]}\n'
                f'Количество: {cart_item["quantity"]} шт.\n'
                f'Цена: {price} ₽\n\n'
            )

    text += f'💰 <b>Итого:</b> {total_items_price} ₽\n'

    kb = types.InlineKeyboardMarkup(row_width=4)

    for cat, items in categories.items():
        for idx, cart_item in items:
            kb.add(
                types.InlineKeyboardButton('➖', callback_data=f'cart_minus_{idx}'),
                types.InlineKeyboardButton(cart_item['item']['name'], callback_data='noop'),
                types.InlineKeyboardButton('➕', callback_data=f'cart_plus_{idx}'),
                types.InlineKeyboardButton('❌', callback_data=f'cart_del_{idx}')
            )

    kb.add(types.InlineKeyboardButton('✅ Оформить заказ', callback_data='checkout'))
    home_button(kb)

    bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=kb)


# ================= ГЛАВНОЕ МЕНЮ =================
def main_menu(chat_id):
    kb = types.InlineKeyboardMarkup()

    kb.add(
        types.InlineKeyboardButton('🍕 Пицца', callback_data='menu_pizza'),
        types.InlineKeyboardButton('🍟 Закуски', callback_data='menu_zakuski'),
        types.InlineKeyboardButton('🥤 Напитки', callback_data='menu_napitki'),
        types.InlineKeyboardButton('🌯 Шаурма', callback_data='menu_shaurma'),
        types.InlineKeyboardButton('➕ Добавки', callback_data='menu_additives')
    )

    if is_admin(chat_id):
        kb.add(
            types.InlineKeyboardButton('🛠 Новые заказы', callback_data='admin_orders'),
            types.InlineKeyboardButton('📦 Архив заказов', callback_data='admin_archive')
        )

        if is_owner(chat_id):
            kb.add(
                types.InlineKeyboardButton('👥 Администраторы', callback_data='admin_manage')
            )

    kb.add(
        types.InlineKeyboardButton('🛒 Корзина', callback_data='show_cart')
    )
    kb.add(
        types.InlineKeyboardButton('ℹ️ О нас', callback_data='about_us')
    )

    # 📜 История заказов — ТОЛЬКО не админам
    if not is_admin(chat_id):
        kb.add(
            types.InlineKeyboardButton('📜 История заказов', callback_data='order_history')
        )

    bot.send_message(
        chat_id,
        '🏠 <b>Главное меню</b>',
        parse_mode='HTML',
        reply_markup=kb
    )

def split_snacks():
    striptsy = []
    sauces = []
    other_snacks = []

    for z in zakuski_menu:
        if z.get("category") == "соус":
            sauces.append(z)
        elif z["name"] == "Стрипсы":
            striptsy.append(z)
        else:
            other_snacks.append(z)

    return striptsy, sauces, other_snacks


# ================= ПИЦЦА =================
def pizza_menu(chat_id):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton('🍕 Одиночные пиццы', callback_data='pizza_single'),
        types.InlineKeyboardButton('📦 Комбо-наборы', callback_data='pizza_combo')
    )
    home_button(kb)
    bot.send_message(
        chat_id,
        '🍕 <b>Пицца</b>',
        parse_mode='HTML',
        reply_markup=kb
    )
def pizza_single_menu(chat_id):
    kb = types.InlineKeyboardMarkup()

    for p in pizzas:
        kb.add(
            types.InlineKeyboardButton(
                f'🍕 {p["name"]}',
                callback_data=f'pizza_info_{p["id"]}'
            )
        )

    back_button(kb, 'menu_pizza')
    home_button(kb)

    bot.send_message(
        chat_id,
        '🍕 <b>Одиночные пиццы</b>',
        parse_mode='HTML',
        reply_markup=kb
    )
def pizza_combo_menu(chat_id):
    kb = types.InlineKeyboardMarkup()

    for c in combos:
        kb.add(
            types.InlineKeyboardButton(
                f'📦 {c["name"]}',
                callback_data=f'combo_info_{c["id"]}'
            )
        )

    back_button(kb, 'menu_pizza')
    home_button(kb)

    bot.send_message(
        chat_id,
        '📦 <b>Комбо-наборы</b>',
        parse_mode='HTML',
        reply_markup=kb
    )
def pizza_details(chat_id, pid):
    p = next(x for x in pizzas if x['id'] == pid)

    kb = types.InlineKeyboardMarkup()

    # Проверяем, есть ли несколько размеров
    if "sizes" in p and p["sizes"]:
        for s in p["sizes"]:
            kb.add(types.InlineKeyboardButton(
                f'{s["diameter"]} см — {s["price"]} ₽',
                callback_data=f'add_to_cart_pizza_{pid}_{s["diameter"]}'
            ))
    else:
        # Если размер один (у старых пицц без поля sizes)
        kb.add(types.InlineKeyboardButton(
            f'{p.get("diameter", "—")} см — {p.get("price", "—")} ₽',
            callback_data=f'add_to_cart_pizza_{pid}_{p.get("diameter", 0)}'
        ))

    add_card_navigation(kb, 'pizza_single')

    text = (
        f'<b>{p["name"]}</b>\n\n'
        f'🧾 <b>Состав:</b>\n{p.get("ingredients", "—")}'
    )

    import time
    image_url = f'{p.get("image")}?v={int(time.time())}'

    send_item_with_image(
        chat_id,
        image_url,
        text,
        kb
    )

def combo_details(chat_id, cid):
    c = next(x for x in combos if x['id'] == cid)

    text = (
        f'<b>{c["name"]}</b>\n'
        f'💰 Цена: {c["price"]} ₽\n\n'
        f'{c["description"]}'
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        '➕ В корзину',
        callback_data=f'add_to_cart_combo_{cid}'
    ))

    add_card_navigation(kb, 'pizza_combo')

    bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=kb)


# ================= ДРУГИЕ РАЗДЕЛЫ =================
def additives_menu(chat_id):
    kb = types.InlineKeyboardMarkup()

    for a in additives:
        kb.add(
            types.InlineKeyboardButton(
                f'➕ {a["name"]} — {a["price"]} ₽',
                callback_data=f'add_to_cart_additive_{a["id"]}'
            )
        )

    home_button(kb)
    bot.send_message(
        chat_id,
        '➕ <b>Добавки</b>',
        parse_mode='HTML',
        reply_markup=kb
    )

def snacks_menu(chat_id):
    striptsy, sauces, other_snacks = split_snacks()

    kb = types.InlineKeyboardMarkup()

    for z in other_snacks:
        kb.add(types.InlineKeyboardButton(
            f'🍟 {z["name"]}',
            callback_data=f'snack_info_{z["id"]}'
        ))

    if striptsy:
        kb.add(types.InlineKeyboardButton(
            '🍗 Стрипсы',
            callback_data='snack_striptsy'
        ))

    if sauces:
        kb.add(types.InlineKeyboardButton(
            '🥫 Соусы',
            callback_data='snack_sauces'
        ))

    home_button(kb)
    bot.send_message(
        chat_id,
        '🍟 <b>Закуски</b>',
        parse_mode='HTML',
        reply_markup=kb
    )

def snack_details(chat_id, snack):
    text = f'<b>{snack["name"]}</b>\n💰 Цена: {snack["price"]} ₽'

    if snack.get("kolichestvo"):
        text += f'\n📦 Количество: {snack["kolichestvo"]} шт.'

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        '➕ В корзину',
        callback_data=f'add_to_cart_zakuska_{snack["id"]}'
    ))

    add_card_navigation(kb, 'menu_zakuski')

    bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=kb)


def striptsy_menu(chat_id):
    striptsy, _, _ = split_snacks()
    kb = types.InlineKeyboardMarkup()

    for s in striptsy:
        kb.add(types.InlineKeyboardButton(
            f'{s["kolichestvo"]} шт — {s["price"]} ₽',
            callback_data=f'add_to_cart_zakuska_{s["id"]}'
        ))

    back_button(kb, 'menu_zakuski')
    home_button(kb)
    bot.send_message(chat_id, '🍗 Стрипсы:', reply_markup=kb)
def snack_sauces_menu(chat_id):
    _, sauces, _ = split_snacks()

    kb = types.InlineKeyboardMarkup()

    for s in sauces:
        kb.add(
            types.InlineKeyboardButton(
                f'🥫 {s["name"]} — {s["price"]} ₽',
                callback_data=f'add_to_cart_zakuska_{s["id"]}'
            )
        )

    back_button(kb, 'menu_zakuski')
    home_button(kb)

    bot.send_message(
        chat_id,
        '🥫 <b>Соусы</b>',
        parse_mode='HTML',
        reply_markup=kb
    )

def drinks_menu(chat_id):
    kb = types.InlineKeyboardMarkup()

    # Общие категории напитков
    for key, category in DRINK_CATEGORIES.items():
        # Пропускаем лимонады, чтобы сделать отдельную кнопку
        if key in ['orange_yuzu', 'lemonade']:
            continue
        kb.add(types.InlineKeyboardButton(category['button'], callback_data=f'drink_cat_{key}'))

    # Кнопка отдельного меню лимонадов
    kb.add(types.InlineKeyboardButton('🍋 Лимонады', callback_data='drink_lemonades'))

    home_button(kb)
    bot.send_message(
        chat_id,
        '🥤 <b>Напитки</b>',
        parse_mode='HTML',
        reply_markup=kb
    )

def lemonades_menu(chat_id):
    kb = types.InlineKeyboardMarkup()
    # Дикий апельсин и юдзу
    kb.add(types.InlineKeyboardButton(
        DRINK_CATEGORIES['orange_yuzu']['button'],
        callback_data='drink_lemon_orange_yuzu'
    ))
    # Лимонад Черноголовка
    kb.add(types.InlineKeyboardButton(
        DRINK_CATEGORIES['lemonade']['button'],
        callback_data='drink_lemon_blackhead'
    ))

    back_button(kb, 'menu_napitki')
    home_button(kb)

    bot.send_message(
        chat_id,
        '🍋 <b>Лимонады</b>',
        parse_mode='HTML',
        reply_markup=kb
    )
def lemonade_details(chat_id, key):
    cat = DRINK_CATEGORIES[key]
    kb = types.InlineKeyboardMarkup()

    # Находим напитки соответствующие категории
    drinks = [d for d in drinks_list if cat['match'].lower() in d['name'].lower()]
    if not drinks:
        bot.send_message(chat_id, '❌ Напитки не найдены')
        return

    text = f'<b>{cat["title"]}</b>'
    if cat.get('description'):
        text += f'\n{cat["description"]}'

    # Кнопки с объёмом и ценой
    for d in drinks:
        kb.add(types.InlineKeyboardButton(
            f'{d["liters"]} л — {d["price"]} ₽',
            callback_data=f'add_to_cart_drink_{d["id"]}'
        ))

    back_button(kb, 'drink_lemonades')
    home_button(kb)

    bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=kb)
def drink_category_menu(chat_id, key):
    cat = DRINK_CATEGORIES.get(key)
    if not cat:
        return

    kb = types.InlineKeyboardMarkup()

    for d in drinks_list:
        if cat['match'] in d['name']:
            kb.add(types.InlineKeyboardButton(
                f'{d["liters"]} л — {d["price"]} ₽',
                callback_data=f'add_to_cart_drink_{d["id"]}'
            ))

    text = f'<b>{cat["title"]}</b>'
    if cat['description']:
        text += f'\n{cat["description"]}'

    back_button(kb, 'menu_napitki')
    home_button(kb)

    bot.send_message(
        chat_id,
        text,
        parse_mode='HTML',
        reply_markup=kb
    )

def shaurma_menu(chat_id):
    kb = types.InlineKeyboardMarkup()

    for s in shaurma_list:
        kb.add(types.InlineKeyboardButton(
            f'🌯 {s["name"]}',
            callback_data=f'shaurma_info_{s["id"]}'
        ))

    home_button(kb)
    bot.send_message(
        chat_id,
        '🌯 <b>Шаурма</b>',
        parse_mode='HTML',
        reply_markup=kb
    )
def shaurma_details(chat_id, sh):
    text = (
        f'<b>{sh["name"]}</b>\n'
        f'💰 Цена: {sh["price"]} ₽'
    )

    if sh.get('description'):
        text += f'\n\n🧾 <b>Состав:</b>\n{sh["description"]}'

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton(
            '➕ В корзину',
            callback_data=f'add_to_cart_shaurma_{sh["id"]}'
        )
    )

    add_card_navigation(kb, 'menu_shaurma')

    import time
    image_url = f'{sh.get("image")}?v={int(time.time())}'

    send_item_with_image(
        chat_id,
        image_url,
        text,
        kb
    )

# ================= ОФОРМЛЕНИЕ =================
def start_order(chat_id):
    if not user_carts.get(chat_id):
        bot.send_message(chat_id, '❌ Корзина пуста')
        return

    user_order_data.setdefault(chat_id, {})  # 🔥 ВАЖНО

    msg = bot.send_message(chat_id, '👤 Как вас зовут?')
    bot.register_next_step_handler(msg, get_name)


def get_name(message):
    chat_id = message.chat.id

    # гарантируем, что словарь существует
    user_order_data.setdefault(chat_id, {})

    user_order_data[chat_id]['name'] = message.text.strip()

    msg = bot.send_message(
        chat_id,
        '📞 Введите номер телефона:'
    )
    bot.register_next_step_handler(msg, get_phone)


def get_phone(message):
    chat_id = message.chat.id
    user_order_data.setdefault(chat_id, {})
    user_order_data[chat_id]['phone'] = message.text.strip()

    if user_order_data[chat_id].get('delivery_type') == 'Доставка':
        if user_order_data[chat_id].get('delivery_zone') == 'Город':
            msg = bot.send_message(chat_id, '📍 Введите адрес доставки:')
            bot.register_next_step_handler(msg, get_address)
        else:
            msg = bot.send_message(chat_id, '⏰ Укажите желаемое время доставки:')
            bot.register_next_step_handler(msg, get_delivery_time)
    else:
        ask_payment(chat_id)


def get_delivery_zone(message):
    chat_id = message.chat.id
    text = message.text.lower()

    if 'город' in text:
        user_order_data[chat_id]['delivery_zone'] = 'Город'
        user_order_data[chat_id]['delivery_price'] = None

        bot.send_message(
            chat_id,
            '🚚 <b>Доставка по городу</b>\n'
            'Минимальная стоимость доставки — <b>от 900 ₽</b>\n'
            'Точная сумма будет рассчитана администратором.',
            parse_mode='HTML'
        )

        msg = bot.send_message(chat_id, '📍 Введите адрес доставки:')
        bot.register_next_step_handler(msg, get_address)
        return

    # ===== РАЙОН =====
    user_order_data[chat_id]['delivery_zone'] = 'Район'

    kb = types.InlineKeyboardMarkup(row_width=2)
    for name, price in DISTRICT_PRICES.items():
        kb.add(
            types.InlineKeyboardButton(
                f'{name} — {price} ₽',
                callback_data=f'district_{name}'
            )
        )

    kb.add(types.InlineKeyboardButton(
        '✍️ Другой населённый пункт',
        callback_data='district_other'
    ))

    bot.send_message(
        chat_id,
        '🚚 <b>Доставка по району</b>\n'
        'ℹ️ Минимальная стоимость доставки — <b>от 1200 ₽</b>\n'
        'Выберите населённый пункт:',
        parse_mode='HTML',
        reply_markup=kb
    )

def get_address(message):
    chat_id = message.chat.id
    user_order_data[chat_id]['address'] = message.text

    msg = bot.send_message(chat_id, '⏰ Укажите желаемое время доставки:')
    bot.register_next_step_handler(msg, get_delivery_time)


def get_delivery_time(message):
    chat_id = message.chat.id
    user_order_data[chat_id]['delivery_time'] = message.text

    ask_payment(chat_id)

def ask_payment(chat_id):
    kb = types.InlineKeyboardMarkup(row_width=1)

    kb.add(
        types.InlineKeyboardButton('💵 Наличными', callback_data='pay_cash'),
        types.InlineKeyboardButton('🔁 Переводом', callback_data='pay_transfer'),
        types.InlineKeyboardButton('💳 Банковской картой', callback_data='pay_card')
    )

    bot.send_message(
        chat_id,
        '💳 <b>Как вы хотите оплатить заказ?</b>',
        parse_mode='HTML',
        reply_markup=kb
    )

def ask_cash_change(chat_id):
    msg = bot.send_message(
        chat_id,
        '💵 С какой суммы нужна сдача?\n'
        'Например: 1000\n'
        'Если без сдачи — напишите «без сдачи»'
    )
    bot.register_next_step_handler(msg, get_cash_change)

def get_cash_change(message):
    chat_id = message.chat.id
    user_order_data[chat_id]['cash_change'] = message.text
    ask_comment(chat_id)

def ask_comment(chat_id):
    msg = bot.send_message(
        chat_id,
        '📝 Комментарий к заказу (если нет — напишите «нет»):'
    )
    bot.register_next_step_handler(msg, get_comment)

def get_comment(message):
    chat_id = message.chat.id
    text = message.text

    if text.lower() == 'нет':
        text = '—'

    user_order_data[chat_id]['comment'] = text
    finish_order(chat_id)

def finish_order(chat_id):
    order_id = save_order(chat_id)

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton('🏠 Главное меню', callback_data='back_main')
    )

    bot.send_message(
        chat_id,
        f'✅ Заказ успешно оформлен!\n'
        f'🆔 Номер заказа: {order_id}\n'
        f'Мы будем уведомлять вас о статусе заказа 🙌',
        reply_markup=kb
    )

    # Очищаем корзину и данные заказа
    user_carts[chat_id] = []
    user_order_data.pop(chat_id, None)

def notify_admin_new_order(order_id):
    for admin_id in get_all_admins():
        try:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton('🛠 Новые заказы', callback_data='admin_orders'))

            bot.send_message(
                admin_id,
                f'📣 <b>Поступил новый заказ!</b> №{order_id}',
                parse_mode='HTML',
                reply_markup=kb
            )
        except Exception as e:
            print(f"Ошибка отправки уведомления администратору {admin_id}: {e}")

def send_order_to_archive_group(order_id):
    cursor.execute('SELECT is_sent_to_group FROM orders WHERE id = ?', (order_id,))
    row = cursor.fetchone()
    if row and row[0] == 1:
        return  # Заказ уже был отправлен в группу

    text = build_admin_order_text(order_id)

    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton(
            '📦 Заказ заархивирован',
            callback_data='archive_stub'
        )
    )

    bot.send_message(
        ARCHIVE_GROUP_ID,
        text,
        parse_mode='HTML',
        reply_markup=kb,
        disable_web_page_preview=True
    )

    # Обновляем флаг отправки в группу
    cursor.execute('UPDATE orders SET is_sent_to_group = 1 WHERE id = ?', (order_id,))
    conn.commit()

def save_order(chat_id):
    data = user_order_data[chat_id]
    order_text = build_order_text(chat_id)  # Формируем текст заказа из корзины

    now = datetime.now(tz)
    created_at = now.strftime('%d/%m/%Y - %H:%M')

    cursor.execute('''
        INSERT INTO orders (
            user_id, name, phone, delivery_type, delivery_zone, address,
            delivery_time, payment_method, cash_change, comment,
            order_text, order_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        chat_id,
        data.get('name', ''),
        data.get('phone', ''),
        data.get('delivery_type', ''),
        data.get('delivery_zone', ''),
        data.get('address', ''),
        data.get('delivery_time', ''),
        data.get('payment_method', ''),
        data.get('cash_change', '—'),
        data.get('comment', '—'),
        order_text,
        'Новый',
        created_at
    ))

    conn.commit()
    order_id = cursor.lastrowid

    # Уведомляем администратора о новом заказе
    notify_admin_new_order(order_id)

    return order_id


# ================= CALLBACK =================
@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):
    chat_id = c.message.chat.id
    d = c.data

    # ===== ГЛАВНОЕ МЕНЮ =====
    if d == 'menu_pizza':
        pizza_menu(chat_id)
    elif d == 'pizza_single':
        pizza_single_menu(chat_id)
    elif d == 'pizza_combo':
        pizza_combo_menu(chat_id)
    elif d == 'menu_additives':
        additives_menu(chat_id)
    elif d == 'menu_zakuski':
        snacks_menu(chat_id)
    elif d == 'menu_shaurma':
        shaurma_menu(chat_id)
    elif d == 'back_main':
        main_menu(chat_id)
    elif d == 'admin_orders':
        show_all_orders_admin(chat_id)
    elif d == 'admin_archive':
        show_archive_orders_admin(chat_id)
    elif d.startswith('admin_order_'):
        order_id = int(d.split('_')[2])
        show_order_detail_admin(chat_id, order_id)
    elif d == 'archive_search':
        msg = bot.send_message(
            chat_id,
            '🔍 Введите:\n'
            '• номер заказа (например: 125)\n'
            '• или дату (например: 12/03/2025)'
        )
        bot.register_next_step_handler(msg, search_archive)
    elif d == 'admin_manage':
        admin_manage_menu(chat_id)

    elif d == 'admin_add':
        msg = bot.send_message(chat_id, '🆔 Введите Telegram ID пользователя:')
        bot.register_next_step_handler(msg, admin_add_handler)

    elif d == 'about_us':
        text = (
            '🍕 <b>PAPA PIZZA</b>\n\n'
            'Если хочешь подкрепиться — позвони нам ☎️\n'
            '🔵 Мы в ВКонтакте:\n'
            'https://vk.com/pizzakansk\n\n'
            '🕙 <b>Время работы:</b>\n'
            'с 10:00 до 22:00\n\n'
            '🚚 <b>Доставка:</b>\n'
            '• По городу — 100 ₽\n'
            '• <b>Бесплатно от 900 ₽</b>\n\n'
            '🏢 <b>ИП:</b> Храмцова Полина Александровна\n'
            '🧾 <b>ИНН:</b> 245010278534\n\n'
            '📍 <b>Адрес:</b>\n'
            '40 лет Октября, 1/6, Канск'
        )

        kb = types.InlineKeyboardMarkup(row_width=2)

        # Кнопки в одном ряду
        kb.add(
            types.InlineKeyboardButton('📞 Позвонить', callback_data='call_phone'),

        )

        kb.add(
            types.InlineKeyboardButton(
                '🗺 Открыть карту',
                url='https://yandex.ru/maps/-/CLtcqXKo'
            )
        )

        kb.add(
            types.InlineKeyboardButton('◀️ Назад', callback_data='back_main')
        )

        bot.send_message(
            chat_id,
            text,
            parse_mode='HTML',
            reply_markup=kb,
            disable_web_page_preview=True
        )

    elif d == 'call_phone':
        bot.send_message(
            chat_id,
            '📞 <b>PAPA PIZZA</b>\n\n'
            'Нажмите на номер ниже, чтобы позвонить 👇\n\n'
            '<a href="tel:+79538492223">+79538492223</a>',
            parse_mode='HTML',
            disable_web_page_preview=True
        )


    elif d.startswith('remove_admin_'):
        admin_id = int(d.split('_')[2])

        # Убедимся, что пользователь пытается удалить другого администратора, а не себя
        if admin_id == chat_id:
            bot.answer_callback_query(c.id, 'Нельзя удалить самого себя!')
            return

        cursor.execute('DELETE FROM admins WHERE user_id = ?', (admin_id,))
        conn.commit()

        bot.answer_callback_query(c.id, f'Администратор {admin_id} удалён')
        # После удаления заново показать список администраторов
        admin_manage_menu(chat_id)


        # Напитки
    if d == 'menu_napitki':
        drinks_menu(chat_id)
    elif d.startswith('drink_cat_'):
        key = d.replace('drink_cat_', '')
        drink_category_menu(chat_id, key)

        # Лимонады
    elif d == 'drink_lemonades':
        lemonades_menu(chat_id)
    elif d == 'drink_lemon_orange_yuzu':
        lemonade_details(chat_id, 'orange_yuzu')
    elif d == 'drink_lemon_blackhead':
        lemonade_details(chat_id, 'lemonade')

        # Добавление в корзину
    elif d.startswith('add_to_cart_drink_'):
        drink_id = int(d.replace('add_to_cart_drink_', ''))
        drink = next((x for x in drinks_list if x['id'] == drink_id), None)
        if drink:
            add_to_cart(chat_id, 'drink', drink, call_id=c.id)

    # ===== ИНФОРМАЦИЯ О ПРЕДМЕТАХ =====
    elif d.startswith('pizza_info_'):
        pizza_details(chat_id, int(d.split('_')[2]))
    elif d.startswith('combo_info_'):
        combo_details(chat_id, int(d.split('_')[2]))
    elif d.startswith('snack_info_'):
        sid = int(d.split('_')[2])
        snack = next(x for x in zakuski_menu if x["id"] == sid)
        snack_details(chat_id, snack)
    elif d.startswith('shaurma_info_'):
        sid = int(d.split('_')[2])
        sh = next((x for x in shaurma_list if x['id'] == sid), None)
        if sh:
            shaurma_details(chat_id, sh)


    # ===== СПЕЦИАЛЬНЫЕ МЕНЮ =====
    elif d == 'snack_striptsy':
        striptsy_menu(chat_id)
    elif d == 'snack_sauces':
        snack_sauces_menu(chat_id)
    elif d.startswith('archive_toggle_'):
        month_key = d.replace('archive_toggle_', '')

        archive_month_state.setdefault(chat_id, {})
        current = archive_month_state[chat_id].get(month_key, True)

        # переключаем состояние
        archive_month_state[chat_id][month_key] = not current

        show_archive_orders_admin(chat_id)

    elif d == 'archive_delete':
        archive_delete_menu(chat_id)

    elif d == 'archive_delete_month':
        archive_delete_month_menu(chat_id)

    elif d.startswith('archive_delete_month_'):
        month_key = d.replace('archive_delete_month_', '')
        delete_archive_month(chat_id, month_key)

    elif d == 'archive_delete_order':
        msg = bot.send_message(
            chat_id,
            '📦 Введите номер заказа для удаления из архива:'
        )
        bot.register_next_step_handler(msg, ask_delete_order_id)


    # ===== КОРЗИНА =====
    elif d == 'show_cart':
        show_cart(chat_id)
    elif d.startswith('cart_plus_'):
        idx = int(d.split('_')[2])
        if idx < len(user_carts[chat_id]):
            user_carts[chat_id][idx]['quantity'] += 1
            bot.answer_callback_query(c.id, 'Количество увеличено')
            show_cart(chat_id)
    elif d.startswith('cart_minus_'):
        idx = int(d.split('_')[2])
        if idx < len(user_carts[chat_id]):
            if user_carts[chat_id][idx]['quantity'] > 1:
                user_carts[chat_id][idx]['quantity'] -= 1
                bot.answer_callback_query(c.id, 'Количество уменьшено')
            else:
                user_carts[chat_id].pop(idx)
                bot.answer_callback_query(c.id, 'Товар удалён')
            show_cart(chat_id)
    elif d.startswith('cart_del_'):
        idx = int(d.split('_')[2])
        if idx < len(user_carts[chat_id]):
            user_carts[chat_id].pop(idx)
            bot.answer_callback_query(c.id, 'Товар удалён')
            show_cart(chat_id)
    elif d == 'checkout':
        total = get_cart_total(chat_id)
        text = (
            "⚠️ <b>Внимание!</b>\n\n"
            "Если вам нужна доставка, минимальная сумма заказа:\n"
            "🏙 <b>По городу</b> — от <b>900 ₽</b>\n"
            "🌄 <b>По району</b> — от <b>1500 ₽</b>\n\n"
            f"💰 Сейчас в корзине: <b>{total} ₽</b>\n\n"
            "Как вы хотите получить заказ?"
        )

        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton('🏠 Самовывоз', callback_data='pre_pickup'),
            types.InlineKeyboardButton('🚚 Доставка', callback_data='pre_delivery'),
            types.InlineKeyboardButton('◀️ Назад в корзину', callback_data='show_cart')
        )

        bot.send_message(
            chat_id,
            text,
            parse_mode='HTML',
            reply_markup=kb
        )

    elif d == 'pre_pickup':
        user_order_data[chat_id] = {
            'delivery_type': 'Самовывоз',
            'address': 'Самовывоз',
            'delivery_time': '—'
        }
        start_order(chat_id)

    # ===== ЕДИНОЕ МЕНЮ ДОСТАВКИ =====
    elif d == 'pre_delivery':
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton('🏙 По городу', callback_data='check_city'),
            types.InlineKeyboardButton('🌄 По району', callback_data='check_district'),
            types.InlineKeyboardButton('◀️ Назад', callback_data='show_cart')
        )
        bot.send_message(
            chat_id,
            '🚚 <b>Выберите тип доставки:</b>',
            parse_mode='HTML',
            reply_markup=kb
        )

    elif d in ['check_city', 'check_district']:
        # Новый единый блок обработки доставки
        total = get_cart_total(chat_id)
        if d == 'check_city':
            min_sum = 900
            delivery_type = 'Городу'
        else:
            min_sum = 1500
            delivery_type = 'Району'

        if total < min_sum:
            bot.send_message(
                chat_id,
                f'❌ Недостаточная сумма для доставки по {delivery_type.lower()}.\n'
                f'Минимум: {min_sum} ₽\n'
                f'Сейчас: {total} ₽\n'
                f'Не хватает: {min_sum - total} ₽'
            )
            return

        if d == 'check_city':
            user_order_data[chat_id] = {
                'delivery_type': 'Доставка',
                'delivery_zone': 'Город',
                'delivery_price': None,
                'address': 'По городу'
            }
            bot.send_message(
                chat_id,
                f'🚚 <b>Доставка по городу</b>\n'
                f'Сумма корзины: {total} ₽\n'
                f'Итого: {total} ₽\n\n'
                f'Начнем оформление заказа:',
                parse_mode='HTML'
            )
            start_order(chat_id)
        else:
            kb = types.InlineKeyboardMarkup(row_width=2)
            for name, price in DISTRICT_PRICES.items():
                kb.add(types.InlineKeyboardButton(f'{name} — {price} ₽', callback_data=f'district_{name}'))
            kb.add(types.InlineKeyboardButton('✍️ Моего населённого пункта нет', callback_data='district_other'))
            bot.send_message(
                chat_id,
                '🚚 <b>Доставка по району</b>\nВыберите населённый пункт или напишите свой:',
                parse_mode='HTML',
                reply_markup=kb
            )

    elif d.startswith('district_'):
        district = d.replace('district_', '')

        # ===== РУЧНОЙ ВВОД НАСЕЛЁННОГО ПУНКТА =====
        if district == 'other':
            msg = bot.send_message(
                chat_id,
                '✍️ Напишите населённый пункт:\n'
                '⚠️ Стоимость доставки уточнит администратор'
            )
            bot.register_next_step_handler(msg, manual_district)
            return

        # ===== ВЫБРАЛИ НАСЕЛЁННЫЙ ПУНКТ ИЗ СПИСКА =====
        delivery_price = DISTRICT_PRICES.get(district, 0)
        cart_total = get_cart_total(chat_id)
        total_with_delivery = cart_total + delivery_price

        # 🔥 СОХРАНЯЕМ ДАННЫЕ
        user_order_data[chat_id] = {
            'delivery_type': 'Доставка',
            'delivery_zone': 'Район',
            'address': district,  # адрес = населённый пункт
            'delivery_price': delivery_price
        }

        # 📩 ПОКАЗЫВАЕМ ИТОГ
        bot.send_message(
            chat_id,
            f'📍 Населённый пункт: <b>{district}</b>\n'
            f'🛒 Сумма заказа: {cart_total} ₽\n'
            f'🚚 Доставка: {delivery_price} ₽\n'
            f'💰 <b>Итого: {total_with_delivery} ₽</b>\n\n'
            f'Начнём оформление заказа 👇',
            parse_mode='HTML'
        )

        # ✅ СТАРТ СЦЕНАРИЯ: ИМЯ → ТЕЛЕФОН → ВРЕМЯ
        start_order(chat_id)

        # ===== ИСТОРИЯ ЗАКАЗОВ =====
    elif d == 'order_history':
        if is_admin(chat_id):
            bot.answer_callback_query(c.id, '❌ История заказов доступна только клиентам')
            return

        show_order_history(chat_id)


    elif d.startswith('order_detail_'):
        order_id = int(d.split('_')[2])

        if is_admin(chat_id):
            bot.answer_callback_query(c.id, '❌ Администраторам история клиентов недоступна')
            return

        show_order_detail_user(chat_id, order_id)


    # ===== СТАТУСЫ ЗАКАЗОВ (ОПЕРАТОР) =====
    elif d.startswith('status_'):
        _, order_id_str, status_key = d.split('_')
        order_id = int(order_id_str)

        if status_key not in ORDER_STATUSES:
            bot.answer_callback_query(c.id, '❌ Некорректный статус')
            return

        cursor.execute('SELECT order_status, is_archived, user_id, is_sent_to_group FROM orders WHERE id = ?',
                       (order_id,))
        row = cursor.fetchone()
        if not row:
            bot.answer_callback_query(c.id, '❌ Заказ не найден')
            return

        current_status, is_archived, user_id, is_sent_to_group = row

        new_status = ORDER_STATUSES[status_key]
        new_is_archived = 1 if status_key in ('done', 'canceled') else 0

        cursor.execute(
            '''
            UPDATE orders
            SET order_status = ?, is_archived = ?
            WHERE id = ?
            ''',
            (new_status, new_is_archived, order_id)
        )
        conn.commit()

        if new_status == ORDER_STATUSES['done'] and not is_sent_to_group:
            send_order_to_archive_group(order_id)

        if user_id:
            try:
                bot.send_message(
                    user_id,
                    f'📦 Статус вашего заказа №{order_id}: {new_status}'
                )
            except:
                pass

        if new_is_archived:
            show_archive_orders_admin(chat_id)
        else:
            text = build_admin_order_text(order_id)
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=c.message.message_id,
                text=text,
                parse_mode='HTML',
                reply_markup=operator_status_keyboard(order_id)
            )

        bot.answer_callback_query(c.id, f'Статус: {new_status}')

    # ===== ОПЛАТА =====
    elif d.startswith('pay_'):
        payment_map = {
            'pay_cash': 'Наличными',
            'pay_transfer': 'Переводом',
            'pay_card': 'Банковской картой'
        }
        user_order_data[chat_id]['payment_method'] = payment_map[d]
        bot.answer_callback_query(c.id, f'Выбрано: {payment_map[d]}')
        if d == 'pay_cash':
            ask_cash_change(chat_id)
        else:
            user_order_data[chat_id]['cash_change'] = '—'
            ask_comment(chat_id)

    # ===== ДОСТАВКА/САМОЗАБОР ЗАВЕРШЕНИЕ =====
    # ===== ДОБАВЛЕНИЕ В КОРЗИНУ ПИЦЦЫ С ВЫБОРОМ РАЗМЕРА =====
    elif d.startswith('add_to_cart_pizza_'):
        parts = d.replace('add_to_cart_pizza_', '').split('_')

        pid = int(parts[0])
        diameter = int(parts[1]) if len(parts) > 1 else None

        pizza = next(x for x in pizzas if x['id'] == pid)

        # ----- ПИЦЦЫ С НЕСКОЛЬКИМИ РАЗМЕРАМИ -----
        if 'sizes' in pizza:
            size_data = next(
                (s for s in pizza['sizes'] if s['diameter'] == diameter),
                None
            )

            if size_data:
                item = pizza.copy()
                item['diameter'] = size_data['diameter']
                item['price'] = size_data['price']

                item.pop('grams', None)

                add_to_cart(chat_id, 'pizza', item, c.id)
                return

        # ----- ПИЦЦЫ С ОДНИМ РАЗМЕРОМ -----
        item = pizza.copy()
        item.pop('grams', None)

        add_to_cart(chat_id, 'pizza', item, c.id)

    elif d.startswith('add_to_cart_'):
        t, i = d.replace('add_to_cart_', '').split('_')
        sources = {
            'pizza': pizzas,
            'combo': combos,
            'zakuska': zakuski_menu,
            'drink': drinks_list,
            'shaurma': shaurma_list,
            'additive': additives
        }
        item = next(x for x in sources[t] if x['id'] == int(i))
        add_to_cart(chat_id, t, item, c.id)


# ================= ТЕКСТОВЫЕ КОМАНДЫ =================
@bot.message_handler(commands=['start', 'menu'])
def cmd_start(message):
    main_menu(message.chat.id)


@bot.message_handler(func=lambda m: m.text and m.text.lower() in ('меню', 'menu', '/menu', 'главное меню'))
def force_main_menu(message):
    chat_id = message.chat.id

    # 🔥 ОЧИЩАЕМ next_step_handler
    bot.clear_step_handler_by_chat_id(chat_id)

    # (опционально) очищаем незавершённый заказ
    user_order_data.pop(chat_id, None)

    main_menu(chat_id)


@bot.message_handler(func=lambda m: m.text and m.text.lower() == 'назад')
def text_back(message):
    main_menu(message.chat.id)

@bot.message_handler(func=lambda m: m.text and m.text.lower() == 'узнать свой id')
def send_user_id(message):
    chat_id = message.chat.id
    bot.reply_to(message, f"Ваш Telegram ID: `{chat_id}`", parse_mode="Markdown")

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    file_id = message.photo[-1].file_id

    bot.send_message(
        message.chat.id,
        f'🆔 <b>file_id изображения:</b>\n<code>{file_id}</code>',
        parse_mode='HTML'
    )

# ================= ЗАПУСК =================
bot.infinity_polling(
    timeout=60,
    long_polling_timeout=60
)

