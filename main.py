import os
import json
import logging
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "8584774550:AAGtw2Nk_pbFvrw2fOipJo2wlyZ4vxTTNu8"
ADMIN_CHAT_ID = 7088391128

SLOTS_FILE = "slots.json"
BOOKINGS_FILE = "bookings.json"

# ===== ЛОГИРОВАНИЕ =====
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== РАБОТА С ФАЙЛАМИ =====
def load_json(filepath, default=None):
    if default is None:
        default = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_slots():
    slots = load_json(SLOTS_FILE, [])
    now = datetime.now()
    valid = []
    for s in slots:
        try:
            dt = datetime.strptime(s, "%d.%m.%Y %H:%M")
            if dt > now:
                valid.append(s)
        except ValueError:
            pass
    if len(valid) != len(slots):
        save_json(SLOTS_FILE, valid)
    return valid

def add_slot(date_str, time_str):
    slot = f"{date_str} {time_str}"
    slots = get_slots()
    if slot not in slots:
        slots.append(slot)
        slots.sort(key=lambda s: datetime.strptime(s, "%d.%m.%Y %H:%M"))
        save_json(SLOTS_FILE, slots)
        return True
    return False

def remove_slot(slot_str):
    slots = get_slots()
    if slot_str in slots:
        slots.remove(slot_str)
        save_json(SLOTS_FILE, slots)
        return True
    return False

def add_booking(booking):
    bookings = load_json(BOOKINGS_FILE, [])
    bookings.append(booking)
    save_json(BOOKINGS_FILE, bookings)

def get_bookings():
    return load_json(BOOKINGS_FILE, [])

# ===== СОСТОЯНИЯ =====
BOOKING_NAME, BOOKING_CONTACT, BOOKING_NOTE = range(3)

# ===== ТЕКСТЫ =====
WELCOME_TEXT = """🌿 *Здравствуйте! Я — бот психолога Кристины Шелест.*

Я помогу вам:
• Узнать об услугах и стоимости
• Записаться на консультацию
• Получить ответы на частые вопросы

Выберите, что вас интересует 👇"""

ABOUT_TEXT = """👩‍⚕️ *Кристина Шелест*
_Кризисный психолог_

Работаю с людьми, столкнувшимися с травматическим опытом, насилием, потерями и тревожными расстройствами.

🎓 *Образование:*
• Высшее психологическое образование
• Профессиональная переподготовка: «Кризисная психология»
• Регулярная супервизия и личная терапия

💡 *Подход:*
• Когнитивно-поведенческая терапия (КПТ)
• Кризисное консультирование
• Работа с травмой

📍 Очно — Москва
🌐 Онлайн — из любой точки мира

🔗 [Сайт](https://kristina-shelest.ru)"""

SERVICES_TEXT = """📋 *С чем я работаю:*

*1. ПТСР и последствия травматического опыта*
Флешбэки, ночные кошмары, эмоциональное онемение, гипербдительность, избегание.

*2. Фобии и тревожные расстройства*
Панические атаки, конкретные фобии, ГТР, социальная тревожность.

*3. Последствия насилия*
Домашнее, сексуальное, эмоциональное насилие, буллинг.

*4. Проблемы самооценки и негативные убеждения*
Хроническая самокритика, перфекционизм, синдром самозванца, токсический стыд.

*5. Трудности в отношениях*
Повторяющиеся конфликты, созависимость, избегание близости, когнитивные искажения.

👇 Нажмите, чтобы узнать стоимость:"""

PRICES_TEXT = """💰 *Стоимость консультаций:*

🕐 *1 час (50 минут)*
🌐 Онлайн — *3 500 ₽*
🏠 Очно (Москва) — *4 000 ₽*

🕑 *2 часа (1 час 50 минут)* ⭐ рекомендую
🌐 Онлайн — *7 000 ₽*
🏠 Очно (Москва) — *8 000 ₽*

💡 _Почему 2 часа лучше?_
_За один час мы знакомимся и обозначаем проблему. За два — можно по-настоящему погрузиться в запрос и начать глубокую проработку. Особенно рекомендую для первой встречи._

🆘 *Экстренная консультация*
до 30 минут — *5 000 ₽*
Связь в течение 2 часов после обращения

_Оплата: перевод на карту перед сессией._"""

