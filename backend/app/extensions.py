import os
import ipaddress
from flask import current_app, request
from authlib.integrations.flask_client import OAuth
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def get_client_ip():
    """Use Render's edge-overwritten client address; never trust X-Forwarded-For."""
    if current_app.config.get("RENDER_SERVICE"):
        forwarded = request.headers.get("CF-Connecting-IP", "").strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return get_remote_address()


oauth = OAuth()
limiter = Limiter(
    key_func=get_client_ip,
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
    storage_options={"ssl_cert_reqs": "required", "ssl_check_hostname": True},
)
