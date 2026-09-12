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

    # Kunci TERPISAH untuk endpoint Activity (Community MAPS). Dokumen MAPID
    # menyebutnya API_KEY_MISSION, dan ia BUKAN MAPID_API_KEY: diuji 11 Sep,
    # MAPID_API_KEY ditolak dengan balasan yang sama persis dengan kunci
    # asal-asalan. Server membalas 500 untuk kunci salah, bukan 401, jadi
    # kegagalan autentikasi tidak bisa dibedakan dari error lain lewat status.
    MAPID_MISSION_KEY: str | None = None
    MAPID_ACTIVITY_URL: str = "https://server.mapid.io/web/competition/activities"


    # Panel AI Insight. Namanya sengaja netral penyedia: kode memakai SDK
    # OpenAI yang bisa diarahkan ke layanan mana pun yang menyediakan endpoint
    # OpenAI-compatible, jadi berpindah penyedia cukup mengubah tiga nilai ini
    # tanpa menyentuh kode. Bawaannya Groq — lihat ADJUSTMENT.md bagian 7.7.
    LLM_API_KEY: str | None = None
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_MODEL: str = "openai/gpt-oss-120b"

    # Penyedia cadangan, dipakai berurutan saat kuota HARIAN penyedia sebelumnya
    # habis. Bentuk tiap entri: nama|base_url|model|kunci, dipisah titik koma.
    # Semua penyedia berbicara protokol OpenAI-compatible, jadi yang berbeda
    # hanya ketiga nilai itu. Lihat services/llm_penyedia.py.
    LLM_FALLBACKS: str | None = None


settings = Settings()