FAQ_TEXT = """❓ *Частые вопросы:*

Выберите вопрос, который вас интересует 👇"""

FAQ_ANSWERS = {
    "faq_first": "🔹 *Как проходит первая консультация?*\n\nПервая встреча — это знакомство. Мы обсудим ваш запрос, я расскажу, как строится работа и какие методы использую. Вы решите, комфортно ли вам продолжать. Никакого давления — это ваш выбор.\n\nДлительность: 50 минут.",
    "faq_howmany": "🔹 *Сколько сессий нужно?*\n\nЗависит от запроса. Иногда достаточно 5–10 встреч, в более сложных случаях работа может занять несколько месяцев. Мы обсудим примерные сроки уже на первой консультации.\n\nСредний курс: 8–16 сессий.",
    "faq_conf": "🔹 *Это конфиденциально?*\n\nДа. Всё, что вы рассказываете на сессии, строго конфиденциально. Я соблюдаю этический кодекс психолога. Без вашего письменного согласия информация не передаётся третьим лицам.",
    "faq_approach": "🔹 *Какой подход вы используете?*\n\nОснова моей работы — когнитивно-поведенческая терапия (КПТ). Это один из наиболее исследованных и эффективных подходов при тревоге, депрессии и ПТСР. Также использую техники кризисного консультирования и работы с травмой.",
    "faq_cancel": "🔹 *Можно ли отменить или перенести сессию?*\n\nДа. Пожалуйста, предупредите не менее чем за 24 часа. При отмене менее чем за 24 часа сессия считается состоявшейся.\n\nПеренос — бесплатно при предупреждении за 24+ часов.",
    "faq_online": "🔹 *Как проходит онлайн-консультация?*\n\nВидеозвонок в Zoom, Telegram или WhatsApp — на ваш выбор. Всё, что нужно — устойчивый интернет и тихое место, где вас не побеспокоят. Онлайн-формат так же эффективен, как и очный.",
}

AUTO_REPLY_TEXT = """🕐 *Спасибо за сообщение!*

Сейчас я не на связи, но обязательно отвечу вам в течение 24 часов.

Если вам нужна срочная помощь:
• Запишитесь через бота — нажмите /start
• Телефон доверия: *8-800-2000-122* (бесплатно, круглосуточно)"""

DAYS_RU = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}

# ===== КЛАВИАТУРЫ =====
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Услуги", callback_data="services"),
         InlineKeyboardButton("💰 Стоимость", callback_data="prices")],
        [InlineKeyboardButton("❓ Частые вопросы", callback_data="faq"),
         InlineKeyboardButton("👩‍⚕️ Обо мне", callback_data="about")],
        [InlineKeyboardButton("📅 Записаться на консультацию", callback_data="book")],
        [InlineKeyboardButton("💬 Связаться напрямую", callback_data="contact")]
    ])

def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Главное меню", callback_data="menu")]])

def services_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Стоимость", callback_data="prices")],
        [InlineKeyboardButton("📅 Записаться", callback_data="book")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="menu")]
    ])

def prices_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 Записаться", callback_data="book")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="menu")]
    ])

def faq_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Первая консультация", callback_data="faq_first")],
        [InlineKeyboardButton("Сколько сессий нужно?", callback_data="faq_howmany")],
        [InlineKeyboardButton("Конфиденциальность", callback_data="faq_conf")],
        [InlineKeyboardButton("Какой подход?", callback_data="faq_approach")],
        [InlineKeyboardButton("Отмена/перенос", callback_data="faq_cancel")],
        [InlineKeyboardButton("Онлайн-консультация", callback_data="faq_online")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="menu")]
    ])

