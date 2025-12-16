"""
Chrome Native Messaging Bridge for Insta Outreach Logger.

This script is the Native Host launched by Chrome via chrome.runtime.sendNativeMessage().
It acts as a lightweight proxy between Chrome (StdIO) and the IPC Server (Socket).

Data Flow:
    Chrome Extension -> StdIO -> Bridge -> Socket -> IPC Server -> LocalDatabase

Architecture Notes:
    - This script is spawned PER MESSAGE by Chrome (short-lived process)
    - It does NOT touch the database directly (prevents SQLite locking)
    - All data is forwarded to the Main App's IPC Server

AI Agent Note: This is Phase 3.4 - IPC Client (Bridge Update)
"""

import sys
import json
import struct
import os
import socket
import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ipc_protocol import (
    PORT,
    AUTH_KEY,
    send_msg,
    recv_msg,
    create_client_socket,
    create_auth_message
)


# =============================================================================
# Configuration
# =============================================================================

# Get the project root directory for logging
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
LOG_FILE_PATH = os.path.join(PROJECT_ROOT, 'debug_bridge.log')

# Enable/disable debug logging (set False for production)
DEBUG_LOGGING = True


# =============================================================================
# Debug Logging
# =============================================================================

def log_message(message: str):
    """
    Appends a message to the debug log file.

    Args:
        message: The message to log with timestamp.
    """
    if not DEBUG_LOGGING:
        return

    try:
        with open(LOG_FILE_PATH, 'a', encoding='utf-8') as f:
            timestamp = datetime.datetime.now().isoformat()
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass  # Fail silently - logging should never break the bridge


# =============================================================================
# Chrome Native Messaging Protocol (StdIO)
# =============================================================================

def read_from_chrome() -> dict:
    """
    Read a message from Chrome via stdin.

    Chrome Native Messaging Protocol:
        - First 4 bytes: message length (native byte order, unsigned int)
        - Remaining bytes: UTF-8 JSON message

    Returns:
        Parsed JSON message as dict.

    Raises:
        EOFError: If stdin is closed (Chrome disconnected).
    """
    # Read the 4-byte length header
    raw_length = sys.stdin.buffer.read(4)

    if len(raw_length) == 0:
        raise EOFError("Chrome disconnected (stdin closed)")

    if len(raw_length) < 4:
        raise ValueError(f"Incomplete length header: {len(raw_length)} bytes")

    # Unpack message length (native byte order)
    message_length = struct.unpack('@I', raw_length)[0]

    # Sanity check - prevent memory exhaustion
    if message_length > 1024 * 1024:  # 1MB max
        raise ValueError(f"Message too large: {message_length} bytes")

    # Read the message body
    message_bytes = sys.stdin.buffer.read(message_length)

    if len(message_bytes) < message_length:
        raise ValueError(f"Incomplete message: expected {message_length}, got {len(message_bytes)}")

    return json.loads(message_bytes.decode('utf-8'))


def send_to_chrome(data: dict):
    """
    Send a message to Chrome via stdout.

    Chrome Native Messaging Protocol:
        - First 4 bytes: message length (native byte order, unsigned int)
        - Remaining bytes: UTF-8 JSON message

    Args:
        data: Dictionary to serialize and send to Chrome.
    """
    # Serialize to JSON bytes
    encoded_content = json.dumps(data).encode('utf-8')

    # Pack length header (native byte order for Chrome compatibility)
    packed_length = struct.pack('@I', len(encoded_content))

    # Write to stdout
    sys.stdout.buffer.write(packed_length)
    sys.stdout.buffer.write(encoded_content)
    sys.stdout.buffer.flush()


# =============================================================================
# IPC Server Communication
# =============================================================================

def forward_to_server(message: dict) -> dict:
    """
    Forward a message to the IPC Server and return the response.

    Protocol:
        1. Connect to IPC Server
        2. Send AUTH message
        3. Receive AUTH response
        4. Send the actual message
        5. Receive response
        6. Close connection

    Args:
        message: The message to forward to the server.

    Returns:
        Server response dict.

    Raises:
        ConnectionRefusedError: If server is not running.
        Exception: For other communication errors.
    """
    sock = None

    try:
        # Step 1: Connect to IPC Server
        sock = create_client_socket(timeout=5.0)
        log_message(f"Connected to IPC Server on port {PORT}")

        # Step 2: Send authentication
        send_msg(sock, create_auth_message(AUTH_KEY))

        # Step 3: Receive auth response
        auth_response = recv_msg(sock, timeout=5.0)

        if not auth_response or not auth_response.get('success'):
            error_msg = auth_response.get('error', 'Authentication failed') if auth_response else 'No response'
            raise Exception(f"Auth failed: {error_msg}")

        log_message("Authentication successful")

        # Step 4: Send the actual message from Chrome
        send_msg(sock, message)

        # Step 5: Receive server response
        response = recv_msg(sock, timeout=10.0)

        if response is None:
            raise Exception("Server closed connection without response")

        log_message(f"Server response: {response}")
        return response

    finally:
        # Step 6: Always close the socket
        if sock:
            try:
                sock.close()
            except:
                pass


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """
    Main bridge loop - reads from Chrome, forwards to server, responds to Chrome.
    """
    log_message("=" * 50)
    log_message("Bridge process started")

    try:
        while True:
            # Read message from Chrome
            try:
                chrome_message = read_from_chrome()
                log_message(f"Received from Chrome: {chrome_message}")
            except EOFError:
                log_message("Chrome disconnected (EOF)")
                break
            except Exception as e:
                log_message(f"Error reading from Chrome: {e}")
                break

            # Forward to IPC Server
            try:
                server_response = forward_to_server(chrome_message)
                send_to_chrome(server_response)

            except ConnectionRefusedError:
                # IPC Server is not running
                log_message("ERROR: IPC Server is offline (connection refused)")
                send_to_chrome({
                    'status': 'error',
                    'success': False,
                    'message': 'Database Server Offline. Please start Insta Outreach Logger.'
                })

            except socket.timeout:
                log_message("ERROR: IPC Server timeout")
                send_to_chrome({
                    'status': 'error',
                    'success': False,
                    'message': 'Database Server timeout. Please check if Insta Outreach Logger is responding.'
                })

            except Exception as e:
                log_message(f"ERROR forwarding to server: {e}")
                send_to_chrome({
                    'status': 'error',
                    'success': False,
                    'message': f'Bridge error: {str(e)}'
                })

    except KeyboardInterrupt:
        log_message("Bridge interrupted by user")

    except Exception as e:
        log_message(f"FATAL ERROR: {e}")
        # Try to notify Chrome before dying
        try:
            send_to_chrome({
                'status': 'error',
                'success': False,
                'message': f'Bridge crashed: {str(e)}'
            })
        except:
            pass
        sys.exit(1)

    finally:
        log_message("Bridge process terminated")


# =============================================================================
# Script Entry Point
# =============================================================================

if __name__ == '__main__':
    main()
