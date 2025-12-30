import oracledb
import os
import sys
from dotenv import load_dotenv

# Add the project root to the Python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.append(PROJECT_ROOT)

# Load environment variables from .env file
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# Check if database credentials are available
if not all([os.getenv('DB_USER'), os.getenv('DB_PASSWORD'), os.getenv('DB_DSN')]):
    print("Error: .env file not found or missing database credentials.")
    print("Please copy .env.example to .env and fill in your database credentials.")
    sys.exit(1)

# --- SQL Commands from schema.dbml ---

CREATE_TABLE_STATEMENTS = [
    # OPERATORS
    """
    CREATE TABLE OPERATORS (
        OPR_ID VARCHAR2(20) NOT NULL PRIMARY KEY,
        OPR_EMAIL VARCHAR2(255) NOT NULL UNIQUE,
        OPR_NAME VARCHAR2(32) NOT NULL UNIQUE,
        OPR_STATUS VARCHAR2(20) NOT NULL,
        CREATED_AT TIMESTAMP NOT NULL,
        LAST_ACTIVITY TIMESTAMP NOT NULL,
        CONSTRAINT chk_opr_status CHECK (OPR_STATUS IN ('online', 'offline'))
    )
    """,
    # ACTORS
    """
    CREATE TABLE ACTORS (
        ACT_ID VARCHAR2(20) NOT NULL PRIMARY KEY,
        ACT_USERNAME VARCHAR2(32) NOT NULL,
        OPR_ID VARCHAR2(20) NOT NULL,
        ACT_STATUS VARCHAR2(50) NOT NULL,
        CREATED_AT TIMESTAMP NOT NULL,
        LAST_ACTIVITY TIMESTAMP NOT NULL,
        CONSTRAINT fk_act_opr FOREIGN KEY (OPR_ID) REFERENCES OPERATORS(OPR_ID),
        CONSTRAINT uq_act_opr UNIQUE (ACT_USERNAME, OPR_ID)
    )
    """,
    # TARGETS (Formerly PROSPECTS)
    """
    CREATE TABLE TARGETS (
        TAR_ID VARCHAR2(20) NOT NULL PRIMARY KEY,
        TAR_USERNAME VARCHAR2(32) NOT NULL UNIQUE,
        TAR_STATUS VARCHAR2(50) NOT NULL,
        FIRST_CONTACTED TIMESTAMP NOT NULL,
        NOTES CLOB DEFAULT 'N/A' NOT NULL,
        LAST_UPDATED TIMESTAMP NOT NULL,
        EMAIL VARCHAR2(500) DEFAULT 'N/S' NOT NULL,
        PHONE_NUM VARCHAR2(500) DEFAULT 'N/S' NOT NULL,
        CONT_SOURCE CLOB DEFAULT 'N/S' NOT NULL
    )
    """,
    # EVENT_LOGS
    """
    CREATE TABLE EVENT_LOGS (
        ELG_ID VARCHAR2(20) NOT NULL PRIMARY KEY,
        EVENT_TYPE VARCHAR2(50) NOT NULL,
        ACT_ID VARCHAR2(20) NOT NULL,
        OPR_ID VARCHAR2(20) NOT NULL,
        TAR_ID VARCHAR2(20) NOT NULL,
        DETAILS CLOB,
        CREATED_AT TIMESTAMP NOT NULL,
        CONSTRAINT fk_elg_act FOREIGN KEY (ACT_ID) REFERENCES ACTORS(ACT_ID),
        CONSTRAINT fk_elg_opr FOREIGN KEY (OPR_ID) REFERENCES OPERATORS(OPR_ID),
        CONSTRAINT fk_elg_tar FOREIGN KEY (TAR_ID) REFERENCES TARGETS(TAR_ID)
    )
    """,
    # OUTREACH_LOGS (Linked to EVENT_LOGS)
    """
    CREATE TABLE OUTREACH_LOGS (
        OLG_ID VARCHAR2(20) NOT NULL PRIMARY KEY,
        ELG_ID VARCHAR2(20) NOT NULL UNIQUE,
        MESSAGE_TEXT CLOB NOT NULL,
        SENT_AT TIMESTAMP NOT NULL,
        CONSTRAINT fk_olg_elg FOREIGN KEY (ELG_ID) REFERENCES EVENT_LOGS(ELG_ID)
    )
    """,
    # GOALS
    """
    CREATE TABLE GOALS (
        GOAL_ID VARCHAR2(20) NOT NULL PRIMARY KEY,
        METRIC VARCHAR2(50) NOT NULL,
        TARGET_VALUE INTEGER NOT NULL,
        FREQUENCY VARCHAR2(20) NOT NULL,
        ASSIGNED_TO_OPR VARCHAR2(20),
        ASSIGNED_TO_ACT VARCHAR2(20),
        STATUS VARCHAR2(20) DEFAULT 'Active' NOT NULL,
        SUGGESTED_BY VARCHAR2(20),
        CREATED_AT TIMESTAMP NOT NULL,
        START_DATE TIMESTAMP NOT NULL,
        END_DATE TIMESTAMP,
        CONSTRAINT fk_gol_opr FOREIGN KEY (ASSIGNED_TO_OPR) REFERENCES OPERATORS(OPR_ID),
        CONSTRAINT fk_gol_act FOREIGN KEY (ASSIGNED_TO_ACT) REFERENCES ACTORS(ACT_ID),
        CONSTRAINT fk_gol_sug FOREIGN KEY (SUGGESTED_BY) REFERENCES OPERATORS(OPR_ID)
    )
    """,
    # RULES
    """
    CREATE TABLE RULES (
        RULE_ID VARCHAR2(20) NOT NULL PRIMARY KEY,
        TYPE VARCHAR2(50) NOT NULL,
        METRIC VARCHAR2(50) NOT NULL,
        LIMIT_VALUE INTEGER NOT NULL,
        TIME_WINDOW_SEC INTEGER NOT NULL,
        SEVERITY VARCHAR2(50) DEFAULT 'Soft Warning',
        ASSIGNED_TO_OPR VARCHAR2(20),
        ASSIGNED_TO_ACT VARCHAR2(20),
        STATUS VARCHAR2(20) DEFAULT 'Active' NOT NULL,
        SUGGESTED_BY VARCHAR2(20),
        CREATED_AT TIMESTAMP NOT NULL,
        CONSTRAINT fk_rul_opr FOREIGN KEY (ASSIGNED_TO_OPR) REFERENCES OPERATORS(OPR_ID),
        CONSTRAINT fk_rul_act FOREIGN KEY (ASSIGNED_TO_ACT) REFERENCES ACTORS(ACT_ID),
        CONSTRAINT fk_rul_sug FOREIGN KEY (SUGGESTED_BY) REFERENCES OPERATORS(OPR_ID)
    )
    """
]

