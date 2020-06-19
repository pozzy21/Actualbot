import asyncio
import datetime
import apiai
import json
from aiogram.utils.emoji import emojize
import logging

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import CommandStart
from aiogram.types import (Message, InlineKeyboardMarkup, InlineKeyboardButton,
                           CallbackQuery, LabeledPrice,ReplyKeyboardMarkup, PreCheckoutQuery)
from aiogram.utils.callback_data import CallbackData

import database
import states
from config import lp_token, admin_id
from load_all import dp, bot, _
import asyncio

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.redis import RedisStorage2
from aiogram.dispatcher import DEFAULT_RATE_LIMIT
from aiogram.dispatcher.handler import CancelHandler, current_handler
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.utils.exceptions import Throttled

db = database.DBCommands()
logging.basicConfig(level=logging.INFO)

# Используем CallbackData для работы с коллбеками, в данном случае для работы с покупкой товаров
buy_item = CallbackData("buy", "item_id")

def rate_limit(limit: int, key=None):
    """
    Decorator for configuring rate limit and key in different functions.

    :param limit:
    :param key:
    :return:
    """

    def decorator(func):
        setattr(func, 'throttling_rate_limit', limit)
        if key:
            setattr(func, 'throttling_key', key)
        return func

    return decorator


class ThrottlingMiddleware(BaseMiddleware):
    """
    Simple middleware
    """

    def __init__(self, limit=DEFAULT_RATE_LIMIT, key_prefix='antiflood_'):
        self.rate_limit = limit
        self.prefix = key_prefix
        super(ThrottlingMiddleware, self).__init__()

    async def on_process_message(self, message: types.Message, data: dict):
        """
        This handler is called when dispatcher receives a message

        :param message:
        """
        # Get current handler
        handler = current_handler.get()

        # Get dispatcher from context
        dispatcher = Dispatcher.get_current()
        # If handler was configured, get rate limit and key from handler
        if handler:
            limit = getattr(handler, 'throttling_rate_limit', self.rate_limit)
            key = getattr(handler, 'throttling_key', f"{self.prefix}_{handler.__name__}")
        else:
            limit = self.rate_limit
            key = f"{self.prefix}_message"

        # Use Dispatcher.throttle method.
        try:
            await dispatcher.throttle(key, rate=limit)
        except Throttled as t:
            # Execute action
            await self.message_throttled(message, t)

            # Cancel current handler
            raise CancelHandler()

    async def message_throttled(self, message: types.Message, throttled: Throttled):
        """
        Notify user only on first exceed and notify about unlocking only on last exceed

        :param message:
        :param throttled:
        """
        handler = current_handler.get()
        dispatcher = Dispatcher.get_current()
        if handler:
            key = getattr(handler, 'throttling_key', f"{self.prefix}_{handler.__name__}")
        else:
            key = f"{self.prefix}_message"

        # Calculate how many time is left till the block ends
        delta = throttled.rate - throttled.delta

        # Prevent flooding
        if throttled.exceeded_count <= 2:
            await message.reply('Слишком много одинаковых запросов!\n'
                                'Попробуйте через 5 секунд.')

        # Sleep.
        await asyncio.sleep(delta)

        # Check lock status
        thr = await dispatcher.check_key(key)

        # If current message is not last with current key - do not send message
        if thr.exceeded_count == throttled.exceeded_count:
            await message.reply('Unlocked.')

# Для команды /start есть специальный фильтр, который можно тут использовать
@dp.message_handler(commands=['start'])
@rate_limit(5, 'start')
async def register_user(message: types.Message):
    welcome_text = _("🖐🏻Добро пожаловать!")
    chat_id = message.from_user.id
    referral = message.get_args()
    user = await db.add_new_user(referral=referral)
    id = user.id
    count_users = await db.count_users()
    count_items = await db.count_items()
    # клавиатура с выбором языков
    languages_markup = InlineKeyboardMarkup(
        inline_keyboard=
        [
            [
                InlineKeyboardButton(text="🇷🇺" + "  Русский", callback_data="lang_ru")],
            [
                InlineKeyboardButton(text="🇬🇧" + "  English", callback_data="lang_en"),
                InlineKeyboardButton(text="🇺🇦" + "  Україньска", callback_data="lang_uk"),

            ]
        ]
    )

