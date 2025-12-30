"""
IPC Server for InstaCRM Ecosystem.
This is the "Main Process" of the application backend. It runs continuously
in the background, listening for data from Chrome Extension instances.
It is responsible for establishing the OPERATOR identity for the device.

Updated for Phase 4: Event Logs & Pre-Flight Checks
Updated for Phase 2: Session State & Active Actor Tracking
Updated for Feature: Auto Tab Switcher
"""

import socket
import threading
import json
import traceback
import os
import sys
import time
from datetime import datetime, timezone
import pyautogui

# Add the current directory to path for sibling imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from local_db import LocalDatabase
from sync_engine import SyncEngine
from contact_discovery import ContactDiscoverer
from security import PreFlightChecker
from input_validation import (
    validate_outreach_log,
    validate_prospect_status,
    validate_payload_size,
    sanitize_username
)
from ipc_protocol import (
    PORT,
    AUTH_KEY,
    recv_msg,
    send_msg,
    create_ack_response,
    create_error_response,
    MessageType,
    generate_challenge,
    verify_response,
    create_challenge_message,
    RateLimiter
)

# Define path for operator config - handle both frozen (PyInstaller) and dev environments
if getattr(sys, 'frozen', False):
    # Running as compiled exe - config is in the exe directory
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    # Running as script - config is in project root (2 levels up from src/core/)
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))

OPERATOR_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'operator_config.json')
USER_PREFS_PATH = os.path.join(PROJECT_ROOT, 'user_preferences.json')

