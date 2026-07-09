from app.db.base import Base
from app.db.session import engine
import app.db.models_import  # noqa: F401  # registers models with Base metadata


def init() -> None:
    Base.metadata.create_all(bind=engine)
    print("Database tables created.")


if __name__ == "__main__":
    init()