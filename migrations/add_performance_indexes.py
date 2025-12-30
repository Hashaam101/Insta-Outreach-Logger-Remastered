"""
Database performance migration: Add indexes for frequently queried columns.

This script adds indexes to improve query performance for the local SQLite database.
Run this after updating to Phase 6.5.
"""

import sqlite3
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Define PROJECT_ROOT
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = Path(__file__).parent.parent

DB_PATH = PROJECT_ROOT / "local_data.db"


def add_indexes(conn):
    """
    Add performance indexes to the database.
    
    Args:
        conn: SQLite connection object.
    """
    cursor = conn.cursor()
    
    indexes = [
        # EVENT_LOGS indexes for frequent queries
        ("idx_event_logs_act_id", "CREATE INDEX IF NOT EXISTS idx_event_logs_act_id ON event_logs(act_id)"),
        ("idx_event_logs_created_at", "CREATE INDEX IF NOT EXISTS idx_event_logs_created_at ON event_logs(created_at)"),
        ("idx_event_logs_event_type", "CREATE INDEX IF NOT EXISTS idx_event_logs_event_type ON event_logs(event_type)"),
        ("idx_event_logs_tar_id", "CREATE INDEX IF NOT EXISTS idx_event_logs_tar_id ON event_logs(tar_id)"),
        
        # PROSPECTS (TARGETS) indexes
        ("idx_prospects_username", "CREATE INDEX IF NOT EXISTS idx_prospects_tar_username ON prospects(tar_username)"),
        ("idx_prospects_status", "CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status)"),
        ("idx_prospects_owner", "CREATE INDEX IF NOT EXISTS idx_prospects_owner_actor ON prospects(owner_actor)"),
        ("idx_prospects_last_updated", "CREATE INDEX IF NOT EXISTS idx_prospects_last_updated ON prospects(last_updated)"),
        
        # RULES indexes
        ("idx_rules_status", "CREATE INDEX IF NOT EXISTS idx_rules_is_active ON rules(is_active)"),
        ("idx_rules_assigned_opr", "CREATE INDEX IF NOT EXISTS idx_rules_assigned_opr ON rules(assigned_to_opr)"),
        ("idx_rules_assigned_act", "CREATE INDEX IF NOT EXISTS idx_rules_assigned_act ON rules(assigned_to_act)"),
        
        # GOALS indexes
        ("idx_goals_status", "CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status)"),
        ("idx_goals_assigned_opr", "CREATE INDEX IF NOT EXISTS idx_goals_assigned_opr ON goals(assigned_to_opr)"),
        ("idx_goals_assigned_act", "CREATE INDEX IF NOT EXISTS idx_goals_assigned_act ON goals(assigned_to_act)"),
        
        # Composite indexes for common query patterns
        ("idx_event_logs_act_created", "CREATE INDEX IF NOT EXISTS idx_event_logs_act_created ON event_logs(act_id, created_at)"),
        ("idx_event_logs_type_created", "CREATE INDEX IF NOT EXISTS idx_event_logs_type_created ON event_logs(event_type, created_at)"),
    ]
    
    print("[Migration] Adding database indexes for performance...")
    
    for index_name, index_sql in indexes:
        try:
            cursor.execute(index_sql)
            print(f"[Migration] ✓ Created index: {index_name}")
        except sqlite3.Error as e:
            print(f"[Migration] ⚠ Warning for {index_name}: {e}")
    
    conn.commit()
    print("[Migration] Index creation completed.")


def analyze_database(conn):
    """
    Run ANALYZE to update statistics for the query optimizer.
    
    Args:
        conn: SQLite connection object.
    """
    cursor = conn.cursor()
    print("[Migration] Analyzing database for query optimization...")
    cursor.execute("ANALYZE")
    conn.commit()
    print("[Migration] ✓ Database analysis completed.")


def vacuum_database(conn):
    """
    Run VACUUM to optimize database file size and performance.
    
    Args:
        conn: SQLite connection object.
    """
    print("[Migration] Vacuuming database (this may take a moment)...")
    conn.execute("VACUUM")
    print("[Migration] ✓ Database vacuum completed.")


def main():
    """Main migration function."""
    if not DB_PATH.exists():
        print(f"[Migration] Error: Database not found at {DB_PATH}")
        print("[Migration] Please ensure the application has been run at least once.")
        return 1
    
    print(f"[Migration] Connecting to database: {DB_PATH}")
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        
        # Add indexes
        add_indexes(conn)
        
        # Analyze for query optimizer
        analyze_database(conn)
        
        # Vacuum to optimize
        vacuum_database(conn)
        
        conn.close()
        
        print("\n[Migration] ✓ Performance migration completed successfully!")
        print("[Migration] Your database has been optimized for better performance.")
        return 0
        
    except Exception as e:
        print(f"\n[Migration] ✗ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
