import os
import io
import base64
import httpx
import json

from anthropic import Anthropic
from elevenlabs.client import ElevenLabs, VoiceSettings
from loguru import logger

# from redis import Redis
from functools import partial
from dotenv import load_dotenv
from io import BytesIO
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
)
from functools import wraps
from aiolimiter import AsyncLimiter

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ANTHROPIC_TOKEN = os.getenv("ANTHROPIC_TOKEN")
TTS_TOKEN = os.getenv("ELEVENLABS_TOKEN")
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
SD_SERVER_URL = os.getenv("SD_SERVER_URL")
LLM_SERVER_URL = os.getenv("LLM_SERVER_URL")

TEXT2TEXT_LOCAL = "text2text_local"
TEXT2TEXT_API = "text2text_api"
TEXT2SPEECH_API = "text2speech"
TEXT2IMG = "text2img"
COMMANDS = [TEXT2TEXT_LOCAL, TEXT2TEXT_API, TEXT2SPEECH_API, TEXT2IMG]
END = ConversationHandler.END

limiter = AsyncLimiter(2)
redis_client = json.loads(os.getenv("REDIS_DEFAULTS")) or {}
# redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT)
claude_client = Anthropic(api_key=ANTHROPIC_TOKEN)
claude_prompt = partial(
    claude_client.messages.create,
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    temperature=0,
    system="You are best personal assistant. Respond only with short answer no more than five sentences.",
)
elevenlabs_client = ElevenLabs(api_key=TTS_TOKEN)
elevenlab_prompt = partial(
    # elevenlabs_client.text_to_speech.convert,
    elevenlabs_client.generate,
    voice="Charlotte",  # Charlotte
    model="eleven_turbo_v2_5",  # eleven_turbo_v2_5, eleven_multilingual_v2
    output_format="mp3_44100_64",  #
    stream=False,
    voice_settings=VoiceSettings(
        stability=0.7,
        similarity_boost=0.5,
        style=0.0,
        use_speaker_boost=True,
    ),
)

sd_payload = {
    "prompt": "",
    "negative_prompt": "(deformed, destorted, disfigured: 1.3),stacked torsos,\
        totem pole,poorly drawn,bad anatomy,extra limb,missing limb,floating limbs,\
        (mutated hands and fingers: 1.4),disconnected limbs,mutation,mutated,ugly,\
        disgusting,blur,blurry,amputation,out of focus,childish,surreal,text,\
        by <bad-artist:0.8>,by <bad-artist-anime:0.8>,<bad_prompt_version2:0.8>,<bad-hands-5:0.8>",
    "steps": 20,
    "sampler_index": "DPM++ 2M Karras",  # k_dpmpp_sde_ka
    "script_name": "",
    "sampler_name": "",
    "override_settings": {
        "sd_model_checkpoint": "deliberate_v3.safetensors [aadddd3d75]"
    },
}

ollama_payload = {
    "model": "llama3.2",
    "keep_alive": "10m",
    "stream": False,
}

claude_payload = {
    "model": "claude-3-5-sonnet-20241022",
    "max_tokens": "1024",
    "temperature": "0",
    "system": "You are best personal assistant. Respond only with short answer no more than five sentences.",
    "messages": [
        {"role": "user", "content": "Hello, how are you?"},
    ],
}

help_text = """
    Useful commands:
    /text2text - I will generate response according to your request. Currently available only for English. LLM Model: Gemma 7B
    /text2img - I will create image according to your description. SD Model: Deliberate v3
"""


def check_auth(func):
    """Check if user authorized"""

    @wraps(func)
    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):
        user_id = context.user_data.get("user_id") or kwargs.get("user_id")
        value = redis_client.get(user_id)
        # user_data = json.loads(value) if value else None
        if not value:
            logger.info(f"User {user_id} not authorized")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="To use this service you should be logged in",
            )
            return

        logger.info(f"User {user_id} authorized")
        await func(update, context, *args, **kwargs)

    return wrapper


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    logger.info("User %s started the conversation.", user.first_name)
    await update.message.reply_text(f"Hello there! \n {help_text}")


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Help command activated")
    await update.message.reply_text(f"{help_text}")


