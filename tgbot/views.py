import concurrent

import logging
import traceback

import telebot
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from tgbot.tg_logic import bot, timers_view


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
        data = request.body.decode("utf-8")
        update = telebot.types.Update.de_json(data)
        if update.update_id in UPDATE_IDS:
            return JsonResponse({"ok": "POST processed"})
        UPDATE_IDS = [update.update_id] + UPDATE_IDS[:1000]

        if update.message and update.message.photo:
            UPDATE_QUEUE.append(update)

        else:
            process_new_update(update)
            if UPDATE_QUEUE:
                part_to_update, UPDATE_QUEUE = UPDATE_QUEUE[:10], UPDATE_QUEUE[10:]
                threaded_process_new_updates(part_to_update)

        if len(UPDATE_QUEUE) > 30:
            part_to_update, UPDATE_QUEUE = UPDATE_QUEUE[:10], UPDATE_QUEUE[10:]
            threaded_process_new_updates(part_to_update)


        return JsonResponse({"ok": "POST processed"})
    else:
        return JsonResponse({"ok": "GET processed", "TIMERS": timers_view()})
