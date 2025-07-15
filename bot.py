import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.markdown import hbold
from aiogram.client.default import DefaultBotProperties
from datetime import datetime
import random
import asyncio
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Конфигурация бота
BOT_TOKEN = "7674146920:AAGeXErfsN2FqmwG-q82esQ_FAzGSH7Wjeg"  # Замените на реальный токен
MANAGER_USERNAME = "lonufaal"  # Без @
ORDERS_FILE = "orders.txt"

# Инициализация бота
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Хранение данных в памяти
orders_db = {}  # {order_id: order_data}
users_orders = {}  # {user_id: [order_id1, order_id2]}

# Создаем файл для заказов, если его нет
if not os.path.exists(ORDERS_FILE):
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        f.write("")


# Состояния FSM
class OrderStates(StatesGroup):
    waiting_for_service_type = State()
    waiting_for_service_details = State()
    waiting_for_ad_duration = State()


# Сервисы и их типы
SERVICES = {
    "video": ["Эдит", "Монтаж", "Рекламный ролик", "Другое"],
    "photo": ["Аватарка", "Дизайн", "Другое"],
    "ad": ["Пост"]
}


# Функция для сохранения заказа в файл
def save_order_to_file(order_data):
    with open(ORDERS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {order_data}\n")


# Клавиатура главного меню
def get_main_menu():
    builder = ReplyKeyboardBuilder()
    builder.row(
        types.KeyboardButton(text="🎥 Заказ видео"),
        types.KeyboardButton(text="📸 Заказ фото"),
    )
    builder.row(
        types.KeyboardButton(text="📢 Реклама"),
    )
    builder.row(
        types.KeyboardButton(text="💡 Генератор идей"),
        types.KeyboardButton(text="❓ FAQ"),
    )
    builder.row(
        types.KeyboardButton(text="📞 Поддержка"),
        types.KeyboardButton(text="📋 Мои заказы"),
    )
    return builder.as_markup(resize_keyboard=True)


async def show_main_menu(chat_id, first_name):
    await bot.send_message(
        chat_id=chat_id,
        text=f"👋 Привет, {hbold(first_name)}!\nЯ бот для заказа креативных услуг. Выберите нужную опцию: 🎥 Видео - 📸 Фото - 📢 Реклама",
        reply_markup=get_main_menu()
    )


# Стартовая команда
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = message.from_user.id
    if user_id not in users_orders:
        users_orders[user_id] = []

    await show_main_menu(message.chat.id, message.from_user.first_name)


# Обработка выбора услуги
@dp.message(F.text.in_(["🎥 Заказ видео", "📸 Заказ фото", "📢 Реклама"]))
async def select_service(message: Message, state: FSMContext):
    service_map = {
        "🎥 Заказ видео": "video",
        "📸 Заказ фото": "photo",
        "📢 Реклама": "ad"
    }
    service_type = service_map[message.text]

    builder = InlineKeyboardBuilder()
    for service in SERVICES[service_type]:
        builder.add(types.InlineKeyboardButton(
            text=service,
            callback_data=f"type_{service_type}_{service}"
        ))
    builder.add(types.InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="back_to_main_menu"
    ))
    builder.adjust(2)

    await state.update_data(service_type=service_type)
    await state.set_state(OrderStates.waiting_for_service_type)
    await message.answer(
        f"Выберите тип {service_type}:",
        reply_markup=builder.as_markup()
    )


# Обработка кнопки "Назад"
@dp.callback_query(F.data == "back_to_main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await show_main_menu(callback.message.chat.id, callback.from_user.first_name)


# Обработка выбора типа услуги
@dp.callback_query(F.data.startswith("type_"), OrderStates.waiting_for_service_type)
async def select_service_type(callback: CallbackQuery, state: FSMContext):
    _, service_type, service_name = callback.data.split("_", 2)
    await state.update_data(service_name=service_name)

    if service_type == "ad":
        builder = InlineKeyboardBuilder()
        durations = [("1 день - 350₽", 1), ("3 дня - 600₽", 3),
                     ("7 дней - 1200₽", 7), ("14 дней - 2000₽", 14)]
        for text, days in durations:
            builder.add(types.InlineKeyboardButton(
                text=text,
                callback_data=f"duration_{days}"
            ))
        builder.add(types.InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back_to_main_menu"
        ))
        builder.adjust(2)

        await state.set_state(OrderStates.waiting_for_ad_duration)
        await callback.message.edit_text(
            "Выберите длительность рекламы:",
            reply_markup=builder.as_markup()
        )
    else:
        await state.set_state(OrderStates.waiting_for_service_details)
        await callback.message.edit_text(
            f"Вы выбрали: {service_name}\n\n"
            "Опишите детали заказа:\n"
            "- Пожелания\n- Референсы\n- Особые требования\n\n"
            "Напишите все в одном сообщении."
        )