async def text2img(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    context.user_data["command"] = TEXT2IMG
    await update.message.reply_text("Write image description")
    return TEXT2IMG


async def text2text_local(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    context.user_data["command"] = TEXT2TEXT_LOCAL
    await update.message.reply_text("Write your request")
    return TEXT2TEXT_LOCAL


async def text2text_api(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    context.user_data["command"] = TEXT2TEXT_API
    await update.message.reply_text("Write your request")
    return TEXT2TEXT_API


async def text2speech(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    context.user_data["command"] = TEXT2SPEECH_API
    await update.message.reply_text("Write your request")
    return TEXT2SPEECH_API


@check_auth
async def call_api_11labs(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str
) -> None:
    """
    Makes a request to the Ollama API to generate a response based on a given
    message using Gemma model.
    """
    try:
        response = elevenlab_prompt(text=text)
        audio_stream = BytesIO()
        for chunk in response:
            audio_stream.write(chunk)
        audio_stream.seek(0)
        logger.info("Response recieved")
        await context.bot.send_audio(
            chat_id=update.effective_chat.id,
            audio=audio_stream,
            filename="audio.mp3",
            title="Your audio file...",
        )
    except Exception as e:
        logger.error(e)
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Sorry, something went wrong"
        )


@check_auth
async def call_api_claude(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str
) -> None:
    """
    Makes a request to the Ollama API to generate a response based on a given
    message using Gemma model.
    """
    try:
        response = claude_prompt(
            messages=[
                {
                    "role": "user",
                    "content": [{"type": "text", "text": text}],
                }
            ],
        )
        logger.info("Response recieved")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text=response.content[0].text
        )
    except Exception as e:
        logger.error(e)
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Sorry, something went wrong"
        )


@check_auth
async def call_api_local_llm(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str
) -> None:
    """
    Makes a request to the Ollama API to generate a response based on a given
    message using Gemma model.
    """
    payload = ollama_payload.copy()
    payload["prompt"] = text
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Request to {LLM_SERVER_URL}")
            response = await client.post(
                url=f"{LLM_SERVER_URL}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            logger.info("Response recieved")
            await context.bot.send_message(
                chat_id=update.effective_chat.id, text=response.json()["response"]
            )
    except httpx.TimeoutException as e:
        logger.error(f"HTTP TimeoutException for {e.request.url} - {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Sorry, timeout error"
        )
    except httpx.HTTPError as e:
        logger.error(f"HTTP Exception for {e.request.url} - {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Sorry, something went wrong"
        )
    except Exception as e:
        logger.error(e)
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Sorry, something went wrong"
        )


@check_auth
async def call_api_sd(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str
) -> None:
    """
    Makes a POST request to an image generation API with a given description
    as the payload.
    Processes the response to obtain the generated image.
    """
    payload = sd_payload.copy()
    payload["prompt"] = text
    # user_info = redis_client.get(user_id)
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Request for status {SD_SERVER_URL}")
            response = await client.get(
                url=f"{SD_SERVER_URL}/sdapi/v1/progress",
                # auth=(user_info["login"], user_info["pwd"]),
            )
            response.raise_for_status()
            logger.info(f"Request for image to {SD_SERVER_URL}")
            response = await client.post(
                url=f"{SD_SERVER_URL}/sdapi/v1/txt2img",
                # auth=(user_info["login"], user_info["pwd"]),
                json=payload,
            )
            response.raise_for_status()
            image = io.BytesIO(base64.b64decode(response.json()["images"][0]))
            logger.info("Image recieved")
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=image)
    except httpx.TimeoutException as e:
        logger.error(f"HTTP TimeoutException for {e.request.url} - {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Sorry, image service unavailable"
        )
    except httpx.HTTPError as e:
        logger.error(f"HTTP Exception for {e.request.url} - {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Sorry, something went wrong"
        )
    except Exception as e:
        logger.error(e)
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Sorry, something went wrong"
        )


# async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """
#     Handles the login process for the bot.
#     It takes the user's login and password as input, sends a request
#     to the image generation API to verify the credentials, and stores the user's login and password
#     in the `known_users` dictionary if the login is successful. It then calls the `text2img` function
#     to proceed with the text-to-image conversion.

