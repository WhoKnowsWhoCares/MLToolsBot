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
run_login = False
limiter = AsyncLimiter(2)
known_users = {}

payload = {
    "prompt": "",
    "steps": 20,
    "script_name": "",
    "sampler_name": "",
    "override_settings": {
        "sd_model_checkpoint": "deliberate_v3.safetensors [aadddd3d75]"
    },
}

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
    # last_message = update.message.text
    logger.info(f"Last message: {last_message}")
    if last_message != "":
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Proceed request..."
        )
        async with limiter:
            response = await call_api_g4f(last_message)
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=response
            )
        last_message = ""
        run_text2text = False
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Please write your request"
        )
        run_text2text = True


# TODO: change service to ChatGPT
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
        logger.info(f"G4F response: {response}")
        return response if response != "" else "Service now unavailable"
    except Exception as e:
        logger.error(e)
        return "Sorry, something went wrong"


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
    global last_message, run_text2img, run_login
    # last_message = update.message.text
    logger.info(f"Last message: {last_message}")
    chat_id = update.effective_chat.id
    if chat_id not in known_users:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="To use this service you should be logged in. Please write login:password to proceed",
        )
        run_login = True
        return

    if last_message != "":
        await context.bot.send_message(chat_id=chat_id, text="Proceed request...")
        async with limiter:
            response = await call_api_sd(chat_id, last_message)
        if isinstance(response, str):
            await context.bot.send_message(chat_id=chat_id, text=response)
        else:
            await context.bot.send_photo(chat_id=chat_id, photo=response)
        last_message = ""
        run_text2img = False
    else:
        await context.bot.send_message(
            chat_id=chat_id, text="Please write image description"
        )
        run_text2img = True


async def call_api_sd(chat_id: int, description: str):
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
            logger.info(f"Request for status {SD_SERVER_URL}")
            response = await client.get(
                url=f"{SD_SERVER_URL}/sdapi/v1/progress",
                auth=(known_users[chat_id]["login"], known_users[chat_id]["pwd"]),
            )
            response.raise_for_status()
            logger.info(f"Request for image to {SD_SERVER_URL}")
            response = await client.post(
                url=f"{SD_SERVER_URL}/sdapi/v1/txt2img",
                auth=(known_users[chat_id]["login"], known_users[chat_id]["pwd"]),
                json=payload,
            )
            response.raise_for_status()
            image = io.BytesIO(base64.b64decode(response.json()["images"][0]))
            return image
    except httpx.TimeoutException as e:
        logger.error(f"HTTP TimeoutException for {e.request.url} - {e}")
        return "Sorry, image service unavailable"
    except httpx.HTTPError as e:
        logger.error(f"HTTP Exception for {e.request.url} - {e}")
        return "Sorry, something went wrong"
    except Exception as e:
        logger.error(e)
        return "Sorry, something went wrong"


async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles the login process for the bot.
    It takes the user's login and password as input, sends a request
    to the image generation API to verify the credentials, and stores the user's login and password
    in the `known_users` dictionary if the login is successful. It then calls the `text2img` function
    to proceed with the text-to-image conversion.

    Args:
        update (Update): The update object containing information about the incoming message.
        context (ContextTypes.DEFAULT_TYPE): The context object containing information
        about the bot and its environment.
    """
    global run_login, run_text2img
    text = update.message.text
    ind = text.find(":")
    login = text[:ind].strip().split()[-1]
    pwd = text[ind + 1 :].strip().split()[0]
    logger.info("Trying to login")
    chat_id = update.effective_chat.id
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url=f"{SD_SERVER_URL}/sdapi/v1/progress", auth=(login, pwd)
            )
            response.raise_for_status()
        known_users[chat_id] = {"login": login, "pwd": pwd}
        await context.bot.send_message(chat_id=chat_id, text="Success.")
        await text2img(update, context)
    except httpx.TimeoutException as e:
        logger.error(f"HTTP TimeoutException for {e.request.url} - {e}")
        await context.bot.send_message(
            chat_id=chat_id, text="Sorry, image service unavailable"
        )
    except httpx.HTTPError as e:
        logger.error(f"HTTP Exception for {e.request.url} - {e}")
        await context.bot.send_message(
            chat_id=chat_id, text="Incorrect login or password"
        )
    except ValueError as e:
        logger.error(f"Value Error: {e}")
    run_login = False
    return


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles text messages received by the bot.
    It stores the last message received, checks if there is a pending request
        for text-to-text or text-to-image conversion, and calls the corresponding
        functions to process the message accordingly.

    Args:
        update (Update): The update object containing information about
        the incoming message.
        context (ContextTypes.DEFAULT_TYPE): The context object containing
        information about the bot and its environment.
    """
    global last_message, run_text2text
    if run_login:
        await login(update, context)
    elif run_text2text:
        last_message = update.message.text
        await text2text(update, context)
    elif run_text2img:
        last_message = update.message.text
        await text2img(update, context)
    else:
        last_message = update.message.text
        logger.info(f"Last message: {last_message}")
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
