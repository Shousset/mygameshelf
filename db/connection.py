import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Return a new psycopg2 connection using .env credentials."""
    password = os.getenv("DB_PASSWORD")
    if not password:
        raise RuntimeError(
            "DB_PASSWORD is not set. Copy .env.example to .env and fill in your local Postgres credentials."
        )
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "mygameshelf"),
        user=os.getenv("DB_USER", "postgres"),
        password=password,
    )


def initialize_schema():
    """Run schema.sql to create tables if they don't exist."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    finally:
        conn.close()
