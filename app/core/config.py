import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")

if not DATABASE_URL:
    MYSQL_HOST = os.getenv("MYSQL_HOST") or os.getenv("MYSQLHOST") or "127.0.0.1"
    MYSQL_PORT = os.getenv("MYSQL_PORT") or os.getenv("MYSQLPORT") or "3306"
    MYSQL_USER = os.getenv("MYSQL_USER") or os.getenv("MYSQLUSER") or "root"
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD") or os.getenv("MYSQLPASSWORD") or ""
    MYSQL_DB = os.getenv("MYSQL_DB") or os.getenv("MYSQLDATABASE") or "bitbeer"

    DATABASE_URL = (
        f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
    )

JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "10080"))