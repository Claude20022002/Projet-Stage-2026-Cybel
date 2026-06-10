from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    robot_host: str = "10.42.0.1"
    robot_ws_port: int = 9090
    robot_mock: bool = True
    speech_topic: str = ""
    speech_service: str = ""
    backend_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
