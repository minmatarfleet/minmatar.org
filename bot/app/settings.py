from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DEBUG: bool = False
    DISCORD_BOT_TOKEN: str
    DISCORD_GUILD_ID: str = "1041384161505722368"
    DISCORD_HELP_CHANNEL_ID: int = 1183401618943791186
    DISCORD_MODERATOR_ROLE_ID: int = 1201878796093882398
    MINMATAR_API_TOKEN: str
    API_URL: str = "https://api.minmatar.org/api"

    class Config:
        env_file = ".env"


settings = Settings()
