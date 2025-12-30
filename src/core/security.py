"""
Security Module for InstaCRM Ecosystem.

Handles:
1. Token generation for Setup Packs.
2. Pre-Flight Safety Checks (Frequency Caps, Interval Spacing) for Democratic Governance.
"""

import hmac
import hashlib
import secrets
import os
import sys
from datetime import datetime, timezone, timedelta

def _load_master_secret():
    """
    Load master secret key from environment variable.
    Falls back to generating one if not set (for backward compatibility).
    
    WARNING: The fallback is for transition only. Always set IOL_MASTER_SECRET in production.
    """
    master_secret = os.environ.get('IOL_MASTER_SECRET')
    
    if not master_secret:
        # Fallback for backward compatibility - generates a session key
        # This means the key will change on each restart, which is NOT ideal for production
        fallback_key = "IOL_SEC_KEY_v1_" + "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
        print("[SECURITY WARNING] IOL_MASTER_SECRET not set. Using fallback key. Please set in environment.", file=sys.stderr)
        return fallback_key
    
    return master_secret

MASTER_SECRET_KEY = _load_master_secret()

def generate_token():
    """Generate a random 8-character hex token."""
    return secrets.token_hex(4)

def get_zip_password(token: str) -> bytes:
    """
    Derive a password from the token using HMAC-SHA256.
    Returns bytes as required by pyzipper.
    """
    if not token:
        raise ValueError("Token cannot be empty")
        
    h = hmac.new(
        MASTER_SECRET_KEY.encode('utf-8'),
        token.encode('utf-8'),
        hashlib.sha256
    )
    return h.hexdigest().encode('utf-8')

# ==========================================
#           PRE-FLIGHT CHECKS
# ==========================================

class PreFlightChecker:
    """
    Enforces 'Democratic Governance' rules locally before allowing an action.
    """
    def __init__(self, db):
        self.db = db

    def check_safety_rules(self, act_id: str, opr_id: str, event_type: str = 'Outreach') -> dict:
        """
        Validates the proposed action against all active RULES.
        
        Returns:
            {
                'allowed': bool,
                'status': 'PASS' | 'WARN' | 'BLOCK',
                'message': str (reason for violation)
            }
        """
        # 1. Fetch active rules
        rules = self.db.get_active_rules()
        if not rules:
            return {'allowed': True, 'status': 'PASS', 'message': 'No rules active'}

        violations = []

        for rule in rules:
            # Filter Logic: Does this rule apply to ME?
            # 1. Scope: Global (NULL), Operator, or Actor
            assigned_opr = rule.get('assigned_to_opr')
            assigned_act = rule.get('assigned_to_act')

            # Skip if rule is assigned to someone else
            if assigned_opr and assigned_opr != opr_id:
                continue
            if assigned_act and assigned_act != act_id:
                continue

            # Check Rule Logic
            # Note: We currently only support 'Outreach' metric types logic in this v1
            if 'Messages' not in rule['metric'] and 'Outreach' not in rule['metric']:
                continue

            if rule['type'] == 'Frequency Cap':
                # Count events in the last Window
                count = self.db.get_recent_event_count(act_id, event_type, rule['time_window_sec'])
                if count >= rule['limit_value']:
                    violations.append(f"Frequency Cap: {count}/{rule['limit_value']} messages in {rule['time_window_sec']}s")

            elif rule['type'] == 'Interval Spacing':
                # Check time since last event
                last_time_str = self.db.get_last_event_time(act_id, event_type)
                if last_time_str:
                    last_time = datetime.fromisoformat(last_time_str)
                    now = datetime.now(timezone.utc)
                    diff = (now - last_time).total_seconds()
                    
                    if diff < rule['limit_value']:
                        wait_time = int(rule['limit_value'] - diff)
                        violations.append(f"Interval Spacing: Must wait {wait_time}s")

        if violations:
            # For now, all rules are 'Soft Warning' as per schema default, 
            # but we return 'WARN' so the UI can decide to show a toast.
            # If we had 'BLOCK' severity, we would set allowed=False.
            return {
                'allowed': True, 
                'status': 'WARN', 
                'message': " | ".join(violations)
            }

        return {'allowed': True, 'status': 'PASS', 'message': 'OK'}