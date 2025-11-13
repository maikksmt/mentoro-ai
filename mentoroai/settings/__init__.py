import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
env = (os.getenv("DJANGO_ENV") or "development").lower()

if env in {"prod", "production"}:
    from .production import *  # noqa: F403,F401
elif env in {"ci", "test", "testing"}:
    from .development import *  # noqa: F403,F401
else:
    from .development import *  # noqa: F403,F401
