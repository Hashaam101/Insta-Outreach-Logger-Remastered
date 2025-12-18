# 📸 Insta Outreach Logger (Remastered)

A stealthy, local-first CRM for distributed Instagram outreach teams.

---

## 📌 Overview

Insta Outreach Logger is a specialized tool designed to track high-volume Instagram outreach **without triggering anti-bot detection**. Unlike traditional browser extensions that make API calls directly from the browser (which Instagram can detect), this tool uses **Chrome Native Messaging** to offload all logic, storage, and networking to a local desktop application.

### Key Philosophy:

-   **Stealth First**: The browser extension is "dumb." It only scrapes the DOM and passes text to the local OS. It makes **zero** external network requests.
-   **Local Speed**: All data is saved instantly to a local SQLite database (0ms latency), ensuring the UI never lags.
-   **Cloud Sync**: A background process performs "Delta Syncs" (GitHub-style) with a central Oracle Autonomous Database to keep the whole team aligned.

---

## 🚀 Key Features

-   **🕵️‍♂️ Invisible Logging**: Uses `chrome.runtime.sendNativeMessage` to bypass browser network stacks.
-   **🤖 Automated Actor & Operator Discovery**: Eliminates manual configuration by automatically identifying the human operator and Instagram account being used. Detects account switching in real-time.
-   **🔔 Real-Time Status Check**: Visual notification banners show whether a prospect has been contacted before, directly on Instagram profile and DM pages.
-   **📊 Status Dropdown**: Update prospect status (Cold, Warm, Hot, Booked, etc.) directly from the notification banner.
-   **⚡ Zero-Config Deployment**: Distributed as a compiled `.exe` launcher that auto-updates from GitHub Releases.
-   **🔄 Delta Sync Engine**: Uses a `LAST_UPDATED` timestamp to pull only changed records from Oracle Cloud, making syncs incredibly fast and bandwidth-efficient.
-   **🛡️ Secure & Free**: Built on Oracle Cloud's "Always Free" tier (20GB storage) with mTLS encryption.
-   **👥 Multi-Profile Support**: Handles multiple Instagram accounts running on the same machine seamlessly.

---

## 🌐 Web Dashboard (Command Center)

The Command Center is a web-based interface built with Streamlit that provides a centralized location for administrators and team leads to manage the outreach process. It allows users to:

-   **View Global Statistics**: Get a real-time overview of key performance indicators (KPIs) like total prospects logged, messages sent, and team activity.
-   **Filter and Group Analytics**: Dynamically pivot all performance data by Operator or Actor, and filter by date ranges (Today, This Week, etc.).
-   **Manage Leads**: Interactively filter, sort, and edit the status and notes for every prospect in the database.
-   **Access from Anywhere**: Because it's a web app, the dashboard can be accessed from any device with a web browser, enabling on-the-go management.

## ☁️ Streamlit Cloud Deployment

