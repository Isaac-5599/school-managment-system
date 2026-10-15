#!/usr/bin/env python3
"""Entry point for the School Management System.

    python3 run.py [--port 8000] [--host 127.0.0.1] [--reset]

HOST and PORT may also come from the environment; hosting platforms such as
Render inject PORT and expect the service to listen on 0.0.0.0.
"""

import argparse
import os

from sms import db
from sms.server import serve

parser = argparse.ArgumentParser(description="School Management System")
parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
parser.add_argument("--reset", action="store_true", help="delete the database and re-seed demo data")
args = parser.parse_args()

if args.reset:
    if os.path.exists(db.DB_PATH):
        os.remove(db.DB_PATH)
    print("Existing database removed; demo data will be re-seeded.")

serve(args.host, args.port)
