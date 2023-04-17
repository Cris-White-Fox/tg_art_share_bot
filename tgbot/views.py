import random
from io import BytesIO
import imagehash
from PIL import Image
from telegram import Update
from telegram.ext import ContextTypes, filters, MessageHandler, CommandHandler

from project.settings import tg_application


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")


async def save_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global unique_id
    photo = update.message.photo[-1]
    if photo.file_unique_id in unique_id:
        await context.bot.send_message(chat_id=update.effective_chat.id, text='photo already in database')
        return

    file = await photo.get_file()
    file_bytes = BytesIO()
    await file.download_to_memory(file_bytes)
    phash = imagehash.phash(Image.open(file_bytes))
    global phash_list
    if phash in phash_list:
        await context.bot.send_message(chat_id=update.effective_chat.id, text='photo already in database')
        return

    global photos
    unique_id.append(photo.file_unique_id)
    phash_list.append(phash)
    photos.append(photo.file_id)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f'photo saved {phash}')


async def send_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=random.choice(photos))

handlers = [
    CommandHandler('start', start),
    CommandHandler('photo', send_photo),
    MessageHandler(filters.PHOTO & (~filters.COMMAND), save_photo),
]

for handler in handlers:
    tg_application.add_handler(handler)
