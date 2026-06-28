from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://lead:lead@localhost:5432/lead"

    jwt_secret: str = "change-me-in-prod"
    jwt_expire_minutes: int = 60
    jwt_algorithm: str = "HS256"

    frontend_origin: str = "http://localhost:3000"
    cookie_name: str = "access_token"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    default_attorney_email: str = "attorney@firm.com"
    default_attorney_password: str = "password123"

    smtp_host: str = "localhost"
    smtp_port: int = 1025
    email_from: str = "no-reply@firm.com"
    attorney_email: str = "attorney@firm.com"

    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "resumes"
    s3_region: str = "us-east-1"

    max_resume_mb: int = 5


settings = Settings()