##
    keyboard_markup = types.ReplyKeyboardMarkup(row_width=3,resize_keyboard=True)
    # default row_width is 3, so here we can omit it actually
    # kept for clearness
    btns_text = ('👀Комнаты','☺Помощь', '😇Рефералы','')
    keyboard_markup.row(*(types.KeyboardButton(text) for text in btns_text))
    await bot.send_message(chat_id, welcome_text, reply_markup=keyboard_markup)
    await asyncio.sleep(0.3)



    bot_username = (await bot.me).username
    bot_link = f"https://t.me/{bot_username}?start={id}"

    # Для многоязычности, все тексты, передаваемые пользователю должны передаваться в функцию "_"
    # Вместо "текст" передаем _("текст")

    text = _("\n"
             "\n"
             "😺В данный момент нашими услугами пользуются <b>{count_users} человек!</b>\n"
             "😇Ваша реферальная ссылка:\n {bot_link}\n"
             "👀Просмотреть каталог комнат можно по нажатию на соответствующие кнопки!\n").format(
        count_users=count_users + 12,
        count_items=count_items + 15,
        bot_link=bot_link,
    )

    # if message.from_user.id == admin_id:
    #     text += _("____________________________\n"
    #               "<b>ПАНЕЛЬ АДМИНИСТРАТОРА:</b>\n"
    #               "Добавить новый товар: /add_item\n"
    #               "Просмотреть активные заказы : /show_orders\n"
    #               "Сделать массовую рассылку: /tell_everyone \n"
    #               "Добавить нового администратора: /add_admin")
    await bot.send_photo(chat_id, caption=text,
                         photo="AgACAgIAAxkBAAILe17mEby95kQBtKiPDnrDwJ1Ud6_CAAKDrjEblDExS8zpTPqVna7fKEF9kS4AAwEAAwIAA3gAA1N0BAABGgQ",
                         reply_markup=languages_markup)
    admin_markup = InlineKeyboardMarkup
    if message.from_user.id == admin_id:
        admin_text = "<b>Вы являетесь администратором.</b>\n"
        admin_markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
        # default row_width is 3, so here we can omit it actually
        # kept for clearness
        btns_text = ('👀Комнаты', '☺Помощь', '😇Рефералы', '😎Администрирование')
        admin_markup.row(*(types.KeyboardButton(text) for text in btns_text))
        await bot.send_message(chat_id = admin_id, text = admin_text,reply_markup = admin_markup)


@dp.message_handler(text_contains = "😎")#Администрирование
async def admin_inline(message : Message):
    text =_("Панель администратора представлена ниже: \n")
    admin_markup = InlineKeyboardMarkup(
        inline_keyboard=
        [
            [
                InlineKeyboardButton(text="Добавить товар", callback_data="add_items")],

            [
                InlineKeyboardButton(text="Актуальные заказы", callback_data="show_orders"),
                InlineKeyboardButton(text="Рассылка", callback_data="tell_everyone"),

            ],
            [
                InlineKeyboardButton(text="Редактировать товар", callback_data="edit_item")

            ]

        ]
    )
    await bot.send_message(chat_id = message.from_user.id, text = text, reply_markup = admin_markup)


@dp.message_handler(text_contains = '☺') #Связь с менеджером
@rate_limit(5, '☺')
async def admin_contact(message:Message):
    await bot.send_contact(chat_id=message.from_user.id, phone_number = '+79246811768',first_name = 'Pavel', last_name='Prutkov')



# Альтернативно можно использовать фильтр text_contains, он улавливает то, что указано в call.data
@dp.callback_query_handler(text_contains="lang")
async def change_language(call: CallbackQuery):
    await call.message.edit_reply_markup()
    # Достаем последние 2 символа (например ru)
    lang = call.data[-2:]
    await db.set_language(lang)

    # После того, как мы поменяли язык, в этой функции все еще указан старый, поэтому передаем locale=lang
    await call.message.answer(_("Ваш язык был изменен", locale=lang))


@dp.message_handler(text_contains = '😇') # Рефералы
async def check_referrals(message: types.Message):
    referrals = await db.check_referrals()
    text = _("Ваши рефералы:\n{referrals}").format(referrals=referrals)
    await message.answer(text)


