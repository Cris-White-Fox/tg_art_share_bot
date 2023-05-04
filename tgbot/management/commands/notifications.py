import time

import telebot
from django.core.management.base import BaseCommand
from telebot.util import quick_markup

from tgbot.models import Image, Profile
from project.settings import bot


class Command(BaseCommand):
    def handle(self, *args, **options):
        notifications_loop()


def job():
    profiles = Profile.list_need_notification()
    for tg_id in profiles:
        if photo := Image.colab_filter_image(tg_id) or Image.random_image(tg_id):
            markup = quick_markup({
                "🚫": {'callback_data': f'dislike|{photo.file_unique_id}'},
                "❤️": {'callback_data': f'like|{photo.file_unique_id}'},
            })
            try:
                bot.send_photo(
                    chat_id=tg_id,
                    photo=photo.file_id,
                    caption="Found image for you!",
                    reply_markup=markup
                )
            except telebot.apihelper.ApiTelegramException:
                Profile.block_profile(tg_id)
            else:
                Profile.update_notification(tg_id)


def notifications_loop():
    while True:
        try:
            job()
        except Exception as e:
            print(e)
        print('end loop')
        time.sleep(15 * 60)
