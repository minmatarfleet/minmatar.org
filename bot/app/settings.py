from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DEBUG: bool = False
    DISCORD_BOT_TOKEN: str
    DISCORD_GUILD_ID: str = "1041384161505722368"
    DISCORD_STANDINGFLEET_VOICE_CHANNEL_ID: str = "1306515072650313728"
    MINMATAR_API_TOKEN: str
    API_URL: str = "https://api.minmatar.org/api"

    class Config:
        env_file = ".env"


settings = Settings()