def initialize_schema():
    """
    Connects to the Oracle database and executes the DDL statements
    to create the required schema for the application.
    Includes error handling to prevent crashes if objects already exist.
    """
    # Check for required environment variables
    if not all([os.getenv('DB_USER'), os.getenv('DB_PASSWORD'), os.getenv('DB_DSN')]):
        print("Error: Database credentials not found in .env file")
        print("Please ensure DB_USER, DB_PASSWORD, and DB_DSN are set.")
        return

    try:
        print("Connecting to the database...")
        with oracledb.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            dsn=os.getenv('DB_DSN')
        ) as connection:
            print("Connection successful.")
            with connection.cursor() as cursor:
                
                # --- Create Tables ---
                print("\nCreating tables...")
                for statement in CREATE_TABLE_STATEMENTS:
                    try:
                        cursor.execute(statement)
                        # Extract table name for logging
                        parts = statement.strip().split()
                        table_name = parts[2]
                        print(f"  - Table '{table_name}' created successfully.")
                    except oracledb.DatabaseError as e:
                        error_obj, = e.args
                        if error_obj.code == 955: # ORA-00955: name is already used by an existing object
                            parts = statement.strip().split()
                            table_name = parts[2]
                            print(f"  - Table '{table_name}' already exists. Skipping.")
                        else:
                            print(f"  - Error creating table: {e}")
                
                # --- Commit Transaction ---
                connection.commit()
                print("\nDatabase initialization complete. All changes have been committed.")

    except oracledb.Error as e:
        print(f"Database connection or setup failed: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == '__main__':
    initialize_schema()