"""Delta Sync Engine for InstaCRM Ecosystem.
This module handles the synchronization of the local SQLite queue to Oracle Cloud.
Updated for Phase 3 (Event Logs, Rules, Goals) & Phase 4 (Safety Heartbeats).
"""

import time
import threading
import traceback
from datetime import datetime, timezone
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from local_db import LocalDatabase
from database import DatabaseManager


class SyncEngine:
    """
    Syncs Event Logs, Outreach Logs, Targets, Rules, and Goals between Local and Cloud.
    Handles Heartbeats for Operator and Actor status.
    """

    def __init__(self, server_ref, operator_name: str, sync_interval: int = 60, on_update_callback=None):
        """
        Initialize the Sync Engine.
        Args:
            server_ref: Reference to the IPC Server (to access session state).
            operator_name: The name of the human operator running this instance.
            sync_interval: Seconds between sync cycles.
            on_update_callback: Function to call when new data is pulled from cloud.
        """
        self.server_ref = server_ref
        self.operator_name = operator_name
        self.running = False
        self.interval = sync_interval
        self.failure_count = 0 # Track consecutive failures
        self._thread = None
        self._lock = threading.Lock()
        self.db_manager = DatabaseManager()
        self.on_update_callback = on_update_callback

        print(f"[SyncEngine] Initialized for Operator: {self.operator_name}, Interval: {self.interval}s")

    def _send_heartbeat(self):
        """
        Updates the 'LAST_ACTIVITY' timestamp for the Operator and the current Active Actor.
        """
        try:
            # 1. Operator Heartbeat (Always)
            print(f"[SyncEngine] Sending Heartbeat for Operator: {self.operator_name}")
            self.db_manager.update_operator_heartbeat(self.operator_name)

            # 2. Actor Heartbeat (If active session)
            session = self.server_ref.session_state
            active_actor = session.get("last_active_actor")
            last_ts = session.get("last_activity_ts")
            
            # Logic: Only heartbeat if active in last 5 minutes
            if active_actor and last_ts:
                delta = (datetime.now(timezone.utc) - last_ts).total_seconds()
                if delta < 300: # 5 minutes lease
                    print(f"[SyncEngine] Sending Heartbeat for Active Actor: {active_actor}")
                    self.db_manager.update_actor_heartbeat(active_actor, self.operator_name)
                else:
                    # Clear stale session
                    session["last_active_actor"] = None

        except Exception as e:
            print(f"[SyncEngine] Heartbeat failed: {e}")

    def _pull_governance_data(self, local_db: LocalDatabase):
        """
        Fetches the latest RULES and GOALS from Oracle and updates local cache.
        This is a full refresh strategy as these tables are small.
        """
        try:
            print("[SyncEngine] Pulling Governance Data (Rules & Goals)...")
            rules = self.db_manager.fetch_active_rules()
            goals = self.db_manager.fetch_active_goals()
            
            local_db.update_rules_cache(rules)
            local_db.update_goals_cache(goals)
            print(f"[SyncEngine] Governance updated: {len(rules)} Rules, {len(goals)} Goals.")
        except Exception as e:
            print(f"[SyncEngine] Governance Pull Error: {e}")

    def _push_local_events(self, local_db: LocalDatabase):
        """
        Pushes unsynced EVENT_LOGS and their children OUTREACH_LOGS to Cloud.
        Updates local records with the generated Cloud IDs.
        """
        try:
            unsynced = local_db.get_unsynced_events(limit=50) # Batch size 50
            if not unsynced:
                return

            print(f"[SyncEngine] Pushing {len(unsynced)} local events...")
            
            # Transform for Cloud DB (Oracle expects specific structure)
            # We need to resolve IDs here if they are still names
            events_to_push = []
            
            for event in unsynced:
                # Resolve IDs if missing (Self-healing)
                act_id = event['act_id']
                if not act_id.startswith('ACT-'):
                    # It's a username, try to resolve via Cloud DB cache or fetch
                    # For now, we let DatabaseManager handle resolution or insertion
                    pass

                events_to_push.append(event)

            # Bulk Push to Oracle
            # Returns mapping: {local_id: {'elg_id': 'ELG-...', 'tar_id': 'TAR-...'}}
            id_mapping = self.db_manager.push_events_batch(events_to_push)
            
            # Update Local DB with real IDs and mark synced
            if id_mapping:
                # Extract IDs that succeeded
                synced_ids = [k for k in id_mapping.keys()]
                local_db.mark_events_synced(synced_ids, id_mapping)
                print(f"[SyncEngine] Successfully synced {len(synced_ids)} events.")

        except Exception as e:
            print(f"[SyncEngine] Push Error: {e}")
            traceback.print_exc()

    def sync_cycle(self):
        """
        Execute a single sync cycle.
        1. Heartbeat
        2. Pull Governance (Rules/Goals)
        3. Push Events (Logs)
        """
        local_db = None
        try:
            local_db = LocalDatabase()
            
            # 1. Heartbeat (High Priority)
            self._send_heartbeat()

            # 2. Pull Governance
            self._pull_governance_data(local_db)

            # 3. Push Events
            self._push_local_events(local_db)

            # 4. Success Callback
            if self.on_update_callback:
                self.on_update_callback(True)

        except Exception as e:
            print(f"[SyncEngine] FATAL: Sync cycle failed: {e}")
            traceback.print_exc()
            if self.on_update_callback:
                self.on_update_callback(False)
        finally:
            if local_db:
                local_db.close()

    def _sync_loop(self):
        print("[SyncEngine] Background sync thread started.")
        while self.running:
            current_wait = self.interval
            try:
                with self._lock:
                    if self.running: 
                        self.sync_cycle()
                        # On success, reset failure count
                        if self.failure_count > 0:
                            print(f"[SyncEngine] Connection restored after {self.failure_count} failures.")
                            self.failure_count = 0
            except Exception as e:
                self.failure_count += 1
                backoff = min(self.interval * (2 ** self.failure_count), 300) # Max 5 mins
                current_wait = backoff
                print(f"[SyncEngine] Sync Error (Attempt {self.failure_count}): {e}")
                print(f"[SyncEngine] Backing off for {backoff} seconds...")
            
            # Smart sleep (interruptible)
            for _ in range(current_wait):
                if not self.running: break
                time.sleep(1)
        print("[SyncEngine] Background sync thread stopped.")

    def start(self):
        if self.running: return
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
