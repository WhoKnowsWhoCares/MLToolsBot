import os
from dotenv import load_dotenv
from telegram.ext import ConversationHandler
from mltoolsbot.exceptions import ConfigError

load_dotenv()


class Config:
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

    # State definitions for top level conversation
    SELECTING_ACTION, TEXT2TEXT, TEXT2IMG = map(chr, range(3))
    # State definitions for text2text level conversation
    SELECTING_PROMPT, SUMMARIZE, TRANSLATE = map(chr, range(3, 6))
    # Meta states
    TYPING, STOPPING, START_OVER = map(chr, range(6, 9))
    END = ConversationHandler.END

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
        Useful commands:
        /text2text - I will generate response according to your request. LLM Model: Claude-3.5-sonnet
        /text2img - I will create image according to your description. SD Model: Flux
    """

    @classmethod
    def validate(cls):
        """Validate configuration settings."""
        if not cls.BOT_TOKEN:
            raise ConfigError("Bot token not configured")
