# 🤖 Project Context for AI Assistants

## 📌 Project Identity

- **Name**: InstaCRM Ecosystem (Desktop Agent + Dashboard)
- **Type**: Distributed Desktop Application (Python/Chrome) + Cloud Dashboard (Next.js)
- **Purpose**: A stealthy, local-first Instagram CRM designed for distributed outreach teams. It logs DM outreach and tracks prospect status without triggering Instagram's anti-bot detection mechanisms, governed by a central democratic policy system.

## 🏗️ System Architecture

The ecosystem allows multiple agents (Operators) to control multiple Instagram accounts (Actors) while syncing data to a central Cloud Core (Oracle ATP).

### 1. Identity: Google OAuth & Auto-Discovery

Setup is fully automated and secure. The identity of the human user (**Operator**) is established via Google Sign-In, linking them to the central dashboard.

-   **Operator (The Human):** The identity of the team member.
    1.  **First Run:** The user launches the desktop app (`start_gui.py`).
    2.  **Login:** The app prompts the user to "Sign in with Google". This uses OAuth 2.0 PKCE flow to authenticate against the central project credentials.
    3.  **Verification:** The app checks if the email exists in the `OPERATORS` table.
        *   **Found:** The session is authorized, and the dashboard launches.
        *   **New User:** An "Establish Identity" form appears, allowing the user to set their `OPR_NAME` and register.
    4.  **Persistence:** The authorized identity is saved locally (`operator_config.json`), allowing the background IPC server to run autonomously.

-   **Actor (The Instagram Account):** The Instagram account sending the DMs.
    1.  **Discovery:** When the extension is installed or the user switches accounts, the content script scrapes the current username.
    2.  **Shared Ownership:** A single Actor (e.g., `@company_account`) can be managed by multiple Operators. The system tracks "My Contribution" vs. "Team Contribution" for shared assets.

### 2. Data Logging: The "Stealth Bridge" (Updated)

This process ensures that no network requests are made from the browser to external APIs, avoiding bot detection.

1.  **Message Sent (Browser):** The user sends a DM. The `content.js` script captures the `target` username and `message` text.
2.  **Pre-Flight Check (Local):** Before confirming, the local host checks the `RULES` table (e.g., "Max 50 DMs/hour").
3.  **Resilient IPC:** The data is sent via Native Messaging to the Python Host. The bridge features **Auto-Reconnect** logic, ensuring communication remains active even if the desktop app is restarted.
4.  **Event Logging (Host):** The `ipc_server.py` creates a structured record in the local SQLite DB.
5.  **Response:** Immediate success/warning response to the browser.
6.  **Automation (Optional):** If "Auto-Tab Switcher" is enabled, the host triggers a `Ctrl+W` / `Ctrl+Tab` key sequence. This includes a **Foreground Window Check** (via `ctypes`) to ensure keys are only sent if Chrome/Instagram is in active focus.

### 3. Sync Engine: "GitHub-Style" Delta Sync

To keep bandwidth low and syncs fast, the system uses a **Last-Write-Wins** delta strategy.

-   **Cloud Source:** Oracle Autonomous Database (ATP).
-   **Local Cache:** SQLite with **Self-Healing Resilience**. The system maintains an auto-backup (`.bak`) and automatically restores data if corruption is detected.
-   **Adaptive Sync:** Featuring **Exponential Backoff**, the engine reduces sync frequency during network outages to save resources.

### 4. Democratic Governance & Rules
... (rest remains similar) ...

---

## 📦 Distribution Architecture

### 1. The Launcher (`InstaLogger.exe`)
-   Auto-updates the binary from GitHub Releases on every launch.
-   Self-Heals: Dynamically registers the Native Messaging Host paths in the Windows Registry.
-   Configuration: Prompts for the Update Source URL if missing or invalid.

### 2. One-Click Installer (`installer_gui.py`)
-   Deploys the entire environment to `Documents/Insta Outreach Logger`.
-   Manages process lifecycles: Safely kills running instances during updates to avoid file locks.
-   Creates system-wide shortcuts (Start Menu & Desktop).
-   Registers the Chrome Extension path automatically.
