# 📸 InstaCRM Desktop Agent (Remastered)

A stealthy, local-first CRM agent for distributed Instagram outreach teams. Part of the **InstaCRM Ecosystem**.

---

## 📌 Overview

The InstaCRM Desktop Agent is a specialized tool designed to track high-volume Instagram outreach **without triggering anti-bot detection**. It works in tandem with the **InstaCRM Dashboard** to provide a complete outreach solution.

### Key Philosophy:

-   **Stealth First**: Uses **Chrome Native Messaging** to offload all logic to a local Python host. Zero external network requests from the browser.
-   **Governance & Safety**: Enforces team-wide **Rules** (Frequency Caps, Interval Spacing) locally to protect accounts from bans.
-   **Secure Identity**: Authenticates operators via **Google OAuth**, linking all activity to a verifiable team member.
-   **Local Speed**: All data is saved instantly to a local SQLite database (0ms latency).
-   **Cloud Sync**: Background "Delta Syncs" with the central Oracle Database keep the team aligned.

---

## 🚀 Key Features

-   **🕵️‍♂️ Invisible Logging**: Bypasses browser network stacks using local IPC.
-   **🔐 Secure Login**: Operators sign in with Google to establish a verified session linked to the Dashboard.
-   **🛡️ Active Safety Protocols**: Locally enforces "Frequency Caps" and "Interval Spacing" rules.
-   **🛠️ Self-Healing Data**: Automatic local database backup and corruption recovery.
-   **📂 Resilient Bridge**: Auto-reconnecting IPC bridge ensures no downtime between browser and host.
-   **📊 Real-Time Status**: Visual banners on Instagram profiles with integrated **Toast Notifications**.
-   **📡 Mission Control UI**: Desktop dashboard showing sync health, session telemetry, and easy access to logs/support.
-   **⚡ Auto-Tab Switcher**: Configurable automation with **Foreground Focus Protection** to prevent accidental keypresses in other apps.
-   **📦 One-Click Installer**: Deploys to Documents, manages shortcuts, and handles auto-updates.

---

## 🌐 The Ecosystem
... (rest remains similar) ...

### 🧪 Developer Testing Guide

For a comprehensive, step-by-step verification protocol, please refer to the **[Detailed Testing Guide in ToDo.md](ToDo.md#5-phase-5-comprehensive-verification--testing)**.

#### Quick End-to-End Verification
1.  **Start the Agent**: Run `python launcher.py`.
2.  **Login**: Click "Sign in with Google".
3.  **Verify Sync**: Check the sidebar for `SYNC: OK`.
4.  **Test Privacy**: Mark a target as "Excluded" and send a DM; verify `message_text` is `None` in the logs.
5.  **Test Safety**: Switch focus away from Chrome during an Auto-Tab Switch delay; verify the switch is skipped.
6.  **Test Scroller**: Navigate to DMs and verify the pulsing 📜 icon triggers smooth scrolling with toast feedback.

---

## ✅ Development Status

- [x] Phase 1: Core Bridge & Native Messaging (Complete)
- [x] Phase 2: Auto-Discovery Architecture (Complete)
- [x] Phase 3: Dashboard V1 Migration (Complete)
- [x] Phase 4: Governance & Event Schema Update (Complete)
    -   [x] Migrate Local DB to `EVENT_LOGS` / `OUTREACH_LOGS` schema.
    -   [x] Implement `RULES` and `GOALS` sync.
    -   [x] Add Pre-flight Safety Checks to Bridge.
    -   [x] Update Sync Engine for bi-directional flow.
    -   [x] Rebrand Desktop GUI with Session Telemetry.
    -   [x] Implement Google OAuth Login.