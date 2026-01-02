# Oracle Database Documentation

## Overview
This project uses an **Oracle Autonomous Database (ATP)** stored in the cloud. The schema is designed for tracking Instagram outreach activities, including operators, actors, targets, and logs.

### Key Features
-   **Cloud-First**: Hosted on Oracle Cloud Infrastructure (OCI).
-   **Auto-ID Generation**: All primary keys are automatically generated via triggers (e.g., `OPR-A1B2C3D4`) if left NULL during insertion.
-   **Strict Constraints**: Enums are enforced via `CHECK` constraints. Foreign Keys maintain strict referential integrity.
-   **Timezone**: All timestamps are stored in **UTC** (`TIMESTAMP WITH TIME ZONE`).

---

## Schema Structure

### 1. OPERATORS (`OPERATORS`)
**Prefix:** `OPR-`  
Represents the human users or team members managing the outreach.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| **OPR_ID** | `VARCHAR2(32)` | **PK** | Auto-generated ID (e.g., `OPR-X7Y8Z9W0`). |
| `OPR_EMAIL` | `VARCHAR2(255)` | UNIQUE, NOT NULL | Login email. |
| `OPR_NAME` | `VARCHAR2(32)` | UNIQUE, NOT NULL | Display name. |
| `OPR_STATUS` | `VARCHAR2(50)` | NOT NULL | Enum: `online`, `offline`. |
| `CREATED_AT` | `TIMESTAMP` | NOT NULL | UTC Creation time. |
| `LAST_ACTIVITY`| `TIMESTAMP` | NOT NULL | UTC Last Active time. |

### 2. ACTORS (`ACTORS`)
**Prefix:** `ACT-`  
Represents the Instagram Accounts being used to send messages. Owned by an Operator.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| **ACT_ID** | `VARCHAR2(32)` | **PK** | Auto-generated ID (e.g., `ACT-X7Y8Z9W0`). |
| `ACT_USERNAME` | `VARCHAR2(32)` | NOT NULL | Instagram Handle. |
| `OPR_ID` | `VARCHAR2(32)` | FK -> `OPERATORS` | Owner of this account. |
| `ACT_STATUS` | `VARCHAR2(50)` | NOT NULL | Enum: `Active`, `Suspended...`. |
| `CREATED_AT` | `TIMESTAMP` | NOT NULL | UTC Creation time. |
| `LAST_ACTIVITY`| `TIMESTAMP` | NOT NULL | UTC Last Active time. |

### 3. TARGETS (`TARGETS`)
**Prefix:** `TAR-`  
Represents the potential leads or users being contacted.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| **TAR_ID** | `VARCHAR2(32)` | **PK** | Auto-generated ID (e.g., `TAR-X7Y8Z9W0`). |
| `TAR_USERNAME` | `VARCHAR2(32)` | UNIQUE, NOT NULL | Instagram Handle. |
| `TAR_STATUS` | `VARCHAR2(50)` | NOT NULL | Enum: `Cold No Reply`, `Warm`, `Booked`... |
| `FIRST_CONTACTED`| `TIMESTAMP` | NOT NULL | UTC first interaction. |
| `LAST_UPDATED` | `TIMESTAMP` | NOT NULL | UTC last update. |
| `NOTES` | `CLOB` | Default 'N/A' | Free text notes. |

### 4. EVENT LOGS (`EVENT_LOGS`)
**Prefix:** `ELG-`  
The central log for all system activities (Outreach, Status Changes, System Events).

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| **ELG_ID** | `VARCHAR2(32)` | **PK** | Auto-generated ID (10-char suffix). |
| `EVENT_TYPE` | `VARCHAR2(50)` | NOT NULL | Enum: `Outreach`, `System`, `Change...`. |
| `ACT_ID` | `VARCHAR2(32)` | FK -> `ACTORS` | Actor involved. |
| `OPR_ID` | `VARCHAR2(32)` | FK -> `OPERATORS`| Operator responsible. |
| `TAR_ID` | `VARCHAR2(32)` | FK -> `TARGETS` | Target involved. |
| `DETAILS` | `CLOB` | NULLABLE | Context (e.g., JSON or text). |
| `CREATED_AT` | `TIMESTAMP` | NOT NULL | UTC timestamp. |

### 5. OUTREACH LOGS (`OUTREACH_LOGS`)
**Prefix:** `OLG-`  
Child table ~1:1 with `EVENT_LOGS` when Type=`Outreach`. Stores message content.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| **OLG_ID** | `VARCHAR2(32)` | **PK** | Auto-generated ID. |
| `ELG_ID` | `VARCHAR2(32)` | FK -> `EVENT_LOGS` | Parent Event ID. |
| `MESSAGE_TEXT` | `CLOB` | NOT NULL | The actual DM sent. |
| `SENT_AT` | `TIMESTAMP` | NOT NULL | Actual sent time (may differ from log time). |

---

## Automation & Triggers

### Auto-ID Generation
We use **BEFORE INSERT** triggers on all tables. If you insert a row with `ID = NULL`, the database automatically generates one using:
`PREFIX-` + `UPPER(SUBSTR(SYS_GUID(), 1, LENGTH))`

**Example:**
```sql
INSERT INTO OPERATORS (OPR_NAME...) VALUES ('John Doe'...);
-- Result: OPR_ID = 'OPR-A1B2C3D4'
```

**Triggers List:**
-   `TRG_OPERATORS_ID`
-   `TRG_ACTORS_ID`
-   `TRG_TARGETS_ID`
-   `TRG_EVENT_LOGS_ID`
-   `TRG_OUTREACH_LOGS_ID`
-   `TRG_GOALS_ID`
-   `TRG_RULES_ID`

---

