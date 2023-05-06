import django
import io
import logging
import time

import imagehash
from PIL import Image as PILImage
from telebot.types import Message, CallbackQuery
from telebot.util import quick_markup

from project.settings import bot

from tgbot.models import Image, ImageScore, Profile, Report

TIMERS = {}
IMAGES_CACHE = {}
SCORE_RESULTS = {}


def timers_view():
    return {
        func_name: {
            "count": len(timer),
            "mean_time": sum(timer)/len(timer),
            "worst 10": [round(t, 3) for t in sorted(timer, reverse=True)[:10]],
        } for func_name, timer in TIMERS.items()
    }


def score_results_view():
    return {
        uid: {
            taste_similarity: {
                "count": len(results),
                "likes": len([r for r in results if r > 0]),
                "dislikes": len([r for r in results if r < 0]),
            }
            for taste_similarity, results in user_results.items()
        }
        for uid, user_results in SCORE_RESULTS.items()
    }


def update_user(func):
    def inner(message: Message):
        logging.debug(message)
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
        'ru': "Хей, пришли мне арт, которым хочешь поделиться и я найду того, кому он понравится!\n"
              "Либо иcпользуй команду /image",
        'default': "Hey, send me the art you want to share and I'll find someone who likes it!\n"
                   "Or use /image",
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
            'Загружено изображений: {uploaded_images}\n'
            'Лайки от тебя: {likes_from}\n'
            'Лайки для тебя: {likes_to}',
        'default':
            'Images uploaded: {uploaded_images}\n'
            'Likes from you: {likes_from}\n'
            'Likes to you: {likes_to}',
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
        'ru': 'Загрузка изображений ограничена из-за жалоб пользователей!',
        'default': "Image uploads are limited due to user complaints!",
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
    profile_id = message.from_user.id
    if Report.check_reported(profile_id):
        bot.reply_to(
            message=message,
            text=response_text(
                template='report_limit',
                tg_id=message.from_user.id
            ),
        )
        return

    if Image.check_limit(profile_id):
        bot.reply_to(
            message=message,
            text=response_text(
                template='upload_limit',
                tg_id=message.from_user.id
            ),
        )
        return

    file_info = bot.get_file(message.photo[1].file_id)
    file_bytes = bot.download_file(file_info.file_path)
    phash = imagehash.phash(PILImage.open(io.BytesIO(file_bytes)))

    photo = message.photo[-1]

    try:
        Image.new_image(
            tg_id=profile_id,
            file_id=photo.file_id,
            file_unique_id=photo.file_unique_id,
            phash=phash,
        )
    except django.db.utils.IntegrityError:
        bot.reply_to(
            message=message,
            text=response_text(
                template='already_in_db',
                tg_id=message.from_user.id
            ),
        )
        return
    markup = quick_markup({
        'Delete': {'callback_data': 'delete|'+photo.file_unique_id},
    })

    bot.reply_to(
        message=message,
        text=response_text(
            template='img_saved',
            tg_id=message.from_user.id
        ),
        reply_markup=markup,
    )


def send_photo_with_default_markup(chat_id, photo):
    markup = quick_markup({
        "❗️": {'callback_data': f'report|{photo["file_unique_id"]}'},
        "👎": {'callback_data': f'dislike|{photo["file_unique_id"]}|{photo["taste_similarity"]}'},
        "❤️": {'callback_data': f'like|{photo["file_unique_id"]}|{photo["taste_similarity"]}'},
    }, row_width=3)
    bot.send_photo(
        chat_id=chat_id,
        photo=Image.objects.get(file_unique_id=photo["file_unique_id"]).file_id,
        reply_markup=markup
    )


