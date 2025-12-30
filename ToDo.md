# To-Do: InstaCRM Desktop Agent Roadmap

This document outlines the development phases for the Desktop Agent and Chrome Extension.

---

## Completed Phases

### Phase 1: Local Database & Schema Migration

- [x] Refactor `init_db()` with new schema
- [x] Create `event_logs` table (parent)
- [x] Create `outreach_logs` table (child)
- [x] Create `rules` and `goals` tables
- [x] Migration script for existing data

### Phase 2: Backend Logic & Bridge Updates

- [x] Update message handling for EVENT_LOG structure
- [x] Implement Pre-Flight Safety Checks
- [x] Add `check_safety_rules()` function
- [x] Update JSON response format with status

### Phase 3: Sync Engine Overhaul

- [x] Push Logic (Local -> Cloud) with batch insert
- [x] ID Mapping for Cloud-generated IDs
- [x] Pull Logic for Rules & Goals
- [x] Delta Sync for Targets

### Phase 4: Chrome Extension Updates

- [x] Update Status Banner for new response types
- [x] Add Warning UI with toast notifications
- [x] Ensure robust username scraping

---

## Phase 5: Comprehensive Verification & Testing

### 1. Setup & Identity (First Run)

- [ ] Run `launcher.py` (or `.exe`) with fresh install
- [ ] Ensure `operator_config.json` is deleted (wallet files no longer used)
- [ ] Verify Setup Wizard auto-launches
- [ ] Test Step 1: Upload `Setup_Pack.zip` validation (contains only .env file)
- [ ] Test Step 2: Operator Name auto-complete
- [ ] Test Step 3: "Open Extension Folder" opens explorer
- [ ] Test Step 4: Extension ID entry
- [ ] Verify Login Screen appears after completion

### 2. Authentication & Onboarding

- [ ] Click "Sign in with Google"
- [ ] Verify browser opens to Google Login
- [ ] Verify localhost redirect after auth
- [ ] Test new user flow: "Establish Identity" screen
- [ ] Test existing user flow: Direct to Dashboard

### 3. Dashboard & Sync Status

- [ ] Verify `SYNC: STARTING...` → `SYNC: OK (HH:MM)`
- [ ] Verify Session timer counts up
- [ ] Test internet disconnect: `SYNC: ERROR` after ~60s
- [ ] Test reconnect: Status returns to Green

### 4. Extension & Scroller

- [ ] Navigate to `instagram.com/direct/`
- [ ] Verify pulsing "📜" button appears
- [ ] Test Scroller Panel open/close
- [ ] Test auto-scrolling with toast feedback
- [ ] Verify button disappears when navigating away

### 5. Outreach Logging & Privacy

- [ ] Send DM to new target
- [ ] Verify "Not Contacted Before" banner
- [ ] Verify Dashboard "Outreach Sent" counter
- [ ] Test Privacy: Mark target as "Excluded"
- [ ] Verify `message_text` is NULL in EVENT_LOGS for excluded

### 6. Auto-Tab Switcher

- [ ] Enable in Settings (Trigger=1, Delay=2s)
- [ ] Send DM in Chrome
- [ ] Verify 2-second delay before switch
- [ ] Verify Ctrl+W (close tab) + Ctrl+Tab (next tab)
- [ ] Test Foreground Protection: Focus away → skip switch

### 7. Auto-Updater

- [ ] Verify "Update Source" in Settings shows GitHub URL
- [ ] Simulate: Lower version in `version.py` to `0.0.1`
- [ ] Restart and verify update detection
- [ ] Verify download and restart (requires GitHub release)

### 8. Installer (Final Artifact)
- [ ] Run `src/scripts/installer_gui.py`
- [ ] Verify installer UI opens
- [ ] Click "Install Now" and verify file copy
- [ ] Verify Desktop shortcut creation
- [ ] Verify Start Menu shortcut creation
- [ ] Run shortcut and verify app launches

---

## Phase 6: Security & Code Quality Improvements

### 6.1 Critical Security Fixes

#### 6.1.1 Remove Hardcoded Secrets

- [ ] **CRITICAL**: Move `MASTER_SECRET_KEY` from `security.py:15` to environment variable
  - Current: `MASTER_SECRET_KEY = "IOL_SEC_KEY_v1_" + "9f86d081..."` (hardcoded)
  - Target: Load from `os.environ.get('IOL_MASTER_SECRET')` or encrypted config
- [ ] **CRITICAL**: Move `AUTH_KEY` from `ipc_protocol.py:39` to environment variable
  - Current: `AUTH_KEY = b'insta_lead_secret_key'` (hardcoded, weak)
  - Target: Generate secure random key on first run, store in system keyring

