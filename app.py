import asyncio
import logging
from aiogram import executor

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.redis import RedisStorage2
from aiogram.dispatcher import DEFAULT_RATE_LIMIT
from aiogram.dispatcher.handler import CancelHandler, current_handler
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.utils.exceptions import Throttled
from handlers import ThrottlingMiddleware


from config import admin_id
from database import create_db
from load_all import bot


async def on_shutdown(dp):
    await bot.close()


async def on_startup(dp):
    await create_db()
    await bot.send_message(admin_id, "Я запущен!")


if __name__ == '__main__':
    from admin_panel import dp
    from handlers import dp
    dp.middleware.setup(ThrottlingMiddleware())
    executor.start_polling(dp, on_shutdown=on_shutdown, on_startup=on_startup, skip_updates=True)