@bot.message_handler(commands=['image'])
@update_user
@timeit
def send_photo(message):
    user_id = message.from_user.id
    global IMAGES_CACHE
    if IMAGES_CACHE.get(user_id):
        send_photo_with_default_markup(message.chat.id, IMAGES_CACHE[user_id].pop())
    elif file_unique_ids := Image.colab_filter_images(user_id) or Image.random_images(user_id):
        IMAGES_CACHE[user_id] = file_unique_ids
        send_photo_with_default_markup(message.chat.id, IMAGES_CACHE[user_id].pop())
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
    bot.answer_callback_query(
        callback_query_id=callback.id,
        text=response_text(
            template='img_deleted',
            tg_id=callback.from_user.id
        ),
    )
    bot.delete_message(callback.message.chat.id, callback.message.id)


@bot.callback_query_handler(
    func=lambda callback: callback.data.startswith('like') or callback.data.startswith('dislike')
)
@timeit
def score_photo(callback: CallbackQuery):
    if len(callback.data.split('|')) == 3:
        action, unique_id, taste_similarity = callback.data.split('|')
    else:
        action, unique_id = callback.data.split('|')
        taste_similarity = 0
    if action == 'dislike':
        score = -1
        global IMAGES_CACHE
        IMAGES_CACHE[callback.from_user.id] = []
    else:
        score = 1
    global SCORE_RESULTS
    SCORE_RESULTS.setdefault(callback.from_user.id, {}).setdefault(taste_similarity, []).append(score)
    try:
        ImageScore.new_score(
            tg_id=callback.from_user.id,
            file_unique_id=unique_id,
            score=score,
        )
    except django.db.utils.IntegrityError:
        pass
    callback.message.from_user = callback.from_user
    send_photo(callback.message)
    bot.answer_callback_query(callback_query_id=callback.id)
    if action == 'dislike':
        bot.delete_message(callback.message.chat.id, callback.message.id)
    else:
        bot.edit_message_reply_markup(callback.message.chat.id, callback.message.id)


@bot.message_handler(commands=['stat'])
@update_user
@timeit
def my_stat(message: Message) -> None:
    uploaded_images, likes_from, likes_to = Profile.user_stat(message.from_user.id)
    bot.send_message(
        chat_id=message.chat.id,
        text=response_text(
            template='stat',
            tg_id=message.from_user.id
        ).format(
            uploaded_images=uploaded_images,
            likes_from=likes_from,
            likes_to=likes_to
        ),
    )


@bot.callback_query_handler(
    func=lambda callback: callback.data.startswith('confirm_report') or callback.data.startswith('reject_report')
)
def confirm_report(callback: CallbackQuery):
    action, unique_id = callback.data.split('|')
    bot.answer_callback_query(callback_query_id=callback.id)
    callback.message.from_user = callback.from_user
    if action == "reject_report":
        markup = quick_markup({
            "❗️": {'callback_data': f'report|{unique_id}'},
            "👎": {'callback_data': f'dislike|{unique_id}'},
            "❤️": {'callback_data': f'like|{unique_id}'},
        }, row_width=3)
        bot.edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.id,
            caption=None,
            reply_markup=markup,
        )
        return

    file_info = bot.get_file(Image.objects.get(file_unique_id=unique_id).file_id)
    file_bytes = bot.download_file(file_info.file_path)
    buffered = io.BytesIO()
    image = PILImage.open(io.BytesIO(file_bytes))
    image.thumbnail((300, 300))
    image.save(buffered, format="JPEG", quality=60)
    file_bytes = buffered.getvalue()

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
            image_file=file_bytes,
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

    callback.message.from_user = callback.from_user
    send_photo(callback.message)


@bot.callback_query_handler(func=lambda callback: callback.data.startswith('report'))
@timeit
def report_photo(callback: CallbackQuery):
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
        "❌": {'callback_data': f'confirm_report|{unique_id}'},
    })
    bot.answer_callback_query(callback_query_id=callback.id)
    bot.edit_message_caption(
        chat_id=callback.message.chat.id,
        message_id=callback.message.id,
        caption=response_text(
            template='report_photo',
            tg_id=callback.from_user.id
        ),
        reply_markup=markup,
    )