#### 6.1.2 Secure Token Storage

- [ ] Replace `pickle` for token storage with encrypted JSON or keyring
  - Current: `token.pickle` (pickle is insecure, can execute arbitrary code)
  - Target: Use `keyring` library or encrypt with DPAPI on Windows
- [ ] Add token expiry validation before use

#### 6.1.3 IPC Security Hardening

- [ ] Implement proper authentication handshake with challenge-response
  - Current: Simple static key comparison
  - Target: HMAC-based challenge-response authentication
- [ ] Add rate limiting to prevent brute-force attacks on IPC
- [ ] Validate all incoming message structures (schema validation)
- [ ] Add message integrity check (HMAC signature on messages)

#### 6.1.4 Input Validation & Sanitization

- [ ] Add SQL parameterization audit (verify no SQL injection vectors)
- [ ] Sanitize usernames before database queries
- [ ] Validate JSON structure on all IPC messages
- [ ] Add length limits on all text inputs

#### 6.1.5 Credential Management

- [ ] Verify `local_config.py` is in `.gitignore` and never committed
- [ ] Add pre-commit hook to prevent credential commits
- [ ] Add secrets scanning to CI pipeline
- [ ] Document secure credential setup in README

---

### 6.2 Code Quality Improvements

#### 6.2.1 Error Handling

- [ ] Replace bare `except:` blocks with specific exception types
  - `auth.py:105` - bare except
  - `app_ui.py:130` - bare except
  - `app_ui.py:138` - bare except
- [ ] Add structured error logging with context
- [ ] Implement graceful degradation for non-critical failures

#### 6.2.2 Type Hints & Documentation

- [ ] Add type hints to all public functions in `local_db.py`
- [ ] Add type hints to all public functions in `sync_engine.py`
- [ ] Add type hints to all public functions in `ipc_server.py`
- [ ] Add docstrings to undocumented functions

#### 6.2.3 Port Configuration Consistency

- [ ] Resolve port discrepancy: `ipc_protocol.py` uses 65432, `bridge.py` mentions 12345
  - Audit all files for port references
  - Centralize port configuration in `version.py` or config file

#### 6.2.4 Code Cleanup

- [ ] Remove legacy comments and dead code
- [ ] Remove `# TODO` comments that are completed
- [ ] Consolidate duplicate utility functions
- [ ] Extract magic numbers to named constants

#### 6.2.5 Logging Improvements

- [ ] Implement structured logging with log levels
- [ ] Add log rotation to prevent disk space issues
- [ ] Add request/response logging for debugging
- [ ] Create separate log files per component (sync, ipc, auth)

---

### 6.3 Workflow & Developer Experience

#### 6.3.1 CI/CD Pipeline

- [ ] Create GitHub Actions workflow for:
  - Python linting (flake8, pylint)
  - Type checking (mypy)
  - Unit tests (pytest)
  - Security scanning (bandit, safety)
- [ ] Add automated version tagging on release
- [ ] Add automated GitHub Release creation

#### 6.3.2 Development Setup

- [ ] Create `setup.py` or `pyproject.toml` for proper package management
- [ ] Add `requirements-dev.txt` for development dependencies
- [ ] Create `Makefile` or `scripts/` for common dev tasks
- [ ] Add pre-commit hooks configuration (`.pre-commit-config.yaml`)

#### 6.3.3 Testing Infrastructure

- [ ] Create `tests/` directory structure:
  ```
  tests/
  ├── unit/
  │   ├── test_local_db.py
  │   ├── test_security.py
  │   └── test_sync_engine.py
  ├── integration/
  │   └── test_ipc_flow.py
  └── conftest.py
  ```
- [ ] Add pytest fixtures for database mocking
- [ ] Add coverage threshold requirement (80%)

#### 6.3.4 Configuration Management

- [ ] Create centralized config loader (`config.py`)
- [ ] Support environment variables for all settings
- [ ] Add config validation on startup
- [ ] Support `.env` files for development

---

### 6.4 UI/UX Improvements

#### 6.4.1 Dashboard Enhancements

- [ ] Add loading spinner during sync operations
- [ ] Add progress bar for batch operations
- [ ] Add confirmation dialogs for destructive actions
- [ ] Add keyboard shortcuts (Ctrl+S for sync, Ctrl+Q to quit)

#### 6.4.2 Settings Window Improvements

- [ ] Add "Reset to Defaults" button
- [ ] Add import/export settings functionality
- [ ] Add sync interval configuration
- [ ] Add log level configuration

#### 6.4.3 Extension UI Improvements

