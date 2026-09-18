from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.app.core.config as config
import backend.app.database.database as database
from backend.app.database import models


def test_runtime_settings_survive_reload(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'settings.db'}")
    models.Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "SessionLocal", session_factory)

    original = config.get_runtime_settings()
    try:
        config.update_runtime_settings({"detection_confidence": 0.61})
        config._settings = config.DEFAULT_RUNTIME_SETTINGS.copy()
        config.load_persisted_settings()
        assert config.get_runtime_settings()["detection_confidence"] == 0.61
    finally:
        config._settings = original
