import concurrent

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from tgbot.tg_logic import bot, timers_view


@csrf_exempt
def telegram_handle(request):
    if request.method == 'POST':
        if updates := bot.get_updates(
                offset=bot.last_update_id + 1,
                limit=100,
                long_polling_timeout=0.1,
                allowed_updates=["photo", "text"]
        ):
            bot.last_update_id = max(update.update_id for update in updates)
            with concurrent.futures.ThreadPoolExecutor() as executor:
                for update in updates:
                    print(update)
                    executor.submit(bot.process_new_updates, [update])
        return JsonResponse({"ok": "POST processed"})
    else:
        return JsonResponse({"ok": "GET processed", "TIMERS": timers_view()})
