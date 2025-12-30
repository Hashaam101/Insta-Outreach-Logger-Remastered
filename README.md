# InstaCRM Desktop Agent (Remastered)

A stealthy, local-first CRM agent for distributed Instagram outreach teams. Part of the **InstaCRM Ecosystem**.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage Guide](#usage-guide)
- [The Ecosystem](#the-ecosystem)
- [Security Model](#security-model)
- [Development](#development)
- [Testing Guide](#testing-guide)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The InstaCRM Desktop Agent is a specialized tool designed to track high-volume Instagram outreach **without triggering anti-bot detection**. It works in tandem with the **InstaCRM Dashboard** to provide a complete outreach solution.

### Key Philosophy

| Principle | Implementation |
|-----------|----------------|
| **Stealth First** | Uses **Chrome Native Messaging** to offload all logic to a local Python host. Zero external network requests from the browser. |
| **Governance & Safety** | Enforces team-wide **Rules** (Frequency Caps, Interval Spacing) locally to protect accounts from bans. |
| **Secure Identity** | Authenticates operators via **Google OAuth 2.0**, linking all activity to a verifiable team member. |
| **Local Speed** | All data is saved instantly to a local SQLite database (0ms latency). |
| **Cloud Sync** | Background "Delta Syncs" with the central Oracle Database keep the team aligned. |

---

## Key Features

### Core Functionality

- **Invisible Logging**: Bypasses browser network stacks using local IPC (Inter-Process Communication)
- **Secure Login**: Operators sign in with Google to establish a verified session linked to the Dashboard
- **Active Safety Protocols**: Locally enforces "Frequency Caps" and "Interval Spacing" rules
- **Self-Healing Data**: Automatic local database backup and corruption recovery
- **Resilient Bridge**: Auto-reconnecting IPC bridge ensures no downtime between browser and host

### User Experience

- **Real-Time Status**: Visual banners on Instagram profiles with integrated **Toast Notifications**
- **Mission Control UI**: Desktop dashboard showing sync health, session telemetry, and easy access to logs/support
- **Auto-Tab Switcher**: Configurable automation with **Foreground Focus Protection** to prevent accidental keypresses
- **One-Click Installer**: Deploys to Documents, manages shortcuts, and handles auto-updates

### Data Management

- **Local SQLite Database**: Fast offline-first storage with automatic backups
- **Oracle Cloud Sync**: Bidirectional delta sync with exponential backoff
- **Contact Enrichment**: Background scraping of emails/phones from target profiles
- **Event Logging**: Comprehensive audit trail with parent-child event structure

---

## Architecture

```
+------------------+     Native Messaging      +------------------+
|  Chrome Browser  | <-----------------------> |   Python Host    |
|                  |     (stdin/stdout)        |                  |
|  +------------+  |                           |  +------------+  |
|  | Extension  |  |                           |  | IPC Server |  |
|  | (content.js|  |                           |  +------+-----+  |
|  | background)|  |                           |         |        |
|  +------------+  |                           |         v        |
+------------------+                           |  +------------+  |
                                               |  | Local DB   |  |
                                               |  | (SQLite)   |  |
                                               |  +------+-----+  |
                                               |         |        |
                                               |         v        |
                                               |  +------------+  |
                                               |  | Sync Engine|  |
                                               |  +------+-----+  |
                                               +---------|--------+
                                                         |
                                                         v
                                               +------------------+
                                               |   Oracle Cloud   |
                                               |   (ATP Database) |
                                               +------------------+
```

### Three-Layer Design

1. **Browser Layer** (Chrome Extension)
   - DOM monitoring and message capture
   - Profile data scraping (username, bio, verified status)
   - UI injection (status banners, toasts)
   - Native Messaging communication

2. **Desktop Layer** (Python Application)
   - IPC Server for message handling
   - Local SQLite database management
   - Pre-flight safety checks (Rules enforcement)
   - Background sync engine
   - GUI dashboard for monitoring

3. **Cloud Layer** (Oracle ATP)
   - Central database for team data
   - Operator/Actor management
   - Rules and Goals distribution
   - Team-wide analytics

---

## Installation

### Prerequisites

- **Python 3.9+** with pip
- **Google Chrome** browser
- **Oracle TLS Connection String** (provided via Setup Pack)
- **Google OAuth Credentials** (client_secret.json)

### Quick Install

1. **Download the Latest Release**
   ```bash
   # Clone or download from GitHub
   git clone https://github.com/hashaam101/Insta-Outreach-Logger-Remastered.git
   cd Insta-Outreach-Logger-Remastered
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Setup Wizard**
   ```bash
   python launcher.py
   ```
   - Upload your `Setup_Pack.zip` (contains .env with TLS connection string)
   - Enter your Operator name
   - Load the Chrome extension from the generated folder
   - Enter the Extension ID

4. **Sign In with Google**
   - Click "Sign in with Google" on the login screen
   - Complete OAuth flow in your browser

### One-Click Installer (For End Users)

Run the installer GUI for automatic deployment:
```bash
python src/scripts/installer_gui.py
```

This will:
- Copy files to `Documents/Insta Outreach Logger`
- Create Desktop and Start Menu shortcuts
- Configure Native Messaging registry entries

---

## Configuration

### File Structure

```
project_root/
├── local_config.py          # Oracle DB credentials (NEVER commit!)
├── operator_config.json     # Operator identity (auto-generated)
├── user_preferences.json    # User settings (auto-generated)
├── update_config.json       # Auto-update source config
├── token.pickle             # OAuth tokens (auto-generated)
└── assets/
    ├── client_secret.json   # Google OAuth credentials
    └── (wallet directory removed - using TLS connection strings)
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `IOL_DB_USER` | Oracle database username | From local_config.py |
| `IOL_DB_PASSWORD` | Oracle database password | From local_config.py |
| `IOL_DB_DSN` | Oracle connection string | From local_config.py |

### User Preferences (user_preferences.json)

```json
{
  "auto_tab_switch": true,
  "tab_switch_frequency": 1,
  "tab_switch_delay": 2.0
}
```

---

## Usage Guide

### Starting the Agent

1. Launch the application:
   ```bash
   python launcher.py
   ```

2. Sign in with Google (if not already authenticated)

3. Click **"CONNECT AGENT"** to start the IPC server

4. The sidebar will show:
   - `SYNC: OK (HH:MM)` - Green when synced
   - `SYNC: ERROR` - Red if sync failed
   - Active Actor username

### Dashboard Metrics

| Metric | Description |
|--------|-------------|
| **Outreach Sent** | Total DMs logged this session |
| **Profiles Scraped** | Profiles with data extracted |
| **Leads Enriched** | Contacts with email/phone found |
| **Safety Alerts** | Rule violations triggered |

### Chrome Extension

1. **Profile Pages**: Shows banner with contact status
   - "Not Contacted" - First time reaching out
   - "Cold No Reply" - Previously contacted, no response
   - "Replied" / "Warm" / "Booked" etc. - Conversation status

2. **DM Pages**: Automatically logs sent messages

3. **DM Scroller**: Click the pulsing icon to auto-scroll DM list

### Auto-Tab Switcher

Configure in Settings:
- **Trigger Frequency**: Switch after N messages
- **Delay**: Wait time before switching (seconds)
- **Foreground Protection**: Skips if Chrome loses focus

---

## The Ecosystem

### Component Relationships

```
+------------------------+
|   InstaCRM Dashboard   |  <-- Web App (Team Analytics)
|   (Next.js / React)    |
+-----------+------------+
            |
            v
+------------------------+
|    Oracle ATP Cloud    |  <-- Central Database
|  (EVENT_LOGS, RULES,   |
|   GOALS, OPERATORS)    |
+-----------+------------+
            ^
            |
+-----------+------------+
|   Desktop Agent        |  <-- This Application
|   (Python + Chrome)    |
+------------------------+
```

### Data Flow

1. **Outreach Logging**
   - Extension detects DM send → Native Message to Python
   - Python creates EVENT_LOG + OUTREACH_LOG locally
   - Sync Engine pushes to Oracle in batches

2. **Safety Checks**
   - Before logging, PreFlightChecker validates against RULES
   - Returns PASS/WARN/BLOCK status to extension
   - Extension shows toast notification if warned

3. **Governance Sync**
   - Sync Engine pulls RULES and GOALS from Oracle
   - Stores in local SQLite cache
   - PreFlightChecker uses local cache for speed

---

## Security Model

### Authentication Flow

```
User -> Google OAuth 2.0 -> token.pickle (local)
                         -> Oracle lookup by email
                         -> Operator identity established
```

### Data Protection

| Layer | Protection |
|-------|------------|
| **Browser** | Native Messaging (no external network) |
| **IPC** | Localhost only (127.0.0.1:65432) |
| **Local DB** | SQLite with auto-backup |
| **Cloud** | Oracle ATP with TLS connection string |
| **Credentials** | Setup Pack encrypted with HMAC-derived key |

### Privacy Features

- **Excluded Targets**: Message text is NOT logged for excluded profiles
- **Local-First**: All data stored locally before cloud sync
- **No Browser Network**: Extension never makes external HTTP requests

---

## Development

### Project Structure

```
src/
├── core/
│   ├── ipc_server.py      # Main IPC server (19KB)
│   ├── local_db.py        # SQLite manager (19KB)
│   ├── sync_engine.py     # Cloud sync logic (8KB)
│   ├── bridge.py          # Native messaging bridge (5KB)
│   ├── auth.py            # Google OAuth (3KB)
│   ├── security.py        # Pre-flight checks (4KB)
│   ├── database.py        # Oracle manager (11KB)
│   └── version.py         # Version info (1KB)
├── gui/
│   ├── app_ui.py          # Main dashboard (25KB)
│   └── setup_wizard.py    # First-run wizard (31KB)
├── extension/
│   ├── manifest.json      # Extension config
│   ├── background.js      # Service worker (8KB)
│   ├── content.js         # DOM interaction (36KB)
│   └── scroller/          # DM scroller module
└── scripts/
    ├── dev_cli.py         # Developer tools (22KB)
    ├── installer_gui.py   # Installer (6KB)
    └── bump_version.py    # Version utility
```

### Developer CLI

```bash
python src/scripts/dev_cli.py
```

Options:
1. **Compile App** - PyInstaller one-folder build
2. **Generate Setup Pack** - Create encrypted deployment package
3. **Bump Version** - Update version across all files
4. **Clean Artifacts** - Remove build directories
5. **MASTER BUILD** - Full release pipeline

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=src tests/
```

---

## Testing Guide

### Phase 5: Comprehensive Verification

#### 1. Setup & Identity (First Run)

- [ ] Run `launcher.py` with fresh install (no `operator_config.json`)
- [ ] Verify Setup Wizard launches automatically
- [ ] Upload `Setup_Pack.zip` and verify extraction
- [ ] Enter Operator name (should auto-complete from DB)
- [ ] Verify extension folder created in Documents

#### 2. Authentication & Onboarding

- [ ] Click "Sign in with Google"
- [ ] Verify browser opens OAuth flow
- [ ] Verify redirect to localhost callback
- [ ] New users see "Establish Identity" screen
- [ ] Existing users go directly to Dashboard

#### 3. Dashboard & Sync Status

- [ ] Verify `SYNC: STARTING...` → `SYNC: OK (HH:MM)`
- [ ] Session timer counts up
- [ ] Disconnect internet → `SYNC: ERROR` after ~60s
- [ ] Reconnect → Status returns to Green

#### 4. Extension & Scroller

- [ ] Navigate to `instagram.com/direct/`
- [ ] Verify pulsing icon appears
- [ ] Click to open Scroller panel
- [ ] Start scrolling → DM list scrolls
- [ ] Navigate away → Button disappears

#### 5. Outreach Logging & Privacy

- [ ] Send DM to new target
- [ ] Verify banner: "Not Contacted Before"
- [ ] Verify Dashboard metric increases
- [ ] Mark target as "Excluded"
- [ ] Send another message → Verify `message_text` is NULL in logs

#### 6. Auto-Tab Switcher

- [ ] Enable in Settings (Trigger=1, Delay=2s)
- [ ] Send DM in Chrome
- [ ] Wait 2 seconds → Tab closes
- [ ] Focus switches to next tab

#### 7. Auto-Updater

- [ ] Check Settings for update source URL
- [ ] Manually lower version in `version.py`
- [ ] Restart → Should detect update and install

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Application not running" in extension | Start the Desktop Agent and click CONNECT |
| "Native host not found" | Run Setup Wizard to configure registry |
| Sync stuck on ERROR | Check internet connection, verify DB_DSN in .env |
| OAuth fails | Ensure `client_secret.json` exists in `assets/` |
| Extension not detecting DMs | Refresh Instagram page, check extension permissions |

### Log Files

```
Documents/Insta Logger Remastered/logs/
├── app.log          # Main application logs
├── sync.log         # Sync engine logs
└── bridge.log       # Native messaging logs
```

### Debug Mode

```bash
python launcher.py --debug
```

---

## Contributing

### Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Keep functions under 50 lines
- Document complex logic with comments

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Reporting Issues

Use the GitHub Issues tab:
- Include Python version and OS
- Attach relevant log files
- Describe steps to reproduce

---

## Development Status

- [x] Phase 1: Core Bridge & Native Messaging
- [x] Phase 2: Auto-Discovery Architecture
- [x] Phase 3: Dashboard V1 Migration
- [x] Phase 4: Governance & Event Schema Update
  - [x] Migrate Local DB to `EVENT_LOGS` / `OUTREACH_LOGS` schema
  - [x] Implement `RULES` and `GOALS` sync
  - [x] Add Pre-flight Safety Checks to Bridge
  - [x] Update Sync Engine for bi-directional flow
  - [x] Rebrand Desktop GUI with Session Telemetry
  - [x] Implement Google OAuth Login
- [ ] Phase 5: Comprehensive Verification & Testing (See ToDo.md)
- [ ] Phase 6: Security & Workflow Improvements (See ToDo.md)

---

## License

This project is proprietary software. All rights reserved.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/hashaam101/Insta-Outreach-Logger-Remastered/issues)
- **Documentation**: This README and ToDo.md
- **Contact**: Through the Dashboard support channels
