from flask import Flask
from config import Config
from app.extensions import db, migrate, csrf, login_manager
from flask_compress import Compress


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    Compress(app)

    from app import models  # noqa: F401
    from app.routes import auth, main, leave, admin
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(leave.bp)
    app.register_blueprint(admin.bp)

    @app.route("/health")
    def health():
        db.session.execute(db.text("SELECT 1"))
        return "Database connected"

    return app