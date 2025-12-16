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
    4.  **Persistence:** This username is now persistently available to the content script for all future logging.

### 2. Data Logging: The "Stealth Bridge"

This process ensures that no network requests are made from the browser, avoiding bot detection.

1.  **Message Sent (Browser):** The user sends a DM. The `content.js` script captures the `target` username, `message` text, and reads the `actor` username from storage.
2.  **IPC Message (Browser -> Host):** The content script sends this data packet (`{actor, target, message}`) to the background script, which forwards it to the native Python host (`ipc_server.py`).
3.  **Data Enrichment (Host):** The `ipc_server.py` receives the packet. It injects the `operator_name` from its config into the data.
4.  **Local Queue (Host):** The fully enriched log (`{actor, operator, target, message}`) is saved into a local SQLite database (`local_data.db`). The response to the browser is immediate.
5.  **Cloud Sync (Host):** In the background, `sync_engine.py` reads unsynced logs from the SQLite queue.
    -   It calls `ensure_actor_exists()` in `database.py` to auto-register any new Actor in the Oracle `ACTORS` table, linking them to the `OWNER_OPERATOR`.
    -   It then bulk-inserts the logs and prospect data into the Oracle database.

### 3. Reporting: The Command Center

-   A web dashboard (`src/dashboard/app.py`) built with Streamlit.
-   It reads directly from the Oracle Cloud database to provide near real-time analytics on team and account performance.
-   Features a "View Mode" to pivot all metrics and charts by either **Operator** (human performance) or **Actor** (account performance), and a **Date Filter** ("Today", "This Week", etc.) for time-based analysis.

---

## 🗓️ Development Status

All major development phases are complete. The application is a functional end-to-end system.

-   **Phase 1: Foundation & Backend Logic:** Complete.
-   **Phase 2: Chrome Extension & Bridge:** Complete.
-   **Phase 3: Admin Command Center:** Complete.
-   **Phase 4: Auto-Discovery Architecture:** Complete.
-   **Next Step:** Final cleanup and removal of debugging logs.
