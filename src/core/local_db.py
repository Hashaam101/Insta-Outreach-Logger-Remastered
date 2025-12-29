"""
Local SQLite Database Manager for InstaCRM Ecosystem.

This module provides the LocalDatabase class which handles all local data
persistence. The Main App is the exclusive owner of this connection to
prevent SQLite locking issues in the Server-Client architecture.

AI Agent Note: Updated for Phase 4 (Governance & Event Schema)
"""

import sqlite3
import os
import sys
import json
import shutil
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
    
    New Architecture:
        - event_logs: Parent table for all activities (Outreach, System, etc.)
        - outreach_logs: Child table for message content.
        - prospects: Local cache of lead status (Targets).
        - rules: Cached safety protocols.
        - goals: Cached performance targets.
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
        self.conn = None
        
        try:
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            # Quick check to ensure file is valid
            self.conn.execute("PRAGMA integrity_check")
        except sqlite3.DatabaseError as e:
            print(f"[LocalDB] Database corruption detected: {e}")
            if self.conn:
                self.conn.close()
            
            backup_path = db_path + ".bak"
            if os.path.exists(backup_path):
                print(f"[LocalDB] Restoring from backup: {backup_path}")
                try:
                    shutil.copy2(backup_path, db_path)
                    self.conn = sqlite3.connect(db_path, check_same_thread=False)
                    print("[LocalDB] Restoration successful.")
                except Exception as restore_err:
                    print(f"[LocalDB] Restoration failed: {restore_err}")
                    raise e
            else:
                print("[LocalDB] No backup found. Database might be lost.")
                raise e

        self.conn.row_factory = sqlite3.Row  # Enable dict-like row access
        self.cursor = self.conn.cursor()

        # Auto-Backup on successful connect
        try:
            shutil.copy2(db_path, db_path + ".bak")
        except Exception:
            pass # Ignore backup errors (permissions/locks)

        # Initialize schema on first connection
        self.init_schema()

    def init_schema(self):
        """
        Create the local database tables if they don't exist.
        Handles migration by resetting schema if incompatible changes are detected.
        """
        # Check if we need to migrate (simple check: does event_logs exist?)
        try:
            self.cursor.execute("SELECT 1 FROM event_logs LIMIT 1")
        except sqlite3.OperationalError:
            # Table doesn't exist, likely old schema. Resetting DB for v2 upgrade.
            print("[LocalDB] Old schema detected or first run. Initializing v2 schema...")
            self.cursor.executescript("""
                DROP TABLE IF EXISTS outreach_logs;
                DROP TABLE IF EXISTS prospects;
                DROP TABLE IF EXISTS event_logs;
                DROP TABLE IF EXISTS rules;
                DROP TABLE IF EXISTS goals;
                DROP TABLE IF EXISTS meta;
                DROP TABLE IF EXISTS pending_deletions;
            """)

        # 1. EVENT_LOGS (Parent Table)
        # Stores the "Who, When, What" of every action
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                elg_id TEXT,  -- Oracle ID (populated after sync)
                event_type TEXT NOT NULL, -- 'Outreach', 'System', 'User'
                act_id TEXT,  -- Actor ID (if known)
                opr_id TEXT,  -- Operator ID
                tar_id TEXT,  -- Target ID (if known)
                details TEXT, -- JSON context
                created_at TEXT NOT NULL,
                synced_to_cloud INTEGER DEFAULT 0
            )
        """)

        # 2. OUTREACH_LOGS (Child Table)
        # Stores the actual message content for Outreach events
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS outreach_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                olg_id TEXT, -- Oracle ID
                event_log_id INTEGER NOT NULL, -- FK to local event_logs.id
                message_text TEXT,
                sent_at TEXT,
                FOREIGN KEY(event_log_id) REFERENCES event_logs(id) ON DELETE CASCADE
            )
        """)

        # 3. PROSPECTS (Local Cache of TARGETS)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS prospects (
                target_username TEXT PRIMARY KEY,
                tar_id TEXT, -- Oracle ID
                status TEXT DEFAULT 'Cold No Reply',
                owner_actor TEXT, -- Cached for display logic
                notes TEXT,
                last_updated TEXT,
                first_contacted TEXT,
                email TEXT,
                phone_number TEXT,
                source_summary TEXT,
                discovery_status TEXT DEFAULT 'pending'
            )
        """)

        # 4. RULES (Safety Protocols)
        # Synced from Cloud to enforce limits locally
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS rules (
                rule_id TEXT PRIMARY KEY,
                type TEXT, -- 'Frequency Cap', 'Interval Spacing'
                metric TEXT,
                limit_value INTEGER,
                time_window_sec INTEGER,
                severity TEXT,
                assigned_to_opr TEXT,
                assigned_to_act TEXT,
                status TEXT DEFAULT 'Active'
            )
        """)

        # 5. GOALS (Performance Targets)
        # Synced from Cloud for UI display
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                goal_id TEXT PRIMARY KEY,
                metric TEXT,
                target_value INTEGER,
                frequency TEXT,
                assigned_to_opr TEXT,
                assigned_to_act TEXT,
                status TEXT DEFAULT 'Active',
                suggested_by TEXT,
                start_date TEXT,
                end_date TEXT
            )
        """)

        # 6. META (Config & Sync Timestamps)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # 7. PENDING DELETIONS
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_deletions (
                target_username TEXT PRIMARY KEY
            )
        """)

        self.conn.commit()

    # ==========================================
    #           EVENT LOGGING (NEW)
    # ==========================================

    def log_event(self, event_type: str, data: dict) -> int:
        """
        Logs a general event. Optionally creates an OUTREACH_LOG if message_text is provided.
        Updates PROSPECT status if it's an outreach or status change.
        
        Args:
            event_type: 'Outreach', 'Change in Tar Info', 'Tar Exception Toggle', 'User', 'System'
            data: {
                'target_username': str,
                'actor_username': str,
                'operator_name': str,
                'message_text': str (optional),
                'act_id': str (optional),
                'opr_id': str (optional),
                'timestamp': str (ISO),
                'details': str (optional JSON or text)
            }
        """
        target_username = data.get('target_username')
        print(f"[LocalDB] Logging event '{event_type}' for: {target_username}")
        
        now = datetime.now(timezone.utc).isoformat()
        ts = data.get('timestamp', now)
        
        # Determine details
        details = data.get('details')
        if not details and target_username:
             # Default details for simple outreach or status changes if not provided
             details = json.dumps({'target_username': target_username})

        # 1. Insert Event Log
        self.cursor.execute("""
            INSERT INTO event_logs (
                event_type, act_id, opr_id, details, created_at, synced_to_cloud
            ) VALUES (?, ?, ?, ?, ?, 0)
        """, (
            event_type,
            data.get('act_id', 'UNKNOWN'),
            data.get('opr_id', 'UNKNOWN'),
            details,
            ts
        ))
        
        event_id = self.cursor.lastrowid
        
        # 2. Insert Outreach Log (Only if message_text is present)
        # The ipc_server determines if message_text should be provided based on status.
        if data.get('message_text'):
            self.cursor.execute("""
                INSERT INTO outreach_logs (
                    event_log_id, message_text, sent_at
                ) VALUES (?, ?, ?)
            """, (
                event_id,
                data['message_text'],
                ts
            ))
        
        # 3. Update/Upsert Prospect (If target is involved)
        if target_username:
            # Default status for new prospects found via Outreach
            new_status = 'Cold No Reply'
            if event_type == 'Outreach':
                new_status = 'Cold No Reply'
            # For other events like 'Change in Tar Info', the status update is likely handled separately via update_prospect_status,
            # but we ensure the record exists here.
            
            # Use 'INSERT OR IGNORE' pattern or upsert to ensure existence without overwriting status if not intended
            # Actually, for Outreach, we want to set to 'Cold No Reply' if it was 'new'.
            
            self.cursor.execute("""
                INSERT INTO prospects (target_username, status, last_updated, first_contacted, owner_actor, discovery_status)
                VALUES (?, ?, ?, ?, ?, 'pending')
                ON CONFLICT(target_username) DO UPDATE SET
                    last_updated = excluded.last_updated,
                    first_contacted = COALESCE(prospects.first_contacted, excluded.first_contacted),
                    owner_actor = excluded.owner_actor
            """, (target_username, new_status, ts, ts, data.get('actor_username')))
            
            # If it's an outreach event, we might want to ensure status isn't overwritten if it's already 'Warm' etc.
            # But the logic above only updates metadata, not status (unless inserted).
            
        self.conn.commit()
        return event_id

    # Keeping legacy alias for now to minimize breakage if I missed a call, 
    # but the goal is to use log_event everywhere.
    def log_outreach_event(self, data: dict) -> int:
        return self.log_event('Outreach', data)

    def get_unsynced_events(self, limit: int = 100) -> list:
        """
        Fetch unsynced events joined with their outreach logs.
        Used by Sync Engine to Push to Cloud.
        """
        self.cursor.execute("""
            SELECT 
                e.id, e.event_type, e.act_id, e.opr_id, e.details, e.created_at,
                o.message_text, o.sent_at
            FROM event_logs e
            LEFT JOIN outreach_logs o ON e.id = o.event_log_id
            WHERE e.synced_to_cloud = 0
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in self.cursor.fetchall()]

    def mark_events_synced(self, event_ids: list, mapping: dict = None):
        """
        Mark events as synced.
        Optionally update local records with real Cloud IDs (ELG_ID, TAR_ID).
        
        Args:
            event_ids: List of local IDs to mark synced.
            mapping: Dict of {local_id: {'elg_id': '...', 'tar_id': '...'}}
        """
        if not event_ids:
            return

        placeholders = ",".join("?" * len(event_ids))
        
        # Bulk mark synced
        self.cursor.execute(f"UPDATE event_logs SET synced_to_cloud = 1 WHERE id IN ({placeholders})", event_ids)
        
        # Update IDs if mapping provided
        if mapping:
            for local_id, ids in mapping.items():
                if 'elg_id' in ids:
                    self.cursor.execute("UPDATE event_logs SET elg_id = ? WHERE id = ?", (ids['elg_id'], local_id))
                # Update target ID if we discovered it
                if 'tar_id' in ids and 'target_username' in ids:
                    self.cursor.execute("UPDATE prospects SET tar_id = ? WHERE target_username = ?", (ids['tar_id'], ids['target_username']))
                    self.cursor.execute("UPDATE event_logs SET tar_id = ? WHERE id = ?", (ids['tar_id'], local_id))

        self.conn.commit()

    # ==========================================
    #           GOVERNANCE & RULES
    # ==========================================

    def get_active_rules(self) -> list:
        """Fetch all active rules for Pre-Flight Checks."""
        self.cursor.execute("SELECT * FROM rules WHERE status = 'Active'")
        return [dict(row) for row in self.cursor.fetchall()]

    def get_recent_event_count(self, act_id: str, event_type: str, seconds: int) -> int:
        """
        Count events of a type for an actor in the last X seconds.
        Used for Frequency Cap checks.
        """
        # SQLite datetime comparison
        self.cursor.execute("""
            SELECT COUNT(*) as cnt 
            FROM event_logs 
            WHERE act_id = ? 
            AND event_type = ? 
            AND datetime(created_at) > datetime('now', ?)
        """, (act_id, event_type, f'-{seconds} seconds'))
        
        row = self.cursor.fetchone()
        return row['cnt'] if row else 0

    def get_last_event_time(self, act_id: str, event_type: str) -> str:
        """Get timestamp of last event for Interval Spacing checks."""
        self.cursor.execute("""
            SELECT created_at 
            FROM event_logs 
            WHERE act_id = ? AND event_type = ? 
            ORDER BY created_at DESC LIMIT 1
        """, (act_id, event_type))
        
        row = self.cursor.fetchone()
        return row['created_at'] if row else None

    # ==========================================
    #           SYNC HELPERS
    # ==========================================

    def update_rules_cache(self, rules: list):
        """Replace local rules cache with fresh data from Cloud."""
        self.cursor.execute("DELETE FROM rules") # Full refresh strategy
        if not rules:
            return
            
        data = []
        for r in rules:
            data.append((
                r['RULE_ID'], r['TYPE'], r['METRIC'], r['LIMIT_VALUE'], 
                r['TIME_WINDOW_SEC'], r['SEVERITY'], 
                r.get('ASSIGNED_TO_OPR'), r.get('ASSIGNED_TO_ACT'), r['STATUS']
            ))
            
        self.cursor.executemany("""
            INSERT INTO rules (rule_id, type, metric, limit_value, time_window_sec, severity, assigned_to_opr, assigned_to_act, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        self.conn.commit()

    def update_goals_cache(self, goals: list):
        """Replace local goals cache."""
        self.cursor.execute("DELETE FROM goals")
        if not goals:
            return
            
        data = []
        for g in goals:
            data.append((
                g['GOAL_ID'], g['METRIC'], g['TARGET_VALUE'], g['FREQUENCY'],
                g.get('ASSIGNED_TO_OPR'), g.get('ASSIGNED_TO_ACT'), g['STATUS'],
                g.get('SUGGESTED_BY'), 
                str(g.get('START_DATE')), str(g.get('END_DATE'))
            ))
            
        self.cursor.executemany("""
            INSERT INTO goals (goal_id, metric, target_value, frequency, assigned_to_opr, assigned_to_act, status, suggested_by, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, data)
        self.conn.commit()

    # ==========================================
    #           PROSPECT MANAGEMENT
    # ==========================================

    def get_prospect(self, target_username: str) -> dict:
        """Retrieve a single prospect's local record."""
        self.cursor.execute("SELECT * FROM prospects WHERE target_username = ?", (target_username,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    def update_prospect_status(self, target_username: str, status: str) -> bool:
        """Update a prospect's status."""
        now = datetime.now(timezone.utc).isoformat()
        self.cursor.execute("""
            UPDATE prospects SET status = ?, last_updated = ? WHERE target_username = ?
        """, (status, now, target_username))
        self.conn.commit()
        return self.cursor.rowcount > 0

    def set_last_sync_timestamp(self, timestamp: str):
        self.cursor.execute("""
            INSERT INTO meta (key, value) VALUES ('last_cloud_sync', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (timestamp,))
        self.conn.commit()

    def get_last_sync_timestamp(self) -> str:
        self.cursor.execute("SELECT value FROM meta WHERE key = 'last_cloud_sync'")
        row = self.cursor.fetchone()
        return row['value'] if row else None

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

# CLI Test
if __name__ == "__main__":
    print("Testing LocalDB v2...")
    try:
        os.remove("test_v2.db")
    except OSError:
        pass
        
    with LocalDatabase("test_v2.db") as db:
        # Test Event Log
        eid = db.log_event('Outreach', {
            'target_username': 'john_doe',
            'actor_username': 'my_actor',
            'message_text': 'Hello world',
            'act_id': 'ACT-1',
            'opr_id': 'OPR-1'
        })
        print(f"Logged Event ID: {eid}")
        
        # Test Fetch
        unsynced = db.get_unsynced_events()
        print(f"Unsynced: {len(unsynced)}")
        print(unsynced[0] if unsynced else "None")
        
        # Test Rules
        db.update_rules_cache([{
            'RULE_ID': 'R1', 'TYPE': 'Frequency Cap', 'METRIC': 'Total Messages',
            'LIMIT_VALUE': 50, 'TIME_WINDOW_SEC': 3600, 'SEVERITY': 'Soft',
            'STATUS': 'Active'
        }])
        rules = db.get_active_rules()
        print(f"Active Rules: {len(rules)}")

    os.remove("test_v2.db")
    print("Test Complete.")
