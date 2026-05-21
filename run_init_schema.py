from db.connection import initialize_schema
import sys

if __name__ == "__main__":
    try:
        print("Initializing schema...")
        initialize_schema()
        print("Schema initialized successfully!")
        sys.exit(0)
    except Exception as e:
        print(f"Error initializing schema: {e}")
        sys.exit(1)
