import os
from pathlib import Path

os.environ["AEGIS_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{Path('/tmp/aegis-alpha-tests.db')}"
os.environ["REDIS_URL"] = "redis://127.0.0.1:6399/15"
os.environ["TRUSTED_HOSTS"] = "testserver,localhost"

from app.database import Base, engine  # noqa: E402
from app import models  # noqa: E402,F401

Base.metadata.create_all(bind=engine)
