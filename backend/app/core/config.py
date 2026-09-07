from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "StaSIUN API"
    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    DATABASE_URL: str | None = None

    MAPID_GEOSERVER_URL: str = "https://geoserver.mapid.io"
    MAPID_API_KEY: str | None = None
    MAPID_PROJECT_ID: str | None = None
    MAPID_BASEMAP_KEY: str | None = None

    # Panel AI Insight. Namanya sengaja netral penyedia: kode memakai SDK
    # OpenAI yang bisa diarahkan ke layanan mana pun yang menyediakan endpoint
    # OpenAI-compatible, jadi berpindah penyedia cukup mengubah tiga nilai ini
    # tanpa menyentuh kode. Bawaannya Groq — lihat ADJUSTMENT.md bagian 7.7.
    LLM_API_KEY: str | None = None
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_MODEL: str = "openai/gpt-oss-120b"


settings = Settings()
