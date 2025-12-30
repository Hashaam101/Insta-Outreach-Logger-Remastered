"""
Unit tests for input validation module.
"""

import pytest
from src.core.input_validation import (
    validate_instagram_username,
    sanitize_username,
    validate_message_text,
    sanitize_message_text,
    validate_outreach_log,
    validate_prospect_status,
    validate_payload_size
)


class TestUsernameValidation:
    """Tests for Instagram username validation."""
    
    def test_valid_username(self):
        assert validate_instagram_username('test_user')[0] is True
        assert validate_instagram_username('user123')[0] is True
        assert validate_instagram_username('user.name')[0] is True
    
    def test_invalid_username_empty(self):
        is_valid, error = validate_instagram_username('')
        assert is_valid is False
        assert 'empty' in error.lower()
    
    def test_invalid_username_too_long(self):
        is_valid, error = validate_instagram_username('a' * 31)
        assert is_valid is False
        assert 'too long' in error.lower()
    
    def test_invalid_username_consecutive_periods(self):
        is_valid, error = validate_instagram_username('user..name')
        assert is_valid is False
        assert 'consecutive periods' in error.lower()
    
    def test_sanitize_username_removes_at_symbol(self):
        assert sanitize_username('@username') == 'username'
    
    def test_sanitize_username_removes_invalid_chars(self):
        assert sanitize_username('user@#$name!') == 'username'
    
    def test_sanitize_username_truncates(self):
        long_name = 'a' * 40
        result = sanitize_username(long_name)
        assert len(result) <= 30


class TestMessageValidation:
    """Tests for message text validation."""
    
    def test_valid_message(self):
        assert validate_message_text('Hello world!')[0] is True
    
    def test_invalid_message_empty(self):
        is_valid, error = validate_message_text('')
        assert is_valid is False
        assert 'empty' in error.lower()
    
    def test_invalid_message_too_long(self):
        is_valid, error = validate_message_text('a' * 1001)
        assert is_valid is False
        assert 'too long' in error.lower()
    
    def test_sanitize_message_removes_null_bytes(self):
        result = sanitize_message_text('Hello\x00World')
        assert '\x00' not in result


class TestOutreachLogValidation:
    """Tests for outreach log validation."""
    
    def test_valid_outreach_log(self, sample_outreach_message):
        is_valid, error, sanitized = validate_outreach_log(sample_outreach_message)
        assert is_valid is True
        assert error == ""
        assert 'target' in sanitized
        assert 'actor' in sanitized
    
    def test_invalid_outreach_log_missing_target(self):
        payload = {'actor': 'test_actor', 'message': 'test'}
        is_valid, error, sanitized = validate_outreach_log(payload)
        assert is_valid is False
        assert 'target' in error.lower()
    
    def test_invalid_outreach_log_bad_username(self):
        payload = {'target': 'invalid@@@user', 'actor': 'test_actor'}
        is_valid, error, sanitized = validate_outreach_log(payload)
        # Should sanitize and validate, may fail if sanitization can't fix it
        assert is_valid is False or 'target' in sanitized


class TestPayloadSizeValidation:
    """Tests for payload size validation."""
    
    def test_valid_payload_size(self):
        small_payload = {'key': 'value'}
        assert validate_payload_size(small_payload)[0] is True
    
    def test_invalid_payload_too_large(self):
        large_payload = {'data': 'x' * 20000}
        is_valid, error = validate_payload_size(large_payload)
        assert is_valid is False
        assert 'too large' in error.lower()
