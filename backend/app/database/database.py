from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker


DATABASE_URL = "sqlite:///./sentinel.db"


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def ensure_compatibility_columns():
    """Add optional MVP columns to databases created by the prototype."""
    inspector = inspect(engine)
    additions = {
        "cameras": {"source_type": "VARCHAR(20) DEFAULT 'video'", "status": "VARCHAR(20) DEFAULT 'offline'"},
        "alerts": {"camera_id": "INTEGER", "track_id": "INTEGER", "object_type": "VARCHAR(50)", "zone": "VARCHAR(100)", "score": "INTEGER", "reason": "TEXT", "evidence_path": "VARCHAR(500)", "timestamp": "DATETIME"},
        "events": {"type": "VARCHAR(100)"},
    }
    with engine.begin() as connection:
        for table, columns in additions.items():
            if table not in inspector.get_table_names():
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for name, definition in columns.items():
                if name not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
