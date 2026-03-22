"""Shared security utilities used across multiple plugin containers.

These functions are copied into each container's build context at install time,
so they must remain self-contained with no external dependencies beyond stdlib.
"""
import os


def safe_path(base: str, user_input: str) -> str:
    """Validate that a user-supplied path stays within the base directory.

    Raises ValueError if the resolved path escapes the base directory.
    """
    joined = os.path.abspath(os.path.join(base, user_input))
    if not joined.startswith(os.path.abspath(base)):
        raise ValueError(f"Path traversal blocked: {user_input}")
    return joined
