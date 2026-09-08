from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_PATH = PROJECT_ROOT / "sentinel.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"


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
    _migrate_legacy_zones(inspector)
    inspector = inspect(engine)
    additions = {
        "cameras": {"source_type": "VARCHAR(20) DEFAULT 'video'", "status": "VARCHAR(20) DEFAULT 'offline'"},
        "alerts": {"camera_id": "INTEGER", "track_id": "INTEGER", "object_type": "VARCHAR(50)", "zone": "VARCHAR(100)", "zone_type": "VARCHAR(30)", "score": "INTEGER", "reason": "TEXT", "evidence_path": "VARCHAR(500)", "timestamp": "DATETIME"},
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


def reset_runtime_statuses():
    """A process restart means no camera worker is live yet."""
    with engine.begin() as connection:
        connection.execute(text("UPDATE cameras SET status = 'offline'"))


def _migrate_legacy_zones(inspector):
    """Rebuild a zones table polluted by the prototype's old event columns."""
    if "zones" not in inspector.get_table_names():
        return

    columns = inspector.get_columns("zones")
    expected = {"id", "camera_id", "name", "zone_type", "polygon_points", "enabled", "created_at", "updated_at"}
    has_required_legacy_column = any(column["name"] not in expected and not column["nullable"] and column["default"] is None for column in columns)
    if not has_required_legacy_column:
        return

    legacy_name = "zones_legacy"
    with engine.begin() as connection:
        if legacy_name in inspect(connection).get_table_names():
            legacy_name = "zones_legacy_previous"
        connection.execute(text(f"ALTER TABLE zones RENAME TO {legacy_name}"))
        Base.metadata.tables["zones"].create(connection)
        connection.execute(text(f"INSERT INTO zones (id, camera_id, name, zone_type, polygon_points, enabled, created_at, updated_at) SELECT id, camera_id, name, zone_type, polygon_points, enabled, created_at, updated_at FROM {legacy_name}"))
