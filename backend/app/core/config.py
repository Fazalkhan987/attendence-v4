from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Smart Attendance API"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/smart_attendance"
    AUTO_CREATE_TABLES: bool = True

    # Auth
    SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    LOGIN_MAX_FAILURES: int = 5
    LOGIN_LOCK_MINUTES: int = 15

    # Biometric data protection (Fernet key)
    BIOMETRIC_ENCRYPTION_KEY: str = ""

    # Time handling: schedules and "work dates" are evaluated in this timezone.
    TIMEZONE: str = "Asia/Karachi"
    CORS_ORIGINS: str = "http://localhost:5173"

    # Face engine (enrollment service)
    FACE_ENGINE_URL: str = "http://127.0.0.1:8100"
    FACE_ENGINE_SERVICE_KEY: str = "change-me"
    MIN_ENROLL_SAMPLES: int = 3
    MAX_ENROLL_IMAGES: int = 10
    MAX_ENROLL_IMAGE_BYTES: int = 3_000_000
    DUPLICATE_FACE_THRESHOLD: float = 0.65  # new face too similar to another employee => reject

    # Recognition event validation
    RECOGNITION_MIN_CONFIDENCE: float = 0.50
    EVENT_MAX_AGE_SECONDS: int = 300
    EVENT_MAX_FUTURE_SECONDS: int = 30
    DUPLICATE_EVENT_WINDOW_SECONDS: int = 60
    MIN_CHECKOUT_AFTER_CHECKIN_MINUTES: int = 5
    HALF_DAY_RATIO: float = 0.5  # worked < ratio * session length => Half Day

    # Background jobs
    ENABLE_BACKGROUND_JOBS: bool = True
    FINALIZER_INTERVAL_SECONDS: int = 60
    FINALIZER_LOOKBACK_DAYS: int = 2
    RECOGNITION_RETENTION_DAYS: int = 90

    UPLOAD_DIR: str = "uploads"

    ADMIN_EMAIL: str = "admin@company.com"
    ADMIN_PASSWORD: str = "ChangeMe@123"
    ADMIN_NAME: str = "System Administrator"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


settings = Settings()

if settings.is_production and (settings.SECRET_KEY == "change-me" or not settings.BIOMETRIC_ENCRYPTION_KEY):
    raise RuntimeError("Set SECRET_KEY and BIOMETRIC_ENCRYPTION_KEY before running in production.")