def faq_answer_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❓ Другие вопросы", callback_data="faq")],
        [InlineKeyboardButton("📅 Записаться", callback_data="book")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="menu")]
    ])

def contact_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✈️ Telegram", url="https://t.me/Shelest_Kristina")],
        [InlineKeyboardButton("📱 WhatsApp", url="https://wa.me/79627522929")],
        [InlineKeyboardButton("📧 Email", url="mailto:Leshestk@mail.ru")],
        [InlineKeyboardButton("🌐 Сайт", url="https://kristina-shelest.ru")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="menu")]
    ])

def format_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌐 Онлайн", callback_data="fmt_online")],
        [InlineKeyboardButton("🏠 Очно (Москва)", callback_data="fmt_offline")],
        [InlineKeyboardButton("🆘 Экстренная — 5 000 ₽", callback_data="fmt_urgent")],
        [InlineKeyboardButton("◀️ Главное меню", callback_data="menu")]
    ])

def duration_keyboard(fmt):
    """Клавиатура выбора длительности: 1 час или 2 часа"""
    if fmt == "fmt_online":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🕐 1 час — 3 500 ₽", callback_data=f"dur_{fmt}_1h")],
            [InlineKeyboardButton("🕑 2 часа — 7 000 ₽ ⭐", callback_data=f"dur_{fmt}_2h")],
            [InlineKeyboardButton("◀️ Назад", callback_data="book")]
        ])
    elif fmt == "fmt_offline":
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🕐 1 час — 4 000 ₽", callback_data=f"dur_{fmt}_1h")],
            [InlineKeyboardButton("🕑 2 часа — 8 000 ₽ ⭐", callback_data=f"dur_{fmt}_2h")],
            [InlineKeyboardButton("◀️ Назад", callback_data="book")]
        ])

