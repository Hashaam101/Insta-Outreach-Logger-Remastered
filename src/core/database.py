import oracledb
import os
import sys
import pandas as pd

# Define PROJECT_ROOT for both frozen (PyInstaller) and dev environments
if getattr(sys, 'frozen', False):
    # Running as compiled exe - root is the exe directory
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    # Running as script - root is 2 levels up from src/core/
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Add the project root to the Python path to allow importing 'local_config'
sys.path.insert(0, PROJECT_ROOT)

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
        wallet_location = os.path.join(PROJECT_ROOT, 'assets', 'wallet')
        
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
        Also ensures the Operator exists in the operators table.
        """
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                # 1. Ensure Operator Exists
                cursor.execute("SELECT count(*) FROM operators WHERE operator_name = :1", [operator_name])
                if cursor.fetchone()[0] == 0:
                    print(f"[OracleDB] Operator '{operator_name}' not found. Creating...")
                    cursor.execute("INSERT INTO operators (operator_name) VALUES (:1)", [operator_name])
                    # We commit here to ensure the parent key exists for the next insert
                    connection.commit()

                # 2. Ensure Actor Exists
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
            WHEN MATCHED THEN
                UPDATE SET LAST_UPDATED = CURRENT_TIMESTAMP
            WHEN NOT MATCHED THEN
                INSERT (TARGET_USERNAME, OWNER_ACTOR, STATUS, LAST_UPDATED)
                VALUES (new.TARGET_USERNAME, new.OWNER_ACTOR, 'new', CURRENT_TIMESTAMP)
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
        # Filter logs to only include fields needed for Oracle insert
        filtered_logs = []
        for log in logs:
            filtered_logs.append({
                'actor_username': log['actor_username'],
                'target_username': log['target_username'],
                'message_snippet': log['message_snippet'],
                'timestamp': pd.to_datetime(log['timestamp'])
            })

        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.executemany(sql, filtered_logs, batcherrors=True)
                for error in cursor.getbatcherrors():
                    print("[OracleDB] Error during log insert:", error.message)
                connection.commit()

    def get_prospect_status(self, target_username: str) -> str:
        """
        Fetches the status of a single prospect from Oracle.

        Args:
            target_username: The Instagram username to look up.

        Returns:
            The prospect's status string if found, None otherwise.
        """
        sql = "SELECT STATUS FROM PROSPECTS WHERE TARGET_USERNAME = :1"
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, [target_username])
                row = cursor.fetchone()
                if row:
                    return row[0]
                return None

    def update_prospect_status(self, username, new_status, notes):
        """
        Updates the status and notes for a given prospect.
        """
        if notes is not None:
            sql = "UPDATE PROSPECTS SET STATUS = :1, NOTES = :2, LAST_UPDATED = CURRENT_TIMESTAMP WHERE TARGET_USERNAME = :3"
            params = [new_status, notes, username]
        else:
            sql = "UPDATE PROSPECTS SET STATUS = :1, LAST_UPDATED = CURRENT_TIMESTAMP WHERE TARGET_USERNAME = :2"
            params = [new_status, username]

        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                connection.commit()

    def fetch_prospects_updates(self, since_timestamp=None):
        """
        Fetches prospect statuses updated after the given timestamp.
        
        Args:
            since_timestamp: ISO format string or datetime object.
            
        Returns:
            List of dicts: {'target_username', 'status', 'owner_actor', 'notes', 'last_updated'}
        """
        if since_timestamp:
            sql = "SELECT TARGET_USERNAME, STATUS, OWNER_ACTOR, NOTES, LAST_UPDATED FROM PROSPECTS WHERE LAST_UPDATED > :1"
            # Ensure timestamp is in a format Oracle likes (datetime object)
            if isinstance(since_timestamp, str):
                try:
                    since_timestamp = pd.to_datetime(since_timestamp)
                except:
                    pass
            params = [since_timestamp]
        else:
            sql = "SELECT TARGET_USERNAME, STATUS, OWNER_ACTOR, NOTES, LAST_UPDATED FROM PROSPECTS"
            params = []

        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                # Convert to list of dicts
                return [
                    {
                        'target_username': row[0],
                        'status': row[1],
                        'owner_actor': row[2],
                        'notes': row[3],
                        'last_updated': row[4]
                    }
                    for row in rows
                ]

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
