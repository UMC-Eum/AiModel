from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    env: str = Field(default="local")
    aws_region: str = Field(default="ap-northeast-2")
    stt_bucket: str = Field(default="")
    llm_endpoint: str = Field(default="")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    return Settings()
