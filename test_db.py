from sqlalchemy import text

from app.core.database import engine


if __name__ == "__main__":
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print(result.scalar())