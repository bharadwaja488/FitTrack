import os
from authlib.integrations.flask_client import OAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

oauth = OAuth()
limiter = Limiter(key_func=get_remote_address, storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"))
