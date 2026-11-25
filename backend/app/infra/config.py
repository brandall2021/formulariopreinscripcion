from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../infra/.env", extra="ignore")
    database_url: str = "postgresql+psycopg://face:face@localhost:5432/face"
    test_database_url: str = "postgresql+psycopg://face:face@localhost:5433/face_test"
    minio_endpoint: str = "localhost:9000"
    minio_public_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "face-documentos"
    redis_url: str = "redis://localhost:6379/0"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "preinscripcion@face.unt.edu.ar"
    smtp_tls: bool = False
    smtp_ssl: bool = False
    secret_key: str = "dev-secret-change-me-please-use-32-bytes-minimum"
    otp_ttl_seconds: int = 600
    otp_max_intentos: int = 5
    upload_url_ttl: int = 900
    download_url_ttl: int = 300
    seed_demo: bool = True
    expose_docs: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
