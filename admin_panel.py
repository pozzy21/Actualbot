from asyncio import sleep

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import admin_id
from load_all import dp, _, bot
from states import NewItem, Mailing, Confirming
from database import Item, User, Purchase
import database


db = database.DBCommands()


@dp.message_handler(user_id=admin_id, commands=["cancel"], state=NewItem)
async def cancel(message: types.Message, state: FSMContext):
    await message.answer(_("Вы отменили создание услуги"))
    await state.reset_state()


@dp.message_handler(user_id=admin_id, commands=["add_item"])
async def add_item(message: types.Message):
    await message.answer(_("Введите название услуги или введите /cancel"))
    await NewItem.Name.set()


@dp.message_handler(user_id=admin_id, state=NewItem.Name)
async def enter_name(message: types.Message, state: FSMContext):
    name = message.text
    item = Item()
    item.name = name
    await message.answer(_("Введите описание услуги или введите /cancel"))
    await NewItem.Description.set()
    await state.update_data(item=item)

@dp.message_handler(user_id=admin_id, state=NewItem.Description)
async def set_desc(message: types.Message,state:FSMContext):
    description = message.text
    data = await state.get_data()
    item: Item = data.get("item")
    item.description = description
    await message.answer(_("\nЗагрузите фотографию или введите /cancel"))
    await NewItem.Photo.set()
    await state.update_data(item=item)


@dp.message_handler(user_id=admin_id, state=NewItem.Photo, content_types=types.ContentType.PHOTO)
async def add_photo(message: types.Message, state: FSMContext):
    photo = message.photo[-1].file_id
    data = await state.get_data()
    item: Item = data.get("item")
    item.photo = photo

    await message.answer_photo(
        photo=photo,
        caption=_(
                  "\nПришлите мне цену товара в копейках или введите /cancel"))

    await NewItem.Price.set()
    await state.update_data(item=item)


@dp.message_handler(user_id=admin_id, state=NewItem.Price)
async def enter_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    item: Item = data.get("item")
    try:
        price = int(message.text)
    except ValueError:
        await message.answer(_("Неверное значение, введите число"))
        return

    item.price = price
    markup = InlineKeyboardMarkup(
        inline_keyboard=
        [
            [InlineKeyboardButton(text=_("Да"), callback_data="confirm")],
            [InlineKeyboardButton(text=_("Ввести заново"), callback_data="change")],
        ]
    )
    await message.answer(_("Цена: {price:,}0\n"
                           ).format(price=price / 100),
                         reply_markup=markup)
    await state.update_data(item=item)
    await NewItem.Confirm.set()


@dp.callback_query_handler(user_id=admin_id, text_contains="change", state=NewItem.Confirm)
async def enter_price(call: types.CallbackQuery):
    await call.message.edit_reply_markup()
    await call.message.answer(_("Введите заново цену услуги в копейках"))
    await NewItem.Price.set()


@dp.callback_query_handler(user_id=admin_id, text_contains="confirm", state=NewItem.Confirm)
async def enter_price(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_reply_markup()
    data = await state.get_data()
    item: Item = data.get("item")
    await item.create()
    await call.message.answer(_("Услуга удачно создана."))
    await state.reset_state()


# Фича для рассылки по юзерам (учитывая их язык)
@dp.message_handler(user_id=admin_id, commands=["tell_everyone"])
async def mailing(message: types.Message):
    await message.answer(_("Пришлите текст рассылки"))
    await Mailing.Text.set()


@dp.message_handler(user_id=admin_id, state=Mailing.Text)
async def mailing(message: types.Message, state: FSMContext):
    text = message.text
    await state.update_data(text=text)
    markup = InlineKeyboardMarkup(
        inline_keyboard=
        [
            [InlineKeyboardButton(text="Русский", callback_data="ru")],
            [InlineKeyboardButton(text="English", callback_data="en")],
            [InlineKeyboardButton(text="Україньска", callback_data="uk")],
        ]
    )
    await message.answer(_("\n"
                           "Текст вашей рассылки:\n"
                           "{text}").format(text=text),
                         reply_markup=markup)
    await Mailing.Language.set()


@dp.callback_query_handler(user_id=admin_id, state=Mailing.Language)
async def mailing_start(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("text")
    await state.reset_state()
    await call.message.edit_reply_markup()

    users = await User.query.where(User.language == call.data).gino.all()
    for user in users:
        try:
            await bot.send_message(chat_id=user.user_id,
                                   text=text)
            await sleep(0.3)
        except Exception:
            pass
    await call.message.answer(_("Рассылка выполнена."))

@dp.message_handler(user_id=admin_id,text_contains = "/show_orders")
async def show_orders(message: types.Message, state:FSMContext):
    all_orders, all_items = await db.show_orders()
    orders_markup = InlineKeyboardMarkup(
        inline_keyboard=[
        [
            InlineKeyboardButton(text=_("Бронь"),callback_data="confirm"),
        ]
    ])
    for num, order in enumerate(all_orders):
        confirm = order
       # if not order.delivered and (order.successful == True):
        text = _("<b>ID заказа:</b> \t <u>{id}</u>\n"
                     "<b>ID Комнаты:</b> \t <u>{item_id}</u>\n"
                     "<b>Название:</b> \t <u>{item_name}</u>\n"
                     "<b>Имя Клиента:</b> \t <u>{name}</u>\n"
                     "<b>Итоговый чек:</b> \t{amount:,}RUB\n"
                     "<b>E-mail: \t<u>{email}</u></b>\n"
                     "<b>Номер телефона: \t<u>{phone_number}</u></b>")
        for num, occup in enumerate(all_items):
            confirm = occup
        await message.answer(text.format(
                    id = order.id,
                    item_id = order.item_id,
                    item_name=order.item_name,
                    name= order.receiver,
                    amount=order.amount / 100,
                    email=order.email,
                    phone_number = order.phone_number,
                ), reply_markup=orders_markup)

        await state.update_data(confirm1=occup)
        await Confirming.Confirm1.set()


@dp.callback_query_handler(text_contains = "confirm", state=Confirming.Confirm1)
async def confirm_order(call: types.CallbackQuery,state: FSMContext):
    await call.message.edit_reply_markup()
    data = await state.get_data()
    confirm1 = data.get("confirm1")
    if confirm1.occupied == False:
        await confirm1.update(occupied=True).apply()
        text = _("Комната с номером <b>{id}</b> отмечена как забронированная\n")
        await state.finish()
    else:
        await confirm1.update(occupied=False).apply()
        text = _("Комната с номером <b>{id}</b> отмечена как свободная\n")
        await state.finish()


    await bot.send_message(text = text.format(
        id = confirm1.id,),chat_id = admin_id)


@dp.callback_query_handler(text_contains = "release", state=Confirming.Confirm1)
async def release_order(call: types.CallbackQuery,state: FSMContext):
    await call.message.edit_reply_markup()
    data = await state.get_data()
    confirm1 = data.get("confirm1")
    await confirm1.update(occupied=False).apply()
    await state.finish()
    text = _("Заказ с номером <b>{id}</b> на сумму <u>{amount}0</u> отмечен как выполненый\n"
             )



