from app.db.base import Base
from app.db.session import engine

# Import models so SQLAlchemy sees them
from app.models.record import Record
from app.models.manual_record import ManualRecord
from app.models.delivery import Delivery
from app.models.fetch_run import FetchRun

def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("Database tables created.")