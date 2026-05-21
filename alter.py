from db.connection import get_connection

conn = get_connection()
try:
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE games ADD COLUMN IF NOT EXISTS external_id VARCHAR(100);")
    conn.commit()
    print("Column 'external_id' successfully added to 'games'")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
