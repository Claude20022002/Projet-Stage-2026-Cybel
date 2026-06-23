from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    robot_host: str = "10.42.0.1"
    robot_ws_port: int = 9090
    robot_connect_timeout: float = 20.0
    robot_connect_retries: int = 3
    robot_stale_seconds: float = 25.0
    robot_mock: bool = True
    speech_topic: str = ""
    speech_service: str = ""
    speech_http_host: str = "172.16.0.194"
    speech_http_port: int = 0
    speech_http_path: str = ""
    speech_adb_serial: str = ""
    speech_local_broadcast: bool = False
    kiosk_backend_url: str = "http://172.16.0.131:8000"
    localization_min_percent: float = 60.0
    auto_relocalize_on_connect: bool = True
    navigation_wait_timeout: float = 300.0
    backend_port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
