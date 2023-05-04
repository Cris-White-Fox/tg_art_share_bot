from django.core.management.base import BaseCommand
from tgbot.tg_logic import bot


class Command(BaseCommand):
    def handle(self, *args, **options):
        bot.remove_webhook()
        bot.infinity_polling(long_polling_timeout=120)
