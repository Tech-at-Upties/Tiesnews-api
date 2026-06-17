import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.admin_keys import create_admin_key
from app.database import Base, SessionLocal, engine


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and store a GeoAtlas admin API key.")
    parser.add_argument("--name", default="local-admin", help="Human-readable key name stored in the database.")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        key, plaintext = create_admin_key(db, args.name)
    finally:
        db.close()

    print("GeoAtlas admin key created.")
    print(f"Key id: {key.id}")
    print(f"Name: {key.name}")
    print("Copy this plaintext key now. It is stored only as a hash in the database:")
    print(plaintext)


if __name__ == "__main__":
    main()