# Обработка длительности для рекламы
@dp.callback_query(F.data.startswith("duration_"), OrderStates.waiting_for_ad_duration)
async def select_ad_duration(callback: CallbackQuery, state: FSMContext):
    days = int(callback.data.split("_")[1])
    await state.update_data(days=days)
    await state.set_state(OrderStates.waiting_for_service_details)
    await callback.message.edit_text(
        "Опишите детали рекламного заказа:\n"
        "- Текст поста\n- Ссылки\n- Пожелания по оформлению\n\n"
        "Напишите все в одном сообщении."
    )


# Обработка деталей заказа
@dp.message(OrderStates.waiting_for_service_details)
async def process_order_details(message: Message, state: FSMContext):
    user_data = await state.get_data()
    service_type = user_data["service_type"]
    details = message.text

    # Генерация цены и срока
    if service_type == "video":
        price = random.randint(500, 1000)
        days = random.randint(1, 3)
    elif service_type == "photo":
        price = random.randint(150, 300)
        days = random.randint(1, 3)
    elif service_type == "ad":
        days = user_data.get("days", 1)
        price = 350 if days == 1 else \
            600 if days == 3 else \
                1200 if days == 7 else \
                    2000 if days == 14 else 350

    await state.update_data(
        details=details,
        price=price,
        days=days
    )

    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_order"),
        types.InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_order"),
    )

    order_info = (
        f"📋 Детали заказа:\n"
        f"Тип: {user_data['service_name']}\n"
        f"Стоимость: {price} руб\n"
        f"Срок: {days} дней\n\n"
        f"Описание:\n{details}"
    )

    await message.answer(
        order_info,
        reply_markup=builder.as_markup()
    )


# Подтверждение заказа
@dp.callback_query(F.data == "confirm_order")
async def confirm_order(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    user_data = await state.get_data()

    order_id = f"order_{random.randint(1000, 9999)}"
    order_data = {
        "id": order_id,
        "user_id": user.id,
        "username": user.username or "нет username",
        "first_name": user.first_name,
        "service": user_data["service_type"],
        "service_name": user_data["service_name"],
        "price": user_data["price"],
        "days": user_data["days"],
        "details": user_data["details"],
        "status": "ожидает подтверждения",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Сохраняем заказ
    orders_db[order_id] = order_data
    if user.id not in users_orders:
        users_orders[user.id] = []
    users_orders[user.id].append(order_id)

    # Сохраняем в файл
    save_order_to_file(order_data)

    # Формируем текст для пересылки
    order_text = (
        f"📋 Новый заказ #{order_id}\n"
        f"👤 Клиент: @{order_data['username']} ({order_data['first_name']})\n"
        f"📌 Услуга: {order_data['service_name']}\n"
        f"💰 Стоимость: {order_data['price']} руб\n"
        f"⏳ Срок: {order_data['days']} дней\n"
        f"📝 Детали:\n{order_data['details']}\n\n"
        f"🆔 ID: {user.id}"
    )

    # Сообщение пользователю
    await callback.message.edit_text(
        "✅ <b>Заказ успешно создан!</b>\n\n"
        f"Номер заказа: <code>{order_id}</code>\n\n"
        "Чтобы менеджер начал работу:\n"
        f"1. Перейдите в чат с @{MANAGER_USERNAME}\n"
        "2. Перешлите ему следующее сообщение:\n\n"
        "──────────────────\n"
        f"{order_text}\n"
        "──────────────────\n\n"
        "3. Дождитесь ответа менеджера",
        parse_mode=ParseMode.HTML
    )

    await state.clear()


# Отмена заказа
@dp.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Заказ отменен")
    await state.clear()


# Поддержка
@dp.message(F.text == "📞 Поддержка")
async def support(message: Message):
    builder = InlineKeyboardBuilder()
    builder.add(types.InlineKeyboardButton(
        text="Написать менеджеру",
        url=f"https://t.me/{MANAGER_USERNAME}"
    ))
    await message.answer(
        "Свяжитесь с нашим менеджером:",
        reply_markup=builder.as_markup()
    )


# Генератор идей
@dp.message(F.text == "💡 Генератор идей")
async def idea_generator_start(message: Message):
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="🎥 Для видео", callback_data="idea_video"),
        types.InlineKeyboardButton(text="📸 Для фото", callback_data="idea_photo"),
    )
    builder.add(
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main_menu")
    )
    builder.adjust(2)

    await message.answer(
        "💡 Выберите категорию для генерации идей:",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data.startswith("idea_"))
