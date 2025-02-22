import os
from dotenv import load_dotenv
from telegram.ext import ConversationHandler
from mltoolsbot.exceptions import ConfigError
from loguru import logger

load_dotenv()


class Config:
    logger.info("Init config")
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ANTHROPIC_TOKEN = os.getenv("ANTHROPIC_TOKEN")
    TTS_TOKEN = os.getenv("ELEVENLABS_TOKEN")
    YDX_FOLDER_ID = os.getenv("YDX_FOLDER_ID")
    YDX_API_KEY = os.getenv("YDX_API_KEY")
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = os.getenv("REDIS_PORT", 6379)
    SD_SERVER_URL = os.getenv("SD_SERVER_URL")
    LLM_SERVER_URL = os.getenv("LLM_SERVER_URL")

    TEXT2TEXT_LOCAL = "text2text_local"
    TEXT2TEXT_API = "text2text_api"
    TEXT2SPEECH_API = "text2speech"
    TEXT2IMG = "text2img"
    COMMANDS = [TEXT2TEXT_LOCAL, TEXT2TEXT_API, TEXT2SPEECH_API, TEXT2IMG]

    # State definitions for top level conversation
    SELECTING_ACTION, TEXT2TEXT, TEXT2IMG = map(chr, range(3))
    # State definitions for text2text level conversation
    SELECTING_PROMPT, SUMMARIZE, TRANSLATE, CLAUDE_LLM, YDX_LLM = map(chr, range(3, 8))
    SUBCOMMANDS = [TEXT2TEXT, SUMMARIZE, TRANSLATE, CLAUDE_LLM, YDX_LLM, TEXT2IMG]
    # Meta states
    TYPING, STOPPING, START_OVER = map(chr, range(8, 11))
    END = ConversationHandler.END
    TIMEOUT = ConversationHandler.TIMEOUT

    SD_PAYLOAD = {
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

    OLLAMA_PAYLOAD = {
        "model": "llama3.2",
        "keep_alive": "10m",
        "stream": False,
    }

    CLAUDE_PAYLOAD = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": "1024",
        "temperature": "0",
        "system": "You are best personal assistant. Respond only with short answer no more than five sentences.",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"},
        ],
    }

    HELP_TEXT = """
    Use /start to begin, /stop to end. Commands:
    text2text - generate response according to your request
        summarize - summarize input text
        translate - translate input to english
        claude - general conversation with claude-3.5-sonnet model
        yandex - general conversation with yandex-gpt model
    text2img - create image according to your description using yandex-art
    """

    @classmethod
    def validate(cls):
        """Validate configuration settings."""
        if not cls.BOT_TOKEN:
            raise ConfigError("Bot token not configured")
