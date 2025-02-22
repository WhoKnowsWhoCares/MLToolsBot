import json
from redis import Redis
from typing import Optional, Any
from loguru import logger
from mltoolsbot.config import Config


class RedisClient:
    redis_client: Redis

    def __init__(self):
        logger.info(f"Init redis client: {Config.REDIS_HOST}:{Config.REDIS_PORT}")

        self.redis_client = Redis(
            host=Config.REDIS_HOST,
            # host="localhost",
            port=Config.REDIS_PORT,
            decode_responses=True,  # Automatically decode responses to strings
        )

    def set_value(
        self, key: str, value: Any, expire_seconds: Optional[int] = None
    ) -> bool:
        """
        Store a value in Redis with optional expiration
        """
        try:
            logger.info("Set value to redis")
            # Convert complex objects to JSON string
            if not isinstance(value, (str, int, float, bool)):
                value = json.dumps(value)

            self.redis_client.set(key, value)
            if expire_seconds:
                self.redis_client.expire(key, expire_seconds)
            return True
        except Exception as e:
            print(f"Error setting value in Redis: {e}")
            return False

    def get_value(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from Redis
        """
        try:
            logger.info("Get data from redis")
            value = self.redis_client.get(key)
            if value is None:
                return default
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            print(f"Error getting value from Redis: {e}")
            return default

    def delete_value(self, key: str) -> bool:
        """
        Delete a value from Redis
        """
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            print(f"Error deleting value from Redis: {e}")
            return False