The dashboard is deployed via a separate orphan branch to maintain a lightweight environment. For instructions on how to sync code updates without breaking dependencies, see [DASHBOARD.md > Deployment & Maintenance](DASHBOARD.md#deployment--maintenance).

---

## 🛠️ Technology Stack

-   **Frontend**: Chrome Extension (Manifest V3, JavaScript, MutationObserver)
-   **Desktop App**: Python 3.11+ (Compiled via PyInstaller)
-   **GUI**: CustomTkinter (Modern Dark Mode UI)
-   **Local DB**: SQLite (with `meta` table for sync tracking)
-   **Cloud DB**: Oracle Autonomous Transaction Processing (ATP)
-   **Driver**: `python-oracledb` (Thin Mode)

---

## 🏁 Installation & Usage (End Users)

### Prerequisites
-   **Google Chrome** installed.
-   **Setup Pack**: Ask your team administrator for your `Setup_Pack.zip` file.
-   **Visual C++ Redistributable**: Required for the native bridge (usually pre-installed on most Windows systems).

### Steps
1.  **Download the App**: Get the latest `InstaLogger_App.zip` from the **[Releases Page](../../releases)**.
2.  **Extract the Zip**: Unzip to a folder (e.g., `C:\InstaLogger\`).
3.  **Bypass Antivirus (Recommended)**:
    -   Right-click `Fix_Antivirus_Block.bat` and select **"Run as administrator"**.
    -   This script adds a Windows Defender exclusion and unblocks the files to prevent SmartScreen errors.
4.  **Run the Launcher**: Double-click `InstaLogger.exe` inside the folder.
    -   **First Run**: The **Setup Wizard** will appear. Click the drop zone or "Browse" to select your `Setup_Pack.zip`.
    -   **Operator Name**: When prompted, enter your name (e.g., "Sarah"). This links all your outreach to you.
5.  **Install the Extension**:
    -   Open Chrome and go to `chrome://extensions`.
    -   Enable **Developer Mode** (top right).
    -   Click **Load Unpacked**.
    -   Select the `src/extension` folder inside the InstaLogger folder.
6.  **Start Outreach**:
    -   The app runs in the background. Open Instagram and start messaging!
    -   **Note**: If you switch Instagram accounts, the extension will auto-detect the new "Actor" within 5 seconds.

---

## 👨‍💻 Developer Guide

### Environment Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/hashaam101/Insta-Outreach-Logger-Remastered.git
    cd Insta-Outreach-Logger-Remastered
    pip install -r requirements.txt
    ```

2.  **Configure Credentials**:
    -   Place your Oracle Wallet in `assets/wallet/`.
    -   Create `local_config.py` with your DB credentials (see `example_local_config.py`).

3.  **Run in Development Mode**:
    ```bash
    # Run the IPC server directly
    python src/core/ipc_server.py

    # Or use the launcher
    python launcher.py --skip-update --debug
    ```

### Developer CLI (`dev_cli.py`)

The Developer CLI is an interactive toolkit for building, packaging, and managing releases.

```bash
python src/scripts/dev_cli.py
```

**Menu Options:**

| Option | Description |
|--------|-------------|
| **1. Compile** | Runs PyInstaller (One-Folder mode) to create `dist/InstaLogger/`. |
| **2. Generate Setup_Pack** | Creates `dist/Setup_Pack.zip` containing wallet and config. |
| **3. Bump Version & Tag** | Updates `src/core/version.py`, creates a git tag, and optionally pushes to remote. |
| **4. Clean Artifacts** | Removes `build/`, `dist/`, `*.spec`, and `__pycache__` directories. |
| **5. MASTER BUILD** | Full pipeline: Clean → Bump → Pack → Compile → Zip |

### Master Build Workflow

The recommended workflow for creating a new release:

1.  **Run the Master Build**:
    ```bash
    python src/scripts/dev_cli.py
    # Select option 5 (MASTER BUILD)
    ```

2.  **Follow the prompts**:
    -   Choose whether to bump the version (Patch/Minor/Major/Custom)
    -   Confirm pushing to remote when prompted

3.  **Artifacts Created**:
    -   `dist/InstaLogger/` - Application folder (One-Folder mode)
    -   `dist/InstaLogger_App.zip` - Distribution package for end users
    -   `dist/Setup_Pack.zip` - Credentials package for end users

4.  **Create GitHub Release**:
    -   Go to GitHub Releases and create a new release for the tag
    -   Upload `InstaLogger_App.zip` as a release asset

> **Note:** One-Folder mode is used instead of One-File to reduce antivirus false positives.

### Version Management

The version is managed in `src/core/version.py`:

```python
__version__ = "1.0.0"
```

This is the single source of truth, imported by:
- `launcher.py` - For auto-update version comparison
- `dev_cli.py` - For version bumping
- `ipc_server.py` - For display

### Architecture Notes

**Auto-Update Flow:**
1. Launcher checks GitHub Releases API for latest version
2. Compares with `src/core/version.__version__`
3. If update available, downloads new `.exe` and replaces current

**Setup Wizard Flow:**
1. Launcher detects missing `local_config.py` or `assets/wallet/`
2. Opens Setup Wizard GUI
3. User clicks the drop zone or "Browse" to select `Setup_Pack.zip`
4. Wizard validates and extracts to correct locations
5. Wizard registers the Native Messaging Host in Windows Registry

**Sync Engine (Delta Logic):**
- **Meta Table**: Local DB stores `last_cloud_sync` timestamp.
- **Pull**: Requests `WHERE LAST_UPDATED > last_cloud_sync` from Oracle.
- **Push**: Uploads unsynced local logs.

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
│   │   ├── local_db.py     # Local SQLite Database Manager (with Delta Sync meta)
│   │   ├── database.py     # Oracle Cloud Database Manager
│   │   ├── sync_engine.py  # Delta Sync Engine (GitHub-style pull)
│   │   └── version.py      # Version Source of Truth
│   ├── scripts/            # Developer Tools
│   │   └── dev_cli.py      # Interactive Build & Release CLI
│   ├── extension/
│   │   ├── manifest.json
│   │   ├── background.js
│   │   ├── content.js      # v12: Hardened with MutationObserver
│   │   └── injector.js     # Script Injected into Page for Actor Discovery
│   └── gui/
│       └── setup_wizard.py # First-Run Setup (Drag & Drop Zip)
├── launcher.py             # Main Entry Point (Bootstrapper + Auto-Update)
├── Fix_Antivirus_Block.bat # Utility to bypass Antivirus/SmartScreen
├── dashboard.py            # Streamlit Web Dashboard
├── requirements.txt
├── local_config.py         # Local Oracle DB Credentials (Gitignored)
├── operator_config.json    # Local Operator Name (Gitignored)
├── local_data.db           # Local SQLite Database (Gitignored)
└── README.md
```

---

## Troubleshooting

### "Windows Protected Your PC" (SmartScreen)

Since this is an internal tool and the executable is **unsigned**, Windows SmartScreen may block it on first run.

**Primary Solution:**
Run `Fix_Antivirus_Block.bat` as administrator. This script automatically unblocks all files in the directory.

**Manual Solution:**
1. Click **"More info"** on the warning dialog
2. Click **"Run anyway"**

### Antivirus False Positives

PyInstaller-compiled executables can sometimes trigger false positive alerts from antivirus software.

**Primary Solution:**
Run `Fix_Antivirus_Block.bat` as administrator. It will automatically add the application folder to Windows Defender's exclusion list.

### Extension Not Detecting Account / Red "Checking..." Banner

If the extension is stuck on "Checking..." or shows a red border (Detection Failed):
1. **Refresh the page** - The extension checks for account changes every 5 seconds.
2. **Ensure Input Box is Visible** - The "Proximity Climber" relies on the chat input.
3. **Check Connection** - Ensure `InstaLogger.exe` is running.

### Connection Issues

If the extension can't connect to the desktop app:

1. **Ensure InstaLogger.exe is running** - Check the system tray or task manager
2. **Check the native messaging host** - The Setup Wizard registers this automatically
3. **Restart Chrome** - Sometimes a browser restart is needed after setup
