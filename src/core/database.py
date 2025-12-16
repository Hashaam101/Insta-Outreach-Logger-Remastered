import oracledb
import os
import sys
import pandas as pd

# Add the project root to the Python path to allow importing 'secrets'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

try:
    import local_config as secrets
except ImportError:
    print("Error: local_config.py not found. Please create it with your database credentials.")
    sys.exit(1)

class DatabaseManager:
    def __init__(self):
        """
        Initializes the DatabaseManager, setting up the connection to the Oracle database.
        """
        wallet_location = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'assets', 'wallet'))
        
        if not os.path.exists(wallet_location) or not os.listdir(wallet_location):
            raise FileNotFoundError(f"Wallet directory is empty or not found at {wallet_location}")

        self.pool = oracledb.create_pool(
            user=secrets.DB_USER,
            password=secrets.DB_PASSWORD,
            dsn=secrets.DB_DSN,
            config_dir=wallet_location,
            min=1,
            max=5,
            increment=1,
            getmode=oracledb.POOL_GETMODE_WAIT,
            timeout=10
        )

    def get_connection(self):
        """Acquires a connection from the connection pool."""
        return self.pool.acquire()

    def get_all_prospects_df(self):
        """
        Fetches all records from the PROSPECTS table and returns them as a Pandas DataFrame.
        """
        print("DEBUG: Entering get_all_prospects_df")
        sql = "SELECT * FROM PROSPECTS ORDER BY FIRST_CONTACTED DESC"
        print("DEBUG: Acquiring connection...")
        with self.get_connection() as connection:
            print("DEBUG: Connection acquired!")
            with connection.cursor() as cursor:
                print("DEBUG: Executing SQL...")
                cursor.execute(sql)
                rows = cursor.fetchall()
                print("DEBUG: Rows fetched, converting to DataFrame...")
                columns = [desc[0] for desc in cursor.description]
                return pd.DataFrame.from_records(rows, columns=columns)

    def get_analytics_data(self):
        """
        Fetches data specifically for analytics dashboards to reduce DB load.
        """
        sql = "SELECT OWNER_ACTOR, FIRST_CONTACTED FROM PROSPECTS WHERE FIRST_CONTACTED IS NOT NULL"
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return pd.DataFrame.from_records(rows, columns=columns)

    def get_full_activity_log(self):
        """
        Performs a LEFT JOIN across logs, actors, and prospects to get a complete
        dataset for the dashboard.
        """
        sql = """
            SELECT 
                l.CREATED_AT,
                a.OWNER_OPERATOR,
                l.ACTOR_USERNAME,
                l.TARGET_USERNAME,
                p.STATUS,
                l.MESSAGE_TEXT
            FROM OUTREACH_LOGS l
            JOIN ACTORS a ON l.ACTOR_USERNAME = a.USERNAME
            LEFT JOIN PROSPECTS p ON l.TARGET_USERNAME = p.TARGET_USERNAME
            ORDER BY l.CREATED_AT DESC
        """
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                df = pd.DataFrame.from_records(rows, columns=columns)
                if not df.empty:
                    df['CREATED_AT'] = pd.to_datetime(df['CREATED_AT'])
                return df

    def ensure_actor_exists(self, actor_username, operator_name):
        """
        Checks if an actor exists and creates it if not. Part of Auto-Discovery.
        """
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM ACTORS WHERE USERNAME = :1", [actor_username])
                exists = cursor.fetchone()[0] > 0
                if not exists:
                    print(f"[OracleDB] Actor '{actor_username}' not found. Auto-registering with owner '{operator_name}'...")
                    cursor.execute(
                        "INSERT INTO ACTORS (USERNAME, OWNER_OPERATOR, STATUS) VALUES (:1, :2, 'active')",
                        [actor_username, operator_name]
                    )
                    connection.commit()
                else:
                    print(f"[OracleDB] Actor '{actor_username}' already exists.")

    def upsert_prospects(self, prospects: list):
        """
        Inserts or updates prospect records in the database.
        
        Args:
            prospects: A list of tuples, where each tuple is (target_username, owner_actor).
        """
        print(f"[OracleDB] Upserting {len(prospects)} prospects...")
        sql = """
            MERGE INTO PROSPECTS p
            USING (SELECT :target_username AS TARGET_USERNAME, :owner_actor AS OWNER_ACTOR FROM dual) new
            ON (p.TARGET_USERNAME = new.TARGET_USERNAME)
            WHEN NOT MATCHED THEN
                INSERT (TARGET_USERNAME, OWNER_ACTOR, STATUS)
                VALUES (new.TARGET_USERNAME, new.OWNER_ACTOR, 'new')
        """
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(sql, prospects, batcherrors=True)
                # Log any errors that occurred during the batch operation
                for error in cursor.getbatcherrors():
                    print("[OracleDB] Error during prospect upsert:", error.message)
                connection.commit()

    def insert_logs(self, logs: list):
        """
        Bulk inserts outreach logs into the database.

        Args:
            logs: A list of dictionaries, each representing a log entry.
        """
        print(f"[OracleDB] Bulk inserting {len(logs)} outreach logs...")
        sql = """
            INSERT INTO OUTREACH_LOGS (ACTOR_USERNAME, TARGET_USERNAME, MESSAGE_TEXT, CREATED_AT)
            VALUES (:actor_username, :target_username, :message_snippet, :timestamp)
        """
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                # Convert timestamp strings to datetime objects for the driver
                for log in logs:
                    log['timestamp'] = pd.to_datetime(log['timestamp'])
                cursor.executemany(sql, logs, batcherrors=True)
                for error in cursor.getbatcherrors():
                    print("[OracleDB] Error during log insert:", error.message)
                connection.commit()

    def update_prospect_status(self, username, new_status, notes):
        """
        Updates the status and notes for a given prospect.
        """
        sql = "UPDATE PROSPECTS SET status = :1, notes = :2, last_updated = CURRENT_TIMESTAMP WHERE target_username = :3"
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, [new_status, notes, username])
                connection.commit()

    def close(self):
        """Closes the connection pool."""
        if self.pool:
            self.pool.close()

if __name__ == '__main__':
    # Example usage and testing
    try:
        db_manager = DatabaseManager()
        print("DatabaseManager initialized.")
        
        print("\nFetching prospects...")
        df = db_manager.get_all_prospects_df()
        print(f"Found {len(df)} prospects.")
        if not df.empty:
            print(df.head())
        
        # Example update - use a test user that exists
        if not df.empty:
            test_username = df.iloc[0]['USERNAME']
            print(f"\nUpdating status for user: {test_username} to 'contacted' with notes.")
            db_manager.update_prospect_status(test_username, 'contacted', 'Test note from db manager.')
            print("Update complete.")

            # Verify update
            df_updated = db_manager.get_all_prospects_df()
            print("\nVerified updated data:")
            print(df_updated[df_updated['USERNAME'] == test_username][['USERNAME', 'STATUS', 'NOTES']])

    except oracledb.Error as e:
        print(f"Database operation failed: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if 'db_manager' in locals() and db_manager:
            db_manager.close()
            print("\nDatabase connection pool closed.")
