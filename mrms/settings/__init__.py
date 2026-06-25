import os

ENVIRONMENT = os.environ.get("DJANGO_ENVIRONMENT", "dev")

if ENVIRONMENT == "production":
    from .prod import *  # noqa: F401, F403
else:
    from .dev import *  # noqa: F401, F403
