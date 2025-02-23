from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from aiolimiter import AsyncLimiter
from mltoolsbot.config import Config, ConfigError
from mltoolsbot.api import call_api_claude, call_api_ydx_art, call_api_ydx_gpt
from mltoolsbot.exceptions import error_handler
from loguru import logger
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning

filterwarnings(
    action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning
)

limiter = AsyncLimiter(2)

# TODO: Add exception handling


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Select an action: Start new task."""
    text = "You may choose what task I should help you with. To stop conversation use /stop command."
    logger.info("User start conversation.")
    buttons = [
        [
            InlineKeyboardButton(text="text2text", callback_data=str(Config.TEXT2TEXT)),
            InlineKeyboardButton(text="text2image", callback_data=str(Config.TEXT2IMG)),
            InlineKeyboardButton(text="cancel", callback_data=str(Config.END)),
        ],
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    if context.user_data.get(Config.START_OVER):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text=text, reply_markup=keyboard)
    context.user_data[Config.START_OVER] = False
    return Config.SELECTING_ACTION


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """End Conversation by command."""
    logger.info("User canceled the conversation by /stop command.")
    await update.message.reply_text("Okay, bye.")
    return Config.END


async def stop_second_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """End Conversation by command."""
    logger.info("User canceled the conversation by /stop command.")
    await update.message.reply_text("Okay, bye.")
    return Config.STOPPING


async def end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """End conversation from InlineKeyboardButton."""
    logger.info("User canceled the conversation.")
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(text="See you around! 😉")
    return Config.END


async def end_second_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to top level conversation."""
    logger.info("Back to the beginning.")
    context.user_data[Config.START_OVER] = True
    await start(update, context)
    return Config.END


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Help command"""
    logger.info("Help command activated")
    await update.message.reply_text(f"{Config.HELP_TEXT}")
    return


async def select_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Choose what task to run."""
    text = "Select what task should be done with prompt."
    logger.info("Select task to run for text2text")
    buttons = [
        [
            InlineKeyboardButton(text="summarize", callback_data=str(Config.SUMMARIZE)),
            InlineKeyboardButton(text="translate", callback_data=str(Config.TRANSLATE)),
            InlineKeyboardButton(text="cancel", callback_data=str(Config.END)),
        ],
        [
            InlineKeyboardButton(text="claude", callback_data=str(Config.CLAUDE_LLM)),
            InlineKeyboardButton(text="yandex", callback_data=str(Config.YDX_LLM)),
        ],
    ]
    keyboard = InlineKeyboardMarkup(buttons)
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(text=text, reply_markup=keyboard)
    return Config.SELECTING_PROMPT


async def ask_for_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Prompt user to input data for selected task."""
    text = "Type your description."
    context.user_data["command"] = update.callback_query.data
    logger.info(f"Waiting for input to proceed {update.callback_query.data}")
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(text=text)
    return Config.TYPING


async def proceed_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> str | int:
    """
    Handles text messages received by the bot.
    For text-to-text or text-to-image conversion, and calls the corresponding
    functions to process the message accordingly.
    """
    logger.info("Proceed text message")
    text = update.message.text
    user_id = str(update.message.from_user.id)
    command = context.user_data.get("command")
    context.user_data["command"] = ""
    if command not in Config.SUBCOMMANDS:
        status_msg = await update.message.reply_text("Sorry unknown request. 😔")
        return ConversationHandler.END

    status_msg = await update.message.reply_text("Proceed request... 👨‍💻")
    next = ConversationHandler.END
    if command in [Config.SUMMARIZE, Config.TRANSLATE, Config.CLAUDE_LLM]:
        logger.info("Proceed text2text claude api")
        await call_api_claude(
            update, context, user_id=user_id, text=text, command=command
        )
        if command == Config.CLAUDE_LLM:
            next = Config.TYPING
            context.user_data["command"] = Config.CLAUDE_LLM
    elif command == Config.YDX_LLM:
        logger.info("Proceed text2text yandex api")
        await call_api_ydx_gpt(update, context, user_id=user_id, text=text)
        next = Config.TYPING
        context.user_data["command"] = Config.YDX_LLM
    elif command == Config.TEXT2IMG:
        logger.info("Proceed text2img")
        await call_api_ydx_art(update, context, user_id=user_id, text=text)

    await context.bot.delete_message(
        chat_id=update.effective_chat.id, message_id=status_msg.message_id
    )
    return next


def create_application():
    """Create and configure the bot application."""
    try:
        logger.info("Start building application")
        Config.validate()
        application = Application.builder().token(Config.BOT_TOKEN).build()

        # Set up second level ConversationHandler (text2text)
        text2text_conv = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(select_prompt, pattern=f"^{Config.TEXT2TEXT}$")
            ],
            states={
                Config.SELECTING_PROMPT: [
                    CallbackQueryHandler(
                        ask_for_input,
                        pattern="^" + "$|^".join(Config.SUBCOMMANDS) + "$",
                    )
                ],
                Config.TYPING: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, proceed_command)
                ],
            },
            fallbacks=[
                CallbackQueryHandler(end_second_level, pattern=f"^{Config.END}$"),
                CommandHandler("stop", stop_second_level),
            ],
            map_to_parent={
                Config.STOPPING: Config.END,
                Config.END: Config.SELECTING_ACTION,
            },
        )
        # first-level conversation handler
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", start)],
            states={
                Config.SELECTING_ACTION: [
                    text2text_conv,
                    CallbackQueryHandler(ask_for_input, pattern=f"^{Config.TEXT2IMG}$"),
                    CallbackQueryHandler(end, pattern=f"^{Config.END}$"),
                ],
                Config.TYPING: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, proceed_command)
                ],
            },
            fallbacks=[CommandHandler("stop", stop)],
        )
        application.add_handler(conv_handler)
        application.add_handler(CommandHandler("help", help))
        application.add_error_handler(error_handler)
    except Exception as e:
        logger.error(f"Error creating application: {str(e)}")
        raise ConfigError(f"Failed to create bot application: {str(e)}")
    return application
