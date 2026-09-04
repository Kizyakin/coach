from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Шахматный тренер"
    environment: str = "development"
    database_url: str = "sqlite:///./chess_coach.db"
    stockfish_path: str = "/usr/games/stockfish"
    frontend_origin: str = "http://localhost:5173"
    chesscom_user_agent: str = "ChessCoach/1.0 (educational project)"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
