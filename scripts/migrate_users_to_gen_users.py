#!/usr/bin/env python3
"""
Migration script to copy karaoke-gen users from 'users' collection to 'gen_users' collection.

This script:
1. Identifies karaoke-gen users in the 'users' collection (by presence of 'credits' field)
2. Copies them to the 'gen_users' collection (preserving document ID = email)
3. Optionally deletes the old documents from 'users' collection

Run with:
    python scripts/migrate_users_to_gen_users.py --dry-run  # Preview only
    python scripts/migrate_users_to_gen_users.py            # Execute migration
    python scripts/migrate_users_to_gen_users.py --delete   # Also delete old docs
"""

import argparse
import sys
from google.cloud import firestore


def is_karaoke_gen_user(doc_data: dict) -> bool:
    """
    Determine if a user document belongs to karaoke-gen.

    karaoke-gen users have:
    - Document ID = email address (contains @)
    - 'credits' field
    - 'role' field with value 'user' or 'admin'
    - 'is_active' field

    karaoke-decide users have:
    - Document ID = hash or guest_xxx
    - 'user_id' field
    - 'is_guest' field
    """
    # Check for karaoke-gen specific fields
    has_credits = 'credits' in doc_data
    has_role = doc_data.get('role') in ['user', 'admin']
    has_is_active = 'is_active' in doc_data

    # Check for karaoke-decide specific fields
    has_user_id = 'user_id' in doc_data
    has_is_guest = 'is_guest' in doc_data

    # karaoke-gen users have credits/role/is_active but NOT user_id/is_guest
    return has_credits and has_role and has_is_active and not has_user_id and not has_is_guest


def migrate_users(dry_run: bool = True, delete_old: bool = False):
    """
    Migrate karaoke-gen users from 'users' to 'gen_users' collection.
    """
    db = firestore.Client(project='nomadkaraoke')

    users_collection = db.collection('users')
    gen_users_collection = db.collection('gen_users')

    # Get all documents from users collection
    print("Fetching all documents from 'users' collection...")
    all_docs = list(users_collection.stream())
    print(f"Found {len(all_docs)} total documents in 'users' collection")

    # Filter to karaoke-gen users
    gen_users = []
    decide_users = []
    unknown_users = []

    for doc in all_docs:
        doc_data = doc.to_dict()
        doc_id = doc.id

        if is_karaoke_gen_user(doc_data):
            gen_users.append((doc_id, doc_data))
        elif 'user_id' in doc_data or 'is_guest' in doc_data:
            decide_users.append(doc_id)
        else:
            unknown_users.append(doc_id)

    print(f"\nClassification results:")
    print(f"  - karaoke-gen users: {len(gen_users)}")
    print(f"  - karaoke-decide users: {len(decide_users)}")
    print(f"  - Unknown/other: {len(unknown_users)}")

    if unknown_users:
        print(f"\nUnknown users (first 5): {unknown_users[:5]}")

    if dry_run:
        print(f"\n[DRY RUN] Would migrate {len(gen_users)} users to 'gen_users' collection:")
        for doc_id, doc_data in gen_users[:10]:
            email = doc_data.get('email', doc_id)
            credits = doc_data.get('credits', 0)
            print(f"  - {email} (credits: {credits})")
        if len(gen_users) > 10:
            print(f"  ... and {len(gen_users) - 10} more")
        return

    # Execute migration
    print(f"\nMigrating {len(gen_users)} users to 'gen_users' collection...")
    migrated = 0
    errors = 0

    for doc_id, doc_data in gen_users:
        try:
            # Use the same document ID (email) in the new collection
            gen_users_collection.document(doc_id).set(doc_data)
            migrated += 1

            if migrated % 10 == 0:
                print(f"  Migrated {migrated}/{len(gen_users)}...")
        except Exception as e:
            print(f"  ERROR migrating {doc_id}: {e}")
            errors += 1

    print(f"\nMigration complete: {migrated} migrated, {errors} errors")

    # Optionally delete old documents
    if delete_old and errors == 0:
        print(f"\nDeleting old documents from 'users' collection...")
        deleted = 0
        for doc_id, _ in gen_users:
            try:
                users_collection.document(doc_id).delete()
                deleted += 1
            except Exception as e:
                print(f"  ERROR deleting {doc_id}: {e}")
        print(f"Deleted {deleted} documents from 'users' collection")
    elif delete_old and errors > 0:
        print("\nSkipping deletion due to migration errors")


def main():
    parser = argparse.ArgumentParser(description='Migrate karaoke-gen users to gen_users collection')
    parser.add_argument('--dry-run', action='store_true', help='Preview migration without making changes')
    parser.add_argument('--delete', action='store_true', help='Delete old documents after successful migration')
    args = parser.parse_args()

    # Default to dry-run if neither flag is set
    dry_run = args.dry_run or not args.delete

    if not dry_run:
        print("=" * 60)
        print("WARNING: This will modify production data!")
        print("=" * 60)
        response = input("Type 'yes' to continue: ")
        if response.lower() != 'yes':
            print("Aborted")
            sys.exit(1)

    migrate_users(dry_run=dry_run, delete_old=args.delete)


if __name__ == '__main__':
    main()