async def generate_idea_handler(callback: CallbackQuery):
    idea_type = callback.data.split("_")[-1]

    if idea_type == "video":
        builder = InlineKeyboardBuilder()
        for service in SERVICES["video"]:
            builder.add(types.InlineKeyboardButton(
                text=service,
                callback_data=f"video_idea_{service}"
            ))
        builder.add(types.InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back_to_idea_menu"
        ))
        builder.adjust(2)

        await callback.message.edit_text(
            "Выберите тип видео для генерации идей:",
            reply_markup=builder.as_markup()
        )
    elif idea_type == "photo":
        builder = InlineKeyboardBuilder()
        for service in SERVICES["photo"]:
            builder.add(types.InlineKeyboardButton(
                text=service,
                callback_data=f"photo_idea_{service}"
            ))
        builder.add(types.InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back_to_idea_menu"
        ))
        builder.adjust(2)

        await callback.message.edit_text(
            "Выберите тип фото для генерации идей:",
            reply_markup=builder.as_markup()
        )


@dp.callback_query(F.data.startswith(("video_idea_", "photo_idea_")))
async def show_ideas(callback: CallbackQuery):
    idea_type, _, service = callback.data.split("_", 2)
    ideas = {
        "video": {
            "Эдит": [
                "Эдит в стиле аниме с эффектами частиц",
                "Кинематографичный эдит с плавными переходами",
                "Эдит под динамичную музыку с резкими переходами",
                "Эдит в ретро стиле с VHS эффектами"
            ],
            "Монтаж": [
                "Монтаж клипов с эффектом хромакей",
                "Документальный стиль с закадровым голосом",
                "Монтаж в стиле тикток с трендовыми переходами"
            ],
            "Рекламный ролик": [
                "Ролик с акцентом на продукт (крупные планы)",
                "Реклама с отзывами клиентов",
                "Анимационный рекламный ролик"
            ]
        },
        "photo": {
            "Аватарка": [
                "Аватарка в стиле аниме-персонажа",
                "Аватарка с героем из фильма",
                "Аватарка в космическом стиле",
                "Аватарка с неоновыми эффектами",
                "Аватарка в стиле пиксель-арт"
            ],
            "Дизайн": [
                "Дизайн с градиентными переходами",
                "Минималистичный дизайн с акцентами",
                "Дизайн в стиле ретро-футуризм"
            ]
        }
    }

    idea = random.choice(ideas[idea_type][service])

    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="🔁 Другая идея", callback_data=callback.data),
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data=f"back_to_{idea_type}_ideas")
    )

    await callback.message.edit_text(
        f"💡 Идея для {service}:\n\n{idea}",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "back_to_idea_menu")
async def back_to_idea_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="🎥 Для видео", callback_data="idea_video"),
        types.InlineKeyboardButton(text="📸 Для фото", callback_data="idea_photo"),
    )
    builder.add(
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main_menu")
    )
    builder.adjust(2)

    await callback.message.edit_text(
        "💡 Выберите категорию для генерации идей:",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "back_to_video_ideas")
