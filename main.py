import logging
import random
from io import BytesIO
import imagehash
from PIL import Image
from decouple import config
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes


load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

photos = []
unique_id = []
phash_list = []


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


if __name__ == '__main__':
    application = ApplicationBuilder().token(config("API_TOKEN")).build()

    start_handler = CommandHandler('start', start)
    photo_handler = CommandHandler('photo', send_photo)
    echo_photo_handler = MessageHandler(filters.PHOTO & (~filters.COMMAND), save_photo)

    application.add_handler(start_handler)
    application.add_handler(photo_handler)
    application.add_handler(echo_photo_handler)

    application.run_polling()