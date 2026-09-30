from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 1. Resolve project root (/home/ankit/adk_test_case)
# If this file is in ~/adk_test_case/db/db_init.py:
BASE_DIR = Path(__file__).resolve().parent.parent
DB_FILE = (BASE_DIR / "cnx_data.db").resolve()

# 2. SQLite requires 4 slashes on Linux for absolute paths: sqlite:////home/...
DATABASE_URL = f"sqlite:///{DB_FILE}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def init_db():
    # Model MUST be imported so Base registers the table metadata
    import db.model  # noqa: F401
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()