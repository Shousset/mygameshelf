from db.connection import get_connection
import sys

def test_connection():
    try:
        conn = get_connection()
        print("Successfully connected to the database!")
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()
            print(f"PostgreSQL version: {version[0]}")
            
            cur.execute("SELECT current_database();")
            db_name = cur.fetchone()
            print(f"Connected to database: {db_name[0]}")
            
        conn.close()
        return True
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return False

if __name__ == "__main__":
    if test_connection():
        sys.exit(0)
    else:
        sys.exit(1)
