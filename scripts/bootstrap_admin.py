#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import UserCredentialRecord, UserRoleRecord, get_session
from app.security import hash_password


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Bootstrap first admin/user account')
    parser.add_argument('--user-id', required=True, help='User id to create/update')
    parser.add_argument('--password', required=True, help='Plaintext password to hash and store')
    parser.add_argument('--role', default='admin', choices=['admin', 'user'], help='Role to grant')
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    with get_session() as session:
        cred = session.get(UserCredentialRecord, args.user_id)
        if cred:
            cred.password_hash = hash_password(args.password)
            print(f'updated credential for {args.user_id}')
        else:
            session.add(UserCredentialRecord(user_id=args.user_id, password_hash=hash_password(args.password)))
            print(f'created credential for {args.user_id}')

        role = session.get(UserRoleRecord, args.user_id)
        if role:
            role.role = args.role
            print(f'updated role for {args.user_id} -> {args.role}')
        else:
            session.add(UserRoleRecord(user_id=args.user_id, role=args.role))
            print(f'created role for {args.user_id} -> {args.role}')

    print('bootstrap complete')


if __name__ == '__main__':
    main()
