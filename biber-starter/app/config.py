import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Settings:
    env: str = os.getenv("BIBER_ENV", "dev")
    admin_username: str = os.getenv("BIBER_ADMIN_USERNAME", "biber_admin")
    admin_password: str = os.getenv("BIBER_ADMIN_PASSWORD", "ChangeMeImmediately!123")
    demo_api_key: str = os.getenv("BIBER_DEMO_API_KEY", "dev-api-key-change-me")

    passcode_full_gpu: str = os.getenv("BIBER_PASSCODE_FULL_GPU", "BIBER_FULL_GPU_DEMO")
    passcode_20_gpu: str = os.getenv("BIBER_PASSCODE_20_GPU", "BIBER_20_GPU_DEMO")
    passcode_queue_priority: str = os.getenv("BIBER_PASSCODE_QUEUE_PRIORITY", "BIBER_QUEUE_PRIORITY_DEMO")

    default_model: str = os.getenv("BIBER_DEFAULT_MODEL", "biber-dev-core")

settings = Settings()
