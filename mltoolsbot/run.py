import sys
from telegram import Update
from loguru import logger
from mltoolsbot.main_bot_v2 import create_application
from mltoolsbot.exceptions import BotError


def main():
    """Main entry point for the bot."""
    try:
        app = create_application()
        logger.info("Starting bot...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except BotError as e:
        logger.error(f"Bot error: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
