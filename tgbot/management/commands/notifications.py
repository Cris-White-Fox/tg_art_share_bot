import asyncio
import time

import telegram
from decouple import config
from django.core.management.base import BaseCommand
from tgbot.models import Image, Profile
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = config("API_TOKEN")


class Command(BaseCommand):
    def handle(self, *args, **options):
        notifications_loop()


async def job(bot):
    profiles = await Profile.list_need_notification()
    for tg_id in profiles:
        if photo := await Image.colab_filter_image(tg_id) or await Image.random_image(tg_id):
            keyboard = [
                [
                    InlineKeyboardButton("🚫", callback_data=f'del|{photo.file_unique_id}'),
                    InlineKeyboardButton("❤️", callback_data=f'like|{photo.file_unique_id}'),
                ]
            ]
            print(tg_id, photo.file_id)
            async with bot:
                try:
                    await bot.send_photo(
                        chat_id=tg_id,
                        caption='Found some arts for you!',
                        photo=photo.file_id,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                except telegram.error.Forbidden:
                    pass
                await Profile.update_notification(tg_id)


def notifications_loop():
    bot = Bot(TOKEN)
    while True:
        try:
            asyncio.run(job(bot))
        except Exception as e:
            print(e)
        print('end loop')
        time.sleep(5 * 60)
