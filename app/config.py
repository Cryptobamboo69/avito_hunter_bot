from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    bot_owner_chat_id: int = int(os.getenv("BOT_OWNER_CHAT_ID", "0"))
    database_path: str = os.getenv("DATABASE_PATH", "data/bot.db")
    default_check_interval_seconds: int = int(os.getenv("DEFAULT_CHECK_INTERVAL_SECONDS", "120"))
    request_timeout_seconds: int = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
    min_request_delay_seconds: int = int(os.getenv("MIN_REQUEST_DELAY_SECONDS", "2"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def validate(self) -> None:
        if not self.bot_token:
            raise ValueError("BOT_TOKEN is empty. Fill .env first.")
        if not self.bot_owner_chat_id:
            raise ValueError("BOT_OWNER_CHAT_ID is empty. Fill .env first.")


settings = Settings()
