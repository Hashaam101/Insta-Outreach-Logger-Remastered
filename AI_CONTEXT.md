# 🤖 Project Context for AI Assistants

## 📌 Project Identity

- **Name**: Insta Outreach Logger (Remastered)
- **Type**: Distributed Desktop Application + Chrome Extension
- **Purpose**: A stealthy, local-first Instagram CRM designed for distributed outreach teams. It logs DM outreach and tracks prospect status without triggering Instagram's anti-bot detection mechanisms.

## 🏗️ System Architecture

The application uses a hybrid auto-discovery model to establish identity and a "Stealth Bridge" to log data without being detected.

### 1. Identity: The Auto-Discovery Workflow

Setup is fully automated. The identity of the human user (**Operator**) and the Instagram account being used (**Actor**) are discovered and persisted on first use.

-   **Operator (The Human):** The identity of the team member.
    1.  **First Run:** The backend Python server (`ipc_server.py`) starts.
    2.  **Check/Prompt:** It looks for `operator_config.json`. If not found, it prompts the user in the console for their name (e.g., "John Smith").
    3.  **Persistence:** The name is saved, establishing a persistent Operator identity for that device.

-   **Actor (The Instagram Account):** The Instagram account sending the DMs.
    1.  **First Install:** When the extension is installed or updated, the background script (`background.js`) checks its local storage for an `actorUsername`.
    2.  **Discovery Tab:** If the username is missing, it opens a temporary tab to `instagram.com`.
    3.  **Scrape & Save:** The content script (`content.js`) activates, finds the user's profile link in the navigation rail, scrapes the username, and sends it to the background script. The background script saves it to `chrome.storage.local` and closes the tab.
    4.  **Hardened Detection:** If the user switches accounts (Single Page App navigation), a `MutationObserver` detects the profile change and re-scrapes the new Actor within 5 seconds.

### 2. Data Logging: The "Stealth Bridge"

This process ensures that no network requests are made from the browser, avoiding bot detection.

1.  **Message Sent (Browser):** The user sends a DM. The `content.js` script captures the `target` username, `message` text, and reads the `actor` username from storage.
2.  **IPC Message (Browser -> Host):** The content script sends this data packet (`{actor, target, message}`) to the background script, which forwards it to the native Python host (`bridge.py` / `InstaLogger.exe --bridge`).
3.  **Data Enrichment (Host):** The `ipc_server.py` receives the packet. It injects the `operator_name` from its config into the data.
4.  **Local Queue (Host):** The fully enriched log (`{actor, operator, target, message}`) is saved into a local SQLite database (`local_data.db`). The response to the browser is immediate (0ms latency).

### 3. Sync Engine: "GitHub-Style" Delta Sync

To keep bandwidth low and syncs fast, the system uses a **Last-Write-Wins** delta strategy.

1.  **Local Meta Table:** The local SQLite DB has a `meta` table storing `last_cloud_sync` (timestamp).
2.  **Pull (Cloud -> Local):**
    -   The Sync Engine queries Oracle: `SELECT * FROM PROSPECTS WHERE LAST_UPDATED > :last_cloud_sync`.
    -   Oracle returns *only* the rows that changed since the last sync.
    -   Local DB bulk-upserts these changes.
    -   Local `last_cloud_sync` is updated to `NOW()`.
3.  **Push (Local -> Cloud):**
    -   The Sync Engine reads all `outreach_logs` where `synced_to_cloud = 0`.
    -   It bulk-inserts these logs into Oracle.
    -   It bulk-upserts any new prospects/actors discovered.
    -   It marks local logs as `synced_to_cloud = 1`.

### 4. Real-Time Status Check (UI Notifications)

When the user visits an Instagram profile page or opens a DM thread, the extension displays a visual status banner:

1.  **Check Request:** The content script extracts the target username and sends a `CHECK_PROSPECT_STATUS` message via the native messaging bridge.
2.  **Local Lookup:** The IPC Server checks the local SQLite database (which is kept up-to-date by the Sync Engine).
3.  **Banner Display:**
    -   **Green Banner:** "Not Contacted Before"
    -   **Red Banner:** "Previously Contacted: [Status]" (e.g., Warm, Hot)
    -   **Red Border:** "Detection Failed" (if username cannot be scraped)
4.  **Status Dropdown:** Users can update the prospect's status directly from the banner. Changes are saved locally -> synced to Oracle.

---

## 🖥️ Web Dashboard (Command Center)

A separate, modern web application for centralized management and analytics.

-   **Tech Stack**: Next.js 14, Tailwind CSS, TypeScript.
-   **Repository**: [https://github.com/Hashaam101/insta-outreach-logger-dashboard](https://github.com/Hashaam101/insta-outreach-logger-dashboard)
-   **Functionality**:
    -   **Analytics**: Visualizes team performance, outreach volume, and booking rates.
    -   **Lead Management**: Grid view for filtering and updating prospect statuses.
    -   **Operator Management**: Admin interface for managing team members and access.
    -   **Authentication**: Google OAuth integration linked to Operator IDs.

---

## 💾 Database Architectures

### Local Database (SQLite)
*Acts as a cache and offline queue.*
-   **`prospects`**: Local cache of lead status + `last_updated`.
-   **`outreach_logs`**: Append-only queue of sent messages (`synced_to_cloud` flag).
-   **`meta`**: Key-value store for config (e.g., `last_cloud_sync`).

### Cloud Database (Oracle ATP)
*The central source of truth.*
-   **`OPERATORS`**: List of human team members.
-   **`ACTORS`**: List of Instagram accounts (`OWNER_OPERATOR` FK).
-   **`PROSPECTS`**: Master list of leads (`LAST_UPDATED` timestamp for sync).
-   **`OUTREACH_LOGS`**: Global history of all messages.

---

## 📦 Distribution Architecture

### 1. The Launcher (Bootstrapper)
The entry point is `InstaLogger.exe` (renamed from launcher).
-   **GitHub Releases Integration:** On startup, it queries the GitHub Releases API.
-   **Auto-Update:** If a newer version is available, it downloads and swaps the binary automatically.
-   **Execution:** Once the environment is verified, it launches the main application (`ipc_server`).

### 2. Setup Wizard (First Run)
If credentials are missing (`local_config.py` or `assets/wallet/`), the **Setup Wizard** launches.
-   **Setup Pack:** User drags a `Setup_Pack.zip` (provided by admin) into the window.
-   **Automation:** The wizard extracts credentials and registers the Native Messaging Host in the Windows Registry (`HKCU\Software\Google\Chrome\NativeMessagingHosts`).

---

## 🗓️ Development Status

All major development phases are complete. The application is a functional end-to-end system ready for deployment.

-   **Phase 1: Foundation & Backend Logic:** Complete (Oracle migration).
-   **Phase 2: Chrome Extension & Bridge:** Complete (Hardened v12).
-   **Phase 3: Admin Command Center:** Complete (Migrated to separate [Next.js Dashboard repo](https://github.com/Hashaam101/insta-outreach-logger-dashboard)).
-   **Phase 4: Auto-Discovery Architecture:** Complete.
-   **Phase 5: Real-Time Status Check:** Complete.
-   **Phase 6: Packaging & Distribution:** Complete (Dev CLI, Setup Wizard, Launcher).
-   **Phase 7: Optimization:** Complete (Delta Sync Engine).