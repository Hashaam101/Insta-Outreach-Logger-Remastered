"""
IPC Protocol Definition for Insta Outreach Logger.

This module defines the communication protocol between the Main App (Server)
and the Chrome Bridge instances (Clients). It uses TCP sockets with a simple
length-prefixed JSON message format.

Architecture:
    - Main App runs an IPC Server on localhost:PORT
    - Each bridge.py instance connects as a Client
    - Messages are JSON objects prefixed with a 4-byte length header

AI Agent Note: This is Phase 3 - The Brain (IPC Protocol)
"""

import struct
import json
import socket
from datetime import datetime
from typing import Optional, Any

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# =============================================================================
# Protocol Constants
# =============================================================================

# TCP port for local IPC communication
# Using a high port to avoid conflicts; localhost only for security
PORT = 65432

# Simple authentication key for basic security
# This prevents random processes from connecting to our IPC server
AUTH_KEY = b'insta_lead_secret_key'

# Maximum message size (1MB) to prevent memory exhaustion attacks
MAX_MESSAGE_SIZE = 1024 * 1024

# Header format: unsigned 4-byte integer (big-endian)
HEADER_FORMAT = ">I"
HEADER_SIZE = 4


# =============================================================================
# Message Types
# =============================================================================

class MessageType:
    """
    Enumeration of supported IPC message types.

    These define the 'action' field in JSON messages.
    """
    # Client -> Server
    AUTH = "auth"               # Authentication handshake
    LOG_OUTREACH = "log_outreach"  # Log a new DM message
    GET_PROSPECT = "get_prospect"  # Query prospect status
    UPDATE_STATUS = "update_status"  # Update prospect CRM status

    # Server -> Client
    ACK = "ack"                 # Success acknowledgment
    ERROR = "error"             # Error response
    DATA = "data"               # Data response (for queries)


# =============================================================================
# Protocol Functions
# =============================================================================

def send_msg(sock: socket.socket, msg: dict) -> bool:
    """
    Send a JSON message with a 4-byte length header.

    Protocol format:
        [4 bytes: message length (big-endian)] + [N bytes: JSON data (UTF-8)]

    Args:
        sock: Connected socket to send through.
        msg: Dictionary to serialize and send.

    Returns:
        True if sent successfully, False on error.

    Raises:
        ConnectionError: If the socket is disconnected.
    """
    try:
        # Serialize message to JSON bytes using the DateTimeEncoder
        data = json.dumps(msg, cls=DateTimeEncoder).encode("utf-8")

        # Check message size
        if len(data) > MAX_MESSAGE_SIZE:
            raise ValueError(f"Message too large: {len(data)} bytes")

        # Pack the length header
        header = struct.pack(HEADER_FORMAT, len(data))

        # Send header + data
        sock.sendall(header + data)
        return True

    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as e:
        raise ConnectionError(f"Socket disconnected: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to send message: {e}")


def recv_msg(sock: socket.socket, timeout: Optional[float] = None) -> Optional[dict]:
    """
    Receive a JSON message with a 4-byte length header.

    Protocol format:
        [4 bytes: message length (big-endian)] + [N bytes: JSON data (UTF-8)]

    Args:
        sock: Connected socket to receive from.
        timeout: Optional timeout in seconds. None = blocking.

    Returns:
        Parsed JSON dict, or None if connection closed cleanly.

    Raises:
        ConnectionError: If the socket is disconnected unexpectedly.
        ValueError: If the message is malformed or too large.
    """
    try:
        # Set timeout if specified
        if timeout is not None:
            sock.settimeout(timeout)

        # Read the 4-byte length header
        header_data = _recv_exact(sock, HEADER_SIZE)
        if header_data is None:
            return None  # Clean disconnect

        # Unpack the message length
        msg_length = struct.unpack(HEADER_FORMAT, header_data)[0]

        # Validate message size
        if msg_length > MAX_MESSAGE_SIZE:
            raise ValueError(f"Message too large: {msg_length} bytes")

        if msg_length == 0:
            return {}  # Empty message

        # Read the message body
        msg_data = _recv_exact(sock, msg_length)
        if msg_data is None:
            raise ConnectionError("Connection closed while reading message body")

        # Parse JSON
        return json.loads(msg_data.decode("utf-8"))

    except socket.timeout:
        raise TimeoutError("Socket receive timed out")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON message: {e}")


