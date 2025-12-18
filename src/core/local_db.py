"""
Local SQLite Database Manager for Insta Outreach Logger.

This module provides the LocalDatabase class which handles all local data
persistence. The Main App is the exclusive owner of this connection to
prevent SQLite locking issues in the Server-Client architecture.

AI Agent Note: This is Phase 3 - The Brain (Local Logic)
"""

import sqlite3
import os
import sys
import json
from datetime import datetime, timezone

# Define PROJECT_ROOT for both frozen (PyInstaller) and dev environments
if getattr(sys, 'frozen', False):
    # Running as compiled exe - root is the exe directory
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    # Running as script - root is 2 levels up from src/core/
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


class LocalDatabase:
    """
    Manages the local SQLite database for fast, offline-first data storage.

    Tables:
        - prospects: Tracks lead status locally before cloud sync.
        - outreach_logs: Append-only log of sent messages with sync status.
    """

    def __init__(self, db_path: str = None):
        """
        Initialize connection to the local SQLite database.

        Args:
            db_path: Optional custom path. Defaults to 'local_data.db' in
                     the project root (or exe directory when frozen).
        """
        if db_path is None:
            # Default: Place DB in the project root or alongside the executable
            db_path = os.path.join(PROJECT_ROOT, "local_data.db")

        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable dict-like row access
        self.cursor = self.conn.cursor()

        # Initialize schema on first connection
        self.init_schema()

    def init_schema(self):
        """
        Create the local database tables if they don't exist.

        Tables mirror a subset of the Oracle Cloud schema but include
        local-specific fields like 'synced_to_cloud' for delta sync tracking.
        """
        # Prospects table - local cache of lead status
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS prospects (
                target_username TEXT PRIMARY KEY,
                status TEXT DEFAULT 'Cold_NoReply',
                owner_actor TEXT,
                notes TEXT,
                last_updated TEXT
            )
        """)

        # Migration: Ensure new columns exist for existing databases
        try:
            self.cursor.execute("ALTER TABLE prospects ADD COLUMN owner_actor TEXT")
        except sqlite3.OperationalError:
            pass # Column already exists

        try:
            self.cursor.execute("ALTER TABLE prospects ADD COLUMN notes TEXT")
        except sqlite3.OperationalError:
            pass # Column already exists

        # Outreach logs table - append-only message log with sync tracking
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS outreach_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_username TEXT NOT NULL,
                actor_username TEXT,
                operator_name TEXT,
                message_snippet TEXT,
                timestamp TEXT,
                synced_to_cloud INTEGER DEFAULT 0
            )
        """)

        # Create index for faster unsynced log queries
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_unsynced
            ON outreach_logs(synced_to_cloud) WHERE synced_to_cloud = 0
        """)

        # Meta table for storing sync timestamps and other persistent config
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        self.conn.commit()

    def get_last_sync_timestamp(self) -> str:
        """
        Retrieves the timestamp of the last successful cloud sync.
        Returns: ISO format string or None.
        """
        self.cursor.execute("SELECT value FROM meta WHERE key = 'last_cloud_sync'")
        row = self.cursor.fetchone()
        return row['value'] if row else None

    def set_last_sync_timestamp(self, timestamp: str):
        """
        Updates the last successful cloud sync timestamp.
        """
        self.cursor.execute("""
            INSERT INTO meta (key, value) VALUES ('last_cloud_sync', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (timestamp,))
        self.conn.commit()

    def sync_prospects_from_cloud(self, cloud_prospects: list):
        """
        Bulk updates local prospect cache with data from Oracle Cloud.
        
        Args:
            cloud_prospects: List of dicts from Oracle {'target_username', 'status', 'owner_actor', 'notes'}
        """
        if not cloud_prospects:
            return

        print(f"[LocalDB] Syncing {len(cloud_prospects)} prospects from cloud...")
        fallback_now = datetime.now(timezone.utc).isoformat()
        
        # Prepare data for executemany
        data_to_insert = []
        for p in cloud_prospects:
            # Use the cloud's last_updated if available (converted to ISO string if needed)
            ts = p.get('last_updated')
            if ts:
                if hasattr(ts, 'isoformat'):
                    ts_str = ts.isoformat()
                else:
                    ts_str = str(ts)
            else:
                ts_str = fallback_now

            data_to_insert.append((
                p['target_username'],
                p['status'],
                p.get('owner_actor'), # Use .get() in case key is missing
                p.get('notes'),
                ts_str
            ))

        # Bulk upsert (replace)
        # We use INSERT OR REPLACE (or upsert syntax) to update local state
        sql = """
            INSERT INTO prospects (target_username, status, owner_actor, notes, last_updated)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(target_username) DO UPDATE SET
                status = excluded.status,
                owner_actor = excluded.owner_actor,
                notes = excluded.notes,
                last_updated = excluded.last_updated
        """
        
        try:
            self.cursor.executemany(sql, data_to_insert)
            self.conn.commit()
            print(f"[LocalDB] Cloud sync applied successfully.")
        except Exception as e:
            print(f"[LocalDB] Error applying cloud sync: {e}")

    def log_outreach(self, log_data: dict) -> int:
        """
        Log a new outreach message from an enriched data dictionary.
        
        Args:
            log_data: A dictionary containing all log info, including
                      target, actor, operator, and message.
        Returns:
            The ID of the newly inserted log entry.
        """
        print(f"[LocalDB] Logging outreach: {log_data}")
        # Create a timezone-AWARE UTC timestamp
        now = datetime.now(timezone.utc).isoformat()

        # Insert the enriched outreach log
        self.cursor.execute("""
            INSERT INTO outreach_logs (
                target_username, actor_username, operator_name, 
                message_snippet, timestamp, synced_to_cloud
            )
            VALUES (?, ?, ?, ?, ?, 0)
        """, (
            log_data['target_username'],
            log_data['actor_username'],
            log_data['operator_name'],
            log_data['message_snippet'],
            now
        ))

        log_id = self.cursor.lastrowid

        # Upsert the prospect record
        self.cursor.execute("""
            INSERT INTO prospects (target_username, status, last_updated)
            VALUES (?, 'Contacted', ?)
            ON CONFLICT(target_username) DO UPDATE SET
                last_updated = excluded.last_updated
        """, (log_data['target_username'], now))

        self.conn.commit()
        return log_id

    def get_unsynced_logs(self) -> list:
        """
        Retrieve all outreach logs that haven't been synced to the cloud,
        including the new actor and operator data.
        """
        self.cursor.execute("""
            SELECT id, target_username, actor_username, operator_name, message_snippet, timestamp
            FROM outreach_logs
            WHERE synced_to_cloud = 0
            ORDER BY timestamp ASC
        """)

        rows = self.cursor.fetchall()
        logs = [dict(row) for row in rows]
        if logs:
            print(f"[LocalDB] Found {len(logs)} unsynced logs to be processed.")
        return logs

    def mark_synced(self, log_ids: list) -> int:
        """
        Mark the specified log entries as synced to the cloud.

        Args:
            log_ids: List of log IDs to mark as synced.

        Returns:
            Number of rows updated.
        """
        if not log_ids:
            return 0
        
        print(f"[LocalDB] Marking {len(log_ids)} logs as synced: {log_ids}")
        placeholders = ",".join("?" * len(log_ids))
        self.cursor.execute(f"""
            UPDATE outreach_logs
            SET synced_to_cloud = 1
            WHERE id IN ({placeholders})
        """, log_ids)

        self.conn.commit()
        return self.cursor.rowcount

    def get_prospect(self, target_username: str) -> dict:
        """
        Retrieve a single prospect's local record.

        Args:
            target_username: The Instagram handle to look up.

        Returns:
            Dict with prospect data, or None if not found.
        """
        self.cursor.execute("""
            SELECT target_username, status, owner_actor, notes, last_updated
            FROM prospects
            WHERE target_username = ?
        """, (target_username,))

        row = self.cursor.fetchone()
        return dict(row) if row else None

    def update_prospect_status(self, target_username: str, status: str, notes: str = None) -> bool:
        """
        Update a prospect's CRM status and optionally their notes.

        Args:
            target_username: The Instagram handle to update.
            status: New status (e.g., 'Replied', 'Booked', 'Not_Interested').
            notes: Optional text notes to append or replace.

        Returns:
            True if a row was updated, False otherwise.
        """
        now = datetime.now(timezone.utc).isoformat()

        if notes is not None:
            self.cursor.execute("""
                UPDATE prospects
                SET status = ?, notes = ?, last_updated = ?
                WHERE target_username = ?
            """, (status, notes, now, target_username))
        else:
            self.cursor.execute("""
                UPDATE prospects
                SET status = ?, last_updated = ?
                WHERE target_username = ?
            """, (status, now, target_username))

        self.conn.commit()
        return self.cursor.rowcount > 0

    def close(self):
        """Close the database connection gracefully."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures connection is closed."""
        self.close()
        return False


# CLI Test Entry Point
if __name__ == "__main__":
    print("Testing LocalDatabase...")

    with LocalDatabase("test_local.db") as db:
        # Test logging outreach
        log_id = db.log_outreach("test_user_123", "Hey! I saw your profile...")
        print(f"Created log entry: {log_id}")

        # Test getting unsynced logs
        unsynced = db.get_unsynced_logs()
        print(f"Unsynced logs: {len(unsynced)}")

        # Test marking as synced
        if unsynced:
            ids = [log["id"] for log in unsynced]
            updated = db.mark_synced(ids)
            print(f"Marked {updated} logs as synced")

        # Test prospect lookup
        prospect = db.get_prospect("test_user_123")
        print(f"Prospect: {prospect}")

    # Cleanup test DB
    os.remove("test_local.db")
    print("Test complete!")
