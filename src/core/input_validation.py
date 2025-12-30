"""
Input Validation Module for InstaCRM.

Provides validation functions for user inputs to prevent injection attacks
and ensure data integrity.
"""

import re
from typing import Optional, Tuple, Any, Dict
import json


class ValidationError(Exception):
    """Custom exception for validation failures."""
    pass


# =============================================================================
# Username Validation
# =============================================================================

def validate_instagram_username(username: str) -> Tuple[bool, str]:
    """
    Validate Instagram username format.
    
    Instagram usernames must:
    - Be 1-30 characters long
    - Contain only alphanumeric characters, underscores, and periods
    - Not start or end with a period
    - Not have consecutive periods
    
    Args:
        username: The username to validate.
    
    Returns:
        (is_valid, error_message) tuple.
    """
    if not username:
        return False, "Username cannot be empty"
    
    if len(username) > 30:
        return False, "Username too long (max 30 characters)"
    
    # Instagram username pattern
    pattern = r'^[a-zA-Z0-9_](?:[a-zA-Z0-9._]{0,28}[a-zA-Z0-9_])?$'
    
    if not re.match(pattern, username):
        return False, "Invalid username format"
    
    # Check for consecutive periods
    if '..' in username:
        return False, "Username cannot contain consecutive periods"
    
    return True, ""


def sanitize_username(username: str) -> str:
    """
    Sanitize username by removing invalid characters and trimming.
    
    Args:
        username: The username to sanitize.
    
    Returns:
        Sanitized username.
    """
    # Remove leading/trailing whitespace and @
    username = username.strip().lstrip('@')
    
    # Remove any characters that aren't alphanumeric, underscore, or period
    username = re.sub(r'[^a-zA-Z0-9._]', '', username)
    
    # Remove leading/trailing periods
    username = username.strip('.')
    
    # Replace consecutive periods with single period
    username = re.sub(r'\.{2,}', '.', username)
    
    # Truncate to 30 characters
    username = username[:30]
    
    return username


# =============================================================================
# Message Content Validation
# =============================================================================

def validate_message_text(text: str, max_length: int = 1000) -> Tuple[bool, str]:
    """
    Validate message text content.
    
    Args:
        text: The message text to validate.
        max_length: Maximum allowed length.
    
    Returns:
        (is_valid, error_message) tuple.
    """
    if not text:
        return False, "Message text cannot be empty"
    
    if len(text) > max_length:
        return False, f"Message text too long (max {max_length} characters)"
    
    # Check for null bytes (can cause issues in some systems)
    if '\x00' in text:
        return False, "Message text contains invalid characters"
    
    return True, ""


def sanitize_message_text(text: str, max_length: int = 1000) -> str:
    """
    Sanitize message text by removing potentially harmful content.
    
    Args:
        text: The message text to sanitize.
        max_length: Maximum allowed length.
    
    Returns:
        Sanitized message text.
    """
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    # Truncate to max length
    text = text[:max_length]
    
    return text


# =============================================================================
# JSON/Dict Validation
# =============================================================================

def validate_json_message(msg: Any, required_fields: Optional[list] = None) -> Tuple[bool, str]:
    """
    Validate that a message is a valid dict with required fields.
    
    Args:
        msg: The message to validate.
        required_fields: List of required field names.
    
    Returns:
        (is_valid, error_message) tuple.
    """
    if not isinstance(msg, dict):
        return False, "Message must be a JSON object"
    
    if required_fields:
        missing_fields = [f for f in required_fields if f not in msg]
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"
    
    return True, ""


def validate_message_structure(msg: dict, schema: dict) -> Tuple[bool, str]:
    """
    Validate message structure against a schema.
    
    Args:
        msg: The message to validate.
        schema: Schema dict with field names and expected types.
            Example: {'username': str, 'count': int}
    
    Returns:
        (is_valid, error_message) tuple.
    """
    for field, expected_type in schema.items():
        if field in msg:
            value = msg[field]
            if not isinstance(value, expected_type):
                return False, f"Field '{field}' must be of type {expected_type.__name__}"
    
    return True, ""


