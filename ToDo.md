# 📝 To-Do: Reconstruction Roadmap

This document outlines the detailed steps required to upgrade the Desktop Agent and Chrome Extension to the new **InstaCRM Ecosystem** architecture.

**Goal:** Align the local application with the new Oracle Schema (`EVENT_LOGS`, `RULES`, `GOALS`) and implement the Democratic Governance safety features.

---

## 📦 Phase 1: Local Database & Schema Migration

The local SQLite database must mirror the structure of the new Oracle Schema to facilitate accurate syncing.

### 1. Update `src/core/local_db.py`
- [x] **Refactor `init_db()`**:
    - [x] Rename/Deprecate old `outreach_logs` table if it doesn't match the new structure.
    - [x] Create `event_logs` table:
        - `id` (Primary Key, Auto-inc/UUID)
        - `elg_id` (Text, Nullable - populated after sync)
        - `event_type` (Text: 'Outreach', 'System', etc.)
        - `act_id` (Text)
        - `opr_id` (Text)
        - `tar_id` (Text)
        - `details` (JSON Text)
        - `created_at` (Timestamp)
        - `synced_to_cloud` (Boolean/Int)
    - [x] Create `outreach_logs` table (Child):
        - `id` (PK)
        - `olg_id` (Text, Nullable)
        - `elg_id` (Foreign Key to `event_logs.id` or `event_logs.elg_id`)
        - `message_text` (Text)
        - `sent_at` (Timestamp)
    - [x] Create `rules` table:
        - `rule_id` (Text, PK)
        - `type` (Text: 'Frequency Cap', 'Interval Spacing')
        - `metric` (Text)
        - `limit_value` (Int)
        - `time_window_sec` (Int)
        - `severity` (Text)
        - `assigned_to_opr` (Text, Nullable)
        - `assigned_to_act` (Text, Nullable)
        - `is_active` (Boolean)
    - [x] Create `goals` table (similar structure to `schema.dbml`).

### 2. Migration Script
- [x] Create a migration function in `init_db.py` to migrate existing data (if any important data exists locally) to the new structure, or simply archive/reset the DB for this major version. We can delete the local db data completely and we must not reset or delete anything in the oracle DB as that is our master DB for now.

---

## 🌉 Phase 2: Backend Logic & Bridge Updates

The Python host needs to handle the new logic for assembling Event Logs and checking Rules.

### 1. Update `src/core/ipc_server.py` & `bridge.py`
- [x] **Message Handling**:
    - [x] When receiving a log message from Chrome, construct an `EVENT_LOG` entry first.
    - [x] Extract `message` content and create a linked `OUTREACH_LOG` entry.
- [x] **Pre-Flight Safety Check (`security.py` or new module)**:
    - [x] Implement `check_rules(act_id, opr_id)` function.
    - [x] Logic: Query local `rules` table.
        - *Frequency Cap*: Count `event_logs` for this actor in the last `time_window_sec`.
        - *Interval Spacing*: Check `created_at` of the last log.
    - [x] Return status: `PASS`, `WARN`, or `BLOCK`.
- [x] **Response Format**:
    - [x] Update the JSON response sent back to Chrome to include `status: "warning"` and `message: "Slow down! Rule X violated."` if applicable.

---

## 🔄 Phase 3: Sync Engine Overhaul

The Sync Engine is the most critical component. It handles the bi-directional flow of the new entities.

### 1. Update `src/core/sync_engine.py`
- [x] **Push Logic (Local -> Cloud)**:
    - [x] Select unsynced `event_logs` and their children `outreach_logs`.
    - [x] **Batch Insert**: Send to Oracle using a transaction.
    - [x] **ID Mapping**: Oracle will generate `ELG-XXX` and `OLG-XXX` IDs. The response must be used to update the local SQLite records (replacing temp IDs with real Cloud IDs).
- [x] **Pull Logic (Cloud -> Local)**:
    - [x] **Fetch Rules**: `SELECT * FROM RULES WHERE STATUS = 'Active'`. Update local cache.
    - [x] **Fetch Goals**: `SELECT * FROM GOALS`. Update local cache.
    - [x] **Fetch Targets**: Continue syncing updated targets (Delta Sync).

---

## 🧩 Phase 4: Chrome Extension Updates

The "Dumb" extension needs to be slightly smarter to display the new warnings.

### 1. Update `src/extension/content.js`
- [x] **Status Banner**: Ensure it handles the new response types from the Bridge.
- [x] **Warning UI**:
    - [x] If the Bridge returns a `WARN` status after logging, display a toast or change the banner color (e.g., Orange/Yellow) to alert the user.