async def back_to_video_ideas(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    for service in SERVICES["video"]:
        builder.add(types.InlineKeyboardButton(
            text=service,
            callback_data=f"video_idea_{service}"
        ))
    builder.add(types.InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="back_to_idea_menu"
    ))
    builder.adjust(2)

    await callback.message.edit_text(
        "Выберите тип видео для генерации идей:",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "back_to_photo_ideas")
async def back_to_photo_ideas(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    for service in SERVICES["photo"]:
        builder.add(types.InlineKeyboardButton(
            text=service,
            callback_data=f"photo_idea_{service}"
        ))
    builder.add(types.InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data="back_to_idea_menu"
    ))
    builder.adjust(2)

    await callback.message.edit_text(
        "Выберите тип фото для генерации идей:",
        reply_markup=builder.as_markup()
    )


# FAQ
@dp.message(F.text == "❓ FAQ")
async def faq_start(message: Message):
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="🎥 Видео", callback_data="faq_video"),
        types.InlineKeyboardButton(text="📸 Фото", callback_data="faq_photo"),
    )
    builder.add(
        types.InlineKeyboardButton(text="📢 Реклама", callback_data="faq_ad"),
    )
    builder.add(
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main_menu")
    )
    builder.adjust(2)

    await message.answer(
        "❓ Выберите категорию FAQ:",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data.startswith("faq_"))
async def show_faq(callback: CallbackQuery):
    faq_type = callback.data.split("_")[-1]
    faq_texts = {
        "video": (
            "❓ Частые вопросы по видео:\n\n"
            "1. Можно ли использовать свою музыку?\n"
            "   - Да, вы можете предоставить свою музыку\n\n"
            "2. Какой максимальный срок выполнения?\n"
            "   - Обычно 1-3 дня\n\n"
            "3. Можно ли внести правки после получения?\n"
            "   - Да, 1-2 правки включены в стоимость"
        ),
        "photo": (
            "❓ Частые вопросы по фото:\n\n"
            "1. Какие стили аватарок вы делаете?\n"
            "   - Аниме, кино, игры и другие стили\n\n"
            "2. Нужно ли предоставлять фото для аватарки?\n"
            "   - Не обязательно, но можно по желанию\n\n"
            "3. Какой формат файлов вы предоставляете?\n"
            "   - PNG, JPG, WEBP на выбор"
        ),
        "ad": (
            "❓ Частые вопросы по рекламе:\n\n"
            "1. Можно ли изменить текст поста после публикации?\n"
            "   - Да, 1 изменение бесплатно в течение 12 часов\n\n"
            "2. Какие форматы рекламных постов?\n"
            "   - Текст + фото/видео, карусель, опросы\n\n"
            "3. Есть ли статистика по просмотрам?\n"
            "   - Да, предоставляем скриншоты статистики"
        )
    }

    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_faq_menu")
    )

    await callback.message.edit_text(
        faq_texts[faq_type],
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data == "back_to_faq_menu")
async def back_to_faq_menu(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.add(
        types.InlineKeyboardButton(text="🎥 Видео", callback_data="faq_video"),
        types.InlineKeyboardButton(text="📸 Фото", callback_data="faq_photo"),
    )
    builder.add(
        types.InlineKeyboardButton(text="📢 Реклама", callback_data="faq_ad"),
    )
    builder.add(
        types.InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main_menu")
    )
    builder.adjust(2)

    await callback.message.edit_text(
        "❓ Выберите категорию FAQ:",
        reply_markup=builder.as_markup()
    )


# Мои заказы
@dp.message(F.text == "📋 Мои заказы")
@dp.message(Command("myorders"))
async def my_orders(message: Message):
    user_id = message.from_user.id
    if user_id not in users_orders or not users_orders[user_id]:
        await message.answer("У вас нет активных заказов.")
        return

    orders_list = []
    for order_id in users_orders[user_id]:
        order = orders_db.get(order_id)
        if order:
            orders_list.append(
                f"🔹 #{order_id} - {order['service_name']} ({order['status']})"
            )

    if not orders_list:
        await message.answer("У вас нет активных заказов.")
        return

    await message.answer(
        "📋 <b>Ваши заказы:</b>\n\n" + "\n".join(orders_list),
        parse_mode=ParseMode.HTML
    )


# Запуск бота
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    print("Бот запущен...")
    asyncio.run(main())