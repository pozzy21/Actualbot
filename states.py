from aiogram.dispatcher.filters.state import StatesGroup, State


class Purchase(StatesGroup):
    EnterQuantity = State()
    Approval = State()
    Payment = State()

class Edit(StatesGroup):
    EditName = State()
    EditDesc = State()
    EditPrice = State()
    Confirm = State()



class NewItem(StatesGroup):
    Name = State()
    Photo = State()
    Description = State()
    Price = State()
    Confirm = State()


class Mailing(StatesGroup):
    Text = State()
    Language = State()


class Confirming(StatesGroup):
    Confirm1 = State()
    Confirm2 = State()


