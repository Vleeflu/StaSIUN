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

settings = Settings()