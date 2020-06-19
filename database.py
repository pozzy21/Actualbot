from aiogram import types, Bot
from gino import Gino
from gino.schema import GinoSchemaVisitor
from sqlalchemy import (Column, Integer, BigInteger, String,
                        Sequence, TIMESTAMP, Boolean, JSON)
from sqlalchemy import sql

from config import db_pass, db_user, host

db = Gino()


# Документация
# http://gino.fantix.pro/en/latest/tutorials/tutorial.html

class User(db.Model):
    __tablename__ = 'users'

    id = Column(Integer, autoincrement=True, primary_key=True)
    user_id = Column(BigInteger)
    language = Column(String(2),default='ru')
    full_name = Column(String(100))
    username = Column(String(50))
    referral = Column(Integer)
    query: sql.Select

    def __repr__(self):
        return "<User(id='{}', fullname='{}', username='{}')>".format(
            self.id, self.full_name, self.username)


class Item(db.Model):
    __tablename__ = 'items'
    query: sql.Select

    id = Column(Integer, autoincrement=True, primary_key=True)
    name = Column(String(300))
    photo = Column(String(250))
    price = Column(Integer)
    description = Column(String(1000))
    occupied = Column(Boolean, default=False)


    def __repr__(self):
        return "<Item(id='{}', name='{}', price='{}',description ='{}')>".format(
            self.id, self.name, self.price,self.description)


class Purchase(db.Model):
    __tablename__ = 'purchases'
    query: sql.Select
    id = Column(Integer, autoincrement=True, primary_key=True)
    buyer = Column(BigInteger)
    item_id = Column(Integer)
    item_name = Column(String)
    amount = Column(Integer)  # Цена в копейках
    quantity = Column(Integer)
    purchase_time = Column(TIMESTAMP)
    shipping_address = Column(JSON)
    phone_number = Column(String(50))
    email = Column(String(200))
    receiver = Column(String(100))


    successful = Column(Boolean, default=False)
    delivered = Column(Boolean, default=False)



class DBCommands:


    async def get_user(self, user_id):
        user = await User.query.where(User.user_id == user_id).gino.first()
        return user

    async def add_new_user(self, referral=None):
        user = types.User.get_current()
        old_user = await self.get_user(user.id)
        if old_user:
            return old_user
        new_user = User()
        new_user.user_id = user.id
        new_user.username = user.username
        new_user.full_name = user.full_name

        if referral:
            new_user.referral = int(referral)
        await new_user.create()
        return new_user

    async def set_language(self, language):
        user_id = types.User.get_current().id
        user = await self.get_user(user_id)
        await user.update(language=language).apply()

    async def count_users(self) -> int:
        total = await db.func.count(User.id).gino.scalar()
        return total
    async def count_items(self) -> int:
        total = await db.func.count(Item.id).gino.scalar()
        return total



    async def check_referrals(self):
        bot = Bot.get_current()
        user_id = types.User.get_current().id

        user = await User.query.where(User.user_id == user_id).gino.first()
        referrals = await User.query.where(User.referral == user.id).gino.all()

        return ", ".join([
            f"{num + 1}. " + (await bot.get_chat(referral.user_id)).get_mention(as_html=True)
            for num, referral in enumerate(referrals)
        ])

    async def show_items(self):
        items = await Item.query.gino.all()

        return items


    async def show_orders(self):
        orders = await Purchase.query.gino.all()
        occupied = await Item.query.gino.all()
        return orders, occupied

    async def true_occupied(self):
        await Item.update(occupied = True).where(Item.id == 1).gino.status()


async def create_db():
    await db.set_bind(f'postgresql://{db_user}:{db_pass}@{host}/gino')

# async def switch_bool():
#     await user.update(nickname='daisy').apply()


    # Create tables
    db.gino: GinoSchemaVisitor
    #await db.gino.drop_all()
    await db.gino.create_all()