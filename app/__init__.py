import os
from flask import Flask, request
from flask_compress import Compress
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from app.extensions import db, migrate, csrf, login_manager

# Pages that must never appear in search results
PRIVATE_ROOTS = {
    "/admin", "/leave", "/reports", "/dashboard", "/owner", "/verify", "/invite",
    "/reset-password", "/forgot-password", "/login", "/logout", "/health",
}


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    Compress(app)

    from app import models  # noqa: F401
    from app.routes import auth, main, leave, admin, owner, reports, pages
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(leave.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(owner.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(pages.bp)

    @app.context_processor
    def inject_globals():
        return {
            "owner_session": owner.owner_logged_in(),
            "google_verification": os.environ.get("GOOGLE_SITE_VERIFICATION", "").strip(),
        }

    @app.after_request
    def seo_headers(response):
        first = "/" + request.path.strip("/").split("/")[0]     # matches whole path parts only
        if first in PRIVATE_ROOTS:
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        elif first == "/static":
            response.headers["Cache-Control"] = "public, max-age=604800"
        return response

    @app.route("/health")
    def health():
        db.session.execute(db.text("SELECT 1"))
        return "Database connected"

    from app.cli import register_commands
    register_commands(app)

    return app