### 2. Update `src/extension/background.js`
- [x] Ensure `actorUsername` scraping is robust and supports the "Shared Ownership" model (mostly backend logic, but ensure the correct username is always sent).

---

## 🧪 Phase 5: Comprehensive Verification & Testing

Since this is a major release, follow this sequential testing guide to verify **everything**.

### 1. Setup & Identity (First Run)
- [ ] **Action:** Run `launcher.py` (or the compiled `.exe`).
- [ ] **Condition:** Ensure `operator_config.json` and `assets/wallet/cwallet.sso` are **deleted/moved** before starting to simulate a fresh install.
- [ ] **Expected:**
    1.  The "Setup Wizard" launches automatically.
    2.  Step 1: Upload `Setup_Pack.zip`. It should verify contents.
    3.  Step 2: Enter your Operator Name. It should auto-complete if DB connection works.
    4.  Step 3: Click "Open Extension Folder". Explorer should open to `Documents/...`.
    5.  Step 4: Enter Extension ID.
    6.  Completion: Wizard closes, and the **Login Screen** appears.

### 2. Authentication & Onboarding
- [ ] **Action:** Click "Sign in with Google" on the login screen.
- [ ] **Expected:**
    1.  Default browser opens to Google Login.
    2.  After login, you are redirected to `localhost`.
    3.  App UI updates to "Verifying Identity...".
    4.  **New User:** You see the "Establish Identity" screen. Enter a name and confirm. You are taken to the Dashboard.
    5.  **Existing User:** You go straight to the Dashboard.

### 3. Dashboard & Sync Status
- [ ] **Action:** Observe the Dashboard sidebar.
- [ ] **Expected:**
    1.  **Status:** `SYNC: STARTING...` -> `SYNC: OK (HH:MM)` (Green).
    2.  **Telemetry:** "Session" timer is counting up.
- [ ] **Test Failure:** Disconnect your internet.
    *   **Expected:** After ~60s, status changes to `SYNC: ERROR` (Red). Logs show "Backing off...".
    *   **Recovery:** Reconnect internet. Status should return to Green within minutes.

### 4. Extension & Scroller
- [ ] **Action:** Open Chrome. Go to `instagram.com/direct/`.
- [ ] **Expected:**
    1.  A **Pulsing Button** (📜) appears at the bottom-left.
    2.  Click it -> The Scroller Panel opens.
    3.  Click "Start" -> The DM list scrolls automatically.
    4.  Navigate away from `/direct/` -> Button disappears.

### 5. Outreach Logging & Privacy
- [ ] **Action:** Go to a DM thread. Send a message "Hello test".
- [ ] **Expected:**
    1.  Extension Banner: Appears saying "Searching..." -> "Not Contacted Before".
    2.  Dashboard: "Outreach Sent" count increases by 1.
    3.  **Privacy Test:** Mark a target as **"Excluded"** via the banner dropdown.
        *   Send another message to them.
        *   **Check DB:** The event is logged in `EVENT_LOGS`, but **NO** entry exists in `OUTREACH_LOGS` (message text is hidden).

### 6. Auto-Tab Switcher
- [ ] **Action:** Go to App Settings -> Enable "Auto Tab Switcher". Set Trigger = 1, Delay = 2s.
- [ ] **Action:** Send a DM in Chrome.
- [ ] **Expected:**
    1.  Wait 2 seconds.
    2.  The current tab closes (`Ctrl+W`).
    3.  Focus switches to the next tab (`Ctrl+Tab`).

### 7. Auto-Updater
- [ ] **Action:** Go to App Settings.
- [ ] **Check:** "Update Source" field should show `https://github.com/hashaam101/Insta-Outreach-Logger-Remastered`.
- [ ] **Simulate Update:**
    1.  Open `src/core/version.py` and lower the version to `0.0.1`.
    2.  Run `launcher.py`.
    3.  **Expected:** Console says "Update found... Installing...". It downloads the latest release from GitHub and restarts. (Note: This requires a valid release on GitHub).

### 8. Installer (Final Artifact)
- [ ] **Action:** Run `src/scripts/installer_gui.py`.
- [ ] **Expected:**
    1.  Installer UI opens.
    2.  Click "Install Now".
    3.  Files copied to `Documents/Insta Outreach Logger`.
    4.  Shortcuts created on Desktop and Start Menu.
    5.  Run the Desktop Shortcut -> App launches correctly.
