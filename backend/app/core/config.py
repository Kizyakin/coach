from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Шахматный тренер"
    environment: str = "development"
    # Persistence is optional. Core chess features must work with no DB at all.
    database_url: str | None = None
    stockfish_path: str = "/usr/games/stockfish"
    frontend_origin: str = "http://localhost:5173"
    chesscom_user_agent: str = "ChessCoach/1.0 (educational project)"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
