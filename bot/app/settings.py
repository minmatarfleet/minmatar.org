from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DEBUG: bool = False
    DISCORD_BOT_TOKEN: str
    MINMATAR_API_TOKEN: str

    class Config:
        env_file = ".env"


settings = Settings()
