# FOR_USER.md

## InstaCRM Desktop Agent: User Testing & Pre-Next Steps Checklist

This guide provides a **step-by-step checklist** for thoroughly testing your InstaCRM Desktop Agent installation and setup, based on all current documentation and the latest architecture (TLS connection string, no wallet files). Complete these steps before moving to the next items in your ToDo.md.

---

## 1. Environment & Prerequisites

- [x] **Python 3.9+** is installed (`python --version`)
- [x] **Google Chrome** is installed
- [x] You have received a **Setup_Pack_{TOKEN}.zip** (contains only `.env`)
- [ ] You have your **Google OAuth credentials** (`client_secret.json`)

---

## 2. Initial Setup & Identity

1. **Start with a clean environment:**
   - [x] Delete any old `operator_config.json` and `assets/wallet/` directory (wallets are deprecated)

2. **Run the Setup Wizard:**
   - [ ] `python launcher.py`
   - [ ] Upload your `Setup_Pack_{TOKEN}.zip` when prompted
   - [ ] Enter your Operator name (auto-complete should work if DB is accessible)
   - [ ] Click "Open Extension Folder" and load the Chrome extension in Chrome (chrome://extensions → Load unpacked)
   - [ ] Enter the Extension ID from Chrome into the wizard
   - [ ] Complete the wizard and verify the Login screen appears

---

## 3. Authentication & Onboarding

- [ ] Click **"Sign in with Google"**
- [ ] Complete the OAuth flow in your browser
- [ ] Verify you are redirected to the app and see the correct user identity
- [ ] For new users: Confirm "Establish Identity" screen
- [ ] For existing users: Confirm direct access to Dashboard

---

## 4. Dashboard & Sync Status

- [ ] Confirm `SYNC: STARTING...` transitions to `SYNC: OK (HH:MM)`
- [ ] Session timer counts up
- [ ] Disconnect internet: Confirm `SYNC: ERROR` after ~60s
- [ ] Reconnect: Confirm status returns to Green

---

## 5. Chrome Extension & Scroller

- [ ] Go to `instagram.com/direct/`
- [ ] Confirm pulsing "📜" button appears
- [ ] Click to open Scroller panel
- [ ] Test auto-scrolling (panel should scroll DMs, show toast feedback)
- [ ] Navigate away: Confirm button disappears

---

## 6. Outreach Logging & Privacy

- [ ] Send a DM to a new target
- [ ] Confirm "Not Contacted Before" banner appears
- [ ] Dashboard "Outreach Sent" counter increases
- [ ] Mark a target as "Excluded" in the app
- [ ] Send another message to that target: Confirm `message_text` is NULL in EVENT_LOGS

---

## 7. Auto-Tab Switcher

- [ ] Enable in Settings (Trigger=1, Delay=2s)
- [ ] Send a DM in Chrome
- [ ] Wait 2 seconds: Confirm tab closes and focus switches to next tab
- [ ] Test Foreground Protection: Focus away from Chrome, confirm switch is skipped

---

## 8. Auto-Updater

- [ ] In Settings, verify "Update Source" shows GitHub URL
- [ ] Lower version in `src/core/version.py` to `0.0.1` and restart
- [ ] Confirm update is detected and installed
- [ ] Confirm app restarts with new version

---

## 9. Installer (Final Artifact)

- [ ] Run `python src/scripts/installer_gui.py`
- [ ] Confirm installer UI opens and completes
- [ ] Confirm shortcuts are created and app launches from shortcut

---

## 10. Database & Connection Testing

- [ ] Confirm `.env` contains a valid `DB_DSN` (TLS connection string, single line)
- [ ] Run the following test script:

```python
import os
import oracledb
from dotenv import load_dotenv
load_dotenv()
conn = oracledb.connect(
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    dsn=os.getenv('DB_DSN')
)
print("✅ Connected!")
conn.close()
```
- [ ] If you see errors, check the troubleshooting section in `ORACLE_TLS_SETUP_GUIDE.md`

---

## 11. Security & Best Practices

- [ ] Ensure `.env`, `local_config.py`, `operator_config.json`, and all secrets are **NOT committed to git**
- [ ] Pre-commit hooks are installed (`pre-commit install`)
- [ ] Run `detect-secrets scan` to check for accidental secrets
- [ ] All environment variables are set (see `SECURITY.md`)

---

## 12. Troubleshooting

- [ ] If the extension says "Application not running", start the Desktop Agent and click CONNECT
- [ ] If you see "Native host not found", re-run the Setup Wizard
- [ ] If sync is stuck on ERROR, check internet and verify `DB_DSN` in `.env`
- [ ] If OAuth fails, ensure `client_secret.json` exists in `assets/`
- [ ] For more, see the Troubleshooting section in `README.md` and `ORACLE_TLS_SETUP_GUIDE.md`

---

## 13. (Optional) Developer/Advanced Checks

- [ ] Run all tests: `pytest tests/`
- [ ] Run with coverage: `pytest --cov=src tests/`
- [ ] Run security scan: `bandit -r src/`
- [ ] Generate docs: `sphinx-build -b html docs/ docs/_build`

---

## 14. Ready for Next Steps

Once all the above are checked, you are ready to proceed with the next items in your `ToDo.md`!

---

**References:**
- [README.md](README.md)
- [ORACLE_TLS_SETUP_GUIDE.md](ORACLE_TLS_SETUP_GUIDE.md)
- [TLS_QUICK_START.md](TLS_QUICK_START.md)
- [SECURITY.md](SECURITY.md)
- [PHASE_6_IMPLEMENTATION_SUMMARY.md](PHASE_6_IMPLEMENTATION_SUMMARY.md)
- [ToDo.md](ToDo.md)
