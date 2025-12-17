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

# Define path for operator config
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
OPERATOR_CONFIG_PATH = os.path.join(project_root, 'operator_config.json')


class IPCServer:
    """
    Local IPC Server that receives outreach data from Chrome Bridge instances.
    It is the exclusive owner of the local SQLite DB connection.
    """

    def __init__(self):
        """Initialize the IPC Server, LocalDatabase, SyncEngine, and Operator identity."""
        self.operator_name = self._load_or_prompt_operator()
        self.db = LocalDatabase()
        # Pass operator name to SyncEngine for auto-discovery
        self.sync_engine = SyncEngine(operator_name=self.operator_name, sync_interval=60)
        self.server_socket = None
        self.running = False
        self._lock = threading.Lock()

    def _load_or_prompt_operator(self):
        """
        Loads the operator name from config, or prompts for it if not found.
        This establishes a persistent identity for the human user on this device.
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

        # If file doesn't exist, is invalid, or name is missing, prompt user.
        try:
            name = input(">> Enter Your Operator Name (e.g., 'John Doe'): ")
            while not name:
                print("Operator name cannot be empty.")
                name = input(">> Enter Your Operator Name (e.g., 'John Doe'): ")

            with open(OPERATOR_CONFIG_PATH, 'w') as f:
                json.dump({'operator_name': name}, f)
            
            print(f"[Config] Operator name '{name}' saved.")
            return name
        except Exception as e:
            print(f"Could not save operator config: {e}. Exiting.")
            exit(1)


    def handle_client(self, client_socket: socket.socket, client_addr: tuple):
        client_id = f"{client_addr[0]}:{client_addr[1]}"
        print(f"[IPC] Client connected: {client_id}")
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
                    send_msg(client_socket, response)
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
            client_socket.close()
            print(f"[IPC] Client {client_id} handler terminated")

    def _authenticate_client(self, client_socket: socket.socket, client_id: str) -> bool:
        # (Authentication logic remains the same)
        try:
            auth_msg = recv_msg(client_socket, timeout=10.0)
            if not auth_msg or auth_msg.get("action") != MessageType.AUTH or auth_msg.get("key", "") != AUTH_KEY.decode("utf-8"):
                print(f"[IPC] Client {client_id} failed authentication")
                send_msg(client_socket, create_error_response("Invalid AUTH_KEY"))
                return False
            send_msg(client_socket, create_ack_response(True, {"status": "authenticated"}))
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
                print(f"[IPC] Local HIT for {target}: {local_prospect.get('status')}")
                return create_ack_response(True, {
                    "contacted": True,
                    "status": local_prospect.get("status", "Cold_NoReply"),
                    "source": "local"
                })

            # If not found locally, check Oracle database via sync engine
            try:
                oracle_status = self.sync_engine.check_prospect_in_oracle(target)
                if oracle_status:
                    print(f"[IPC] Oracle HIT for {target}: {oracle_status}")
                    return create_ack_response(True, {
                        "contacted": True,
                        "status": oracle_status,
                        "source": "oracle"
                    })
            except Exception as e:
                print(f"[IPC] Oracle check failed for {target}: {e}")
                # Continue even if Oracle check fails - just return not found

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

            if not target or not new_status:
                return create_error_response("Missing 'target' or 'new_status' in UPDATE_PROSPECT_STATUS")

            # Get the old status before updating
            with self._lock:
                old_prospect = self.db.get_prospect(target)
            old_status = old_prospect.get("status", "New") if old_prospect else "New"

            print(f"[IPC] Updating prospect status: {target} ({old_status} -> {new_status})")

            # Update local SQLite database
            with self._lock:
                updated = self.db.update_prospect_status(target, new_status)

            if updated:
                print(f"[IPC] Local status updated for {target}: {new_status}")
            else:
                # If prospect doesn't exist locally, insert it
                print(f"[IPC] Prospect {target} not in local DB, will be synced via next outreach")

            # Log the status change event to outreach_logs (showing transition)
            status_change_log = {
                "target_username": target,
                "actor_username": actor,
                "message_snippet": f"[Status: {old_status} -> {new_status}]",
                "operator_name": self.operator_name
            }
            with self._lock:
                log_id = self.db.log_outreach(status_change_log)
            print(f"[IPC] Status change logged (ID: {log_id}) for {target}: {old_status} -> {new_status}")

            # Trigger sync engine to push update to Oracle
            try:
                self.sync_engine.update_prospect_status_in_oracle(target, new_status)
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