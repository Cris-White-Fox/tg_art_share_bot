import time

import telebot
from django.core.management.base import BaseCommand

from tgbot.models import Image, Profile
from project.settings import bot
from tgbot.tg_logic import response_text, send_photo_with_default_markup


class Command(BaseCommand):
    def handle(self, *args, **options):
        job()


def job():
    profiles = Profile.list_need_notification()
    for tg_id in profiles:
        if photo := Image.colab_filter_image(tg_id) or Image.random_image(tg_id):
            try:
                bot.send_message(
                    chat_id=tg_id,
                    text=response_text(
                        template='img_notification',
                        tg_id=tg_id
                    )
                )
                send_photo_with_default_markup(tg_id, photo)
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
