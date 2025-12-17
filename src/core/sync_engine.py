"""Delta Sync Engine for Insta Outreach Logger.
This module handles the synchronization of the local SQLite queue to Oracle Cloud.
It is now ACTOR-AGNOSTIC and responsible for the auto-discovery of new actors.
"""

import time
import threading
import traceback
from datetime import datetime
import oracledb
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from local_db import LocalDatabase
from database import DatabaseManager # Use the main Oracle DB manager


class SyncEngine:
    """
    Uploads local logs to Oracle Cloud and performs auto-discovery in bulk.
    """

    def __init__(self, operator_name: str, sync_interval: int = 60):
        """
        Initialize the Sync Engine.
        Args:
            operator_name: The name of the human operator running this instance.
            sync_interval: Seconds between sync cycles.
        """
        self.running = False
        self.interval = sync_interval
        self._thread = None
        self._lock = threading.Lock()
        self.operator_name = operator_name
        self.db_manager = DatabaseManager()

        print(f"[SyncEngine] Initialized for Operator: {self.operator_name}, Interval: {self.interval}s")

    def sync_cycle(self):
        """
        Execute a single sync cycle using efficient bulk operations.
        1. Get all unsynced logs from local SQLite.
        2. Extract unique actors and prospects from the logs.
        3. Bulk ensure all unique actors exist in Oracle.
        4. Bulk upsert all unique prospects in Oracle.
        5. Bulk insert all outreach logs into Oracle.
        6. Mark local logs as synced.
        """
        local_db = None
        try:
            local_db = LocalDatabase()
            unsynced_logs = local_db.get_unsynced_logs()

            if not unsynced_logs:
                return

            print(f"[SyncEngine] Processing {len(unsynced_logs)} logs for Operator '{self.operator_name}'")
            
            # --- Step 2: Extract unique entities ---
            unique_actors = {log['actor_username'] for log in unsynced_logs}
            unique_prospects = {(log['target_username'], log['actor_username']) for log in unsynced_logs}

            # --- Step 3: Bulk ensure actors exist ---
            print(f"[SyncEngine] Ensuring {len(unique_actors)} unique actors exist...")
            for actor in unique_actors:
                self.db_manager.ensure_actor_exists(actor, self.operator_name)
            
            # --- Step 4: Bulk upsert prospects ---
            # Format data for executemany, which expects a list of tuples/dicts
            prospects_to_upsert = [{'target_username': p[0], 'owner_actor': p[1]} for p in unique_prospects]
            if prospects_to_upsert:
                self.db_manager.upsert_prospects(prospects_to_upsert)

            # --- Step 5: Bulk insert logs ---
            if unsynced_logs:
                self.db_manager.insert_logs(unsynced_logs)

            # --- Step 6: Mark local logs as synced ---
            synced_ids = [log['id'] for log in unsynced_logs]
            if synced_ids:
                local_db.mark_synced(synced_ids)

        except Exception as e:
            print(f"[SyncEngine] FATAL: Sync cycle failed: {e}")
            traceback.print_exc()
        finally:
            if local_db:
                local_db.close()

    def check_prospect_in_oracle(self, target_username: str) -> str:
        """
        Check if a prospect exists in Oracle and return their status.

        Args:
            target_username: The Instagram username to check.

        Returns:
            The prospect's status string if found, None otherwise.
        """
        try:
            return self.db_manager.get_prospect_status(target_username)
        except Exception as e:
            print(f"[SyncEngine] Error checking prospect in Oracle: {e}")
            return None

    def update_prospect_status_in_oracle(self, target_username: str, new_status: str):
        """
        Update a prospect's status in Oracle.

        Args:
            target_username: The Instagram username to update.
            new_status: The new status value.
        """
        try:
            self.db_manager.update_prospect_status(target_username, new_status, notes=None)
            print(f"[SyncEngine] Oracle status updated: {target_username} -> {new_status}")
        except Exception as e:
            print(f"[SyncEngine] Error updating prospect status in Oracle: {e}")
            raise

    def _sync_loop(self):
        print("[SyncEngine] Background sync thread started.")
        while self.running:
            try:
                with self._lock:
                    if self.running: self.sync_cycle()
            except Exception as e:
                print(f"[SyncEngine] Unexpected error in sync loop: {e}")
                traceback.print_exc()
            
            for _ in range(self.interval):
                if not self.running: break
                time.sleep(1)
        print("[SyncEngine] Background sync thread stopped.")

    def start(self):
        if self.running:
            print("[SyncEngine] Already running.")
            return
        self.running = True
        self._thread = threading.Thread(target=self._sync_loop, daemon=True)
        self._thread.start()
        print("[SyncEngine] Started.")

    def stop(self):
        if not self.running: return
        print("[SyncEngine] Stopping...")
        self.running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self.db_manager.close()
        print("[SyncEngine] Stopped.")

if __name__ == "__main__":
    print("Testing SyncEngine with manual operator name...")
    op_name = "TestOperator"
    # This test will fail if local_db is not populated with relevant test data
    engine = SyncEngine(operator_name=op_name, sync_interval=10)
    print("\n--- Running single sync cycle ---")
    engine.sync_cycle()
    engine.stop()
    print("\nTest complete!")