# =============================================================================
# ID Validation
# =============================================================================

def validate_id(id_value: str, prefix: Optional[str] = None, max_length: int = 50) -> Tuple[bool, str]:
    """
    Validate ID format.
    
    Args:
        id_value: The ID to validate.
        prefix: Optional prefix that ID must start with.
        max_length: Maximum allowed length.
    
    Returns:
        (is_valid, error_message) tuple.
    """
    if not id_value:
        return False, "ID cannot be empty"
    
    if len(id_value) > max_length:
        return False, f"ID too long (max {max_length} characters)"
    
    if prefix and not id_value.startswith(prefix):
        return False, f"ID must start with '{prefix}'"
    
    # Allow alphanumeric, underscore, hyphen, and period
    if not re.match(r'^[a-zA-Z0-9._-]+$', id_value):
        return False, "ID contains invalid characters"
    
    return True, ""


# =============================================================================
# High-Level Validation Functions
# =============================================================================

def validate_outreach_log(payload: dict) -> Tuple[bool, str, dict]:
    """
    Validate an outreach log message payload.
    
    Args:
        payload: The payload to validate.
    
    Returns:
        (is_valid, error_message, sanitized_payload) tuple.
    """
    # Check required fields
    is_valid, error = validate_json_message(
        payload,
        required_fields=['target', 'actor']
    )
    if not is_valid:
        return False, error, {}
    
    # Validate and sanitize target username
    target = payload.get('target', '')
    target = sanitize_username(target)
    is_valid, error = validate_instagram_username(target)
    if not is_valid:
        return False, f"Invalid target username: {error}", {}
    
    # Validate and sanitize actor username
    actor = payload.get('actor', '')
    actor = sanitize_username(actor)
    is_valid, error = validate_instagram_username(actor)
    if not is_valid:
        return False, f"Invalid actor username: {error}", {}
    
    # Validate and sanitize message text (if present)
    message = payload.get('message', '')
    if message:
        message = sanitize_message_text(message, max_length=500)
        is_valid, error = validate_message_text(message, max_length=500)
        if not is_valid:
            return False, f"Invalid message text: {error}", {}
    
    # Build sanitized payload
    sanitized = {
        'target': target,
        'actor': actor,
        'message': message if message else None
    }
    
    # Pass through optional fields with validation
    if 'operator' in payload:
        sanitized['operator'] = payload['operator']
    
    return True, "", sanitized


def validate_prospect_status(payload: dict) -> Tuple[bool, str, dict]:
    """
    Validate a prospect status query payload.
    
    Args:
        payload: The payload to validate.
    
    Returns:
        (is_valid, error_message, sanitized_payload) tuple.
    """
    # Check required fields
    is_valid, error = validate_json_message(
        payload,
        required_fields=['target']
    )
    if not is_valid:
        return False, error, {}
    
    # Validate and sanitize target username
    target = payload.get('target', '')
    target = sanitize_username(target)
    is_valid, error = validate_instagram_username(target)
    if not is_valid:
        return False, f"Invalid target username: {error}", {}
    
    sanitized = {'target': target}
    
    return True, "", sanitized


# =============================================================================
# Length Limits
# =============================================================================

MAX_USERNAME_LENGTH = 30
MAX_MESSAGE_LENGTH = 1000
MAX_ID_LENGTH = 50
MAX_PAYLOAD_SIZE = 10240  # 10KB for safety


def validate_payload_size(payload: dict) -> Tuple[bool, str]:
    """
    Validate that payload size is within acceptable limits.
    
    Args:
        payload: The payload to check.
    
    Returns:
        (is_valid, error_message) tuple.
    """
    try:
        size = len(json.dumps(payload))
        if size > MAX_PAYLOAD_SIZE:
            return False, f"Payload too large ({size} bytes, max {MAX_PAYLOAD_SIZE})"
        return True, ""
    except Exception as e:
        return False, f"Failed to validate payload size: {e}"
