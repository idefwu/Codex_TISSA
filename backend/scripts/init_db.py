import argparse
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db import get_database_url, get_engine
from app.models import Base


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize database tables.")
    parser.add_argument("--drop", action="store_true", help="Drop all demo tables before creating them.")
    args = parser.parse_args()

    engine = get_engine()

    if args.drop:
        Base.metadata.drop_all(engine)
        print("Dropped existing demo tables.")

    Base.metadata.create_all(engine)
    print(f"Initialized database tables at {get_database_url()}.")


if __name__ == "__main__":
    main()
