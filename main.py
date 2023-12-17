import os
import g4f
import asyncio

from loguru import logger
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from undetected_chromedriver import Chrome, ChromeOptions
from g4f.Provider import (
    Bard,
    Poe,
    AItianhuSpace,
    MyShell,
    PerplexityAi,
)

load_dotenv()

chat_id = os.getenv("chat_id")
bot_token = os.getenv("bot_token")
options = ChromeOptions()
options.add_argument("--incognito");
webdriver = Chrome(options=options, headless=True)
last_message = ''
run_text2text = False

help_text = '''
    Useful commands:
    /text2text - I will generate response according to your request
    /text2img - I will create image according to your description
'''

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Hello there! \n {help_text}")
    
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"{help_text}")
    
async def text2text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_message, run_text2text
    if last_message != '':
        await context.bot.send_message(chat_id=update.effective_chat.id, text='Proceed request...')
        response = await ask_api_g4f(last_message)
        last_message = ''
        run_text2text = False
    else:
        response = 'Could you write your request?'
        run_text2text = True
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

async def ask_api_g4f(message: str):
    try:
        response = await g4f.ChatCompletion.create_async(
            model="gpt-3.5-turbo",
            provider=g4f.Provider.ChatgptAi,
            messages=[{"role": "user", "content": message}],
            # webdriver=webdriver,
        )
        return response
    except Exception as e:
        logger.error(e)
    return 'Sorry, something went wrong'

async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_message, run_text2text
    last_message = update.message.text
    logger.info(f"Last message: {last_message}")
    if run_text2text:
        await text2text(update, context)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text='What to do?')

        
if __name__ == '__main__':
    application = ApplicationBuilder().token(bot_token).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help))
    application.add_handler(CommandHandler('text2text', text2text))
    application.add_handler(MessageHandler(filters.TEXT, text_message))
    
    application.run_polling()


# В ответ на текст: отправить прошлый пост как контекст, основной как запрос