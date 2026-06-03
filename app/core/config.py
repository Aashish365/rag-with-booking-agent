from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import yaml


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "rag_db"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "documents"

    redis_host: str = "localhost"
    redis_port: int = 6379

    llm_config_path: str = "llm_config.yaml"
    tmp_dir: str = "tmp"


def load_llm_config(path: str) -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"llm_config.yaml not found at {path}")
    with open(config_path) as f:
        return yaml.safe_load(f)


settings = Settings()
llm_config = load_llm_config(settings.llm_config_path)
