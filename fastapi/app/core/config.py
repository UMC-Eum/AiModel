from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = Field(default="local")
    aws_region: str = Field(default="ap-northeast-2")
    stt_bucket: str = Field(default="")
    llm_endpoint: str = Field(default="")
    openai_api_key: str = Field(default="")
    postgres_api_endpoint: str = Field(default="")  # (옵션) HTTP 프록시 엔드포인트
    postgres_dsn: str = Field(default="")  # 예: postgresql+asyncpg://user:pass@host:5432/dbname

    class Config:
        # 현재 작업 디렉터리(.env)와 상위(AiModel/.env) 모두 탐색
        env_file = [".env", "../.env"]
        env_file_encoding = "utf-8"
        extra = "ignore"


def get_settings() -> Settings:
    return Settings()
