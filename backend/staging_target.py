"""Fail-closed checks shared by staging database tools.

This module never loads dotenv files. Callers must provide staging credentials
through their process environment or the hosting provider's secret settings.
"""
import os
from pathlib import Path


STAGING_DATABASE = "fittrack_staging"


def validate_staging_target(environ=None):
    env = os.environ if environ is None else environ
    if env.get("FITTRACK_ENV", "").strip().lower() not in {"prod", "production"}:
        raise ValueError("Set FITTRACK_ENV=production so no local dotenv file is loaded.")
    if env.get("DB_NAME", "").strip() != STAGING_DATABASE:
        raise ValueError("Staging tools require DB_NAME=fittrack_staging.")
    if env.get("FITTRACK_EXPECTED_DB_NAME", "").strip() != STAGING_DATABASE:
        raise ValueError("FITTRACK_EXPECTED_DB_NAME must exactly match fittrack_staging.")
    host = env.get("DB_HOST", "").strip()
    if not host or host != env.get("FITTRACK_EXPECTED_DB_HOST", "").strip():
        raise ValueError("DB_HOST must exactly match FITTRACK_EXPECTED_DB_HOST.")
    if env.get("DB_PORT", "").strip() != "4000":
        raise ValueError("TiDB staging connections must use DB_PORT=4000.")
    if env.get("DB_SSL_VERIFY_CERT", "").lower() != "true" or env.get("DB_SSL_VERIFY_IDENTITY", "").lower() != "true":
        raise ValueError("Staging requires database certificate and hostname verification.")
    ca_path = env.get("DB_SSL_CA", "").strip()
    if not ca_path or not Path(ca_path).is_file():
        raise ValueError("DB_SSL_CA must point to an available CA certificate file.")
    for name in ("DB_USER", "DB_PASSWORD"):
        if not env.get(name, "").strip():
            raise ValueError(f"{name} must be configured in the staging environment.")
    return host, ca_path
