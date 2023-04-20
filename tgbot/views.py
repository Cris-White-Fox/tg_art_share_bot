from io import BytesIO
import imagehash
from PIL import Image as PILImage
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, filters, MessageHandler, CommandHandler, CallbackQueryHandler

from project.settings import tg_application
from tgbot.models import Image, ImageScore, Profile


def update_user(func):
    async def inner(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await Profile.update_profile(update.effective_user.id, update.effective_user.full_name)
        return await func(update, context)
    return inner


@update_user
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please send me arts!")


@update_user
async def save_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await Image.check_daily_limit(update.effective_user.id):
        await context.bot.send_message(chat_id=update.effective_chat.id, text='Upload limit!\ntry later')
        return

    photo = update.message.photo[-1]
    if await Image.check_unique_id(photo.file_unique_id):
        await context.bot.send_message(chat_id=update.effective_chat.id, text='Image already in database')
        return

    file = await photo.get_file()
    file_bytes = BytesIO()
    await file.download_to_memory(file_bytes)
    phash = imagehash.phash(PILImage.open(file_bytes))

    if await Image.check_hash(phash):
        await context.bot.send_message(chat_id=update.effective_chat.id, text='Image already in database')
        return

    await Image.new_image(
        profile_id=update.effective_user.id,
        file_id=photo.file_id,
        file_unique_id=photo.file_unique_id,
        phash=phash,
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f'Image saved!')


@update_user
async def send_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if photo := await Image.advanced_random_image(update.effective_user.id):
        keyboard = [
            [
                InlineKeyboardButton("🚫", callback_data=f'del|{photo.file_unique_id}'),
                InlineKeyboardButton("❤️", callback_data=f'like|{photo.file_unique_id}'),
            ]
        ]

        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=photo.file_id,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f'Images not found!\nTry later')


@update_user
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    await query.answer()
    action, unique_id = query.data.split('|')
    if action == 'del':
        score = -1
        await query.delete_message()
    else:
        score = 1
        await query.edit_message_reply_markup()
    await ImageScore.new_score(
        profile_id=update.effective_user.id,
        file_unique_id=unique_id,
        score=score
    )
    await send_photo(update, context)


handlers = [
    CommandHandler('start', start, block=False),
    CommandHandler('image', send_photo, block=False),
    MessageHandler(filters.PHOTO & (~filters.COMMAND), save_photo),
    CallbackQueryHandler(button, block=False)
]
tg_application.add_handlers(handlers)
