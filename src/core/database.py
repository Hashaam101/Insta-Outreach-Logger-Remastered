import oracledb
import os
import sys
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Define PROJECT_ROOT for both frozen (PyInstaller) and dev environments
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Load environment variables from .env file
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Check if database credentials are available
HAS_CONFIG = all([
    os.getenv('DB_USER'),
    os.getenv('DB_PASSWORD'),
    os.getenv('DB_DSN')
])

class DatabaseManager:
    def __init__(self):
        if not HAS_CONFIG:
            raise ImportError("Database configuration (.env file) not found or incomplete.")

        # Use TLS connection string (no wallet required)
        # DSN should be a full connection descriptor like:
        # (description=(retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1522)(host=your-db.oraclecloud.com))(connect_data=(service_name=your_service_name))(security=(ssl_server_dn_match=yes)))
        
        self.pool = oracledb.create_pool(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            dsn=os.getenv('DB_DSN'),
            min=1,
            max=5,
            increment=1,
            getmode=oracledb.POOL_GETMODE_WAIT,
            timeout=10
        )

    def get_connection(self):
        return self.pool.acquire()

    def get_operator_by_email(self, email):
        """
        Fetches an operator by email.
        Returns dict {OPR_ID, OPR_NAME, OPR_EMAIL} or None.
        """
        sql = "SELECT OPR_ID, OPR_NAME, OPR_EMAIL FROM OPERATORS WHERE OPR_EMAIL = :1"
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, [email])
                row = cursor.fetchone()
                if row:
                    return {'OPR_ID': row[0], 'OPR_NAME': row[1], 'OPR_EMAIL': row[2]}
                return None

    def create_operator(self, name, email):
        """
        Creates a new operator record.
        Returns the new OPR_ID.
        """
        import time
        # Simple ID generation logic matching schema format (OPR-XXXXXXXX)
        opr_id = f"OPR-{int(time.time()):X}"
        
        sql = """
            INSERT INTO OPERATORS (OPR_ID, OPR_EMAIL, OPR_NAME, OPR_STATUS, CREATED_AT, LAST_ACTIVITY)
            VALUES (:1, :2, :3, 'online', SYSTIMESTAMP, SYSTIMESTAMP)
        """
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, [opr_id, email, name])
                connection.commit()
        return opr_id

    # ... (Keep existing methods: fetch_prospects_updates, upsert_prospects, etc.) ...
    # I will retain all existing methods below to ensure backward compatibility and full functionality.

    def ensure_actor_exists(self, actor_username, operator_name):
        """
        Checks if an actor is registered to this operator.
        If not, registers it according to the shared ownership model.
        """
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                # 1. Resolve OPR_ID
                cursor.execute("SELECT OPR_ID FROM OPERATORS WHERE OPR_NAME = :1", [operator_name])
                res = cursor.fetchone()
                if not res:
                    print(f"[OracleDB] Error: Operator '{operator_name}' not found in DB.")
                    return
                opr_id = res[0]

                # 2. Check if this specific pair (Actor + Operator) exists
                cursor.execute(
                    "SELECT COUNT(*) FROM ACTORS WHERE ACT_USERNAME = :1 AND OPR_ID = :2", 
                    [actor_username, opr_id]
                )
                exists = cursor.fetchone()[0] > 0
                
                if not exists:
                    print(f"[OracleDB] Registering actor '@{actor_username}' for operator '{operator_name}'...")
                    import time
                    act_id = f"ACT-{int(time.time()):X}"
                    cursor.execute("""
                        INSERT INTO ACTORS (ACT_ID, ACT_USERNAME, OPR_ID, ACT_STATUS, CREATED_AT, LAST_ACTIVITY)
                        VALUES (:1, :2, :3, 'Active', SYSTIMESTAMP, SYSTIMESTAMP)
                    """, [act_id, actor_username, opr_id])
                    connection.commit()

    def fetch_prospects_updates(self, since_timestamp=None):
        if since_timestamp:
            sql = "SELECT TAR_ID, TAR_USERNAME, TAR_STATUS, NOTES, LAST_UPDATED, FIRST_CONTACTED, EMAIL, PHONE_NUM, CONT_SOURCE FROM TARGETS WHERE LAST_UPDATED > :1"
            if isinstance(since_timestamp, str):
                try: since_timestamp = pd.to_datetime(since_timestamp)
                except: pass
            params = [since_timestamp]
        else:
            sql = "SELECT TAR_ID, TAR_USERNAME, TAR_STATUS, NOTES, LAST_UPDATED, FIRST_CONTACTED, EMAIL, PHONE_NUM, CONT_SOURCE FROM TARGETS"
            params = []

        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                return [
                    {
                        'tar_id': row[0],
                        'target_username': row[1],
                        'status': row[2],
                        'notes': row[3],
                        'last_updated': row[4],
                        'first_contacted': row[5],
                        'email': row[6],
                        'phone_number': row[7],
                        'source_summary': row[8]
                    }
                    for row in rows
                ]

    def fetch_active_rules(self):
        sql = "SELECT * FROM RULES WHERE STATUS = 'Active'"
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                # Helper to map cursor description to dict
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def fetch_active_goals(self):
        sql = "SELECT * FROM GOALS WHERE STATUS = 'Active'"
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql)
                columns = [col[0] for col in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def update_operator_heartbeat(self, operator_name):
        sql = "UPDATE OPERATORS SET LAST_ACTIVITY = SYSTIMESTAMP, OPR_STATUS = 'online' WHERE OPR_NAME = :1"
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, [operator_name])
                connection.commit()

    def update_actor_heartbeat(self, actor_username, operator_name):
        """
        Updates the LAST_ACTIVITY for a specific actor-operator pair.
        """
        sql = """
            UPDATE ACTORS a
            SET a.LAST_ACTIVITY = SYSTIMESTAMP
            WHERE a.ACT_USERNAME = :1 
            AND a.OPR_ID = (SELECT o.OPR_ID FROM OPERATORS o WHERE o.OPR_NAME = :2)
        """
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, [actor_username, operator_name])
                connection.commit()

    def push_events_batch(self, events):
        """
        Bulk push local events to Oracle.
        Returns mapping of local_id -> {elg_id, tar_id}
        """
        import time
        mapping = {}
        
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                for event in events:
                    # 1. Resolve/Create Target
                    tar_username = None
                    try:
                        import json
                        details = json.loads(event['details'])
                        tar_username = details.get('target_username')
                    except: pass

                    if not tar_username: continue # Skip invalid

                    # Check/Create Target
                    cursor.execute("SELECT TAR_ID FROM TARGETS WHERE TAR_USERNAME = :1", [tar_username])
                    row = cursor.fetchone()
                    if row:
                        tar_id = row[0]
                    else:
                        tar_id = f"TAR-{int(time.time()*1000):X}" # Simple ID gen
                        cursor.execute(
                            "INSERT INTO TARGETS (TAR_ID, TAR_USERNAME, TAR_STATUS, FIRST_CONTACTED, LAST_UPDATED) VALUES (:1, :2, 'Cold No Reply', SYSTIMESTAMP, SYSTIMESTAMP)",
                            [tar_id, tar_username]
                        )
                    
                    # 2. Insert Event Log
                    elg_id = f"ELG-{int(time.time()*1000):X}"
                    
                    # Resolve IDs from names if needed (simplified)
                    act_id = event['act_id']
                    if not act_id.startswith("ACT-"):
                         cursor.execute("SELECT ACT_ID FROM ACTORS WHERE ACT_USERNAME = :1", [act_id])
                         res = cursor.fetchone()
                         act_id = res[0] if res else 'UNKNOWN'

                    opr_id = event['opr_id']
                    if not opr_id.startswith("OPR-"):
                         cursor.execute("SELECT OPR_ID FROM OPERATORS WHERE OPR_NAME = :1", [opr_id])
                         res = cursor.fetchone()
                         opr_id = res[0] if res else 'UNKNOWN'

                    # Format timestamp to match Oracle's expected format (6 fractional digits)
                    # Python's isoformat() can produce variable fractional seconds
                    created_at_str = event['created_at']
                    if 'T' in created_at_str and '.' in created_at_str:
                        # Ensure exactly 6 fractional digits
                        parts = created_at_str.split('.')
                        if len(parts) == 2:
                            base = parts[0]
                            frac_and_tz = parts[1]
                            # Extract fractional part (before Z or +/-)
                            if 'Z' in frac_and_tz:
                                frac = frac_and_tz.split('Z')[0]
                                tz = 'Z'
                            elif '+' in frac_and_tz:
                                frac = frac_and_tz.split('+')[0]
                                tz = '+' + frac_and_tz.split('+')[1]
                            elif '-' in frac_and_tz:
                                frac = frac_and_tz.split('-')[0]
                                tz = '-' + frac_and_tz.split('-')[1]
                            else:
                                frac = frac_and_tz
                                tz = ''
                            # Pad or truncate to 6 digits
                            frac = (frac + '000000')[:6]
                            # Always use Z regardless of input timezone
                            created_at_str = f"{base}.{frac}Z"
                    
                    cursor.execute("""
                        INSERT INTO EVENT_LOGS (ELG_ID, EVENT_TYPE, ACT_ID, OPR_ID, TAR_ID, DETAILS, CREATED_AT)
                        VALUES (:1, :2, :3, :4, :5, :6, TO_TIMESTAMP(:7, 'YYYY-MM-DD"T"HH24:MI:SS.FF6"Z"'))
                    """, [elg_id, event['event_type'], act_id, opr_id, tar_id, event['details'], created_at_str])

                    # 3. Insert Outreach Log (if applicable)
                    if event.get('message_text'):
                        olg_id = f"OLG-{int(time.time()*1000):X}"
                        
                        # Format sent_at timestamp
                        sent_at_str = event['sent_at']
                        if 'T' in sent_at_str and '.' in sent_at_str:
                            parts = sent_at_str.split('.')
                            if len(parts) == 2:
                                base = parts[0]
                                frac_and_tz = parts[1]
                                if 'Z' in frac_and_tz:
                                    frac = frac_and_tz.split('Z')[0]
                                    tz = 'Z'
                                elif '+' in frac_and_tz:
                                    frac = frac_and_tz.split('+')[0]
                                    tz = '+' + frac_and_tz.split('+')[1]
                                else:
                                    frac = frac_and_tz
                                    tz = ''
                                frac = (frac + '000000')[:6]
                                # Always use Z regardless of input timezone
                                sent_at_str = f"{base}.{frac}Z"
                        
                        cursor.execute("""
                            INSERT INTO OUTREACH_LOGS (OLG_ID, ELG_ID, MESSAGE_TEXT, SENT_AT)
                            VALUES (:1, :2, :3, TO_TIMESTAMP(:4, 'YYYY-MM-DD"T"HH24:MI:SS.FF6"Z"'))
                        """, [olg_id, elg_id, event['message_text'], sent_at_str])

                    mapping[event['id']] = {'elg_id': elg_id, 'tar_id': tar_id, 'target_username': tar_username}
                
                connection.commit()
        return mapping

    def close(self):
        if self.pool:
            self.pool.close()