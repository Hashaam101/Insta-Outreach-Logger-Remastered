# 📸 Insta Outreach Logger (Remastered)

A stealthy, local-first CRM for distributed Instagram outreach teams.

---

## 📌 Overview

Insta Outreach Logger is a specialized tool designed to track high-volume Instagram outreach **without triggering anti-bot detection**. Unlike traditional browser extensions that make API calls directly from the browser (which Instagram can detect), this tool uses **Chrome Native Messaging** to offload all logic, storage, and networking to a local desktop application.

### Key Philosophy:

-   **Stealth First**: The browser extension is "dumb." It only scrapes the DOM and passes text to the local OS. It makes **zero** external network requests.
-   **Local Speed**: All data is saved instantly to a local SQLite database (0ms latency), ensuring the UI never lags.
-   **Cloud Sync**: A background process performs "Delta Syncs" (GitHub-style) with a central Oracle Autonomous Database to keep the whole team aligned.
-   **Security**: Credentials are distributed via AES-256 encrypted Setup Packs and only decrypted into memory while the application is running.

---

## 🚀 Key Features

-   **🕵️‍♂️ Invisible Logging**: Uses `chrome.runtime.sendNativeMessage` to bypass browser network stacks.
-   **🔐 Secure Setup Packs**: Credentials (Oracle Wallet + Config) are distributed in AES-256 encrypted zip files (`Setup_Pack_<token>.zip`). The app dynamically decrypts them on startup using a token-derived key.
-   **📂 Auto-Extension Deployment**: The Chrome Extension is automatically deployed to `Documents/Insta Logger Remastered/extension` on startup, making it easy to load and ensuring all users are on the same version.
-   **🤖 Automated Actor & Operator Discovery**: Eliminates manual configuration by automatically identifying the human operator and Instagram account being used. Detects account switching in real-time.
-   **🔔 Real-Time Status Check**: Visual notification banners show whether a prospect has been contacted before, directly on Instagram profile and DM pages.
-   **📊 Status Dropdown**: Update prospect status (Cold, Warm, Hot, Booked, etc.) directly from the notification banner.
-   **⚡ Zero-Config Deployment**: Distributed as a compiled `.exe` launcher that auto-updates from GitHub Releases.
-   **🔄 Delta Sync Engine**: Uses a `LAST_UPDATED` timestamp to pull only changed records from Oracle Cloud.
-   **👥 Multi-Profile Support**: Handles multiple Instagram accounts running on the same machine seamlessly.

---

## 🕵️ Contact Discovery Module

A background intelligence process that enriches prospect profiles with contact information (Email/Phone) immediately after they are discovered.

### 1. Trigger
This process runs in the background immediately after a new profile is saved to the local database (either via manual message logging or status change).

### 2. Strategy - Step 1 (Direct)
-   **Full Header Scraping**: The extension scrapes the entire profile header text (Name, Bio, Link, Address) to ensure no visible contact info is missed.
-   **Intelligent Name Extraction**: Prioritizes `og:title` metadata to correctly capture the Business Name instead of the address.
-   **Link Analysis**: Checks if a "Bio Link" exists. If present, the module visits the target website (automatically decoding `l.instagram.com` redirects) and crawls for:
    -   `mailto:` links.
    -   `tel:` links.
    -   "Contact Us" pages.

### 3. Strategy - Step 2 (Fallback)
If Step 1 yields no results, the module initiates a headless DuckDuckGo search.
-   **Query Format**: `"{Business Name} {Address from Bio} phone email"`
-   **Parsing**: Analyzes search snippets to identify and extract patterns matching email addresses and phone numbers.
-   **Validation**: Applies strict regex validation to ensure phone numbers match standard US formats (e.g., `(808) 555-0199`) and filters out noise.

### 4. Sync Gating & Data Schema
-   **Gatekeeper Logic**: The system blocks cloud synchronization for a specific prospect until the discovery process is complete (`discovery_status: 'complete'`). This prevents incomplete records from polluting the Oracle Cloud DB.
-   **Fields**:
    -   `email` (string): Discovered email address.
    -   `phone_number` (string): Discovered phone number.
    -   `source_summary` (string): Origin of the data (e.g., "Found on Website footer" or "DuckDuckGo Snippet").

---

## 🌐 Web Dashboard (Command Center)

The Command Center is a web-based interface built with Streamlit that provides a centralized location for administrators and team leads to manage the outreach process. It allows users to:

-   **View Global Statistics**: Get a real-time overview of key performance indicators (KPIs).
-   **Filter and Group Analytics**: Dynamically pivot all performance data by Operator or Actor.
-   **Manage Leads**: Interactively filter, sort, and edit the status and notes for every prospect.

## ☁️ Streamlit Cloud Deployment

