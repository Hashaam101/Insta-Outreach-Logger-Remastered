# 📸 Insta Outreach Logger (Remastered)

A stealthy, local-first CRM for distributed Instagram outreach teams.

---

## 📌 Overview

Insta Outreach Logger is a specialized tool designed to track high-volume Instagram outreach **without triggering anti-bot detection**. Unlike traditional browser extensions that make API calls directly from the browser (which Instagram can detect), this tool uses **Chrome Native Messaging** to offload all logic, storage, and networking to a local desktop application.

### Key Philosophy:

-   **Stealth First**: The browser extension is "dumb." It only scrapes the DOM and passes text to the local OS. It makes **zero** external network requests.
-   **Local Speed**: All data is saved instantly to a local SQLite database (0ms latency), ensuring the UI never lags.
-   **Cloud Sync**: A background process performs "Delta Syncs" with a central Oracle Autonomous Database to keep the whole team aligned.

---

## 🚀 Key Features

-   **🕵️‍♂️ Invisible Logging**: Uses `chrome.runtime.sendNativeMessage` to bypass browser network stacks.
-   **🤖 Automated Actor & Operator Discovery**: Eliminates manual configuration by automatically identifying the human operator and Instagram account being used.
-   **⚡ Zero-Config Deployment**: Distributed as a compiled `.exe` launcher that auto-updates from GitHub Releases.
-   **🔄 Delta Sync Engine**: Syncs only changed rows between Local SQLite and Oracle Cloud to minimize bandwidth.
-   **🛡️ Secure & Free**: Built on Oracle Cloud's "Always Free" tier (20GB storage) with mTLS encryption.
-   **👥 Multi-Profile Support**: Handles multiple Instagram accounts running on the same machine seamlessly.

---

## 🌐 Web Dashboard (Command Center)

The Command Center is a web-based interface built with Streamlit that provides a centralized location for administrators and team leads to manage the outreach process. It allows users to:

-   **View Global Statistics**: Get a real-time overview of key performance indicators (KPIs) like total prospects logged, messages sent, and team activity.
-   **Filter and Group Analytics**: Dynamically pivot all performance data by Operator or Actor, and filter by date ranges (Today, This Week, etc.).
-   **Manage Leads**: Interactively filter, sort, and edit the status and notes for every prospect in the database.
-   **Access from Anywhere**: Because it's a web app, the dashboard can be accessed from any device with a web browser, enabling on-the-go management.

---

## 🛠️ Technology Stack

-   **Frontend**: Chrome Extension (Manifest V3, JavaScript)
-   **Desktop App**: Python 3.11+ (Compiled via PyInstaller)
-   **GUI**: CustomTkinter (Modern Dark Mode UI)
-   **Local DB**: SQLite
-   **Cloud DB**: Oracle Autonomous Transaction Processing (ATP)
-   **Driver**: `python-oracledb` (Thin Mode)

---

## 🏁 Quick Start

### Prerequisites

-   Python 3.11+ installed.
-   Oracle Cloud Account (Always Free Tier) with an ATP Database created.
-   Oracle Wallet downloaded and extracted to `assets/wallet`.

### Installation & Usage

1.  **Clone the repository and install dependencies:**
    ```bash
    git clone https://github.com/hashaam101/Insta-Outreach-Logger-Remastered.git
    cd Insta-Outreach-Logger-Remastered
    pip install -r requirements.txt
    ```

2.  **Run the Backend Server:**
    ```bash
    python src/core/ipc_server.py
    ```
    -   On its *first* run for this device, it will prompt you in the console to **"Enter Your Operator Name"** (e.g., 'John Smith'). This identifies the human user and is saved locally (`operator_config.json`).
    -   If a `local_data.db` already exists from a previous installation, it's recommended to **delete it** first to ensure the latest schema is applied.

3.  **Install the Chrome Extension:**
    -   Open Chrome, navigate to `chrome://extensions`.
    -   Enable "Developer mode" (toggle in top-right).
    -   Click "Load unpacked" and select the `src/extension` directory.
    -   **Actor Discovery:** On initial installation (or update), the extension will automatically open a new tab to `instagram.com` to discover and save your current Instagram username. This tab will close automatically.

4.  **Start Messaging & View Dashboard:**
    -   Open Instagram and begin sending messages as usual. The extension will automatically log outreach.
    -   To view the Command Center Dashboard, run:
        ```bash
        streamlit run src/dashboard/app.py
        ```

---

## 📦 Directory Structure

```plaintext
/
├── assets/
│   ├── wallet/             # Oracle Wallet files (cwallet.sso, tnsnames.ora) - GITIGNORED
│   └── icon.ico            # App Icon
├── src/
│   ├── core/               # Main Logic
│   │   ├── ipc_server.py   # IPC Server & Operator Management
│   │   ├── local_db.py     # Local SQLite Database Manager
│   │   ├── database.py     # Oracle Cloud Database Manager
│   │   └── sync_engine.py  # Delta Sync Engine
│   ├── dashboard/          # Streamlit Web Dashboard
│   │   └── app.py
│   ├── extension/          # Chrome Extension Source
│   │   ├── manifest.json
│   │   ├── background.js
│   │   └── content.js
│   │   └── injector.js     # Script Injected into Page for Actor Discovery
│   └── gui/                # User Interface (e.g., Setup Wizard - largely deprecated)
├── builds/                 # PyInstaller Output (Gitignored)
├── requirements.txt
├── local_config.py         # Local Oracle DB Credentials (Gitignored)
├── operator_config.json    # Local Operator Name (Gitignored)
├── local_data.db           # Local SQLite Database (Gitignored)
└── README.md