
import os
import sys
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.core.database import DatabaseManager

def check_oracle_schema():
    try:
        db = DatabaseManager()
        print("Connected to Oracle.")
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT column_name, data_type FROM user_tab_columns WHERE table_name = 'PROSPECTS'")
                columns = cursor.fetchall()
                print("Columns in PROSPECTS table:")
                for col in columns:
                    print(f"  - {col[0]} ({col[1]})")
        db.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_oracle_schema()
