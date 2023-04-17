import logging
import random
from decouple import config
from telegram import Update
from telegram.ext import filters, MessageHandler, ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

photos = []
unique_id = []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="I'm a bot, please talk to me!")


async def save_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global photos
    global unique_id
    photo = update.message.photo[-1]
    if photo.file_unique_id not in unique_id:
        unique_id.append(photo.file_unique_id)
        photos.append(photo.file_id)
        message = 'photo saved'
    else:
        message = 'photo already in database'
    await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
    # await context.bot.send_photo(chat_id=update.effective_chat.id, photo=random.choice(photos))


async def send_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=random.choice(photos))


if __name__ == '__main__':
    application = ApplicationBuilder().token(config("API_KEY")).build()

    start_handler = CommandHandler('start', start)
    photo_handler = CommandHandler('photo', send_photo)
    echo_photo_handler = MessageHandler(filters.PHOTO & (~filters.COMMAND), save_photo)

    application.add_handler(start_handler)
    application.add_handler(photo_handler)
    application.add_handler(echo_photo_handler)

    application.run_polling()