"""
Pytest configuration and shared fixtures for InstaCRM tests.
"""

import pytest
import os
import sys
import tempfile
import sqlite3
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Initialize database schema
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS event_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            act_id TEXT,
            opr_id TEXT,
            tar_id TEXT,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prospects (
            tar_id TEXT PRIMARY KEY,
            tar_username TEXT UNIQUE NOT NULL,
            status TEXT,
            owner_actor TEXT,
            first_contacted TEXT,
            last_updated TEXT,
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rules (
            rule_id INTEGER PRIMARY KEY,
            rule_name TEXT,
            rule_type TEXT,
            metric TEXT,
            limit_value INTEGER,
            time_window_sec INTEGER,
            severity TEXT,
            is_active INTEGER DEFAULT 1,
            assigned_to_opr TEXT,
            assigned_to_act TEXT
        )
    """)
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv('IOL_MASTER_SECRET', 'test_master_secret_key_1234567890abcdef')
    monkeypatch.setenv('IOL_IPC_AUTH_KEY', 'test_ipc_auth_key_1234567890abcdef')


@pytest.fixture
def sample_outreach_message():
    """Sample outreach message payload."""
    return {
        'target': 'test_user',
        'actor': 'test_actor',
        'message': 'Hey! I noticed your profile...',
        'operator': 'test_operator'
    }


@pytest.fixture
def sample_prospect_data():
    """Sample prospect data."""
    return {
        'tar_username': 'test_user',
        'status': 'Cold No Reply',
        'owner_actor': 'test_actor',
        'notes': 'Initial outreach sent'
    }
