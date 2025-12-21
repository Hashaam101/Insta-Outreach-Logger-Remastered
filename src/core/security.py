import hmac
import hashlib
import secrets

# This key must be identical in both the compiled app and the dev script.
# In a real production scenario with high stakes, you might want to obfuscate this,
# but for this use case, a constant string is sufficient.
MASTER_SECRET_KEY = "IOL_SEC_KEY_v1_" + "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"

def generate_token():
    """Generate a random 8-character hex token."""
    return secrets.token_hex(4)

def get_zip_password(token: str) -> bytes:
    """
    Derive a password from the token using HMAC-SHA256 and the MASTER_SECRET_KEY.
    Returns bytes as required by pyzipper.
    """
    if not token:
        raise ValueError("Token cannot be empty")
        
    # Create HMAC
    h = hmac.new(
        MASTER_SECRET_KEY.encode('utf-8'),
        token.encode('utf-8'),
        hashlib.sha256
    )
    
    # Return the hex digest as bytes
    return h.hexdigest().encode('utf-8')
