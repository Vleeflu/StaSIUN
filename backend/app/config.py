from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    project_name: str
    database_url: str
    mapid_geoserver_url: str
    mapid_api_key: str
    mapid_project_id: str
    mapid_basemap_key: str
    ocr_space_api: str
    ocr_space_url: str

    gemini_api_key: str
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_model: str = "gemini-3.5-flash"

settings = Settings()