import os
from flask import Flask
from flask_compress import Compress
from flask_login import current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from app.extensions import db, migrate, csrf, login_manager


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
    from app.routes import auth, main, leave, admin, owner, reports
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(leave.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(owner.bp)
    app.register_blueprint(reports.bp)

    @app.context_processor
    def inject_owner():
        owner_email = os.environ.get("OWNER_EMAIL", "").strip().lower()
        is_owner = bool(
            owner_email
            and current_user.is_authenticated
            and current_user.email.lower() == owner_email
        )
        return {"is_owner": is_owner}

    @app.route("/health")
    def health():
        db.session.execute(db.text("SELECT 1"))
        return "Database connected"

    return app