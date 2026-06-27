import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    LLM_BACKEND: str = "ollama"
    ANTHROPIC_API_KEY: str | None = None
    OLLAMA_MODEL: str = "mistral"
    OLLAMA_HOST: str = "http://localhost:11434"
    
    AWS_REGION: str = "ap-south-1"
    
    TERRAFORM_BIN: str = "/usr/bin/terraform"
    WORKSPACE_BASE_DIR: str = "./workspaces"
    TF_APPLY_TIMEOUT_SECONDS: int = 600
    
    DB_PATH: str = "./awsforge.db"
    LOG_FILE_DIR: str = "./logs"
    CONFIRM_REQUIRED: bool = True
    MAX_ACTIONS_PER_PLAN: int = 10
    SESSION_HOURLY_RATE_LIMIT: int = 5

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