- [ ] Add dark mode support for injected UI
- [ ] Add animation improvements for banner transitions
- [ ] Add collapsible/expandable banner mode
- [ ] Add "Copy Target Info" button

#### 6.4.4 Error Feedback

- [ ] Show user-friendly error messages (not stack traces)
- [ ] Add "Copy Error Details" button for support
- [ ] Add automatic error reporting (opt-in)
- [ ] Add connection status indicator in system tray

---

### 6.5 Performance Optimizations

#### 6.5.1 Database Performance

- [ ] Add database indexes for frequently queried columns
  - `event_logs.act_id`, `event_logs.created_at`
  - `prospects.target_username`, `prospects.status`
- [ ] Implement connection pooling for SQLite
- [ ] Add query result caching for rules/goals

#### 6.5.2 Sync Optimization

- [ ] Implement incremental sync for rules/goals (not full refresh)
- [ ] Add compression for large payload transfers
- [ ] Implement batch size optimization based on network conditions
- [ ] Add sync priority queue (critical events first)

#### 6.5.3 Extension Performance

- [ ] Add debouncing to DOM observers
- [ ] Optimize profile scraping (cache results)
- [ ] Reduce redundant native message calls
- [ ] Add message batching for multiple events

---

### 6.6 Feature Additions

#### 6.6.1 Analytics Dashboard

- [ ] Add daily/weekly/monthly outreach charts
- [ ] Add target status breakdown pie chart
- [ ] Add performance comparison vs goals
- [ ] Add export to CSV/Excel functionality

#### 6.6.2 Notification System

- [ ] Add system tray notifications for:
  - Sync completion
  - Rule violations
  - Daily goal achievements
- [ ] Add notification preferences in settings
- [ ] Add sound notification options

#### 6.6.3 Backup & Restore

- [ ] Add manual database backup button
- [ ] Add automatic scheduled backups
- [ ] Add restore from backup functionality
- [ ] Add cloud backup option (optional)

#### 6.6.4 Multi-Account Support

- [ ] Add profile switcher in UI
- [ ] Separate settings per profile
- [ ] Add profile-specific stats

---

## Phase 7: Future Considerations

### 7.1 Cross-Platform Support

- [ ] Test and document macOS installation
- [ ] Test and document Linux installation
- [ ] Create platform-specific installers

### 7.2 Advanced Features

- [ ] Implement message templates
- [ ] Add A/B testing for message variants
- [ ] Add reply detection and tracking
- [ ] Add lead scoring algorithm

### 7.3 Team Collaboration

- [ ] Add team chat/notes feature
- [ ] Add shared target pools
- [ ] Add territory/assignment management
- [ ] Add team leaderboards

---

## Priority Matrix

| Priority | Category | Items |
|----------|----------|-------|
| **P0 - Critical** | Security | 6.1.1 (Hardcoded secrets), 6.1.2 (Token storage) |
| **P1 - High** | Security | 6.1.3 (IPC hardening), 6.1.4 (Input validation) |
| **P1 - High** | Quality | 6.2.1 (Error handling), 6.2.3 (Port consistency) |
| **P2 - Medium** | Workflow | 6.3.1 (CI/CD), 6.3.3 (Testing) |
| **P2 - Medium** | UX | 6.4.1 (Dashboard), 6.4.4 (Error feedback) |
| **P3 - Low** | Performance | 6.5.1 (DB indexes), 6.5.2 (Sync optimization) |
| **P3 - Low** | Features | 6.6.1 (Analytics), 6.6.2 (Notifications) |

---

## Implementation Notes

### Security Implementation Order

1. First: Remove hardcoded secrets (can be done without breaking changes)
2. Second: Secure token storage (requires migration script)
3. Third: IPC hardening (requires protocol update)
4. Fourth: Input validation (systematic audit)

### Testing Strategy
1. Unit tests for new security functions
2. Integration tests for auth flow
3. Manual testing for UI changes
4. Automated E2E tests for critical paths

### Rollback Plan
- Keep old pickle loading as fallback during token migration
- Version the IPC protocol for backward compatibility
- Maintain database schema migration scripts

---

## Changelog

### v1.0.0 (Current)
- Phase 1-4 Complete
- Google OAuth integration
- Event/Outreach log schema
- Pre-flight safety checks
- Auto-Tab Switcher
- Mission Control UI

### v1.1.0 (Planned - Security Focus)
- Phase 6.1 (Security fixes)
- Phase 6.2 (Code quality)

### v1.2.0 (Planned - UX Focus)
- Phase 6.3 (Workflow)
- Phase 6.4 (UI improvements)

### v1.3.0 (Planned - Performance)
- Phase 6.5 (Optimizations)
- Phase 6.6 (New features)
