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
-   **🔐 Secure Setup Packs**: Credentials (Oracle Wallet + Config) are distributed in AES-256 encrypted zip files.
-   **📂 Auto-Extension Deployment**: The Chrome Extension is automatically deployed to `Documents/Insta Logger Remastered/extension` on startup.
-   **🤖 Automated Actor & Operator Discovery**: Eliminates manual configuration by automatically identifying the human operator and Instagram account being used.
-   **📊 Status Management**: Visual banners on Instagram for real-time lead status checks and updates.
-   **⚡ Zero-Config Deployment**: Distributed as a compiled `.exe` launcher that auto-updates from GitHub.

---

## 🕵️ Contact Discovery Module

A background intelligence process that enriches prospect profiles with contact information (Email/Phone) immediately after they are discovered.

1.  **Full Header Scraping**: Scrapes Name, Bio, Link, and Address.
2.  **Link Analysis**: Visits bio links to find `mailto:` or `tel:` tags.
3.  **Fallback Search**: Performs headless DuckDuckGo searches if direct scraping fails.
4.  **Sync Gating**: Blocks cloud synchronization until discovery is complete.

---

## 🌐 Web Dashboard (Command Center)

A modern web-based interface built with **Next.js 14** for centralized outreach management.

**Key Features:**
- **🔒 Secure Auth**: Login via Google.
- **🛡️ Operator Onboarding**: link Google accounts to unique team IDs.
- **📊 Real-Time KPIs**: Live metrics for prospects, outreach volume, and booking rates.
- **📋 Lead Management**: Searchable grid to manage prospect status and notes.

> **Note**: The dashboard code is maintained in the `dashboard` branch.

---

## 🗄️ Database Architecture

### Cloud DB (Oracle ATP)
The central source of truth for the entire team.
- **`OPERATORS`**: Human team members.
- **`ACTORS`**: Instagram accounts linked to operators.
- **`PROSPECTS`**: Lead database with status and contact info.
- **`OUTREACH_LOGS`**: Append-only log of every DM sent.

### Local DB (SQLite)
Acts as a high-speed cache and offline queue for the desktop application.

---

## 👨‍💻 Developer Guide

### Environment Setup
1.  **Clone**: `git clone https://github.com/hashaam101/Insta-Outreach-Logger-Remastered.git`
2.  **Dependencies**: `pip install -r requirements.txt`
3.  **Config**: Place Oracle Wallet in `assets/wallet/` and create `local_config.py`.
4.  **Run**: `python start_gui.py`

---

## ✅ Development Status

- [x] Phase 1-6: Core Bridge, Extension, and Sync Engine (Complete)
- [x] Phase 7: Optimization & Delta Sync (Complete)
- [x] Phase 8: Contact Discovery Enhancements (Complete)
- [x] Phase 9: Next.js Dashboard Migration (Complete - see `dashboard` branch)
