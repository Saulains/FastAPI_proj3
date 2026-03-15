import os

from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Дней после last_used_at, после которых ссылка удаляется
UNUSED_LINKS_DAYS = int(os.getenv("UNUSED_LINKS_DAYS", "10"))

SECRET = os.getenv("SECRET", "dev-secret")
# import os, base64
# print(base64.urlsafe_b64encode(os.urandom(32)).decode())
