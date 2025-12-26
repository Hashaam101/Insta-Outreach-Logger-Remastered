import os
import sys
import shutil
import tempfile
import pyzipper
from unittest.mock import patch

# Add project root to path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from src.core.security import generate_token, get_zip_password
from src.core.secrets_manager import SecretsManager

def test_secrets_manager_flow():
    print("--- Starting Secrets Manager Test ---")
    
    # Use TemporaryDirectory for automatic cleanup
    with tempfile.TemporaryDirectory(prefix="test_docs_") as mock_docs_root:
        mock_secrets_dir = os.path.join(mock_docs_root, "Insta Logger Remastered", "secrets")
        os.makedirs(mock_secrets_dir)
        
        print(f"Mock Documents Dir: {mock_docs_root}")

        try:
            # 2. Create Dummy Files
            dummy_config_content = "DB_USER = 'test_user'\nDB_PASSWORD = 'test_pass'"
            dummy_wallet_content = b"fake wallet data"
            
            # 3. Create Secure Zip
            token = generate_token()
            password = get_zip_password(token)
            zip_name = f"Setup_Pack_{token}.zip"
            zip_path = os.path.join(mock_secrets_dir, zip_name)
            
            print(f"Generating Token: {token}")
            print(f"Zip Path: {zip_path}")

            with pyzipper.AESZipFile(zip_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(password)
                zf.writestr('local_config.py', dummy_config_content)
                zf.writestr('wallet/cwallet.sso', dummy_wallet_content)
                
            # 4. Patch SecretsManager to use our mock directory
            with patch('src.core.secrets_manager.SECRETS_DIR', mock_secrets_dir):
                
                # 5. Run Manager
                print("Initializing SecretsManager...")
                with SecretsManager() as secrets:
                    
                    # Check 1: Did it find the zip?
                    if secrets.zip_path != zip_path:
                        print(f"FAIL: Expected zip path {zip_path}, got {secrets.zip_path}")
                        return False
                    print("PASS: Zip found.")
                    
                    # Check 2: Did it decrypt and extract?
                    if not secrets.temp_dir or not os.path.exists(secrets.temp_dir):
                        print("FAIL: Temp dir not created.")
                        return False
                    
                    extracted_config = os.path.join(secrets.temp_dir, 'local_config.py')
                    extracted_wallet = os.path.join(secrets.temp_dir, 'wallet', 'cwallet.sso')
                    
                    if not os.path.exists(extracted_config):
                        print("FAIL: local_config.py not extracted.")
                        return False
                        
                    if not os.path.exists(extracted_wallet):
                        print("FAIL: wallet not extracted.")
                        return False
                        
                    print("PASS: Decryption and extraction successful.")
                    
                    # Check 3: Environment setup
                    if 'DB_WALLET_DIR' not in os.environ:
                        print("FAIL: DB_Wallet_DIR env var not set.")
                        return False
                        
                    if os.environ['DB_Wallet_DIR'] != os.path.join(secrets.temp_dir, 'wallet'):
                        print(f"FAIL: DB_Wallet_DIR mismatch. Got {os.environ['DB_Wallet_DIR']}")
                        return False
                        
                    print("PASS: Environment variable set.")
                    
                    # Check 4: Sys Path
                    if secrets.temp_dir not in sys.path:
                        print("FAIL: Temp dir not in sys.path")
                        return False
                        
                    # Try importing config
                    try:
                        import local_config
                        if local_config.DB_USER != 'test_user':
                            print("FAIL: Imported config has wrong values.")
                            return False
                    except ImportError as e:
                        print(f"FAIL: Could not import local_config: {e}")
                        return False
                        
                    print("PASS: sys.path setup and import successful.")

                # 6. Verify Cleanup
                print("Context exited. Verifying cleanup...")
                
                if secrets.temp_dir and os.path.exists(secrets.temp_dir):
                    print(f"FAIL: Temp dir {secrets.temp_dir} still exists.")
                    return False
                    
                if 'DB_Wallet_DIR' in os.environ:
                    print("FAIL: DB_Wallet_DIR still set.")
                    return False
                    
                print("PASS: Cleanup successful.")
                return True

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    if test_secrets_manager_flow():
        print("\n*** ALL TESTS PASSED ***")
        sys.exit(0)
    else:
        print("\n*** TEST FAILED ***")
        sys.exit(1)