import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")

if not DATABASE_URL:
    MYSQL_HOST     = os.getenv("MYSQLHOST")
    MYSQL_PORT     = os.getenv("MYSQLPORT")
    MYSQL_USER     = os.getenv("MYSQLUSER")
    MYSQL_PASSWORD = os.getenv("MYSQLPASSWORD")
    MYSQL_DB       = os.getenv("MYSQLDATABASE")

    DATABASE_URL = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
    )

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "10080"))