# Показываем список доступных товаров
@dp.message_handler(text_contains = '👀') #комнаты
async def show_items(message: Message):
    await bot.send_message(chat_id = message.from_user.id,text="В данный момент у нас свободны эти комнаты: \n"
                           )
    await asyncio.sleep(0.5)
    # Достаем товары из базы данных
    all_items = await db.show_items()
    # Проходимся по товарам
    for num, item in enumerate(all_items):
        if not item.occupied:
            text = _('\t <u>{name}</u>\n'
                     '<b>Описание:</b> \t {description}\n'
                     '<b>Цена:</b> \t{price:,}0 RUB за сутки\n')
            markup = InlineKeyboardMarkup(
                inline_keyboard=
                [
                    [
                        # Создаем кнопку "купить" и передаем ее айдишник в функцию создания коллбека
                        InlineKeyboardButton(text=_("Забронировать"), callback_data=buy_item.new(item_id=item.id))
                    ],
                ]
            )

        # Отправляем фотку товара с подписью и кнопкой "купить"
            await message.answer_photo(
                photo=item.photo,
                caption=text.format(
                    id=item.id,
                    name=item.name,
                    description = item.description,
                    price=item.price / 100
                ),
                reply_markup=markup
            )
            # Между сообщениями делаем небольшую задержку, чтобы не упереться в лимиты
            await asyncio.sleep(0.5)
    await bot.send_message(chat_id = message.from_user.id,
                           text = "Если у вас возникли вопросы вы можете обратиться к менеджеру\n"
                                   "нажав соотвествующую клавишу в меню ниже👇👇👇👇👇")

# Для фильтрования по коллбекам можно использовать buy_item.filter()
@dp.callback_query_handler(buy_item.filter())
async def buying_item(call: CallbackQuery, callback_data: dict, state: FSMContext):
    # То, что мы указали в CallbackData попадает в хендлер под callback_data, как словарь, поэтому достаем айдишник
    item_id = int(callback_data.get("item_id"))
    await call.message.edit_reply_markup()

    # Достаем информацию о товаре из базы данных
    item = await database.Item.get(item_id)
    if not item:
        await call.message.answer(_("Такого товара не существует"))
        return

    text = _("Вы хотите забронировать \"<b>{name}</b>\" \n"
             "Размер <b>ежедневной оплаты состовляет</b>: <i>{price:,}/сутки.</i>\n"
             "<u>Введите</u> на сколько дней вы планируете остаться у нас.").format(name=item.name,
                                                             price=item.price / 100)
    await call.message.answer(text)
    await states.Purchase.EnterQuantity.set()

    # Сохраняем в ФСМ класс товара и покупки
    await state.update_data(
        item=item,
        purchase=database.Purchase(
            item_id=item_id,
            purchase_time=datetime.datetime.now(),
            buyer=call.from_user.id,
            item_name = item.name
        )
    )


# Принимаем в этот хендлер только цифры
@dp.message_handler(regexp=r"^(\d+)$", state=states.Purchase.EnterQuantity)
async def enter_quantity(message: Message, state: FSMContext):
    # Получаем количество указанного товара
    quantity = int(message.text)
    async with state.proxy() as data:  # Работаем с данными из ФСМ
        data["purchase"].quantity = quantity
        item = data["item"]
        amount = item.price * quantity
        data["purchase"].amount = amount

    # Создаем кнопки
    agree_button = InlineKeyboardButton(
        text=_("👌Все верно!👌"),
        callback_data="agree"
    )
    change_button = InlineKeyboardButton(
        text=_("🤦‍♀Ввести количество заново🤦‍♂"),
        callback_data="change"
    )
    cancel_button = InlineKeyboardButton(
        text=_("🙅‍♀Отменить покупку🙅‍♂"),
        callback_data="cancel"
    )

    # Создаем клавиатуру
    markup = InlineKeyboardMarkup(
        inline_keyboard=
        [
            [agree_button],  # Первый ряд кнопок
            [change_button],  # Второй ряд кнопок
            [cancel_button]  # Третий ряд кнопок
        ]
    )
    await message.answer(
        _("Отлично!    \n"
          "Вы желаете забронировать \"{name}\" \n"
          "на <i>{quantity}</i> суток \n"
          "по цене <b>{price:,} за сутки.</b>\n"
          "____________________________________\n"
          "Общаю сумма составляет: <u><b>{amount:,}0</b></u>.\n"
          "Подтверждаете?").format(
            quantity=quantity,
            name=item.name,
            amount=amount / 100,
            price=item.price / 100
        ),
        reply_markup=markup)
    await states.Purchase.Approval.set()


