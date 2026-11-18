from flask import Flask, jsonify, request, session
from flask_cors import CORS
from mysql.connector import Error
from datetime import timedelta
from werkzeug.exceptions import HTTPException

from .config import Config, validate_security_config
from .extensions import limiter, oauth
from .auth import csrf_valid
from .routes.auth import bp as auth_bp
from .routes.profile import bp as profile_bp
from .routes.personal_fitness import bp as fitness_bp
from .routes.personal_dashboard import bp as dashboard_bp
from .routes.goals import bp as goals_bp
from .routes.settings import bp as settings_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    validate_security_config(app.config)
    app.permanent_session_lifetime = timedelta(seconds=app.config["PERMANENT_SESSION_LIFETIME"])

    @app.after_request
    def exact_origin_headers(response):
        origin = request.headers.get("Origin")
        if request.path.startswith("/api/") and origin in app.config["FRONTEND_ORIGINS"]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Vary"] = "Origin"
            if request.method == "OPTIONS":
                response.headers["Access-Control-Allow-Methods"] = "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS"
                response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token"
                response.headers["Access-Control-Max-Age"] = "600"
        return response

    CORS(app, resources={r"/api/*": {"origins": list(app.config["FRONTEND_ORIGINS"]), "supports_credentials": True,
                                      "allow_headers": ["Content-Type", "X-CSRF-Token"]}})
    limiter.init_app(app)
    if app.config["GOOGLE_ENABLED"]:
        oauth.init_app(app)
        oauth.register("google", client_id=app.config["GOOGLE_CLIENT_ID"],
                       client_secret=app.config["GOOGLE_CLIENT_SECRET"],
                       server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                       client_kwargs={"scope": "openid email profile"})
    for bp in (auth_bp, profile_bp, fitness_bp, dashboard_bp, goals_bp, settings_bp):
        app.register_blueprint(bp, url_prefix="/api")

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.before_request
    def enforce_csrf():
        if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"} and not csrf_valid():
            return jsonify({"error": {"code": "csrf_failed", "message": "Refresh the page and try again."}}), 400

    @app.errorhandler(ValueError)
    def invalid_value(error):
        return jsonify({"error": {"code": "validation_error", "message": str(error)}}), 400

    @app.errorhandler(Error)
    def database_error(error):
        app.logger.exception("Database operation failed", exc_info=error)
        return jsonify({"error": {"code": "database_error", "message": "The database operation could not be completed."}}), 500

    @app.errorhandler(429)
    def rate_limited(error):
        return jsonify({"error": {"code": "rate_limited", "message": "Too many attempts. Wait a little and try again."}}), 429

    @app.errorhandler(HTTPException)
    def http_error(error):
        if not request.path.startswith("/api/"):
            return error
        code = "not_found" if error.code == 404 else "method_not_allowed" if error.code == 405 else "http_error"
        return jsonify({"error": {"code": code, "message": error.description}}), error.code

    @app.errorhandler(Exception)
    def unexpected_error(error):
        if isinstance(error, HTTPException):
            return error
        app.logger.exception("Unexpected request error")
        if request.path.startswith("/api/"):
            return jsonify({"error": {"code": "internal_error", "message": "The request could not be completed."}}), 500
        return "Internal Server Error", 500

    @app.get("/api/health")
    def health():
        from .database import connection
        with connection() as (_, cursor):
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return jsonify({"data": {"status": "ok"}})

    return app
