import django
import io
import logging
import time
import traceback
from threading import Lock
from contextlib import suppress

import imagehash
from PIL import Image as PILImage
from telebot.types import Message, CallbackQuery
from telebot.util import quick_markup
from telebot.apihelper import ApiTelegramException

from project.settings import bot

from tgbot.models import Image, ImageScore, Profile, Report, ImageBlock
from tgbot.recommendations import ColabFilter

TIMERS = {}
IMAGES_CACHE = {}
DB_LOCK = Lock()
COLAB_FILTER = ColabFilter()


def timers_view():
    return {
        func_name: {
            "count": len(timer),
            "median_time": sorted(timer)[len(timer)//2],
            "worst 10": [round(t, 3) for t in sorted(timer, reverse=True)[:10]],
        } for func_name, timer in TIMERS.items()
    }


def update_user(func):
    def inner(message: Message):
        logging.debug(message)
        with DB_LOCK:
            Profile.update_profile(message.from_user.id, message.from_user.full_name, message.from_user.language_code)
        return func(message)
    return inner


def timeit(func):
    def inner(*args, **kwargs):
        global TIMERS
        start = time.time()

        result = func(*args, **kwargs)

        timer = time.time() - start
        TIMERS[str(func)] = [timer] + TIMERS.get(str(func), [])[:1000]
        print(timers_view())
        return result
    return inner


response_templates_dict = {
    'help': {
        'ru': "Хей, пришли мне свои любимые арты, а я найду тех, кому они тоже понравятся!\n"
              "Либо иcпользуй команду /image, чтобы посмотреть чужие арты",
        'default': "Hey, send me your favorite arts and I'll find people who like it too!\n"
                   "Or use the /image command to see other people's arts",
    },
    'img_saved': {
        'ru': "Изображение сохранено!",
        'default': "Image saved!",
    },
    'img_deleted': {
        'ru': "Изображение удалено из базы!",
        'default': "Image deleted from database!",
    },
    'img_not_found': {
        'ru': 'Больше изображений не найдено\nПопробуй позже',
        'default': 'Images not found!\nTry later'
    },
    'upload_limit': {
        'ru': 'Слишком много изображений!\n'
              'Подожди немного и попробуй снова.\n'
              'Пока можешь полистать чужие арты! Используй /image',
        'default': 'Upload limit!\nTry later or use /image',
    },
    'already_in_db': {
        "ru": "Такое изображение уже есть в базе!",
        'default': "Image already in database!",
    },
    'stat': {
        'ru':
            'Загружено изображений: {uploaded_images} (больше чем {uploaded_images_position}% других пользователей)\n'
            'Поставлено оценок: {scores_from} (больше чем {score_images_position}% других пользователей)\n'
            'Люди с похожими вкусами: {similar_profiles}',
        'default':
            'Images uploaded: {uploaded_images}  (it\'s more then {uploaded_images_position}% of other users)\n'
            'Images scored: {scores_from} (it\'s more then {score_images_position}% of other users)\n'
            'Have similar taste: {similar_profiles}'
    },
    'img_notification': {
        'ru': 'Для тебя нашлось несколько новых изображений, надеюсь тебе они понравятся!',
        'default': "Found some images for you, hope you like them!",
    },
    'report_photo': {
        'ru': 'Действительно хочешь отправить жалобу на это изображение?',
        'default': "Do you really want to send a complaint about this image?",
    },
    'report_photo_send': {
        'ru': 'Жалоба отправлена!',
        'default': "Complaint was send!",
    },
    'too_many_reports': {
        'ru': 'Слишком много жалоб подряд!',
        'default': "Too many complaints!",
    },
    'report_limit': {
        'ru': 'Загрузка изображений ограничена из-за жалоб пользователей!\n Проверь /reports',
        'default': "Image uploads are limited due to user complaints!\nCheck /reports",
    },
    'reported_photo_list': {
        'ru': 'Изображения, на которые пожаловались другие пользователи.\n'
              'Их можно скрыть, чтобы снять ограничения.',
        'default': "Images that other users have complained about.\n"
                   "They can be hidden to remove restrictions.",
    },
    'img_blocked': {
        'ru': 'Изображение заблокировано и не будет появляться в поиске.',
        'default': "Image blocked and will not appear in search results.",
    },
    'img_in_queue': {
        'ru': 'Изображение добавлено в очередь загрузки.',
        'default': "The image has been added to the download queue.",
    },
    'img_too_small': {
        'ru': 'Изображение слишком низкого качества!',
        'default': "The image resolution is too low!",
    },
    'default_error': {
        'ru': 'Произошла неожиданная ошибка, попробуй позже.',
        'default': "There was an unexpected error, try again later.",
    }
}


def response_text(template, tg_id, str_args=None):
    response_lang_dict = response_templates_dict[template]
    lang = Profile.objects.get(tg_id=tg_id).language_code
    if lang not in response_lang_dict.keys():
        lang = 'default'
    if str_args:
        return response_lang_dict[lang].format(**str_args)
    else:
        return response_lang_dict[lang]


@bot.message_handler(commands=['start', 'help'])
@update_user
@timeit
def help_(message):
    bot.send_message(
        chat_id=message.chat.id,
        text=response_text(
            template='help',
            tg_id=message.from_user.id
        ),
    )


@bot.message_handler(func=lambda message: True, content_types=['photo'])
@update_user
@timeit
def save_photo(message: Message):
    tg_id = message.from_user.id

    with DB_LOCK:
        reported = Report.check_reported(tg_id, time.time() // 120)
    if reported:
        bot.reply_to(
            message=message,
            text=response_text(
                template='report_limit',
                tg_id=tg_id
            ),
        )
        return

    photo = message.photo[-1]

    if photo.height * photo.width < 350_000:
        bot.reply_to(
            message=message,
            text=response_text(
                template='img_too_small',
                tg_id=tg_id
            ),
        )
        return


    try:
        file_info = bot.get_file(photo.file_id)
        file_bytes = bot.download_file(file_info.file_path)
        pil_image = PILImage.open(io.BytesIO(file_bytes))
        phash = imagehash.phash(pil_image)
        try:
            with DB_LOCK:
                Image.new_image(
                    tg_id=tg_id,
                    file_id=photo.file_id,
                    file_unique_id=file_info.file_unique_id,
                    phash=phash,
                )
        except django.db.utils.IntegrityError:
            bot.reply_to(
                message=message,
                text=response_text(
                    template='already_in_db',
                    tg_id=tg_id
                ),
            )
            with suppress(django.db.utils.IntegrityError), DB_LOCK:
                ImageScore.new_score(
                    tg_id=tg_id,
                    file_unique_id=Image.objects.get(phash=phash).file_unique_id,
                    score=2,
                )
            return

        markup = quick_markup({
            'Delete': {'callback_data': 'delete|' + file_info.file_unique_id},
        })

        bot.reply_to(
            message=message,
            text=response_text(
                template='img_saved',
                tg_id=tg_id
            ),
            reply_markup=markup,
        )
    except Exception as e:
        logging.error(traceback.format_exc())
        bot.reply_to(
            message=message,
            text=response_text(
                template='default_error',
                tg_id=tg_id
            ),
        )


def send_photo_with_default_markup(chat_id, photo):
    image = Image.objects.get(pk=photo["image_id"])
    markup = quick_markup({
        "❗️": {'callback_data': f'report|{image.file_unique_id}'},
        "👎": {'callback_data': f'dislike|{image.file_unique_id}'},
        "❤️": {'callback_data': f'like|{image.file_unique_id}'},
        "❤️‍🔥": {'callback_data': f'superlike|{image.file_unique_id}'},
    }, row_width=4)
    if photo.get("taste_similarity") > 0:
        caption = f'{round(float(photo.get("taste_similarity")), 2)}'
    elif photo.get("taste_similarity") < 0:
        caption = "🔁"
    else:
        caption = '🔀'
    bot.send_photo(
        chat_id=chat_id,
        photo=image.file_id,
        reply_markup=markup,
        caption=caption
    )


@bot.message_handler(commands=['image'])
@update_user
@timeit
def send_photo(message):
    user_id = message.from_user.id
    global IMAGES_CACHE
    if IMAGES_CACHE.get(user_id):
        send_photo_with_default_markup(message.chat.id, IMAGES_CACHE[user_id].pop(0))
    elif file_unique_ids := COLAB_FILTER.predict(Profile.objects.get(tg_id=user_id).id):
        IMAGES_CACHE[user_id] = file_unique_ids
        send_photo_with_default_markup(message.chat.id, IMAGES_CACHE[user_id].pop(0))
    else:
        bot.send_message(
            chat_id=message.chat.id,
            text=response_text(
                template='img_not_found',
                tg_id=message.from_user.id
            ),
        )


@bot.callback_query_handler(func=lambda callback: callback.data.startswith('delete'))
@timeit
def delete_photo(callback: CallbackQuery):
    _, file_unique_id = callback.data.split('|')
    Image.delete_image(callback.from_user.id, file_unique_id)
    with suppress(ApiTelegramException):
        bot.answer_callback_query(
            callback_query_id=callback.id,
            text=response_text(
                template='img_deleted',
                tg_id=callback.from_user.id
            ),
        )
    bot.delete_message(callback.message.chat.id, callback.message.id)


@bot.callback_query_handler(func=lambda callback: callback.data.startswith('block'))
@timeit
def block_photo(callback: CallbackQuery):
    _, file_unique_id = callback.data.split('|')
    ImageBlock.block_image(callback.from_user.id, file_unique_id)
    with suppress(ApiTelegramException):
        bot.answer_callback_query(
            callback_query_id=callback.id,
            text=response_text(
                template='img_blocked',
                tg_id=callback.from_user.id
            ),
        )
    bot.delete_message(callback.message.chat.id, callback.message.id)


@bot.callback_query_handler(
    func=lambda callback:
        callback.data.startswith('superlike')
        or callback.data.startswith('like')
        or callback.data.startswith('dislike')
)
@timeit
def score_photo(callback: CallbackQuery):
    action, unique_id = callback.data.split('|')[:2]
    if action == 'dislike':
        score = -1
        tg_id = callback.from_user.id
        global IMAGES_CACHE
        IMAGES_CACHE[tg_id] = []
    elif action == 'superlike':
        score = 2
    else:
        score = 1
    with suppress(django.db.utils.IntegrityError):
        ImageScore.new_score(
            tg_id=callback.from_user.id,
            file_unique_id=unique_id,
            score=score,
        )
    callback.message.from_user = callback.from_user
    send_photo(callback.message)
    with suppress(ApiTelegramException):
        bot.answer_callback_query(callback_query_id=callback.id)
    if action == 'dislike':
        bot.delete_message(callback.message.chat.id, callback.message.id)
    else:
        bot.edit_message_caption(
            caption=None,
            chat_id=callback.message.chat.id,
            message_id=callback.message.id
        )


@bot.message_handler(commands=['stat'])
@update_user
@timeit
def my_stat(message: Message) -> None:
    uploaded_images, uploaded_images_position, scores_from, score_images_position, similar_profiles = Profile.user_stat(message.from_user.id)
    bot.send_message(
        chat_id=message.chat.id,
        text=response_text(
            template='stat',
            tg_id=message.from_user.id
        ).format(
            uploaded_images=uploaded_images,
            uploaded_images_position=uploaded_images_position + 1,
            scores_from=scores_from,
            score_images_position=score_images_position + 1,
            similar_profiles=similar_profiles,
        ),
    )


@bot.callback_query_handler(
    func=lambda callback: callback.data.startswith('confirm_report') or callback.data.startswith('reject_report')
)
def confirm_report(callback: CallbackQuery):
    action, unique_id = callback.data.split('|')
    with suppress(ApiTelegramException):
        bot.answer_callback_query(callback_query_id=callback.id)
    callback.message.from_user = callback.from_user
    if action == "reject_report":
        markup = quick_markup({
            "❗️": {'callback_data': f'report|{unique_id}'},
            "👎": {'callback_data': f'dislike|{unique_id}'},
            "❤️": {'callback_data': f'like|{unique_id}'},
            "❤️‍🔥": {'callback_data': f'superlike|{unique_id}'},
        }, row_width=4)
        bot.edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.id,
            caption=None,
            reply_markup=markup,
        )
        return

    score = -2
    try:
        ImageScore.new_score(
            tg_id=callback.from_user.id,
            file_unique_id=unique_id,
            score=score,
        )
    except django.db.utils.IntegrityError:
        pass

    try:
        Report.new_report(
            tg_id=callback.from_user.id,
            file_unique_id=unique_id,
        )
    except django.db.utils.IntegrityError:
        pass

    bot.delete_message(callback.message.chat.id, callback.message.id)
    bot.send_message(
        chat_id=callback.message.chat.id,
        text=response_text(
            template='report_photo_send',
            tg_id=callback.from_user.id
        ),
    )

    tg_id = callback.from_user.id
    global IMAGES_CACHE
    IMAGES_CACHE[tg_id] = []

    callback.message.from_user = callback.from_user
    send_photo(callback.message)


@bot.callback_query_handler(func=lambda callback: callback.data.startswith('report'))
@timeit
def report_photo(callback: CallbackQuery):
    with suppress(ApiTelegramException):
        bot.answer_callback_query(callback_query_id=callback.id)
    if Report.check_limit(callback.from_user.id):
        bot.send_message(
            chat_id=callback.message.chat.id,
            text=response_text(
                template='too_many_reports',
                tg_id=callback.from_user.id
            ),
        )
        return
    _, unique_id = callback.data.split('|')
    markup = quick_markup({
        "🔙": {'callback_data': f'reject_report|{unique_id}'},
        "❗️": {'callback_data': f'confirm_report|{unique_id}'},
    })
    bot.edit_message_caption(
        chat_id=callback.message.chat.id,
        message_id=callback.message.id,
        caption=response_text(
            template='report_photo',
            tg_id=callback.from_user.id
        ),
        reply_markup=markup,
    )


@bot.message_handler(commands=['reports'])
@update_user
@timeit
def my_reports(message: Message) -> None:
    bot.send_message(
        chat_id=message.chat.id,
        text=response_text(
            template='reported_photo_list',
            tg_id=message.from_user.id
        ),
    )
    for photo in Image.list_reported_photos(message.from_user.id):
        markup = quick_markup({
            '🚫': {'callback_data': 'block|' + photo["file_unique_id"]},
        })
        bot.send_photo(
            chat_id=message.chat.id,
            photo=Image.objects.get(file_unique_id=photo["file_unique_id"]).file_id,
            reply_markup=markup,
        )
