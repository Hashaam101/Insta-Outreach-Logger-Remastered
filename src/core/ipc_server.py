"""
IPC Server for Insta Outreach Logger.
This is the "Main Process" of the application backend. It runs continuously
in the background, listening for data from Chrome Extension instances.
It is responsible for establishing the OPERATOR identity for the device.
"""

import socket
import threading
import json
import traceback
import os
import sys
from datetime import datetime, timezone

# Add the current directory to path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from local_db import LocalDatabase
from sync_engine import SyncEngine
from ipc_protocol import (
    PORT,
    AUTH_KEY,
    recv_msg,
    send_msg,
    create_ack_response,
    create_error_response,
    MessageType
)

# Define path for operator config - handle both frozen (PyInstaller) and dev environments
if getattr(sys, 'frozen', False):
    # Running as compiled exe - config is in the exe directory
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    # Running as script - config is in project root (2 levels up from src/core/)
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))

OPERATOR_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'operator_config.json')


class IPCServer:
    """
    Local IPC Server that receives outreach data from Chrome Bridge instances.
    It is the exclusive owner of the local SQLite DB connection.
    """

    def __init__(self):
        """Initialize the IPC Server, LocalDatabase, SyncEngine, and Operator identity."""
        self.operator_name = self._load_or_prompt_operator()
        self.db = LocalDatabase()
        # Pass operator name to SyncEngine for auto-discovery, and register broadcast callback
        self.sync_engine = SyncEngine(
            operator_name=self.operator_name, 
            sync_interval=60,
            on_update_callback=self.broadcast_sync_event
        )
        self.server_socket = None
        self.running = False
        self._lock = threading.Lock()
        self.oracle_check_cache = {} # Negative cache for Oracle lookups: {username: timestamp_iso}
        
        # Client management for broadcasting
        self.active_clients = {} # {client_id: {'socket': sock, 'lock': threading.Lock()}}
        self.clients_lock = threading.Lock() # Protects the active_clients dict itself

    def _load_or_prompt_operator(self):
        """
        Loads the operator name from config.
        Identity must be established via the Setup Wizard.
        """
        if os.path.exists(OPERATOR_CONFIG_PATH):
            try:
                with open(OPERATOR_CONFIG_PATH, 'r') as f:
                    config = json.load(f)
                    name = config.get('operator_name')
                    if name:
                        print(f"[Config] Operator Loaded: {name}")
                        return name
            except (json.JSONDecodeError, IOError) as e:
                print(f"[Config] Error reading operator_config.json: {e}")

        # If file doesn't exist, is invalid, or name is missing, we cannot continue in CLI mode.
        raise RuntimeError("Operator identity not established. Please run the Setup Wizard.")

    def _register_client(self, client_id, client_socket):
        with self.clients_lock:
            self.active_clients[client_id] = {
                'socket': client_socket,
                'lock': threading.Lock()
            }
    
    def _unregister_client(self, client_id):
        with self.clients_lock:
            if client_id in self.active_clients:
                del self.active_clients[client_id]

    def _send_to_client(self, client_id, message):
        """Thread-safe send to a specific client."""
        client_info = None
        with self.clients_lock:
            client_info = self.active_clients.get(client_id)
        
        if client_info:
            with client_info['lock']:
                try:
                    send_msg(client_info['socket'], message)
                    return True
                except Exception as e:
                    print(f"[IPC] Error sending to {client_id}: {e}")
                    return False
        return False

    def broadcast_sync_event(self):
        """
        Called by SyncEngine when new data is pulled.
        Broadcasts a 'SYNC_COMPLETED' message to all connected clients.
        """
        print("[IPC] Broadcasting SYNC_COMPLETED to all clients...")
        msg = {"type": "SYNC_COMPLETED"}
        
        # Snapshot keys to avoid holding lock during iteration
        with self.clients_lock:
            client_ids = list(self.active_clients.keys())
            
        for cid in client_ids:
            self._send_to_client(cid, msg)

    def handle_client(self, client_socket: socket.socket, client_addr: tuple):
        client_id = f"{client_addr[0]}:{client_addr[1]}"
        print(f"[IPC] Client connected: {client_id}")
        
        self._register_client(client_id, client_socket)
        
        try:
            if not self._authenticate_client(client_socket, client_id):
                return
            while self.running:
                try:
                    msg = recv_msg(client_socket, timeout=30.0)
                    if msg is None:
                        print(f"[IPC] Client {client_id} disconnected cleanly")
                        break
                    response = self._process_message(msg, client_id)
                    # Use thread-safe sender
                    self._send_to_client(client_id, response)
                except TimeoutError:
                    continue
                except ConnectionError as e:
                    print(f"[IPC] Client {client_id} connection lost: {e}")
                    break
                except Exception as e:
                    print(f"[IPC] Error processing message from {client_id}: {e}")
                    traceback.print_exc()
                    break
        finally:
            self._unregister_client(client_id)
            client_socket.close()
            print(f"[IPC] Client {client_id} handler terminated")

    def _authenticate_client(self, client_socket: socket.socket, client_id: str) -> bool:
        # (Authentication logic remains the same)
        try:
            auth_msg = recv_msg(client_socket, timeout=10.0)
            if not auth_msg or auth_msg.get("action") != MessageType.AUTH or auth_msg.get("key", "") != AUTH_KEY.decode("utf-8"):
                print(f"[IPC] Client {client_id} failed authentication")
                self._send_to_client(client_id, create_error_response("Invalid AUTH_KEY"))
                return False
            self._send_to_client(client_id, create_ack_response(True, {"status": "authenticated"}))
            print(f"[IPC] Client {client_id} authenticated successfully")
            return True
        except Exception as e:
            print(f"[IPC] Auth error for {client_id}: {e}")
            return False

    def _process_message(self, msg: dict, client_id: str) -> dict:
        msg_type = msg.get("type") or msg.get("action", "").upper()
        request_id = msg.get("requestId")  # For response routing

        if msg_type == "LOG_OUTREACH":
            response = self._handle_log_outreach(msg, client_id)
        elif msg_type == "CHECK_PROSPECT_STATUS":
            response = self._handle_check_prospect_status(msg, client_id)
        elif msg_type == "UPDATE_PROSPECT_STATUS":
            response = self._handle_update_prospect_status(msg, client_id)
        elif msg_type == "PING":
            response = {"status": "ok", "type": "PONG"}
        else:
            response = create_error_response(f"Unknown message type: {msg_type}")

        # Include requestId in response for routing
        if request_id:
            response["requestId"] = request_id
        return response

    def _handle_log_outreach(self, msg: dict, client_id: str) -> dict:
        """
        Handle LOG_OUTREACH message, enrich it with operator/actor data, and
        save it to the local DB queue.
        """
        try:
            payload = msg.get("payload", msg)
            target = payload.get("target")
            actor = payload.get("actor") # Actor is now sent from the extension
            message = payload.get("message", "")

            if not target or not actor:
                return create_error_response("Missing 'target' or 'actor' in LOG_OUTREACH")

            # Check if prospect is excluded
            with self._lock:
                local_prospect = self.db.get_prospect(target)
            
            if local_prospect and local_prospect.get('status') == 'Excluded':
                print(f"[IPC] Skipping log for EXCLUDED prospect: {target}")
                return create_ack_response(False, {"message": "Prospect is excluded from logging", "is_excluded": True})

            # Enrich the log with the Operator's identity
            enriched_log = {
                "target_username": target,
                "actor_username": actor,
                "message_snippet": message,
                "operator_name": self.operator_name # Inject the Operator
            }

            # Thread-safe write to the local database queue
            with self._lock:
                log_id = self.db.log_outreach(enriched_log)

            print(f"[IPC] Queued outreach from Operator '{self.operator_name}' via Actor '{actor}': to {target}")
            return create_ack_response(True, {"log_id": log_id})

        except Exception as e:
            print(f"[IPC] Error logging outreach: {e}")
            traceback.print_exc()
            return create_error_response(f"Database error: {e}")

    def _handle_check_prospect_status(self, msg: dict, client_id: str) -> dict:
        """
        Handle CHECK_PROSPECT_STATUS message. Checks local DB first, then Oracle.
        Returns the prospect's status if they've been contacted before.
        """
        try:
            payload = msg.get("payload", msg)
            target = payload.get("target")

            if not target:
                return create_error_response("Missing 'target' in CHECK_PROSPECT_STATUS")

            print(f"[IPC] Checking prospect status for: {target}")

            # First check local SQLite database
            with self._lock:
                local_prospect = self.db.get_prospect(target)

            if local_prospect:
                # Self-Healing: If local record is missing owner_actor, try to fetch from Oracle
                # Only do this if we haven't checked recently (simple negative cache check for this specific flow?)
                # For now, we just check.
                should_check_oracle = False
                if not local_prospect.get("owner_actor"):
                     print(f"[IPC] Local HIT for {target} but missing owner_actor. Attempting self-heal via Oracle...")
                     should_check_oracle = True
                
                if not should_check_oracle:
                    print(f"[IPC] Local HIT for {target}: {local_prospect.get('status')}")
                    return create_ack_response(True, {
                        "contacted": True,
                        "status": local_prospect.get("status", "Cold_NoReply"),
                        "owner_actor": local_prospect.get("owner_actor"),
                        "last_updated": local_prospect.get("last_updated"),
                        "notes": local_prospect.get("notes"),
                        "source": "local"
                    })

            # Check Negative Cache (Optimization)
            # ... (rest of logic)

            # Check Negative Cache (Optimization)
            last_check_ts = self.oracle_check_cache.get(target)
            last_sync_ts = self.sync_engine.get_last_sync_time_memory()

            if last_check_ts and last_sync_ts:
                # If we checked Oracle AFTER the last sync occurred, the result hasn't changed.
                if last_check_ts > last_sync_ts:
                    print(f"[IPC] Optimization: Skipping Oracle check for {target} (Checked at {last_check_ts} > Synced at {last_sync_ts})")
                    return create_ack_response(True, {
                        "contacted": False,
                        "source": "negative_cache"
                    })

            # If not found locally, check Oracle database via sync engine
            try:
                # Store the time of this check (BEFORE the call, to be safe/conservative)
                check_time = datetime.now(timezone.utc).isoformat()
                
                oracle_data = self.sync_engine.check_prospect_in_oracle(target)
                
                # Update Negative Cache regardless of result (we checked!)
                self.oracle_check_cache[target] = check_time

                if oracle_data and isinstance(oracle_data, dict):
                    # Expecting dict from new SyncEngine/DatabaseManager if found
                    status = oracle_data.get('status')
                    # Update local cache so next time it's a Local HIT
                    with self._lock:
                        # We construct a prospect dict to pass to sync_prospects_from_cloud
                        # Note: sync_prospects_from_cloud expects a list
                         self.db.sync_prospects_from_cloud([oracle_data])

                    print(f"[IPC] Oracle HIT for {target}: {status}")
                    return create_ack_response(True, {
                        "contacted": True,
                        "status": status,
                        "owner_actor": oracle_data.get("owner_actor"),
                        "last_updated": oracle_data.get("last_updated"),
                        "notes": oracle_data.get("notes"),
                        "source": "oracle"
                    })
                elif oracle_data and isinstance(oracle_data, str):
                    # Backward compatibility if it returns just a status string
                    print(f"[IPC] Oracle HIT for {target}: {oracle_data} (Legacy String)")
                     # We can't easily sync to local DB without full object, so just return it
                    return create_ack_response(True, {
                        "contacted": True,
                        "status": oracle_data,
                        "source": "oracle_legacy"
                    })

            except Exception as e:
                print(f"[IPC] Oracle check failed for {target}: {e}")
                # Continue even if Oracle check fails - just return not found

            # CRITICAL FALLBACK: If we had a local prospect but forced an Oracle check (self-healing)
            # and it FAILED (or wasn't found in Oracle), we MUST return the local data.
            # Otherwise, we tell the user "Not Contacted" when they ARE contacted locally.
            if 'local_prospect' in locals() and local_prospect:
                print(f"[IPC] Self-healing failed (Oracle miss/error). Returning degraded local data for {target}.")
                return create_ack_response(True, {
                    "contacted": True,
                    "status": local_prospect.get("status", "Cold_NoReply"),
                    "owner_actor": local_prospect.get("owner_actor"), # Will be None/Unknown
                    "last_updated": local_prospect.get("last_updated"), # Should be present
                    "notes": local_prospect.get("notes"),
                    "source": "local_degraded"
                })

            print(f"[IPC] MISS for {target} - not contacted before")
            return create_ack_response(True, {
                "contacted": False,
                "source": "none"
            })

        except Exception as e:
            print(f"[IPC] Error checking prospect status: {e}")
            traceback.print_exc()
            return create_error_response(f"Error checking status: {e}")

    def _handle_update_prospect_status(self, msg: dict, client_id: str) -> dict:
        """
        Handle UPDATE_PROSPECT_STATUS message. Updates the prospect's status
        in both local DB and Oracle, and logs the status change event.
        """
        try:
            payload = msg.get("payload", msg)
            target = payload.get("target")
            new_status = payload.get("new_status")
            actor = payload.get("actor", "unknown_actor")
            notes = payload.get("notes") # Extract notes

            if not target or not new_status:
                return create_error_response("Missing 'target' or 'new_status' in UPDATE_PROSPECT_STATUS")

            # Get the old status before updating
            with self._lock:
                old_prospect = self.db.get_prospect(target)
            old_status = old_prospect.get("status", "New") if old_prospect else "New"

            print(f"[IPC] Updating prospect status: {target} ({old_status} -> {new_status}) Notes: {'Yes' if notes else 'No'}")

            # Update local SQLite database
            with self._lock:
                # Pass notes to local DB
                updated = self.db.update_prospect_status(target, new_status, notes=notes)

            if updated:
                print(f"[IPC] Local status updated for {target}: {new_status}")
            else:
                # If prospect doesn't exist locally, insert it
                print(f"[IPC] Prospect {target} not in local DB, will be synced via next outreach")

            # Log the status change event to outreach_logs (showing transition)
            status_change_log = {
                "target_username": target,
                "actor_username": actor,
                "message_snippet": f"[Status: {old_status} -> {new_status}]" + (f" [Note: {notes}]" if notes else ""),
                "operator_name": self.operator_name
            }
            with self._lock:
                log_id = self.db.log_outreach(status_change_log)
            print(f"[IPC] Status change logged (ID: {log_id}) for {target}: {old_status} -> {new_status}")

            # Trigger sync engine to push update to Oracle
            try:
                # Pass notes to Sync Engine
                self.sync_engine.update_prospect_status_in_oracle(target, new_status, notes=notes)
                print(f"[IPC] Oracle status update queued for {target}")
            except Exception as e:
                print(f"[IPC] Oracle update failed for {target}: {e}")
                # Continue even if Oracle fails - local update is still valid

            return create_ack_response(True, {"success": True})

        except Exception as e:
            print(f"[IPC] Error updating prospect status: {e}")
            traceback.print_exc()
            return create_error_response(f"Error updating status: {e}")

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind(("127.0.0.1", PORT))
            self.server_socket.listen(5)
            self.running = True
            self.sync_engine.start()
            print(f"[IPC] Insta Outreach Logger IPC Server running on port {PORT}...")
            while self.running:
                try:
                    client_socket, client_addr = self.server_socket.accept()
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_addr),
                        daemon=True
                    )
                    client_thread.start()
                except socket.error:
                    if self.running: print(f"[IPC] Socket error during accept")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        if self.sync_engine: self.sync_engine.stop()
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None
        if self.db: self.db.close()
        print("[IPC] Server stopped")

if __name__ == "__main__":
    print("=" * 50)
    print("  Insta Outreach Logger (Remastered) - IPC Server")
    print("=" * 50)
    server = IPCServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[IPC] Shutdown requested...")
    finally:
        server.stop()