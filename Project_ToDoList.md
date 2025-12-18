# ✅ Insta Outreach Logger - Development To-Do List

## 🚀 Phase 1: Foundation & Backend Logic (Complete)
- [x] **Cloud DB:** Oracle Autonomous Database schema created.
- [x] **Local DB:** `local_db.py` created for the SQLite queue.
- [x] **Core Server:** `ipc_server.py` created to handle client connections.
- [x] **Initial Sync Engine:** `sync_engine.py` created for data synchronization.
- [x] **Delta Sync:** Implemented `LAST_UPDATED` logic for efficient GitHub-style syncs.

## 🔗 Phase 2: Chrome Extension & Bridge (Complete)
- [x] **Content Script:** `content.js` created to scrape DM pages.
- [x] **Background Script:** `background.js` created to manage communication.
- [x] **Native Messaging:** Bridge between browser and Python server established.
- [x] **Hardened Detection:** v12 content script handles SPA navigation and account switching.

## 📊 Phase 3: Admin Command Center (Complete)
- [x] **Dependencies:** Added Streamlit and Pandas.
- [x] **Dashboard UI:** Created `src/dashboard/app.py` with multi-tab interface.
- [x] **Data Display:** Implemented KPIs, leaderboards, and daily matrix.
- [x] **Timezone Fix:** Correctly implemented UTC creation and GMT+5 conversion.

## 🤖 Phase 4: Auto-Discovery Architecture (Complete)
- [x] **Operator Identity:** `ipc_server.py` now prompts for and saves the operator's name.
- [x] **Actor Discovery:** The extension now automatically discovers the actor username upon install and saves it to persistent storage.
- [x] **DB Migration:** The database schema was updated to support the Operator/Actor model (e.g., `OWNER_OPERATOR` in `ACTORS` table).
- [x] **Sync Logic Refactor:** `sync_engine.py` now uses the enriched data to auto-register new actors on the fly.

## 📦 Phase 5: Packaging & Distribution (Complete)
- [x] **The Wizard:** Built `src/gui/setup_wizard.py` (Drag-and-Drop Zip Validator with customtkinter).
- [x] **The Launcher:** Built `launcher.py` (GitHub Releases auto-update + Setup Wizard bootstrapper).
- [x] **Dev Tools:** Created `src/scripts/dev_cli.py` for interactive build, pack, version bump, and clean operations.
- [x] **AV Fix:** Created `Fix_Antivirus_Block.bat` to automate folder exclusions and file unblocking.
- [x] **Version Management:** Created `src/core/version.py` as single source of truth.

## 💅 Phase 6: UI & UX Polish (Complete)
- [x] **Visual Feedback:** Added "Checking..." banner during prospect status lookup.
- [x] **Error States:** Added Red Border / Pulsing animation for "Detection Failed" or "Error" states.
- [x] **Fallback Logic:** Implemented Header Scraping fallback for when the chat input box is hidden.

## 🚀 Phase 7: Deployment
- [ ] Create GitHub Release v1.0.0.
- [ ] Deploy Streamlit Dashboard to Cloud.
- [ ] Distribute "Setup Packs" to team.