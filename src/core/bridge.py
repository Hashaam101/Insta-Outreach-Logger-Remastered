#!/usr/bin/env python3
import sys
import struct
import json
import socket
import logging
import time
import os

# --- Configuration ---
# 1MB max message size
MAX_MSG_SIZE = 1024 * 1024
# IPC Port must match the server (ipc_protocol.py)
PORT = 12345
AUTH_KEY = b"SECRET_IPC_KEY_2024"  # Must match server

# Setup logging
try:
    from version import LOG_DIR
    log_dir = LOG_DIR
except ImportError:
    # Fallback if run standalone or path issues
    log_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'Insta Outreach Logger', 'logs')

os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, 'bridge.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def send_native_message(message_content):
    """
    Sends a message to the Chrome extension via stdout (Native Messaging).
    Format: [4 bytes length (little endian)][JSON string]
    """
    try:
        encoded_content = json.dumps(message_content).encode('utf-8')
        sys.stdout.buffer.write(struct.pack('I', len(encoded_content)))
        sys.stdout.buffer.write(encoded_content)
        sys.stdout.buffer.flush()
    except Exception as e:
        logging.error(f"Failed to send native message: {e}")

def read_native_message():
    """
    Reads a message from the Chrome extension via stdin (Native Messaging).
    Format: [4 bytes length][JSON string]
    """
    try:
        text_length_bytes = sys.stdin.buffer.read(4)
        if not text_length_bytes:
            return None
        text_length = struct.unpack('i', text_length_bytes)[0]
        
        if text_length > MAX_MSG_SIZE:
            logging.error(f"Message too large: {text_length}")
            return None
            
        text = sys.stdin.buffer.read(text_length).decode('utf-8')
        return json.loads(text)
    except Exception as e:
        logging.error(f"Failed to read native message: {e}")
        return None

def connect_to_ipc_server():
    """Establishes connection to the local Python IPC Server."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(('127.0.0.1', PORT))
        
        # Authenticate
        s.sendall(struct.pack('>I', len(AUTH_KEY) + 1)) # +1 for action byte
        s.sendall(b'\x01' + AUTH_KEY) # Action 0x01 = AUTH
        
        # Read Auth Response
        header = s.recv(4)
        if not header: return None
        length = struct.unpack('>I', header)[0]
        resp_bytes = s.recv(length)
        resp = json.loads(resp_bytes.decode('utf-8'))
        
        if resp.get('status') == 'ok':
            return s
        else:
            logging.error(f"Auth failed: {resp}")
            return None
    except Exception as e:
        logging.error(f"Could not connect to IPC Server: {e}")
        return None

def main():
    logging.info("Bridge started.")
    
    ipc_socket = None

    while True:
        # 1. Read from Chrome (Blocking)
        message = read_native_message()
        if not message:
            logging.info("Stdin closed, exiting.")
            break
            
        logging.info(f"Received from Chrome: {message}")
        
        # 2. Ensure IPC Connection
        if not ipc_socket:
            logging.info("Connecting to IPC Server...")
            ipc_socket = connect_to_ipc_server()
        
        if not ipc_socket:
            logging.error("Backend offline. Cannot forward message.")
            send_native_message({"status": "error", "message": "Application backend is offline. Please start InstaCRM Agent."})
            continue

        # 3. Forward to IPC
        try:
            msg_bytes = json.dumps(message).encode('utf-8')
            ipc_socket.sendall(struct.pack('>I', len(msg_bytes)))
            ipc_socket.sendall(msg_bytes)
            
            # 4. Read Response
            header = ipc_socket.recv(4)
            if not header:
                raise ConnectionResetError("Server closed connection")
                
            length = struct.unpack('>I', header)[0]
            resp_bytes = ipc_socket.recv(length)
            response = json.loads(resp_bytes.decode('utf-8'))
            
            logging.info(f"Response from IPC: {response}")
            send_native_message(response)
            
        except (ConnectionResetError, BrokenPipeError, socket.error) as e:
            logging.error(f"IPC Connection lost: {e}")
            ipc_socket.close()
            ipc_socket = None
            # Retry logic could be added here, but for now we inform the user
            send_native_message({"status": "error", "message": "Connection to backend lost. Please retry."})
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            send_native_message({"status": "error", "message": str(e)})

if __name__ == '__main__':
    # On Windows, set input/output to binary mode
    if sys.platform == "win32":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    
    main()