import concurrent

import logging
import time
import traceback

import telebot
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from tgbot.tg_logic import bot, timers_view


LAST_PHOTO = time.time()
UPDATE_QUEUE = []
UPDATE_IDS = []


def process_new_update(update):
    try:
        bot.process_new_updates([update])
    except Exception as e:
        logging.exception(traceback.format_exc())


def threaded_process_new_updates(updates):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for update in updates:
            executor.submit(process_new_update, update)


@csrf_exempt
def telegram_handle(request):
    if request.method == 'POST':
        global UPDATE_QUEUE
        global UPDATE_IDS
        global LAST_PHOTO
        data = request.body.decode("utf-8")
        update = telebot.types.Update.de_json(data)
        if update.update_id in UPDATE_IDS:
            return JsonResponse({"ok": "POST processed"})

        if update.message and update.message.photo and time.time() - LAST_PHOTO < 1:
            UPDATE_QUEUE.append(update)
            LAST_PHOTO = time.time()

        else:
            process_new_update(update)
            if UPDATE_QUEUE:
                threaded_process_new_updates(UPDATE_QUEUE)
                UPDATE_QUEUE = []

        if len(UPDATE_QUEUE) > 15:
            threaded_process_new_updates(UPDATE_QUEUE)
            UPDATE_QUEUE = []

        UPDATE_IDS = [update.update_id] + UPDATE_IDS[:1000]
        return JsonResponse({"ok": "POST processed"})
    else:
        return JsonResponse({"ok": "GET processed", "TIMERS": timers_view()})
