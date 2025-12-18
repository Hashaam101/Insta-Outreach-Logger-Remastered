"""
Version information for Insta Outreach Logger.

This is the single source of truth for the application version.
Imported by: launcher.py, dev_cli.py, and the main application.
"""

__version__ = "1.0.0"
__app_name__ = "Insta Outreach Logger (Remastered)"

# GitHub repository for auto-update checks
GITHUB_OWNER = "hashaam101"
GITHUB_REPO = "Insta-Outreach-Logger-Remastered"


def get_version_tuple():
    """Returns version as a tuple of integers for comparison."""
    return tuple(int(x) for x in __version__.split('.'))


def compare_versions(v1: str, v2: str) -> int:
    """
    Compare two version strings.
    Returns: -1 if v1 < v2, 0 if v1 == v2, 1 if v1 > v2
    """
    v1_parts = [int(x) for x in v1.lstrip('v').split('.')]
    v2_parts = [int(x) for x in v2.lstrip('v').split('.')]

    # Pad shorter version with zeros
    max_len = max(len(v1_parts), len(v2_parts))
    v1_parts.extend([0] * (max_len - len(v1_parts)))
    v2_parts.extend([0] * (max_len - len(v2_parts)))

    for a, b in zip(v1_parts, v2_parts):
        if a < b:
            return -1
        elif a > b:
            return 1
    return 0
