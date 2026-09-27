#!/usr/bin/env python3
"""Seed the configured primary profile in JARVIS' private runtime database.

Safe to re-run; voice enrollment is a separate explicit step.

Usage:
    python3 scripts/init_profiles.py          # Create default profiles
    python3 scripts/init_profiles.py --list    # List all profiles
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path so core imports work
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config import Config
from core.user_profile import get_profile_manager


def seed_profiles():
    """Create only the configured primary profile, without voice data."""
    config = Config()
    pm = get_profile_manager(config)
    profile = pm.ensure_primary_profile()
    print(f"  Primary profile ready: {profile['id']} ({profile['name']}, {profile['honorific']})")


def list_profiles():
    """Print all profiles in the database."""
    config = Config()
    pm = get_profile_manager(config)
    profiles = pm.get_all()

    if not profiles:
        print("  (no profiles)")
        return

    for p in profiles:
        emb = "enrolled" if p.get("embedding_path") else "no embedding"
        print(f"  {p['id']:15s} | {p['name']:15s} | {p['honorific']:6s} | "
              f"{p['role']:6s} | {emb} | created {p['created_at']}")


def main():
    print("JARVIS Profile Initialization")
    print("=" * 40)

    if "--list" in sys.argv:
        print("\nAll profiles:")
        list_profiles()
    else:
        print("\nSeeding primary profile...")
        seed_profiles()
        print("\nCurrent profiles:")
        list_profiles()


if __name__ == "__main__":
    main()