def slots_keyboard(fmt):
    slots = get_slots()
    if not slots:
        return None
    dates = {}
    for s in slots:
        d, t = s.split(" ")
        dates.setdefault(d, []).append(t)
    buttons = []
    for date in sorted(dates.keys(), key=lambda x: datetime.strptime(x, "%d.%m.%Y")):
        dt = datetime.strptime(date, "%d.%m.%Y")
        day_name = DAYS_RU[dt.weekday()]
        buttons.append([InlineKeyboardButton(f"📅 {date} ({day_name})", callback_data="noop")])
        row = []
        for time in sorted(dates[date]):
            row.append(InlineKeyboardButton(f"🕐 {time}", callback_data=f"slot_{fmt}_{date}_{time}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
    buttons.append([InlineKeyboardButton("◀️ Главное меню", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)

FORMATS = {
    "dur_fmt_online_1h": "🌐 Онлайн, 1 час (3 500 ₽)",
    "dur_fmt_online_2h": "🌐 Онлайн, 2 часа (7 000 ₽)",
    "dur_fmt_offline_1h": "🏠 Очно, 1 час (4 000 ₽)",
    "dur_fmt_offline_2h": "🏠 Очно, 2 часа (8 000 ₽)",
    "fmt_urgent": "🆘 Экстренная (5 000 ₽)"
}

DURATION_TEXT = """🕑 *Рекомендую формат 2 часа* ⭐

За один час мы знакомимся и обозначаем проблему. За два — можно по-настоящему погрузиться в запрос и начать глубокую проработку.

_Особенно рекомендую для первой встречи._

Выберите длительность 👇"""

# ===== ОБРАБОТЧИКИ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_TEXT, parse_mode="Markdown", reply_markup=main_menu_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "noop":
        return
    elif data == "menu":
        await query.edit_message_text(WELCOME_TEXT, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    elif data == "services":
        await query.edit_message_text(SERVICES_TEXT, parse_mode="Markdown", reply_markup=services_keyboard())
    elif data == "prices":
        await query.edit_message_text(PRICES_TEXT, parse_mode="Markdown", reply_markup=prices_keyboard())
    elif data == "about":
        await query.edit_message_text(ABOUT_TEXT, parse_mode="Markdown", reply_markup=back_keyboard(), disable_web_page_preview=True)
    elif data == "faq":
        await query.edit_message_text(FAQ_TEXT, parse_mode="Markdown", reply_markup=faq_keyboard())
    elif data.startswith("faq_"):
        await query.edit_message_text(FAQ_ANSWERS.get(data, "?"), parse_mode="Markdown", reply_markup=faq_answer_keyboard())
    elif data == "contact":
        await query.edit_message_text("💬 *Свяжитесь со мной удобным способом:*", parse_mode="Markdown", reply_markup=contact_keyboard())
    elif data == "book":
        await query.edit_message_text("📅 *Запись на консультацию*\n\nВыберите формат:", parse_mode="Markdown", reply_markup=format_keyboard())
    elif data in ("fmt_online", "fmt_offline"):
        # Показываем выбор длительности
        await query.edit_message_text(
            DURATION_TEXT, parse_mode="Markdown",
            reply_markup=duration_keyboard(data))
    elif data == "fmt_urgent":
        # Экстренная — сразу к слотам
        context.user_data["format"] = FORMATS.get("fmt_urgent", "?")
        context.user_data["format_key"] = "fmt_urgent"
        kb = slots_keyboard("fmt_urgent")
        if kb:
            await query.edit_message_text(
                f"Вы выбрали: *{context.user_data['format']}*\n\nВыберите удобную дату и время 👇",
                parse_mode="Markdown", reply_markup=kb)
        else:
            await query.edit_message_text(
                f"Вы выбрали: *{context.user_data['format']}*\n\n😔 Сейчас нет свободных слотов.\nНапишите мне, и мы подберём время:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Связаться", callback_data="contact")],
                    [InlineKeyboardButton("◀️ Меню", callback_data="menu")]
                ]))
    elif data.startswith("dur_"):
        # Выбрана длительность — показываем слоты
        context.user_data["format"] = FORMATS.get(data, "?")
        context.user_data["format_key"] = data
        kb = slots_keyboard(data)
        if kb:
            await query.edit_message_text(
                f"Вы выбрали: *{context.user_data['format']}*\n\nВыберите удобную дату и время 👇",
                parse_mode="Markdown", reply_markup=kb)
        else:
            await query.edit_message_text(
                f"Вы выбрали: *{context.user_data['format']}*\n\n😔 Сейчас нет свободных слотов.\nНапишите мне, и мы подберём время:",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Связаться", callback_data="contact")],
                    [InlineKeyboardButton("◀️ Меню", callback_data="menu")]
                ]))

# ===== ЗАПИСЬ =====
async def slot_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    raw = query.data[5:]  # убираем "slot_"
    # Парсим: dur_fmt_online_1h_17.02.2025_10:00 или fmt_urgent_17.02.2025_10:00
    known_prefixes = [
        "dur_fmt_online_1h_", "dur_fmt_online_2h_",
        "dur_fmt_offline_1h_", "dur_fmt_offline_2h_",
        "fmt_urgent_"
    ]
    for prefix in known_prefixes:
        if raw.startswith(prefix):
            fmt_key = prefix[:-1]
            context.user_data["format_key"] = fmt_key
            context.user_data["format"] = FORMATS.get(fmt_key, "?")
            rest = raw[len(prefix):]
            break
    else:
        rest = raw
    date_str, time_str = rest.rsplit("_", 1)
    slot_str = f"{date_str} {time_str}"
    context.user_data["slot"] = slot_str
    dt = datetime.strptime(date_str, "%d.%m.%Y")
    day_name = DAYS_RU[dt.weekday()]
    await query.edit_message_text(
        f"✅ Вы выбрали:\n\n📋 {context.user_data['format']}\n📅 {date_str} ({day_name}), {time_str}\n\nКак вас зовут?",
        parse_mode="Markdown")
    return BOOKING_NAME

