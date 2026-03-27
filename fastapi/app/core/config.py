from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = Field(default="local")
    aws_region: str = Field(default="ap-northeast-2")
    stt_bucket: str = Field(default="")
    llm_endpoint: str = Field(default="")
    openai_api_key: str = Field(default="")

    class Config:
        # 현재 작업 디렉터리(.env)와 상위(AiModel/.env) 모두 탐색
        env_file = [".env", "../.env"]
        env_file_encoding = "utf-8"


def get_settings() -> Settings:
    return Settings()
