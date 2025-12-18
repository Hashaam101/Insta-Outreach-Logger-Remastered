
import os
import sys
import oracledb

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.core.database import DatabaseManager

def migrate():
    print("Running migration: Adding LAST_UPDATED to PROSPECTS table...")
    try:
        db = DatabaseManager()
        with db.get_connection() as conn:
            with conn.cursor() as cursor:
                # Check if column exists
                cursor.execute("SELECT count(*) FROM user_tab_columns WHERE table_name = 'PROSPECTS' AND column_name = 'LAST_UPDATED'")
                exists = cursor.fetchone()[0] > 0
                
                if not exists:
                    print("Column LAST_UPDATED not found. Adding it...")
                    # Add column with default timestamp
                    cursor.execute("ALTER TABLE PROSPECTS ADD (LAST_UPDATED TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
                    print("Column added successfully.")
                else:
                    print("Column LAST_UPDATED already exists.")
                    
        db.close()
        print("Migration complete.")
    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