# То, что не является числом - не попало в предыдущий хендлер и попадает в этот
@dp.message_handler(state=states.Purchase.EnterQuantity)
async def not_quantity(message: Message):
    await message.answer(_("Неверное значение, введите число (* ￣︿￣)"))


# Если человек нажал на кнопку Отменить во время покупки - убираем все
@dp.callback_query_handler(text_contains="cancel", state=states.Purchase)
async def approval(call: CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()  # Убираем кнопки
    await call.message.answer(_("Вы отменили эту покупку (* ￣︿￣)"))
    await state.reset_state()


# Если человек нажал "ввести заново"
@dp.callback_query_handler(text_contains="change", state=states.Purchase.Approval)
async def approval(call: CallbackQuery):
    await call.message.edit_reply_markup()  # Убираем кнопки
    await call.message.answer(_("Введите количество товара заново.   "))
    await states.Purchase.EnterQuantity.set()




# Если человек нажал "согласен"
@dp.callback_query_handler(text_contains="agree", state=states.Purchase.Approval)
async def approval(call: CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()  # Убираем кнопки

    data = await state.get_data()
    purchase: database.Purchase = data.get("purchase")
    item: database.Item = data.get("item")
    # Теперь можно внести данные о покупке в базу данных через .create()
    await purchase.create()
    await bot.send_message(chat_id=call.from_user.id,
                           text=_("Прекрасно, осталось только оплатить!\n"
                                  "Произвести оплату можно по кнопке, которая вот-вот появится!\n"
                                  ).format(amount=purchase.amount))
    await asyncio.sleep(0.5)

    currency = "RUB"
    need_name = True
    need_phone_number = True
    need_email = True
    need_shipping_address = False

    await bot.send_invoice(chat_id=call.from_user.id,
                           title=item.name,
                           description=item.name,
                           payload=str(purchase.id),
                           start_parameter=str(purchase.id),
                           currency=currency,
                           prices=[
                               LabeledPrice(label=item.name, amount=purchase.amount)
                           ],
                           provider_token=lp_token,
                           need_name=need_name,
                           need_phone_number=need_phone_number,
                           need_email=need_email,
                           need_shipping_address=need_shipping_address
                           )
    await state.update_data(purchase=purchase)
    await states.Purchase.Payment.set()


@dp.pre_checkout_query_handler(state=states.Purchase.Payment)
async def checkout(query: PreCheckoutQuery, state: FSMContext):
    await bot.answer_pre_checkout_query(query.id, True)
    data = await state.get_data()
    purchase: database.Purchase = data.get("purchase")
    success = await check_payment(purchase)

    if success:
        await purchase.update(
            successful=True,
            shipping_address=query.order_info.shipping_address.to_python()
            if query.order_info.shipping_address
            else None,
            phone_number=query.order_info.phone_number,
            receiver=query.order_info.name,
            email=query.order_info.email
        ).apply()
        await state.reset_state()
        await bot.send_message(query.from_user.id, _("Спасибо за то, что выбрали нас   \(@^0^@)/"))
        await bot.send_message(query.from_user.id, _("Помните, что хостел — это общежитие.\n"
                                                     "•Уважайте личное пространство других людей.\n"
                                                     "•Соблюдайте тишину.\n"
                                                     "•Не сорите!\n"
                                                     "•Присматривате за своими вещами.\n"
                                                     "•Возьмите с собой одежду для сна, беруши и повязку на глаза.\n"
                                                     "•И самое главное - <b>общайтесь!</b>"))

    else:
        await bot.send_message(query.from_user.id, _("Оплата не была подтверждена, попробуйте позже..."))


#@dp.message_handler()
#async def other_echo(message: Message):
#    await message.answer(message.text)





@dp.message_handler(commands="set_commands", state="*")
async def cmd_set_commands(message: types.Message):
    if message.from_user.id == admin_id:  # Подставьте сюда свой Telegram ID
        commands = [types.BotCommand(command="/start", description="Начать работу")]
        await bot.set_my_commands(commands)
        await message.answer("Команды настроены.")


async def check_payment(purchase: database.Purchase):
    return True



# In this example Redis storage is used

