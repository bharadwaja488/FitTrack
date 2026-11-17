from app import create_app

app = create_app()
print(f"CORS allowlist: {', '.join(app.config['FRONTEND_ORIGINS'])}", flush=True)

if __name__ == "__main__":
    if app.config["IS_PRODUCTION"]:
        raise SystemExit("Production must run behind the configured WSGI server, not Flask's development server.")
    app.run(host="127.0.0.1", port=app.config["PORT"], debug=app.config["DEBUG"])
