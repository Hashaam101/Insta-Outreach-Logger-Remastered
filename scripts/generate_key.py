
import base64
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def generate_key():
    # 1. Generate Private Key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # 2. Get Public Key in DER format
    public_key = private_key.public_key()
    der_key = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    # 3. Calculate Extension ID
    # SHA256 hash of DER public key
    sha = hashlib.sha256(der_key).hexdigest()
    # First 32 chars (16 bytes)
    prefix = sha[:32]
    # Convert hex (0-f) to (a-p)
    # 0->a, 1->b, ... f->p
    # Actually, the algorithm is:
    # 1. SHA256 of public key
    # 2. Take first 128 bits (16 bytes)
    # 3. Convert to base16 using 'a'-'p' alphabet
    
    ext_id = ""
    for char in prefix:
        val = int(char, 16)
        ext_id += chr(ord('a') + val)

    # 4. Base64 encode for manifest "key" field
    b64_key = base64.b64encode(der_key).decode('utf-8')

    with open("key_info.txt", "w") as f:
        f.write(f"EXTENSION_KEY={b64_key}\n")
        f.write(f"EXTENSION_ID={ext_id}\n")

if __name__ == "__main__":
    generate_key()
