#!/usr/bin/env python3
"""Generate a local .env file from .env.example with a cryptographically secure random API key.

Refuses to overwrite an existing .env file and never prints the generated key.
"""

from __future__ import annotations

import re
import secrets
import string
import sys
from pathlib import Path

# 48 characters chosen from URL-safe alphanumeric characters
API_KEY_LENGTH = 48
API_KEY_CHARSET = string.ascii_letters + string.digits


def generate_secure_api_key(length: int = API_KEY_LENGTH) -> str:
    """Generate a high-entropy alphanumeric API key."""
    return "".join(secrets.choice(API_KEY_CHARSET) for _ in range(length))


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    example_path = project_root / ".env.example"
    target_path = project_root / ".env"

    if target_path.exists():
        sys.stderr.write(
            f"Error: Target file '{target_path}' already exists. Refusing to overwrite.\n"
        )
        return 1

    if not example_path.exists():
        sys.stderr.write(f"Error: Template file '{example_path}' was not found.\n")
        return 1

    template_content = example_path.read_text(encoding="utf-8")
    generated_key = generate_secure_api_key()

    # Update or substitute required keys
    content = re.sub(
        r"^CLOUDPILOT_API_KEY=.*$",
        f"CLOUDPILOT_API_KEY={generated_key}",
        template_content,
        flags=re.MULTILINE,
    )
    content = re.sub(
        r"^APP_ENV=.*$",
        "APP_ENV=development",
        content,
        flags=re.MULTILINE,
    )
    content = re.sub(
        r"^ALLOWED_ORIGIN=.*$",
        "ALLOWED_ORIGIN=http://localhost:5173",
        content,
        flags=re.MULTILINE,
    )

    target_path.write_text(content, encoding="utf-8")
    sys.stdout.write(
        f"Successfully generated '{target_path.name}' with a random 48-character API key.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
