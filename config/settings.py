import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "https://cbicareer.com")
SANCTUM_API_KEY = os.getenv("SACTUM_API_KEY", "")

# Pusher Configuration
PUSHER_APP_ID = os.getenv("PUSHER_APP_ID", "")
PUSHER_KEY = os.getenv("PUSHER_KEY", "")
PUSHER_SECRET = os.getenv("PUSHER_SECRET", "")
PUSHER_CLUSTER = os.getenv("PUSHER_CLUSTER", "ap1")

# Ollama Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-7b-tools-Q4")

# Database Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "jobvacancy_ai")

# Ollama model options per quality tier
OLLAMA_CONFIG = {
    "high_quality": {
        "temperature": 0.1,
        "top_p": 0.2,
        "num_predict": 35000,
        "num_ctx": 35000,
        "num_gpu": 24,
        "num_thread": 7,
    },
    "fast": {
        "temperature": 0.1,
        "top_p": 0.2,
        "num_predict": 35000,
        "num_ctx": 35000,
        "num_gpu": 12,
        "num_thread": 4,
    },
    "conservative": {
        "temperature": 0.1,
        "top_p": 0.2,
        "num_predict": 10000,
        "num_ctx": 10000,
        "num_gpu": 4,
        "num_thread": 2,
    },
}

# Timeout & retry configuration
TIMEOUT_CONFIG = {
    "initial_timeout": 600,
    "max_timeout": 1800,
    "retry_attempts": 3,
    "backoff_factor": 2,
}

# Scheduler intervals (in minutes)
SCHEDULER_SEND_INTERVAL = 5
SCHEDULER_WORKER_INTERVAL = 5
SCHEDULER_FETCH_INTERVAL = 30
WORKER_SLEEP_INTERVAL = 60  # seconds


def get_api_headers():
    """Get standard API headers with auth token."""
    return {
        "Authorization": f"Bearer {SANCTUM_API_KEY}",
        "Accept": "application/json",
    }