class IPCServer:
    """
    Local IPC Server that receives outreach data from Chrome Bridge instances.
    It is the exclusive owner of the local SQLite DB connection.
    """

    def __init__(self):
        """Initialize the IPC Server, LocalDatabase, SyncEngine, and Operator identity."""
        self.operator_name = self._load_or_prompt_operator()
        self.db = LocalDatabase()
        self.checker = PreFlightChecker(self.db)
        
        # Session State for Heartbeats
        self.session_state = {
            "last_active_actor": None,
            "last_activity_ts": datetime.now(timezone.utc)
        }
        
        # Auto Switch State
        self.session_outreach_count = 0
        
        # Rate limiter for authentication
        self.rate_limiter = RateLimiter(max_attempts=5, window_seconds=300)
        
        # Pass server reference to SyncEngine so it can read session_state
        self.sync_engine = SyncEngine(
            server_ref=self,
            operator_name=self.operator_name, 
            sync_interval=60,
            on_update_callback=self.broadcast_sync_event
        )
        self.server_socket = None
        self.running = False
        self._lock = threading.Lock()
        
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

    def _load_user_prefs(self):
        if os.path.exists(USER_PREFS_PATH):
            try:
                with open(USER_PREFS_PATH, 'r') as f:
                    return json.load(f)
            except: pass
        return {}

    def _trigger_auto_switch(self, delay: float):
        """Executes the Auto Tab Switch logic in a thread."""
        import ctypes
        try:
            time.sleep(delay)
            
            # Safety Check: Is Chrome/Instagram active?
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            
            if "Chrome" not in title and "Instagram" not in title:
                print(f"[Auto] Skipped: Chrome not in focus (Active: {title})")
                return

            print("[Auto] Triggering Tab Switch (Ctrl+W -> Ctrl+Tab)...")
            pyautogui.hotkey('ctrl', 'w')
            time.sleep(0.3)
            pyautogui.hotkey('ctrl', 'tab')
        except Exception as e:
            print(f"[Auto] Error in auto switch: {e}")

    def _update_active_actor(self, actor_handle: str):
        """Updates the session state with the currently active actor."""
        if actor_handle:
            self.session_state["last_active_actor"] = actor_handle
            self.session_state["last_activity_ts"] = datetime.now(timezone.utc)

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

    def broadcast_sync_event(self, success=True):
        """
        Called by SyncEngine when sync cycle completes.
        Broadcasts a 'SYNC_COMPLETED' message to all clients if successful.
        """
        if success:
            print("[IPC] Broadcasting SYNC_COMPLETED to all clients...")
            print("[SYNC] Status: OK")
            msg = {"type": "SYNC_COMPLETED"}
            
            # Snapshot keys to avoid holding lock during iteration
            with self.clients_lock:
                client_ids = list(self.active_clients.keys())
                
            for cid in client_ids:
                self._send_to_client(cid, msg)
        else:
            print("[SYNC] Status: Error")

    def _run_background_discovery(self, profile_id, profile_data):
        """Runs the Contact Discovery module in a background thread."""
        try:
            discoverer = ContactDiscoverer()
            print(f"[Discovery] Starting background discovery for {profile_id}...")
            
            result = discoverer.process_profile(profile_data)
            
            if result and (result.get('email') or result.get('phone_number')):
                print(f"[Discovery] Found contact info for {profile_id}: {result}")
                # Placeholder for writing discovery results to DB
                # self.db.update_prospect_contact_info(profile_id, ...)
            else:
                print(f"[Discovery] No contact info found for {profile_id}.")
        except Exception as e:
            print(f"[Discovery] Error processing {profile_id}: {e}")
            traceback.print_exc()

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
        """
        Enhanced authentication using HMAC challenge-response.
        
        Args:
            client_socket: The client socket.
            client_id: Identifier for the client.
        
        Returns:
            True if authentication succeeds, False otherwise.
        """
        try:
            # Check rate limit
            if not self.rate_limiter.is_allowed(client_id):
                print(f"[IPC] Client {client_id} rate limited")
                self._send_to_client(client_id, create_error_response("Rate limited. Try again later."))
                return False
            
            # Generate and send challenge
            challenge = generate_challenge()
            send_msg(client_socket, create_challenge_message(challenge))
            
            # Receive response
            auth_msg = recv_msg(client_socket, timeout=10.0)
            
            if not auth_msg or auth_msg.get("action") != MessageType.AUTH:
                print(f"[IPC] Client {client_id} sent invalid auth message")
                self.rate_limiter.record_attempt(client_id, False)
                self._send_to_client(client_id, create_error_response("Invalid authentication"))
                return False
            
            # Verify response
            response = auth_msg.get("response", "")
            if not verify_response(challenge, response, AUTH_KEY):
                print(f"[IPC] Client {client_id} failed authentication")
                self.rate_limiter.record_attempt(client_id, False)
                self._send_to_client(client_id, create_error_response("Invalid credentials"))
                return False
            
            # Success
            self.rate_limiter.record_attempt(client_id, True)
            self._send_to_client(client_id, create_ack_response(True, {"status": "authenticated"}))
            print(f"[IPC] Client {client_id} authenticated successfully")
            return True
            
        except Exception as e:
            print(f"[IPC] Auth error for {client_id}: {e}")
            self.rate_limiter.record_attempt(client_id, False)
            return False

    def _process_message(self, msg: dict, client_id: str) -> dict:
        msg_type = msg.get("type") or msg.get("action", "").upper()
        request_id = msg.get("requestId")

        # Global Session Activity Update
        # If the message contains an 'actor', we update our session tracking
        payload = msg.get("payload", msg)
        if isinstance(payload, dict) and payload.get("actor"):
            self._update_active_actor(payload.get("actor"))

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

        if request_id:
            response["requestId"] = request_id
        return response

    def _handle_log_outreach(self, msg: dict, client_id: str) -> dict:
        """
        Handle LOG_OUTREACH message.
        1. Validate and sanitize inputs.
        2. Perform Pre-Flight Safety Checks.
        3. Log Event to Local DB.
        4. Check Auto Tab Switcher Trigger.
        """
        try:
            payload = msg.get("payload", msg)
            
            # Validate payload size
            is_valid, error = validate_payload_size(payload)
            if not is_valid:
                return create_error_response(error)
            
            # Validate and sanitize outreach log data
            is_valid, error, sanitized_payload = validate_outreach_log(payload)
            if not is_valid:
                return create_error_response(f"Validation error: {error}")
            
            target = sanitized_payload['target']
            actor = sanitized_payload['actor']
            message = sanitized_payload.get('message', '')
            
            act_id = actor # Temp: Use username as ID locally until sync resolves it
            opr_id = self.operator_name # Temp

            # --- 1. PRE-FLIGHT CHECK ---
            with self._lock:
                safety_check = self.checker.check_safety_rules(act_id, opr_id)
            
            if not safety_check['allowed']:
                return create_error_response(f"Blocked: {safety_check['message']}")

            # --- 2. LOG EVENT ---
            log_data = {
                "target_username": target,
                "actor_username": actor,
                "message_text": message if message else None,
                "operator_name": self.operator_name,
                "act_id": act_id,
                "opr_id": opr_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            with self._lock:
                # Privacy Check: Don't log messages for Paid/Clients/Excluded
                prospect = self.db.get_prospect(target)
                current_status = prospect.get('status') if prospect else 'new'
                if current_status in ['Excluded', 'Tableturnerr Client', 'Paid']:
                    print(f"[IPC] Protected status '{current_status}' detected. Message text will not be logged.")
                    log_data['message_text'] = None
                
                log_id = self.db.log_event('Outreach', log_data)
                
                # Increment Session Count
                self.session_outreach_count += 1

            # --- 3. AUTO SWITCHER CHECK ---
            prefs = self._load_user_prefs()
            if prefs.get('auto_tab_switch', False):
                freq = prefs.get('tab_switch_frequency', 1)
                delay = prefs.get('tab_switch_delay', 2.0)
                
                if self.session_outreach_count % freq == 0:
                    threading.Thread(target=self._trigger_auto_switch, args=(delay,), daemon=True).start()

            # Trigger background discovery
            raw_profile_data = payload.get("profile_data", {})
            if raw_profile_data:
                discovery_data = {
                    "target_username": target,
                    "name": raw_profile_data.get("fullName"),
                    "bio_link": raw_profile_data.get("externalLink"),
                    "biography": raw_profile_data.get("bio")
                }
                threading.Thread(
                    target=self._run_background_discovery, 
                    args=(target, discovery_data), 
                    daemon=True
                ).start()

            response_data = {"log_id": log_id}
            if safety_check['status'] == 'WARN':
                response_data['warning'] = safety_check['message']
                
            return create_ack_response(True, response_data)

        except Exception as e:
            print(f"[IPC] Error logging outreach: {e}")
            traceback.print_exc()
            return create_error_response(f"Database error: {e}")

    def _handle_check_prospect_status(self, msg: dict, client_id: str) -> dict:
        """Handle CHECK_PROSPECT_STATUS message."""
        try:
            payload = msg.get("payload", msg)
            
            # Validate payload size
            is_valid, error = validate_payload_size(payload)
            if not is_valid:
                return create_error_response(error)
            
            # Validate and sanitize prospect status query
            is_valid, error, sanitized_payload = validate_prospect_status(payload)
            if not is_valid:
                return create_error_response(f"Validation error: {error}")
            
            target = sanitized_payload['target']

            with self._lock:
                local_prospect = self.db.get_prospect(target)

            if local_prospect:
                return create_ack_response(True, {
                    "contacted": True,
                    "status": local_prospect.get("status", "Cold No Reply"),
                    "owner_actor": local_prospect.get("owner_actor"),
                    "last_updated": local_prospect.get("last_updated"),
                    "notes": local_prospect.get("notes"),
                    "source": "local"
                })

            return create_ack_response(True, {
                "contacted": False,
                "source": "local_miss"
            })

        except Exception as e:
            return create_error_response(f"Local DB error: {e}")

    def _handle_update_prospect_status(self, msg: dict, client_id: str) -> dict:
        """Handle UPDATE_PROSPECT_STATUS message."""
        try:
            payload = msg.get("payload", msg)
            target = payload.get("target")
            new_status = payload.get("new_status")
            actor = payload.get("actor", "unknown_actor")

            if not target or not new_status:
                return create_error_response("Missing 'target' or 'new_status'")

            # Determine Event Type and Message
            protected_statuses = ['Excluded', 'Tableturnerr Client', 'Paid']
            
            if new_status == 'Excluded':
                event_type = 'Tar Exception Toggle'
                message_text = None 
                details = json.dumps({'target_username': target, 'status_change': 'Excluded'})
            elif new_status in protected_statuses:
                event_type = 'Change in Tar Info'
                message_text = None 
                details = json.dumps({'target_username': target, 'status_change': new_status})
            else:
                event_type = 'Change in Tar Info'
                message_text = f"Status updated to: {new_status}" # Log text for non-protected
                details = json.dumps({'target_username': target, 'status_change': new_status})

            log_data = {
                "target_username": target,
                "actor_username": actor,
                "message_text": message_text,
                "operator_name": self.operator_name,
                "act_id": actor, # Temp
                "opr_id": self.operator_name, # Temp
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

            with self._lock:
                # Update local cache first
                self.db.update_prospect_status(target, new_status)
                # Log the event
                self.db.log_event(event_type, log_data)

            return create_ack_response(True, {"success": True})

        except Exception as e:
            return create_error_response(f"Update failed: {e}")

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind(("127.0.0.1", PORT))
            self.server_socket.listen(5)
            self.running = True
            self.sync_engine.start() # Start SyncEngine
            print(f"[IPC] InstaCRM IPC Server running on port {PORT}...")
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
    print("  InstaCRM Ecosystem - IPC Server")
    print("=" * 50)
    server = IPCServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[IPC] Shutdown requested...")
    finally:
        server.stop()
