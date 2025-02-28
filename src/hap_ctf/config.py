from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    process_timeout: int = 300
    max_cpu_seconds: int = 60
    max_memory_bytes: int = 256 * 1024 * 1024
    flags_db_path: str = "/opt/flags.db"


@lru_cache
def get_settings():
    return Settings()
