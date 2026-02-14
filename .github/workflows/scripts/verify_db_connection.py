from sqlalchemy import create_engine, text

from app.config import settings


def main() -> None:
    target = settings.production_database_url or settings.database_url
    engine = create_engine(target, future=True)
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    print('db connection ok')


if __name__ == '__main__':
    main()
