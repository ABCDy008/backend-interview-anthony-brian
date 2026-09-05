from pathlib import Path

from sqlalchemy import text

from app.database import engine


def main() -> None:
    seed_sql = Path(__file__).resolve().parent / "seed.sql"
    with engine.begin() as connection:
        connection.execute(text(seed_sql.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()