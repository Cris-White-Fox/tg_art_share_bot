import time

import telebot
from django.core.management.base import BaseCommand

from tgbot.models import Profile
from project.settings import bot
from tgbot.recommendations import ColabFilter
from tgbot.tg_logic import response_text, send_photo_with_default_markup


class Command(BaseCommand):
    def handle(self, *args, **options):
        job()


def job():
    profiles = Profile.list_need_notification()
    cf = ColabFilter()
    for profile in profiles:
        if file_unique_ids := cf.predict(profile.id):
            try:
                bot.send_message(
                    chat_id=profile.tg_id,
                    text=response_text(
                        template='img_notification',
                        tg_id=profile.tg_id
                    )
                )
                send_photo_with_default_markup(profile.tg_id, file_unique_ids[0])
            except telebot.apihelper.ApiTelegramException:
                Profile.block_profile(profile.tg_id)
            else:
                Profile.update_notification(profile.tg_id)


def notifications_loop():
    while True:
        try:
            job()
        except Exception as e:
            print(e)
        print('end loop')
        time.sleep(15 * 60)