The dashboard is deployed via a separate orphan branch to maintain a lightweight environment. For instructions on how to sync code updates without breaking dependencies, see [DASHBOARD.md > Deployment & Maintenance](DASHBOARD.md#deployment--maintenance).

---

## 🛠️ Technology Stack

-   **Frontend**: Chrome Extension (Manifest V3)
-   **Desktop App**: Python 3.11+ (PyInstaller)
-   **Security**: AES-256 Encryption (pyzipper), HMAC-SHA256
-   **GUI**: CustomTkinter
-   **Local DB**: SQLite
-   **Cloud DB**: Oracle Autonomous Transaction Processing (ATP)

---

## 🏁 Installation & Usage (End Users)

### Prerequisites
-   **Google Chrome** installed.
-   **Setup Pack**: Ask your team administrator for your `Setup_Pack_<token>.zip` file.
-   **Visual C++ Redistributable**: Required for the native bridge.

### Steps
1.  **Download the App**: Get the latest `InstaLogger_App.zip` from the **[Releases Page](../../releases)**.
2.  **Extract the Zip**: Unzip to a folder (e.g., `C:\InstaLogger\`).
3.  **Bypass Antivirus (Recommended)**:
    -   Right-click `Fix_Antivirus_Block.bat` and select **"Run as administrator"**.
    -   This script unblocks files to prevent SmartScreen errors.
4.  **Run the Launcher**: Double-click `InstaLogger.exe`.
    -   **CLI Menu**: Press **ENTER** to start the application.
    -   **First Run**: The **Setup Wizard** will appear. Drag and drop your `Setup_Pack_<token>.zip` onto the window.
    -   **Operator Name**: Enter your name (e.g., "Sarah").
    -   **Note**: The app will automatically copy the extension to your Documents folder.
5.  **Install the Extension**:
    -   Open Chrome and go to `chrome://extensions`.
    -   Enable **Developer Mode** (top right).
    -   Click **Load Unpacked**.
    -   Navigate to **Documents** -> **Insta Logger Remastered** -> **extension**.
6.  **Start Outreach**:
    -   The app runs in the background. Open Instagram and start messaging!

### Uninstallation
To completely remove the application and all its data:
1.  Run `uninstall.exe` (or `python uninstall.py` in dev).
2.  Type `yes` to confirm.
3.  The tool will close all running instances, delete the data in Documents, and remove the application folder.

---

## 👨‍💻 Developer Guide

### Environment Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/hashaam101/Insta-Outreach-Logger-Remastered.git
    cd Insta-Outreach-Logger-Remastered
    pip install -r requirements.txt
    ```

2.  **Configure Credentials (Dev)**:
    -   Place your Oracle Wallet in `assets/wallet/`.
    -   Create `local_config.py` with your DB credentials.

3.  **Run in Development Mode**:
    ```bash
    # Run the GUI Application (Primary Entry Point)
    python start_gui.py
    ```

### Desktop GUI (Command Center)

The application features a modern desktop interface built with `customtkinter`. It is divided into two main sections:

#### 1. Dashboard Tab (Visual Overview)
-   **Live Status**: Displays real-time actions (e.g., "Scanning Bio...", "Syncing with Oracle...").
-   **Stats Grid**: Real-time counters for Profiles Scraped, Emails Found, Phone Numbers Found, and Errors.
-   **Activity Feed**: A chronological list of high-level intelligence events.

#### 2. Raw Console Tab
-   **Unified Logging**: Intercepts `stdout` and `stderr` to display all internal engine logs in a scrollable view.
-   **Stdout Redirector**: Ensures that background processing logs from the IPC Server and Discovery Module are visible without a terminal.

---

## 📦 Directory Structure

```plaintext
/
├── assets/
│   ├── wallet/             # Oracle Wallet files (Dev Only)
│   └── icon.ico            # App Icon
├── src/
│   ├── core/
│   │   ├── ipc_server.py   # IPC Server & Operator Management
│   │   ├── contact_discovery.py # Background Intelligence Module
│   │   ├── secrets_manager.py # Dynamic Credential Decryption
│   │   ├── security.py     # Crypto Logic
│   │   ├── database.py     # Oracle Cloud Database Manager
│   │   └── sync_engine.py  # Delta Sync Engine
│   ├── scripts/
│   │   └── dev_cli.py      # Build & Release CLI
│   ├── extension/
│   │   ├── manifest.json
│   │   ├── background.js
│   │   └── content.js      # Hardened with MutationObserver
│   └── gui/
│       ├── app_ui.py       # Main CustomTkinter GUI
│       └── setup_wizard.py # Secure Setup GUI
├── start_gui.py            # Primary Entry Point (GUI)
├── launcher.py             # Bootstrapper & Auto-Update
├── uninstall.py            # Clean Uninstaller
├── dashboard.py            # Streamlit Web Dashboard
├── requirements.txt
├── local_config.py         # Dev Credentials (Gitignored)
└── README.md
```

---

## Troubleshooting

### "Windows Protected Your PC" (SmartScreen)
Run `Fix_Antivirus_Block.bat` as administrator to unblock the application.

### Extension Errors
-   **Red Border**: Ensure `InstaLogger.exe` is running.
-   **Connection Failed**: Check if the Native Host is registered (run Setup Wizard again via Launcher Menu Option 1).

### Uninstalling Extension
If you need to update the extension manually or delete it, ensure Chrome is fully closed first, or use the app's built-in update mechanism.