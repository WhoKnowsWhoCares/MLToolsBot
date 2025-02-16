from loguru import logger
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
from aiolimiter import AsyncLimiter
from mltoolsbot.config import Config
from mltoolsbot.api import (
    call_api_local_llm,
    # call_api_11labs,
    call_api_sd,
    call_api_claude,
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    logger.info("User %s started the conversation.", user.first_name)
    await update.message.reply_text(f"Hello there! \n {Config.HELP_TEXT}")


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("Help command activated")
    await update.message.reply_text(f"{Config.help_text}")


async def text2img(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    context.user_data["command"] = Config.TEXT2IMG
    await update.message.reply_text("Write image description")
    return Config.TEXT2IMG


async def text2text_local(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    context.user_data["command"] = Config.TEXT2TEXT_LOCAL
    await update.message.reply_text("Write your request")
    return Config.TEXT2TEXT_LOCAL


async def text2text_api(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    context.user_data["command"] = Config.TEXT2TEXT_API
    await update.message.reply_text("Write your request")
    return Config.TEXT2TEXT_API


async def text2speech(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    context.user_data["command"] = Config.TEXT2SPEECH_API
    await update.message.reply_text("Write your request")
    return Config.TEXT2SPEECH_API


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

    if command == Config.TEXT2TEXT_LOCAL:
        logger.info("Proceed text2text local")
        status_msg = await update.message.reply_text("Proceed request...")
        async with AsyncLimiter(2):
            await call_api_local_llm(update, context, user_id=user_id, text=text)
    elif command == Config.TEXT2TEXT_API:
        logger.info("Proceed text2text claude api")
        status_msg = await update.message.reply_text("Proceed request...")
        async with AsyncLimiter(2):
            await call_api_claude(update, context, user_id=user_id, text=text)
    elif command == Config.TEXT2IMG:
        logger.info("Proceed text2img")
        status_msg = await update.message.reply_text("Proceed request...")
        async with AsyncLimiter(2):
            await call_api_sd(update, context, user_id=user_id, text=text)
    # elif command == Config.TEXT2SPEECH_API:
    #     logger.info("Proceed text2speech")
    #     status_msg = await update.message.reply_text("Proceed request...")
    #     async with AsyncLimiter(2):
    #         await call_api_11labs(update, context, user_id=user_id, text=text)
    else:
        context.user_data["last_message"] = text
        context.user_data["user_id"] = user_id
        keyboard = [
            [
                InlineKeyboardButton(
                    "llama32", callback_data=str(Config.TEXT2TEXT_LOCAL)
                ),
                InlineKeyboardButton(
                    "claude35", callback_data=str(Config.TEXT2TEXT_API)
                ),
                InlineKeyboardButton(
                    "text2speech", callback_data=str(Config.TEXT2SPEECH_API)
                ),
                InlineKeyboardButton("text2image", callback_data=str(Config.TEXT2IMG)),
                InlineKeyboardButton(
                    "cancel", callback_data=str(ConversationHandler.END)
                ),
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

    if query.data == Config.TEXT2TEXT_LOCAL:
        await call_api_local_llm(update, context, user_id=user_id, text=text)
    elif query.data == Config.TEXT2TEXT_API:
        await call_api_claude(update, context, user_id=user_id, text=text)
    # elif query.data == Config.TEXT2SPEECH_API:
    #     await call_api_11labs(update, context, user_id=user_id, text=text)
    elif query.data == Config.TEXT2IMG:
        await call_api_sd(update, context, user_id=user_id, text=text)

    context.user_data["last_message"] = ""
    await context.bot.delete_message(
        chat_id=update.effective_chat.id, message_id=status_msg.message_id
    )


def create_application():
    application = Application.builder().token(Config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("llama", text2text_local))
    application.add_handler(CommandHandler("claude", text2text_api))
    application.add_handler(CommandHandler("audio", text2speech))
    application.add_handler(CommandHandler("image", text2img))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_message)
    )
    application.add_handler(CallbackQueryHandler(buttons))
    return application
