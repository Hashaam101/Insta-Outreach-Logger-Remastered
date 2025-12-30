import os
import json
import base64
import hashlib
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

project_root = os.getcwd()
key_path = os.path.join(project_root, 'src', 'extension', 'key.pem')
manifest_path = os.path.join(project_root, 'src', 'extension', 'manifest.json')
nh_manifest_path = os.path.join(project_root, 'src', 'core', 'com.instaoutreach.logger.json')

def generate_key():
    print("Generating key...")
    # Generate Key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    
    # Save Private Key
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    with open(key_path, 'wb') as f:
        f.write(pem)
    print(f"Saved private key to {key_path}")

    # Get Public Key DER
    public_key = private_key.public_key()
    der_key = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    b64_key = base64.b64encode(der_key).decode('utf-8')

    # Update manifest.json
    if os.path.exists(manifest_path):
        with open(manifest_path, 'r') as f:
            data = json.load(f)
        data['key'] = b64_key
        with open(manifest_path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Updated {manifest_path} with key.")
    else:
        print(f"Error: {manifest_path} not found.")

    # Calculate ID
    sha = hashlib.sha256(der_key).hexdigest()
    prefix = sha[:32]
    ext_id = "".join([chr(ord('a') + int(char, 16)) for char in prefix])
    print(f"Extension ID: {ext_id}")

    # Update Native Host Manifest
    if os.path.exists(nh_manifest_path):
        with open(nh_manifest_path, 'r') as f:
            nh_data = json.load(f)
        nh_data['allowed_origins'] = [f"chrome-extension://{ext_id}/"]
        with open(nh_manifest_path, 'w') as f:
            json.dump(nh_data, f, indent=4)
        print(f"Updated {nh_manifest_path} with allowed_origins.")
    else:
        print(f"Error: {nh_manifest_path} not found.")

if __name__ == "__main__":
    generate_key()
