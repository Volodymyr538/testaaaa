"""
Burger King Roblox — Telegram Bot
Один файл: aiogram 3.x + SQLite
"""

import asyncio
import logging
import sqlite3
from typing import Any

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ═══════════════════════════════════════════════════════════════
#  КОНФИГУРАЦИЯ
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# Telegram user_id администраторов
ADMIN_IDS: list[int] = [123456789]

# Если хочешь получать уведомления о заказах — укажи chat_id, иначе None
ORDERS_CHAT_ID: int | None = None

DB_PATH = "database.db"

# ═══════════════════════════════════════════════════════════════
#  ДАННЫЕ МЕНЮ
# ═══════════════════════════════════════════════════════════════

MENU: dict[str, dict] = {
    "burgers": {
        "emoji": "🍔",
        "title": "Бургеры",
        "items": [
            {"name": "Воппер",            "price": 299},
            {"name": "Чизбургер",         "price": 149},
            {"name": "Двойной чизбургер", "price": 199},
            {"name": "Биг Кинг",          "price": 349},
            {"name": "Кинг Роял",         "price": 399},
        ],
    },
    "snacks": {
        "emoji": "🍟",
        "title": "Закуски",
        "items": [
            {"name": "Картофель фри",           "price": 99},
            {"name": "Картофель по-деревенски", "price": 119},
            {"name": "Луковые кольца",          "price": 109},
            {"name": "Наггетсы",                "price": 129},
        ],
    },
    "drinks": {
        "emoji": "🥤",
        "title": "Напитки",
        "items": [
            {"name": "Кола",   "price": 79},
            {"name": "Спрайт", "price": 79},
            {"name": "Фанта",  "price": 79},
            {"name": "Сок",    "price": 89},
            {"name": "Вода",   "price": 49},
        ],
    },
    "desserts": {
        "emoji": "🍦",
        "title": "Десерты",
        "items": [
            {"name": "Мороженое",        "price": 89},
            {"name": "Молочный коктейль", "price": 149},
            {"name": "Пирожки",          "price": 69},
            {"name": "Донаты",           "price": 79},
        ],
    },
}

CATEGORY_CB: dict[str, str] = {
    "cat_burgers":  "burgers",
    "cat_snacks":   "snacks",
    "cat_drinks":   "drinks",
    "cat_desserts": "desserts",
}

HOT_DEALS = [
    "🔥 Скидка 20% на все комбо-наборы!",
    "🔥 Бесплатный напиток при покупке двух бургеров!",
    "🔥 Подарок за заказ от 500₽!",
]

FAQ_TEXT = (
    "❓ <b>Частые вопросы</b>\n\n"
    "<b>Как оформить заказ?</b>\n"
    "Перейди в «🍟 Меню», выбери блюда — они добавятся в корзину. "
    "Затем нажми «🛒 Заказать» → «💳 Оформить заказ».\n\n"
    "<b>Как отменить заказ?</b>\n"
    "После перехода к оформлению нажми «❌ Отменить заказ».\n\n"
    "<b>Как использовать промокод?</b>\n"
    "Перейди в «🎁 Акции» → «🎟 Промокоды» и скопируй нужный код. "
    "Сообщи его при оформлении заказа.\n\n"
    "<b>Как связаться с сотрудником?</b>\n"
    "Перейди в «🆘 Поддержка» → «📩 Связаться с поддержкой»."
)