async def booking_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        f"Приятно познакомиться, *{update.message.text}*! 🌿\n\nУкажите контакт для связи\n(телефон, Telegram или WhatsApp):",
        parse_mode="Markdown")
    return BOOKING_CONTACT

async def booking_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["contact"] = update.message.text
    await update.message.reply_text("Хотите кратко описать запрос?\n(Напишите «нет», чтобы пропустить):", parse_mode="Markdown")
    return BOOKING_NOTE

async def booking_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.text
    if note.lower().strip() in ["нет", "-", "не хочу", "пропустить", "нет спасибо"]:
        note = "Не указано"
    slot = context.user_data.get("slot", "?")
    remove_slot(slot)
    user = update.effective_user
    booking = {
        "format": context.user_data.get("format", ""),
        "slot": slot,
        "name": context.user_data.get("name", ""),
        "contact": context.user_data.get("contact", ""),
        "note": note,
        "tg": f"@{user.username}" if user.username else str(user.id),
        "created": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    add_booking(booking)
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, parse_mode="Markdown",
            text=f"🔔 *Новая запись!*\n\n📋 {booking['format']}\n📅 {booking['slot']}\n👤 {booking['name']}\n📞 {booking['contact']}\n💬 {booking['note']}\n🆔 {booking['tg']}\n🕐 {booking['created']}")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    await update.message.reply_text(
        f"✅ *Вы записаны!*\n\n📋 {booking['format']}\n📅 {booking['slot']}\n\nЯ свяжусь с вами в течение 24 часов. Спасибо! 🌿",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Меню", callback_data="menu_new")]]))
    return ConversationHandler.END

async def booking_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Запись отменена. /start — главное меню 🌿")
    return ConversationHandler.END

# ===== АДМИН =====
def is_admin(uid):
    return uid == ADMIN_CHAT_ID

async def cmd_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    slots = get_slots()
    if not slots:
        await update.message.reply_text("📅 Нет свободных слотов.\n\n/addday ДД.ММ.ГГГГ — добавить день\n/addweek — добавить неделю")
        return
    dates = {}
    for s in slots:
        d, t = s.split(" ")
        dates.setdefault(d, []).append(t)
    text = "📅 *Свободные слоты:*\n\n"
    for date in sorted(dates.keys(), key=lambda x: datetime.strptime(x, "%d.%m.%Y")):
        dt = datetime.strptime(date, "%d.%m.%Y")
        text += f"*{date}* ({DAYS_RU[dt.weekday()]}): {', '.join(sorted(dates[date]))}\n"
    text += f"\nВсего: {len(slots)}\n\n/help — все команды"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_addslot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Формат: /addslot ДД.ММ.ГГГГ ЧЧ:ММ")
        return
    date_str, time_str = args[0], args[1]
    if len(date_str.split(".")) == 2:
        date_str = f"{date_str}.{datetime.now().year}"
    try:
        datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
    except ValueError:
        await update.message.reply_text("❌ Неверный формат.")
        return
    if add_slot(date_str, time_str):
        dt = datetime.strptime(date_str, "%d.%m.%Y")
        await update.message.reply_text(f"✅ Добавлен: *{date_str}* ({DAYS_RU[dt.weekday()]}) *{time_str}*", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Слот уже есть.")

async def cmd_addday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if not context.args:
        await update.message.reply_text("Формат: /addday ДД.ММ.ГГГГ")
        return
    date_str = context.args[0]
    if len(date_str.split(".")) == 2:
        date_str = f"{date_str}.{datetime.now().year}"
    try:
        dt = datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError:
        await update.message.reply_text("❌ Неверный формат.")
        return
    times = ["09:00", "11:00", "13:00", "15:00", "17:00", "19:00"]
    added = sum(1 for t in times if add_slot(date_str, t))
    await update.message.reply_text(
        f"✅ +{added} слотов на *{date_str}* ({DAYS_RU[dt.weekday()]}):\n09:00, 11:00, 13:00, 15:00, 17:00, 19:00",
        parse_mode="Markdown")

async def cmd_addweek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    if context.args:
        date_str = context.args[0]
        if len(date_str.split(".")) == 2:
            date_str = f"{date_str}.{datetime.now().year}"
        try:
            start_date = datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError:
            await update.message.reply_text("❌ Неверный формат.")
            return
    else:
        start_date = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
    times = ["09:00", "11:00", "13:00", "15:00", "17:00", "19:00"]
    total = 0
    text = ""
    for i in range(7):
        day = start_date + timedelta(days=i)
        ds = day.strftime("%d.%m.%Y")
        added = sum(1 for t in times if add_slot(ds, t))
        if added:
            text += f"  {ds} ({DAYS_RU[day.weekday()]}): +{added}\n"
            total += added
    await update.message.reply_text(f"✅ +{total} слотов на неделю:\n\n{text}\n/slots — просмотр", parse_mode="Markdown")

async def cmd_delslot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Формат: /delslot ДД.ММ.ГГГГ ЧЧ:ММ")
        return
    date_str = args[0]
    if len(date_str.split(".")) == 2:
        date_str = f"{date_str}.{datetime.now().year}"
    slot = f"{date_str} {args[1]}"
    if remove_slot(slot):
        await update.message.reply_text(f"✅ Удалён: *{slot}*", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Не найден: *{slot}*", parse_mode="Markdown")

async def cmd_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    bookings = get_bookings()
    if not bookings:
        await update.message.reply_text("📋 Записей нет.")
        return
    text = "📋 *Записи:*\n\n"
    for i, b in enumerate(bookings[-15:], 1):
        text += f"*{i}.* {b.get('slot','?')} | {b.get('format','?')}\n   👤 {b.get('name','?')} | 📞 {b.get('contact','?')}\n   💬 {b.get('note','-')}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    await update.message.reply_text(
        "🔧 *Команды:*\n\n"
        "/slots — свободные слоты\n"
        "/addslot ДД.ММ.ГГГГ ЧЧ:ММ — добавить слот\n"
        "/addday ДД.ММ.ГГГГ — добавить день (6 слотов)\n"
        "/addweek — неделю вперёд (42 слота)\n"
        "/addweek ДД.ММ.ГГГГ — неделю с даты\n"
        "/delslot ДД.ММ.ГГГГ ЧЧ:ММ — удалить слот\n"
        "/bookings — все записи\n\n"
        "_Слоты по 2 часа: 09, 11, 13, 15, 17, 19_",
        parse_mode="Markdown")

# ===== АВТООТВЕТ =====
async def auto_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_CHAT_ID:
        return
    user = update.effective_user
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, parse_mode="Markdown",
            text=f"📩 *Сообщение:*\n👤 {user.first_name} {user.last_name or ''} (@{user.username or '—'})\n💬 {update.message.text}")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
    await update.message.reply_text(AUTO_REPLY_TEXT, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📋 Меню", callback_data="menu_new")]]))

async def menu_new_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(WELCOME_TEXT, parse_mode="Markdown", reply_markup=main_menu_keyboard())

# ===== ЗАПУСК =====
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(slot_selected, pattern="^slot_")],
        states={
            BOOKING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_name)],
            BOOKING_CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_contact)],
            BOOKING_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, booking_note)],
        },
        fallbacks=[CommandHandler("cancel", booking_cancel), CommandHandler("start", start)],
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("slots", cmd_slots))
    app.add_handler(CommandHandler("addslot", cmd_addslot))
    app.add_handler(CommandHandler("addday", cmd_addday))
    app.add_handler(CommandHandler("addweek", cmd_addweek))
    app.add_handler(CommandHandler("delslot", cmd_delslot))
    app.add_handler(CommandHandler("bookings", cmd_bookings))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(menu_new_cb, pattern="^menu_new$"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_reply))
    logger.info("Бот запущен! 🚀")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