def _recv_exact(sock: socket.socket, num_bytes: int) -> Optional[bytes]:
    """
    Receive exactly num_bytes from the socket.

    Internal helper function that handles partial reads.

    Args:
        sock: Socket to read from.
        num_bytes: Exact number of bytes to read.

    Returns:
        The received bytes, or None if connection closed.
    """
    chunks = []
    bytes_received = 0

    while bytes_received < num_bytes:
        chunk = sock.recv(num_bytes - bytes_received)
        if not chunk:
            # Connection closed
            if bytes_received == 0:
                return None  # Clean close
            raise ConnectionError("Connection closed mid-message")

        chunks.append(chunk)
        bytes_received += len(chunk)

    return b"".join(chunks)


# =============================================================================
# Helper Functions for Message Building
# =============================================================================

def create_auth_message(auth_key: bytes = AUTH_KEY) -> dict:
    """
    Create an authentication message for the handshake.

    Args:
        auth_key: The authentication key to send.

    Returns:
        Dict ready to be sent via send_msg().
    """
    return {
        "action": MessageType.AUTH,
        "key": auth_key.decode("utf-8")
    }


def create_log_message(target_username: str, message_snippet: str) -> dict:
    """
    Create a log_outreach message.

    Args:
        target_username: The Instagram handle of the message recipient.
        message_snippet: The beginning of the sent message.

    Returns:
        Dict ready to be sent via send_msg().
    """
    return {
        "action": MessageType.LOG_OUTREACH,
        "target": target_username,
        "message": message_snippet
    }


def create_ack_response(success: bool = True, data: Any = None) -> dict:
    """
    Create an acknowledgment response.

    Args:
        success: Whether the operation succeeded.
        data: Optional data to include in the response.

    Returns:
        Dict ready to be sent via send_msg().
    """
    response = {
        "action": MessageType.ACK if success else MessageType.ERROR,
        "success": success
    }
    if data is not None:
        response["data"] = data
    return response


def create_error_response(error_message: str) -> dict:
    """
    Create an error response.

    Args:
        error_message: Description of what went wrong.

    Returns:
        Dict ready to be sent via send_msg().
    """
    return {
        "action": MessageType.ERROR,
        "success": False,
        "error": error_message
    }


# =============================================================================
# Connection Utilities
# =============================================================================

def create_client_socket(host: str = "127.0.0.1", port: int = PORT,
                         timeout: float = 5.0) -> socket.socket:
    """
    Create and connect a client socket to the IPC server.

    Args:
        host: Server hostname (default: localhost).
        port: Server port (default: PORT).
        timeout: Connection timeout in seconds.

    Returns:
        Connected socket ready for send_msg/recv_msg.

    Raises:
        ConnectionRefusedError: If the server is not running.
        TimeoutError: If the connection times out.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((host, port))
    sock.settimeout(None)  # Reset to blocking after connect
    return sock


def create_server_socket(host: str = "127.0.0.1", port: int = PORT,
                         backlog: int = 5) -> socket.socket:
    """
    Create and bind a server socket for the IPC server.

    Args:
        host: Bind address (default: localhost only for security).
        port: Listen port (default: PORT).
        backlog: Maximum queued connections.

    Returns:
        Bound and listening socket.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(backlog)
    return sock


# =============================================================================
# CLI Test
# =============================================================================

if __name__ == "__main__":
    import threading
    import time

    print("Testing IPC Protocol...")

    # Test server in a thread
    def run_test_server():
        server_sock = create_server_socket()
        print(f"[Server] Listening on port {PORT}")

        client_sock, addr = server_sock.accept()
        print(f"[Server] Client connected from {addr}")

        # Receive auth message
        msg = recv_msg(client_sock)
        print(f"[Server] Received: {msg}")

        # Send ack
        send_msg(client_sock, create_ack_response(True, {"status": "authenticated"}))

        # Receive log message
        msg = recv_msg(client_sock)
        print(f"[Server] Received: {msg}")

        # Send ack
        send_msg(client_sock, create_ack_response(True, {"log_id": 1}))

        client_sock.close()
        server_sock.close()

    # Start server thread
    server_thread = threading.Thread(target=run_test_server, daemon=True)
    server_thread.start()
    time.sleep(0.1)  # Let server start

    # Test client
    client_sock = create_client_socket()
    print("[Client] Connected to server")

    # Send auth
    send_msg(client_sock, create_auth_message())
    response = recv_msg(client_sock)
    print(f"[Client] Auth response: {response}")

    # Send log
    send_msg(client_sock, create_log_message("test_user", "Hey there!"))
    response = recv_msg(client_sock)
    print(f"[Client] Log response: {response}")

    client_sock.close()
    print("Test complete!")
