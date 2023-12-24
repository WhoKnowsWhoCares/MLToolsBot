import os
import g4f
import io
import base64
import httpx

from loguru import logger
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
from aiolimiter import AsyncLimiter

load_dotenv()

CHAT_ID = os.getenv("CHAT_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SD_SERVER_URL = os.getenv("SD_SERVER_URL")
last_message = ""
run_text2text = False
run_text2img = False
limiter = AsyncLimiter(2)

payload = {"prompt": "", "steps": 20, "script_name": "", "sampler_name": ""}

help_text = """
    Useful commands:
    /text2text - I will generate response according to your request
    /text2img - I will create image according to your description
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=f"Hello there! \n {help_text}"
    )


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id, text=f"{help_text}"
    )


async def text2text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    This function takes an update and context as inputs and sends a response
    message to the user based on their request.
    The function uses the call_api_g4f function to generate a response using
    the G4F API.

    Args:
        update (Update): The update object containing information about
        the incoming message.
        context (ContextTypes.DEFAULT_TYPE): The context object containing
        information about the bot and its environment.
    Returns: None
    """
    global last_message, run_text2text
    if last_message != "":
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Proceed request..."
        )
        async with limiter:
            response = await call_api_g4f(last_message)
        last_message = ""
        run_text2text = False
    else:
        response = "Please write your request"
        run_text2text = True
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response)


async def call_api_g4f(message: str) -> str:
    """
    Makes a request to the G4F API to generate a response based on a given
    message using ChatGPT.

    Args:
        message (str): The message for which a response is to be generated.
    Returns: (str) The generated response from the G4F API.
    """
    try:
        response = await g4f.ChatCompletion.create_async(
            model="gpt-3.5-turbo",
            provider=g4f.Provider.ChatgptAi,
            messages=[{"role": "user", "content": message}],
        )
    except Exception as e:
        logger.error(e)
        return "Sorry, something went wrong"
    return response


async def text2img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Generates an image based on a given description.

    Args:
        update (Update): The update object containing information about
        the incoming message.
        context (ContextTypes.DEFAULT_TYPE): The context object containing
        information about the bot and its environment.

    Returns:
        If the image generation API is unavailable or encounters an error,
        a string message indicating the unavailability is returned.
        If the image generation is successful, the generated image is returned
        as a byte stream.
    """
    global last_message, run_text2img
    if update.effective_chat.id != int(CHAT_ID):
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Sorry, not public just yet"
        )
        return
    if last_message != "":
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Proceed request..."
        )
        async with limiter:
            response = await call_api_sd(last_message)
        if isinstance(response, str):
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=response
            )
        else:
            await context.bot.send_photo(
                chat_id=update.effective_chat.id, photo=response
            )
        last_message = ""
        run_text2img = False
    else:
        response = "Please write image description"
        run_text2img = True
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)


async def call_api_sd(description: str):
    """
    Makes a POST request to an image generation API with a given description
    as the payload.
    Processes the response to obtain the generated image.

    Args:
        description (str): The description used as the prompt for generating
        the image.

    Returns:
        If the image generation API is unavailable or encounters an error,
        a string message indicating the unavailability is returned.
        If the image generation is successful, the generated image is returned
        as a byte stream.
    """
    payload["prompt"] = description
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Request for image to {SD_SERVER_URL}")
            response = await client.post(
                url=f"{SD_SERVER_URL}/sdapi/v1/txt2img", json=payload
            )
            image = io.BytesIO(base64.b64decode(response.json()["images"][0]))
    except Exception as e:
        logger.error(e)
        return "Sorry, image service unavailable"
    return image


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles text messages received by the bot.

    Args:
        update (Update): The update object containing information about
        the incoming message.
        context (ContextTypes.DEFAULT_TYPE): The context object containing
        information about the bot and its environment.
    Returns: None

    Summary:
    The `text_message` function is responsible for handling text messages
    received by the bot.
    It stores the last message received, checks if there is a pending request
    for text-to-text or
    text-to-image conversion, and calls the corresponding functions to process
    the message accordingly.

    Code Analysis:
    - The function stores the text message received in the `last_message` variable.
    - It checks if there is a pending request for text-to-text conversion
    (`run_text2text` is True).
    - If there is a pending request, it calls the `text2text` function to generate
    a response based on the message.
    - If there is a pending request for text-to-image conversion (`run_text2img` is True),
    it calls the `text2img` function to generate an image based on the message.
    - If there are no pending requests, it sends a message asking the user to send a command.
    """
    global last_message, run_text2text
    last_message = update.message.text
    logger.info(f"Last message: {last_message}")
    if run_text2text:
        await text2text(update, context)
    elif run_text2img:
        await text2img(update, context)
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Send command what to do with this"
        )


if __name__ == "__main__":
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("text2text", text2text))
    application.add_handler(CommandHandler("text2img", text2img))
    application.add_handler(MessageHandler(filters.TEXT, text_message))

    application.run_polling()

# TODO: В ответ на текст: отправить прошлый пост как контекст, основной как запрос