# ═══════════════════════════════════════════════════════════════
#  БАЗА ДАННЫХ
# ═══════════════════════════════════════════════════════════════

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id   INTEGER PRIMARY KEY,
            username  TEXT,
            full_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            user_name  TEXT,
            items      TEXT,
            total      REAL,
            status     TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            user_name  TEXT,
            text       TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS promotions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT,
            description TEXT,
            promo_code  TEXT,
            active      INTEGER DEFAULT 1,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS staff (
            user_id  INTEGER PRIMARY KEY,
            username TEXT,
            role     TEXT DEFAULT 'support',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS support_tickets (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            user_name  TEXT,
            message    TEXT,
            type       TEXT DEFAULT 'support',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS bot_settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );
    """)
    # Приветствие по умолчанию
    conn.execute(
        "INSERT OR IGNORE INTO bot_settings (key, value) VALUES (?, ?)",
        ("welcome_text", "☀️ Добро пожаловать в Burger King Roblox!")
    )
    conn.commit()
    conn.close()


# ── Helpers ───────────────────────────────────────────────────

def db_upsert_user(user_id: int, username: str, full_name: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?,?,?)",
        (user_id, username, full_name),
    )
    conn.commit(); conn.close()

def db_user_count() -> int:
    conn = get_conn()
    r = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
    conn.close(); return r["c"]

def db_create_order(user_id: int, user_name: str, items: str, total: float) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO orders (user_id, user_name, items, total) VALUES (?,?,?,?)",
        (user_id, user_name, items, total),
    )
    oid = cur.lastrowid; conn.commit(); conn.close(); return oid

def db_order_count() -> int:
    conn = get_conn()
    r = conn.execute("SELECT COUNT(*) AS c FROM orders").fetchone()
    conn.close(); return r["c"]

def db_add_review(user_id: int, user_name: str, text: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO reviews (user_id, user_name, text) VALUES (?,?,?)",
        (user_id, user_name, text),
    )
    conn.commit(); conn.close()

def db_get_reviews(limit: int = 10) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM reviews ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close(); return rows

def db_review_count() -> int:
    conn = get_conn()
    r = conn.execute("SELECT COUNT(*) AS c FROM reviews").fetchone()
    conn.close(); return r["c"]

def db_add_promo(title: str, desc: str, code: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO promotions (title, description, promo_code) VALUES (?,?,?)",
        (title, desc, code),
    )
    conn.commit(); conn.close()

def db_get_promos() -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM promotions WHERE active=1 ORDER BY created_at DESC"
    ).fetchall()
    conn.close(); return rows

def db_add_staff(user_id: int, username: str, role: str = "support") -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO staff (user_id, username, role) VALUES (?,?,?)",
        (user_id, username, role),
    )
    conn.commit(); conn.close()

def db_remove_staff(user_id: int) -> None:
    conn = get_conn()
    conn.execute("DELETE FROM staff WHERE user_id=?", (user_id,))
    conn.commit(); conn.close()

def db_get_staff() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM staff").fetchall()
    conn.close(); return rows

def db_add_ticket(user_id: int, user_name: str, message: str, ttype: str = "support") -> None:
    conn = get_conn()
    conn.execute(
        "INSERT INTO support_tickets (user_id, user_name, message, type) VALUES (?,?,?,?)",
        (user_id, user_name, message, ttype),
    )
    conn.commit(); conn.close()

def db_get_setting(key: str) -> str:
    conn = get_conn()
    r = conn.execute("SELECT value FROM bot_settings WHERE key=?", (key,)).fetchone()
    conn.close(); return r["value"] if r else ""

def db_set_setting(key: str, value: str) -> None:
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO bot_settings (key, value) VALUES (?,?)", (key, value)
    )
    conn.commit(); conn.close()

def db_get_all_users() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close(); return rows

# ═══════════════════════════════════════════════════════════════
#  КЛАВИАТУРЫ
# ═══════════════════════════════════════════════════════════════

def kb_main(is_admin: bool = False) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🍟 Меню",      callback_data="menu"),
        InlineKeyboardButton(text="🛒 Заказать",  callback_data="order"),
    )
    b.row(
        InlineKeyboardButton(text="🎁 Акции",     callback_data="promotions"),
        InlineKeyboardButton(text="🆘 Поддержка", callback_data="support"),
    )
    b.row(InlineKeyboardButton(text="⭐ Отзывы",  callback_data="reviews"))
    if is_admin:
        b.row(InlineKeyboardButton(text="✅ Админка", callback_data="admin"))
    return b.as_markup()

def kb_menu() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🍔 Бургеры", callback_data="cat_burgers"),
        InlineKeyboardButton(text="🍟 Закуски", callback_data="cat_snacks"),
    )
    b.row(
        InlineKeyboardButton(text="🥤 Напитки",  callback_data="cat_drinks"),
        InlineKeyboardButton(text="🍦 Десерты",  callback_data="cat_desserts"),
    )
    b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_main"))
    return b.as_markup()

def kb_category(items: list[dict], cat_key: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, item in enumerate(items):
        b.row(InlineKeyboardButton(
            text=f"{item['name']} — {item['price']}₽",
            callback_data=f"add_{cat_key}_{i}",
        ))
    b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="menu"))
    return b.as_markup()

def kb_order() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📋 Корзина",        callback_data="cart"))
    b.row(InlineKeyboardButton(text="💳 Оформить заказ", callback_data="checkout"))
    b.row(InlineKeyboardButton(text="❌ Очистить корзину", callback_data="clear_cart"))
    b.row(InlineKeyboardButton(text="🔙 Назад",          callback_data="back_main"))
    return b.as_markup()

def kb_checkout() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="✅ Подтвердить заказ", callback_data="confirm_order"))
    b.row(InlineKeyboardButton(text="❌ Отменить заказ",    callback_data="cancel_order"))
    b.row(InlineKeyboardButton(text="🔙 Назад",             callback_data="order"))
    return b.as_markup()

def kb_delivery() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🏠 Самовывоз", callback_data="dlv_pickup"),
        InlineKeyboardButton(text="🚚 Доставка",  callback_data="dlv_delivery"),
    )
    return b.as_markup()

def kb_promotions() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="🎟 Промокоды",         callback_data="promo_codes"),
        InlineKeyboardButton(text="🔥 Горячие предложения", callback_data="hot_deals"),
    )
    b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_main"))
    return b.as_markup()

def kb_support() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="❓ Частые вопросы",         callback_data="faq"))
    b.row(InlineKeyboardButton(text="📩 Связаться с поддержкой", callback_data="contact_support"))
    b.row(InlineKeyboardButton(text="⚠️ Сообщить о проблеме",   callback_data="report_problem"))
    b.row(InlineKeyboardButton(text="🔙 Назад",                  callback_data="back_main"))
    return b.as_markup()

def kb_reviews() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="✍️ Оставить отзыв",    callback_data="leave_review"),
        InlineKeyboardButton(text="📖 Посмотреть отзывы", callback_data="view_reviews"),
    )
    b.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_main"))
    return b.as_markup()

def kb_admin() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="📢 Рассылка",              callback_data="adm_broadcast"))
    b.row(InlineKeyboardButton(text="➕ Добавить акцию",         callback_data="adm_add_promo"))
    b.row(InlineKeyboardButton(text="📊 Статистика",             callback_data="adm_stats"))
    b.row(InlineKeyboardButton(text="👥 Управление персоналом",  callback_data="adm_staff"))
    b.row(InlineKeyboardButton(text="⚙️ Настройки",             callback_data="adm_settings"))
    b.row(InlineKeyboardButton(text="🔙 Назад",                  callback_data="back_main"))
    return b.as_markup()

def kb_staff() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.row(InlineKeyboardButton(text="➕ Добавить сотрудника", callback_data="staff_add"))
    b.row(InlineKeyboardButton(text="➖ Удалить сотрудника",  callback_data="staff_remove"))
    b.row(InlineKeyboardButton(text="📋 Список персонала",    callback_data="staff_list"))
    b.row(InlineKeyboardButton(text="🔙 Назад",               callback_data="admin"))
    return b.as_markup()

def kb_back(target: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=target)]
    ])

def kb_cancel_reply() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

# ═══════════════════════════════════════════════════════════════
#  FSM STATES
# ═══════════════════════════════════════════════════════════════

class OrderSG(StatesGroup):
    waiting_name     = State()
    waiting_delivery = State()

class ReviewSG(StatesGroup):
    waiting_text = State()

class SupportSG(StatesGroup):
    waiting_message = State()

class ReportSG(StatesGroup):
    waiting_message = State()

class AdminSG(StatesGroup):
    broadcast       = State()
    promo_title     = State()
    promo_desc      = State()
    promo_code      = State()
    staff_add_id    = State()
    staff_add_role  = State()
    staff_remove_id = State()
    settings_key    = State()
    settings_value  = State()

# ═══════════════════════════════════════════════════════════════
#  ROUTER & HELPERS
# ═══════════════════════════════════════════════════════════════

router = Router()

WELCOME = (
    "🍔 <b>Добро пожаловать в Burger King Roblox!</b>\n\n"
    "☀️ Здесь вы можете:\n"
    "• Ознакомиться с меню ресторана\n"
    "• Оформить заказ\n"
    "• Узнать о действующих акциях\n"
    "• Получить помощь от поддержки\n"
    "• Оставить отзыв\n\n"
    "Выберите раздел:"
)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def send_main(target: Message | CallbackQuery, edit: bool = False) -> None:
    admin = is_admin(
        target.from_user.id if isinstance(target, Message) else target.from_user.id
    )
    kb = kb_main(admin)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(WELCOME, reply_markup=kb, parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(WELCOME, reply_markup=kb, parse_mode="HTML")

# ═══════════════════════════════════════════════════════════════
#  /start
# ═══════════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(msg: Message) -> None:
    db_upsert_user(msg.from_user.id, msg.from_user.username or "", msg.from_user.full_name)
    await send_main(msg)

@router.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await send_main(call)

# ═══════════════════════════════════════════════════════════════
#  МЕНЮ
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "🍟 <b>Меню ресторана</b>\n\nВыберите категорию:",
        reply_markup=kb_menu(), parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data.in_(CATEGORY_CB.keys()))
async def cb_category(call: CallbackQuery) -> None:
    cat_key = CATEGORY_CB[call.data]
    cat = MENU[cat_key]
    lines = [f"{cat['emoji']} <b>{cat['title']}</b>\n"]
    for item in cat["items"]:
        lines.append(f"• {item['name']} — <b>{item['price']}₽</b>")
    lines.append("\n👆 Нажми на блюдо, чтобы добавить в корзину 🛒")
    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=kb_category(cat["items"], cat_key),
        parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data.startswith("add_"))
async def cb_add_item(call: CallbackQuery, state: FSMContext) -> None:
    _, cat_key, idx_str = call.data.split("_", 2)
    item = MENU[cat_key]["items"][int(idx_str)]
    data = await state.get_data()
    cart: list = data.get("cart", [])
    cart.append(item)
    await state.update_data(cart=cart)
    await call.answer(f"✅ {item['name']} добавлен в корзину! (всего: {len(cart)})")

# ═══════════════════════════════════════════════════════════════
#  ЗАКАЗ / КОРЗИНА
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "order")
async def cb_order(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    cart: list = data.get("cart", [])
    await call.message.edit_text(
        f"🛒 <b>Раздел заказов</b>\n\nТоваров в корзине: <b>{len(cart)}</b>\n\nВыбери действие:",
        reply_markup=kb_order(), parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data == "cart")
async def cb_cart(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    cart: list = data.get("cart", [])
    if not cart:
        await call.answer("🛒 Корзина пуста! Зайди в «Меню» и добавь блюда.", show_alert=True); return
    lines = ["📋 <b>Ваша корзина:</b>\n"]
    total = 0.0
    for i, item in enumerate(cart, 1):
        lines.append(f"{i}. {item['name']} — {item['price']}₽")
        total += item["price"]
    lines.append(f"\n💰 <b>Итого: {total:.0f}₽</b>")
    await call.message.edit_text("\n".join(lines), reply_markup=kb_order(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "clear_cart")
async def cb_clear_cart(call: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(cart=[])
    await call.answer("🗑 Корзина очищена!", show_alert=True)
    await call.message.edit_text(
        "🛒 <b>Корзина пуста.</b>\n\nДобавь блюда из меню:",
        reply_markup=kb_order(), parse_mode="HTML",
    )

@router.callback_query(F.data == "checkout")
async def cb_checkout(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    cart: list = data.get("cart", [])
    if not cart:
        await call.answer("🛒 Корзина пуста! Добавьте блюда из меню.", show_alert=True); return
    total = sum(i["price"] for i in cart)
    lines = ["📋 <b>Ваш заказ:</b>\n"]
    for item in cart:
        lines.append(f"• {item['name']} — {item['price']}₽")
    lines.append(f"\n💰 <b>Итого: {total:.0f}₽</b>")
    await call.message.edit_text("\n".join(lines), reply_markup=kb_checkout(), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "confirm_order")
async def cb_confirm_order(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(OrderSG.waiting_name)
    await call.message.answer(
        "✏️ Введите ваше <b>имя</b> для оформления заказа:",
        reply_markup=kb_cancel_reply(), parse_mode="HTML",
    )
    await call.answer()

@router.message(OrderSG.waiting_name, F.text != "❌ Отмена")
async def order_got_name(msg: Message, state: FSMContext) -> None:
    await state.update_data(order_name=msg.text)
    await state.set_state(OrderSG.waiting_delivery)
    await msg.answer("🚗 Выберите способ получения:", reply_markup=kb_delivery())

@router.callback_query(OrderSG.waiting_delivery, F.data.startswith("dlv_"))
async def order_got_delivery(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    delivery_map = {"dlv_pickup": "🏠 Самовывоз", "dlv_delivery": "🚚 Доставка"}
    delivery = delivery_map.get(call.data, "Самовывоз")
    data = await state.get_data()
    cart: list = data.get("cart", [])
    order_name: str = data.get("order_name", "Без имени")
    total = sum(i["price"] for i in cart)
    items_str = ", ".join(i["name"] for i in cart)
    order_id = db_create_order(call.from_user.id, call.from_user.full_name, items_str, total)

    if ORDERS_CHAT_ID:
        await bot.send_message(
            ORDERS_CHAT_ID,
            f"🆕 <b>Новый заказ #{order_id}</b>\n"
            f"👤 {call.from_user.full_name} (@{call.from_user.username})\n"
            f"📝 Имя: {order_name}\n🚗 {delivery}\n"
            f"🍽 {items_str}\n💰 {total:.0f}₽",
            parse_mode="HTML",
        )

    await state.clear()
    await call.message.edit_text(
        f"✅ <b>Заказ #{order_id} оформлен!</b>\n\n"
        f"📝 Имя: {order_name}\n{delivery}\n"
        f"🍽 {items_str}\n💰 {total:.0f}₽\n\n"
        "Ожидайте — наши сотрудники скоро свяжутся с вами! 🍔",
        parse_mode="HTML",
    )
    await call.answer("🎉 Заказ оформлен!")

@router.callback_query(F.data == "cancel_order")
async def cb_cancel_order(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "❌ Заказ отменён.\n\nВы можете добавить блюда снова:",
        reply_markup=kb_order(),
    )
    await call.answer()

# ═══════════════════════════════════════════════════════════════
#  АКЦИИ
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "promotions")
async def cb_promotions(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "🎁 <b>Акции и специальные предложения</b>\n\nВыбери раздел:",
        reply_markup=kb_promotions(), parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data == "hot_deals")
async def cb_hot_deals(call: CallbackQuery) -> None:
    lines = ["🔥 <b>Горячие предложения</b>\n"] + HOT_DEALS
    promos = db_get_promos()
    if promos:
        lines.append("\n📢 <b>Акции от администрации:</b>")
        for p in promos:
            lines.append(f"\n🏷 <b>{p['title']}</b>\n{p['description']}")
    await call.message.edit_text(
        "\n".join(lines), reply_markup=kb_back("promotions"), parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data == "promo_codes")
async def cb_promo_codes(call: CallbackQuery) -> None:
    promos = [p for p in db_get_promos() if p["promo_code"]]
    if not promos:
        text = "🎟 <b>Промокоды</b>\n\nАктивных промокодов пока нет. Следите за обновлениями!"
    else:
        lines = ["🎟 <b>Активные промокоды:</b>\n"]
        for p in promos:
            lines.append(f"🔖 <code>{p['promo_code']}</code> — {p['title']}\n   {p['description']}")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=kb_back("promotions"), parse_mode="HTML")
    await call.answer()

# ═══════════════════════════════════════════════════════════════
#  ПОДДЕРЖКА
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "support")
async def cb_support(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "🆘 <b>Поддержка</b>\n\n"
        "Если у вас возникли вопросы, проблемы или предложения — мы поможем!\n\n"
        "Выбери раздел:",
        reply_markup=kb_support(), parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data == "faq")
async def cb_faq(call: CallbackQuery) -> None:
    await call.message.edit_text(FAQ_TEXT, reply_markup=kb_back("support"), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "contact_support")
async def cb_contact_support(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SupportSG.waiting_message)
    await call.message.answer(
        "📩 Напишите ваше обращение одним сообщением.\n"
        "Сотрудник ответит при первой возможности.",
        reply_markup=kb_cancel_reply(),
    )
    await call.answer()

@router.message(SupportSG.waiting_message, F.text != "❌ Отмена")
async def support_got_message(msg: Message, state: FSMContext, bot: Bot) -> None:
    db_add_ticket(msg.from_user.id, msg.from_user.full_name, msg.text, "support")
    await state.clear()
    # Уведомляем всех админов
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📩 <b>Новое обращение в поддержку</b>\n"
                f"👤 {msg.from_user.full_name} (@{msg.from_user.username}, id: {msg.from_user.id})\n\n"
                f"{msg.text}",
                parse_mode="HTML",
            )
        except Exception:
            pass
    await msg.answer(
        "✅ Ваше обращение отправлено! Сотрудник ответит при первой возможности.",
        reply_markup=ReplyKeyboardRemove(),
    )

@router.callback_query(F.data == "report_problem")
async def cb_report_problem(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ReportSG.waiting_message)
    await call.message.answer(
        "⚠️ Опишите проблему максимально подробно.\n"
        "Сообщение будет отправлено администрации.",
        reply_markup=kb_cancel_reply(),
    )
    await call.answer()

@router.message(ReportSG.waiting_message, F.text != "❌ Отмена")
async def report_got_message(msg: Message, state: FSMContext, bot: Bot) -> None:
    db_add_ticket(msg.from_user.id, msg.from_user.full_name, msg.text, "problem")
    await state.clear()
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"⚠️ <b>Сообщение о проблеме</b>\n"
                f"👤 {msg.from_user.full_name} (@{msg.from_user.username}, id: {msg.from_user.id})\n\n"
                f"{msg.text}",
                parse_mode="HTML",
            )
        except Exception:
            pass
    await msg.answer(
        "✅ Сообщение отправлено администрации. Спасибо!",
        reply_markup=ReplyKeyboardRemove(),
    )

# ═══════════════════════════════════════════════════════════════
#  ОТЗЫВЫ
# ═══════════════════════════════════════════════════════════════

@router.callback_query(F.data == "reviews")
async def cb_reviews(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "⭐ <b>Отзывы</b>\n\n"
        "Помогите нам стать лучше — оставьте отзыв о работе ресторана и бота!\n\n"
        "Выбери действие:",
        reply_markup=kb_reviews(), parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data == "leave_review")
async def cb_leave_review(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ReviewSG.waiting_text)
    await call.message.answer(
        "✍️ Напишите свой отзыв одним сообщением.\n"
        "Он поможет улучшить наш сервис!",
        reply_markup=kb_cancel_reply(),
    )
    await call.answer()

@router.message(ReviewSG.waiting_text, F.text != "❌ Отмена")
async def review_got_text(msg: Message, state: FSMContext) -> None:
    db_add_review(msg.from_user.id, msg.from_user.full_name, msg.text)
    await state.clear()
    await msg.answer("✅ Спасибо за отзыв! Ваше мнение очень важно для нас. ⭐",
                     reply_markup=ReplyKeyboardRemove())

@router.callback_query(F.data == "view_reviews")
async def cb_view_reviews(call: CallbackQuery) -> None:
    reviews = db_get_reviews(10)
    if not reviews:
        text = "📖 <b>Отзывы</b>\n\nПока отзывов нет. Будьте первым! ⭐"
    else:
        lines = [f"📖 <b>Последние отзывы ({len(reviews)}):</b>\n"]
        for r in reviews:
            lines.append(f"👤 <b>{r['user_name']}</b>\n{r['text']}\n")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=kb_back("reviews"), parse_mode="HTML")
    await call.answer()

# ═══════════════════════════════════════════════════════════════
#  АДМИНКА
# ═══════════════════════════════════════════════════════════════

def admin_only(func):
    """Декоратор-проверка прав администратора"""
    import inspect
    sig_params = set(inspect.signature(func).parameters.keys())

    async def wrapper(call: CallbackQuery, **kwargs):
        if not is_admin(call.from_user.id):
            await call.answer("⛔ Нет доступа!", show_alert=True); return
        filtered = {k: v for k, v in kwargs.items() if k in sig_params}
        return await func(call, **filtered)
    wrapper.__name__ = func.__name__
    return wrapper


@router.callback_query(F.data == "admin")
@admin_only
async def cb_admin(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "✅ <b>Панель администратора</b>\n\nВыберите раздел:",
        reply_markup=kb_admin(), parse_mode="HTML",
    )
    await call.answer()

# ── Статистика ────────────────────────────────────────────────

@router.callback_query(F.data == "adm_stats")
@admin_only
async def cb_adm_stats(call: CallbackQuery) -> None:
    await call.message.edit_text(
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{db_user_count()}</b>\n"
        f"🛒 Заказов: <b>{db_order_count()}</b>\n"
        f"⭐ Отзывов: <b>{db_review_count()}</b>\n"
        f"👔 Сотрудников: <b>{len(db_get_staff())}</b>",
        reply_markup=kb_back("admin"), parse_mode="HTML",
    )
    await call.answer()

# ── Рассылка ─────────────────────────────────────────────────

@router.callback_query(F.data == "adm_broadcast")
@admin_only
async def cb_adm_broadcast(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSG.broadcast)
    await call.message.answer(
        "📢 Введите текст рассылки.\nОн будет отправлен всем пользователям бота.",
        reply_markup=kb_cancel_reply(),
    )
    await call.answer()

@router.message(AdminSG.broadcast, F.text != "❌ Отмена")
async def adm_do_broadcast(msg: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    users = db_get_all_users()
    ok = fail = 0
    for row in users:
        try:
            await bot.send_message(row["user_id"], f"📢 <b>Объявление</b>\n\n{msg.text}", parse_mode="HTML")
            ok += 1
        except Exception:
            fail += 1
    await msg.answer(
        f"✅ Рассылка завершена.\nДоставлено: {ok} | Ошибок: {fail}",
        reply_markup=ReplyKeyboardRemove(),
    )

# ── Добавить акцию ───────────────────────────────────────────

@router.callback_query(F.data == "adm_add_promo")
@admin_only
async def cb_adm_add_promo(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSG.promo_title)
    await call.message.answer("➕ Введите <b>название</b> акции:", reply_markup=kb_cancel_reply(), parse_mode="HTML")
    await call.answer()

@router.message(AdminSG.promo_title, F.text != "❌ Отмена")
async def adm_promo_title(msg: Message, state: FSMContext) -> None:
    await state.update_data(promo_title=msg.text)
    await state.set_state(AdminSG.promo_desc)
    await msg.answer("📝 Введите <b>описание</b> акции:", parse_mode="HTML")

@router.message(AdminSG.promo_desc, F.text != "❌ Отмена")
async def adm_promo_desc(msg: Message, state: FSMContext) -> None:
    await state.update_data(promo_desc=msg.text)
    await state.set_state(AdminSG.promo_code)
    await msg.answer("🎟 Введите <b>промокод</b> (или «-» если без кода):", parse_mode="HTML")

@router.message(AdminSG.promo_code, F.text != "❌ Отмена")
async def adm_promo_code(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    code = "" if msg.text.strip() == "-" else msg.text.strip()
    db_add_promo(data["promo_title"], data["promo_desc"], code)
    await state.clear()
    await msg.answer("✅ Акция добавлена!", reply_markup=ReplyKeyboardRemove())

# ── Управление персоналом ────────────────────────────────────

@router.callback_query(F.data == "adm_staff")
@admin_only
async def cb_adm_staff(call: CallbackQuery) -> None:
    await call.message.edit_text(
        "👥 <b>Управление персоналом</b>", reply_markup=kb_staff(), parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data == "staff_list")
@admin_only
async def cb_staff_list(call: CallbackQuery) -> None:
    staff = db_get_staff()
    if not staff:
        text = "👥 Персонал пока не добавлен."
    else:
        lines = ["👥 <b>Список персонала:</b>\n"]
        for s in staff:
            lines.append(f"• @{s['username']} (id: {s['user_id']}) — {s['role']}")
        text = "\n".join(lines)
    await call.message.edit_text(text, reply_markup=kb_back("adm_staff"), parse_mode="HTML")
    await call.answer()

@router.callback_query(F.data == "staff_add")
@admin_only
async def cb_staff_add(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSG.staff_add_id)
    await call.message.answer(
        "➕ Введите <b>Telegram ID</b> нового сотрудника:",
        reply_markup=kb_cancel_reply(), parse_mode="HTML",
    )
    await call.answer()

@router.message(AdminSG.staff_add_id, F.text != "❌ Отмена")
async def adm_staff_add_id(msg: Message, state: FSMContext) -> None:
    if not msg.text.isdigit():
        await msg.answer("❌ Введите числовой ID."); return
    await state.update_data(new_staff_id=int(msg.text))
    await state.set_state(AdminSG.staff_add_role)
    await msg.answer("🎭 Введите роль (например: support, moderator, manager):")

@router.message(AdminSG.staff_add_role, F.text != "❌ Отмена")
async def adm_staff_add_role(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    db_add_staff(data["new_staff_id"], "", msg.text.strip())
    await state.clear()
    await msg.answer(
        f"✅ Сотрудник (id: {data['new_staff_id']}) добавлен с ролью «{msg.text.strip()}».",
        reply_markup=ReplyKeyboardRemove(),
    )

@router.callback_query(F.data == "staff_remove")
@admin_only
async def cb_staff_remove(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSG.staff_remove_id)
    await call.message.answer(
        "➖ Введите <b>Telegram ID</b> сотрудника для удаления:",
        reply_markup=kb_cancel_reply(), parse_mode="HTML",
    )
    await call.answer()

@router.message(AdminSG.staff_remove_id, F.text != "❌ Отмена")
async def adm_staff_remove_id(msg: Message, state: FSMContext) -> None:
    if not msg.text.isdigit():
        await msg.answer("❌ Введите числовой ID."); return
    db_remove_staff(int(msg.text))
    await state.clear()
    await msg.answer(
        f"✅ Сотрудник (id: {msg.text}) удалён.", reply_markup=ReplyKeyboardRemove(),
    )

# ── Настройки ────────────────────────────────────────────────

@router.callback_query(F.data == "adm_settings")
@admin_only
async def cb_adm_settings(call: CallbackQuery) -> None:
    welcome = db_get_setting("welcome_text")
    await call.message.edit_text(
        f"⚙️ <b>Настройки бота</b>\n\n"
        f"📝 Текущее приветствие:\n<i>{welcome}</i>\n\n"
        "Что хотите изменить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить приветствие", callback_data="set_welcome")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")],
        ]),
        parse_mode="HTML",
    )
    await call.answer()

@router.callback_query(F.data == "set_welcome")
@admin_only
async def cb_set_welcome(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminSG.settings_value)
    await state.update_data(settings_key="welcome_text")
    await call.message.answer(
        "✏️ Введите новый текст приветствия:",
        reply_markup=kb_cancel_reply(),
    )
    await call.answer()

@router.message(AdminSG.settings_value, F.text != "❌ Отмена")
async def adm_save_setting(msg: Message, state: FSMContext) -> None:
    data = await state.get_data()
    db_set_setting(data.get("settings_key", "welcome_text"), msg.text)
    await state.clear()
    await msg.answer("✅ Настройка сохранена!", reply_markup=ReplyKeyboardRemove())

# ═══════════════════════════════════════════════════════════════
#  ОТМЕНА (Reply-кнопка ❌)
# ═══════════════════════════════════════════════════════════════

@router.message(F.text == "❌ Отмена")
async def cancel_any(msg: Message, state: FSMContext) -> None:
    await state.clear()
    await msg.answer("❌ Действие отменено.", reply_markup=ReplyKeyboardRemove())
    await send_main(msg)

# ═══════════════════════════════════════════════════════════════
#  ЗАПУСК
# ═══════════════════════════════════════════════════════════════

async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
