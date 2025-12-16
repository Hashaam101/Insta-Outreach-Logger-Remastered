import sys
import os

# Add the project root directory to Python's path so we can find local_config.py
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '../../'))
sys.path.insert(0, project_root)

try:
    import local_config
    import oracledb
except ImportError as e:
    print(f'Import Error: {e}')
    print('Ensure local_config.py exists in the project root.')
    sys.exit(1)

def test_connection():
    print('Attempting connection...')
    print(f'User: {local_config.DB_USER}')
    print(f'DSN: {local_config.DB_DSN}')
    
    try:
        # Initialize Oracle Client (Thick mode requires this, Thin mode does not but is safer)
        # oracledb.init_oracle_client(lib_dir=local_config.WALLET_PATH) # Uncomment if using Thick mode
        
        connection = oracledb.connect(
            user=local_config.DB_USER,
            password=local_config.DB_PASSWORD,
            dsn=local_config.DB_DSN,
            config_dir=os.path.join(project_root, 'assets', 'wallet'), 
            wallet_location=os.path.join(project_root, 'assets', 'wallet'),
            wallet_password=local_config.DB_PASSWORD  # Usually wallet pass is same as DB pass for ATP
        )
        
        print('✅ Connected successfully!')
        print('Server Version:', connection.version)
        
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM OPERATORS')
        rows = cursor.fetchall()
        print(f'Found {len(rows)} operators: {rows}')
        
        connection.close()
        
    except oracledb.Error as e:
        error_obj = e.args[0]
        print(f'❌ Connection Failed: {error_obj.message}')

if __name__ == '__main__':
    test_connection()