import django
import io
import logging
import time

import imagehash
from PIL import Image as PILImage
from telebot.types import Message, CallbackQuery
from telebot.util import quick_markup

from project.settings import bot

from tgbot.models import Image, ImageScore, Profile


TIMERS = {}


def update_user(func):
    def inner(message: Message):
        logging.debug(message)
        Profile.update_profile(message.from_user.id, message.from_user.full_name)
        return func(message)
    return inner


def timeit(func):
    def inner(*args, **kwargs):
        global TIMERS
        start = time.time()

        result = func(*args, **kwargs)

        timer = time.time() - start
        TIMERS[str(func)] = [timer] + TIMERS.get(str(func), [])[:1000]
        print(str(func), TIMERS[str(func)][0], sum(TIMERS[str(func)])/len(TIMERS[str(func)]))
        return result
    return inner


response_templates_dict = {
    'help': {
        'ru': "Хей, пришли мне арт, которым хочешь поделиться и я найду того, кому он понравится!",
        'default': "Hey, send me the art you want to share and I'll find someone who likes it!",
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
        'ru': 'Слишком много изображений!\nПодожди немного и попробуй снова',
        'default': 'Upload limit!\ntry later',
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
}


def response_text(template, lang='default', str_args=None):
    response_lang_dict = response_templates_dict[template]
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
            lang=message.from_user.language_code
        ),
    )


@bot.message_handler(func=lambda message: True, content_types=['photo'])
@update_user
@timeit
def save_photo(message: Message):
    profile_id = message.from_user.id
    if Image.check_limit(profile_id):
        bot.reply_to(
            message=message,
            text=response_text(
                template='upload_limit',
                lang=message.from_user.language_code
            ),
        )
        return

    file_info = bot.get_file(message.photo[1].file_id)
    file_bytes = bot.download_file(file_info.file_path)
    phash = imagehash.phash(PILImage.open(io.BytesIO(file_bytes)))

    photo = message.photo[-1]

    try:
        Image.new_image(
            profile_id=profile_id,
            file_id=photo.file_id,
            file_unique_id=photo.file_unique_id,
            phash=phash,
        )
    except django.db.utils.IntegrityError:
        bot.reply_to(
            message=message,
            text=response_text(
                template='already_in_db',
                lang=message.from_user.language_code
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
            lang=message.from_user.language_code
        ),
        reply_markup=markup,
    )


@bot.message_handler(commands=['image'])
@update_user
@timeit
def send_photo(message):
    user_id = message.from_user.id
    print('send_photo', message)
    if photo := Image.colab_filter_image(user_id) or Image.random_image(user_id):
        markup = quick_markup({
            "🚫": {'callback_data': f'dislike|{photo.file_unique_id}'},
            "❤️": {'callback_data': f'like|{photo.file_unique_id}'},
        })
        bot.send_photo(
            chat_id=message.chat.id,
            photo=photo.file_id,
            reply_markup=markup
        )
    else:
        bot.send_message(
            chat_id=message.chat.id,
            text=response_text(
                template='img_not_found',
                lang=message.from_user.language_code
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
            lang=callback.from_user.language_code
        ),
    )
    bot.delete_message(callback.message.chat.id, callback.message.id)


@bot.callback_query_handler(
    func=lambda callback: callback.data.startswith('like') or callback.data.startswith('dislike')
)
@timeit
def score_photo(callback: CallbackQuery):
    action, unique_id = callback.data.split('|')
    if action == 'dislike':
        score = -1
        bot.delete_message(callback.message.chat.id, callback.message.id)
    else:
        score = 1
        bot.edit_message_reply_markup(callback.message.chat.id, callback.message.id)
    try:
        print('callback.from_user.id', callback.from_user.id)
        ImageScore.new_score(
            profile_id=callback.from_user.id,
            file_unique_id=unique_id,
            score=score,
        )
    except django.db.utils.IntegrityError:
        pass
    callback.message.from_user = callback.from_user
    send_photo(callback.message)
    bot.answer_callback_query(callback_query_id=callback.id)


@bot.message_handler(commands=['stat'])
@update_user
@timeit
def my_stat(message: Message) -> None:
    uploaded_images, likes_from, likes_to = Profile.user_stat(message.from_user.id)
    bot.send_message(
        chat_id=message.chat.id,
        text=response_text(
            template='stat',
            lang=message.from_user.language_code
        ).format(
            uploaded_images=uploaded_images,
            likes_from=likes_from,
            likes_to=likes_to
        ),
    )
