from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError
from loguru import logger


ERROR_MESSAGE = "Sorry, an error occurred: {}"
TIMEOUT_MESSAGE = "Operation timed out. Please try again."


class BotError(Exception):
    """Base exception class for bot errors."""

    pass


class ConfigError(BotError):
    """Raised when there's a configuration error."""

    pass


class HandlerError(BotError):
    """Raised when there's an error in command handlers."""

    pass


class TimeoutError(BotError):
    """Raised when an operation times out."""

    pass


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in the bot."""
    try:
        raise context.error
    except TimeoutError as e:
        logger.error(f"Timeout error: {str(e)}")
        if update.effective_message:
            await update.effective_message.reply_text(TIMEOUT_MESSAGE)
    except TelegramError as e:
        logger.error(f"Telegram error: {str(e)}")
        if update.effective_message:
            await update.effective_message.reply_text(ERROR_MESSAGE.format(str(e)))
    except BotError as e:
        logger.error(f"Bot error: {str(e)}")
        if update.effective_message:
            await update.effective_message.reply_text(ERROR_MESSAGE.format(str(e)))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        if update.effective_message:
            await update.effective_message.reply_text(
                ERROR_MESSAGE.format("An unexpected error occurred")
            )
