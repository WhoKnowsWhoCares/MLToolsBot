# import os
# import json
import io
import base64
import httpx
import asyncio

from anthropic import Anthropic
from yandex_cloud_ml_sdk import YCloudML

# from elevenlabs.client import ElevenLabs, VoiceSettings

from loguru import logger
from functools import partial, wraps
from telegram import Update
from telegram.ext import ContextTypes
from mltoolsbot.config import Config
from mltoolsbot.redis import RedisClient

redis_client = RedisClient()

claude_client = Anthropic(api_key=Config.ANTHROPIC_TOKEN)
claude_prompt = partial(
    claude_client.messages.create,
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    temperature=0,
)

ydx_client = YCloudML(folder_id=Config.YDX_FOLDER_ID, auth=Config.YDX_API_KEY)
ydx_gpt = ydx_client.models.completions("yandexgpt").configure(temperature=0.5)
ydx_art = ydx_client.models.image_generation("yandex-art").configure(
    width_ratio=2, height_ratio=1
)

# elevenlabs_client = ElevenLabs(api_key=Config.TTS_TOKEN)
# elevenlab_prompt = partial(
#     # elevenlabs_client.text_to_speech.convert,
#     elevenlabs_client.generate,
#     voice="Charlotte",  # Charlotte
#     model="eleven_turbo_v2_5",  # eleven_turbo_v2_5, eleven_multilingual_v2
#     output_format="mp3_44100_64",  #
#     stream=False,
#     voice_settings=VoiceSettings(
#         stability=0.7,
#         similarity_boost=0.5,
#         style=0.0,
#         use_speaker_boost=True,
#     ),
# )


def with_timeout(timeout):
    """Decorator to add timeout to async functions."""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Operation timed out after {timeout} seconds: {func.__name__}"
                )
                raise TimeoutError(f"Operation timed out: {func.__name__}")

        return wrapper

    return decorator


def check_auth(func):
    """Check if user authorized"""

    @wraps(func)
    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs
    ):
        user_id = context.user_data.get("user_id") or kwargs.get("user_id")
        value = redis_client.get_value(user_id)
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


# @check_auth
# async def call_api_11labs(
#     update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str
# ) -> None:
#     """
#     Makes a request to the Ollama API to generate a response based on a given
#     message using Gemma model.
#     """
#     try:
#         response = elevenlab_prompt(text=text)
#         audio_stream = BytesIO()
#         for chunk in response:
#             audio_stream.write(chunk)
#         audio_stream.seek(0)
#         logger.info("Response received")
#         await context.bot.send_audio(
#             chat_id=update.effective_chat.id,
#             audio=audio_stream,
#             filename="audio.mp3",
#             title="Your audio file...",
#         )
#     except Exception as e:
#         logger.error(e)
#         await context.bot.send_message(
#             chat_id=update.effective_chat.id, text="Sorry, something went wrong"
#         )


@check_auth
async def call_api_ydx_gpt(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str
) -> None:
    """
    Makes a request to the Yandex API to generate a response.
    """
    try:
        system = {
            "role": "system",
            "text": "Ты - персональный ассистент. Ответь на следующий вопрос максимально содержательно в пяти предложениях",
        }
        messages = redis_client.get_value(f"{user_id}-ydx-context") or [system]
        messages.append({"role": "user", "text": text})
        response = ydx_gpt.run(messages).alternatives[0].text
        messages.append({"role": "assistant", "text": response})
        redis_client.set_value(f"{user_id}-ydx-context", messages)
        logger.info("Response received")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
    except Exception as e:
        logger.error(e)
        await context.bot.send_message(
            chat_id=update.effective_chat.id, text="Sorry, something went wrong"
        )


@check_auth
async def call_api_claude(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    user_id: str,
    text: str,
    command: str,
) -> None:
    """
    Makes a request to the Claude API to generate a response based on a given message.
    """
    try:
        messages = []
        if command == Config.SUMMARIZE:
            system = "You should summarize next sentence:"
        elif command == Config.TRANSLATE:
            system = "Translate to english:"
        elif command == Config.CLAUDE_LLM:
            messages = redis_client.get_value(f"{user_id}-claude-context") or []
            system = "You are best personal assistant. Respond only with short answer no more than five sentences."
        messages.append({"role": "user", "content": text})
        response = claude_prompt(system=system, messages=messages).content[0].text
        if command == Config.CLAUDE_LLM:
            messages.append({"role": "assistant", "content": response})
            redis_client.set_value(f"{user_id}-claude-context", messages)
        logger.info("Response received")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=response)
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
    payload = Config.OLLAMA_PAYLOAD.copy()
    payload["prompt"] = text
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Request to {Config.LLM_SERVER_URL}")
            response = await client.post(
                url=f"{Config.LLM_SERVER_URL}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            logger.info("Response received")
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
    payload = Config.SD_PAYLOAD.copy()
    payload["prompt"] = text
    # user_info = redis_client.get_value(user_id)
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"Request for status {Config.SD_SERVER_URL}")
            response = await client.get(
                url=f"{Config.SD_SERVER_URL}/sdapi/v1/progress",
                # auth=(user_info["login"], user_info["pwd"]),
            )
            response.raise_for_status()
            logger.info(f"Request for image to {Config.SD_SERVER_URL}")
            response = await client.post(
                url=f"{Config.SD_SERVER_URL}/sdapi/v1/txt2img",
                # auth=(user_info["login"], user_info["pwd"]),
                json=payload,
            )
            response.raise_for_status()
            image = io.BytesIO(base64.b64decode(response.json()["images"][0]))
            logger.info("Image received")
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


@check_auth
async def call_api_ydx_art(
    update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str
) -> None:
    """
    Makes a request to the Yandex API to generate image.
    """
    try:
        logger.info("Request for yandex api")
        response = ydx_art.run_deferred(text).wait()
        image = io.BytesIO(response.image_bytes)
        logger.info("Image received")
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
