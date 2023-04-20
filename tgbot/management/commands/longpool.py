from django.core.management.base import BaseCommand
from project.settings import tg_application
import tgbot.views


class Command(BaseCommand):
    def handle(self, *args, **options):
        tg_application.run_polling()
