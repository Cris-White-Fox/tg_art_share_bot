import telebot
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from tgbot.tg_logic import bot, timers_view


data_list = []


@csrf_exempt
def telegram_handle(request):
    if request.method == 'POST':
        global data_list
        data = request.body.decode("utf-8")
        data_list.append(data)
        bot.process_new_updates([
            telebot.types.Update.de_json(data)
        ])
        return JsonResponse({"ok": "POST processed"})
    else:
        return JsonResponse({"ok": "GET processed", "TIMERS": timers_view()})
