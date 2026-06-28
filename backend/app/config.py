"""Application configuration. All secrets/tunables come from environment.
Copy .env.example to .env and fill in values."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: str = "*"  # comma-separated in production

    # Scraping
    enable_live_scraping: bool = False  # master switch; False = cached/sample data
    scrape_cache_ttl_minutes: int = 360  # don't re-scrape the same query within TTL
    playwright_headless: bool = True
    scrape_timeout_seconds: int = 45
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )

    # Geocoding (Nominatim is free, no key). Set a real contact per their policy.
    nominatim_url: str = "https://nominatim.openstreetmap.org"
    nominatim_email: str = "you@example.com"

    # Optional official APIs (leave blank to use scrapers/estimates)
    amadeus_client_id: str = ""
    amadeus_client_secret: str = ""


settings = Settings()