#     Args:
#         update (Update): The update object containing information about the incoming message.
#         context (ContextTypes.DEFAULT_TYPE): The context object containing information
#         about the bot and its environment.
#     """
#     global run_login, run_text2img
#     text = update.message.text
#     ind = text.find(":")
#     login = text[:ind].strip().split()[-1]
#     pwd = text[ind + 1 :].strip().split()[0]
#     logger.info("Trying to login")
#     chat_id = update.effective_chat.id
#     try:
#         async with httpx.AsyncClient() as client:
#             response = await client.get(
#                 url=f"{SD_SERVER_URL}/sdapi/v1/progress", auth=(login, pwd)
#             )
#             response.raise_for_status()
#         known_users[chat_id] = {"login": login, "pwd": pwd}
#         await context.bot.send_message(chat_id=chat_id, text="Success.")
#         # await text2img(update, context)
#     except httpx.TimeoutException as e:
#         logger.error(f"HTTP TimeoutException for {e.request.url} - {e}")
#         await context.bot.send_message(
#             chat_id=chat_id, text="Sorry, image service unavailable"
#         )
#     except httpx.HTTPError as e:
#         logger.error(f"HTTP Exception for {e.request.url} - {e}")
#         await context.bot.send_message(
#             chat_id=chat_id, text="Incorrect login or password"
#         )
#     except ValueError as e:
#         logger.error(f"Value Error: {e}")
#     run_login = False
#     return


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handles text messages received by the bot.
    It stores the last message received, checks if there is a pending request
        for text-to-text or text-to-image conversion, and calls the corresponding
        functions to process the message accordingly.
    """
    logger.info("Proceed text message")
    text = update.message.text
    user_id = str(update.message.from_user.id)
    command = context.user_data.get("command")
    logger.info(f"Check command: {command}")

    if command == TEXT2TEXT_LOCAL:
        logger.info("Proceed text2text local")
        status_msg = await update.message.reply_text("Proceed request...")
        async with limiter:
            await call_api_local_llm(update, context, user_id=user_id, text=text)
    elif command == TEXT2TEXT_API:
        logger.info("Proceed text2text claude api")
        status_msg = await update.message.reply_text("Proceed request...")
        async with limiter:
            await call_api_claude(update, context, user_id=user_id, text=text)
    elif command == TEXT2IMG:
        logger.info("Proceed text2img")
        status_msg = await update.message.reply_text("Proceed request...")
        async with limiter:
            await call_api_sd(update, context, user_id=user_id, text=text)
    elif command == TEXT2SPEECH_API:
        logger.info("Proceed text2speech")
        status_msg = await update.message.reply_text("Proceed request...")
        async with limiter:
            await call_api_11labs(update, context, user_id=user_id, text=text)
    else:
        context.user_data["last_message"] = text
        context.user_data["user_id"] = user_id
        keyboard = [
            [
                InlineKeyboardButton("llama32", callback_data=str(TEXT2TEXT_LOCAL)),
                InlineKeyboardButton("claude35", callback_data=str(TEXT2TEXT_API)),
                InlineKeyboardButton("text2speech", callback_data=str(TEXT2SPEECH_API)),
                InlineKeyboardButton("text2image", callback_data=str(TEXT2IMG)),
                InlineKeyboardButton("cancel", callback_data=str(END)),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "What should I do with it?", reply_markup=reply_markup
        )
        return

    context.user_data["command"] = ""
    context.user_data["last_message"] = ""
    await context.bot.delete_message(
        chat_id=update.effective_chat.id, message_id=status_msg.message_id
    )


async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    await query.answer()
    text = context.user_data.get("last_message")
    user_id = context.user_data.get("user_id")
    status_msg = await query.edit_message_text("Start working on it")
    logger.info(f"Button pressed: {query.data}")

    if query.data == TEXT2TEXT_LOCAL:
        await call_api_local_llm(update, context, user_id=user_id, text=text)
    elif query.data == TEXT2TEXT_API:
        await call_api_claude(update, context, user_id=user_id, text=text)
    elif query.data == TEXT2SPEECH_API:
        await call_api_11labs(update, context, user_id=user_id, text=text)
    elif query.data == TEXT2IMG:
        await call_api_sd(update, context, user_id=user_id, text=text)

    context.user_data["last_message"] = ""
    await context.bot.delete_message(
        chat_id=update.effective_chat.id, message_id=status_msg.message_id
    )


if __name__ == "__main__":
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("llama32", text2text_local))
    application.add_handler(CommandHandler("claude35", text2text_api))
    application.add_handler(CommandHandler("text2speech", text2speech))
    application.add_handler(CommandHandler("text2img", text2img))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_message)
    )
    application.add_handler(CallbackQueryHandler(buttons))

    logger.info("Bot started")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
