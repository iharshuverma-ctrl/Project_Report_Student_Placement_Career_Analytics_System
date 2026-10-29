"""
app.py - Entry point of the Flask web application.

    python app.py          ->  open http://127.0.0.1:5000
"""
import secrets

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for

from config import Config
from database import DatabaseError
from routes import (auth, companies, dashboard, departments, reports, settings, skills,
                    students)

# Pages that can be opened without logging in
PUBLIC_ENDPOINTS = {"auth.login", "static"}


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    for module in (auth, dashboard, students, companies, departments, skills, reports, settings):
        app.register_blueprint(module.bp)

    # ---------- Access control: every page needs a login ----------
    @app.before_request
    def require_login():
        if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint is None:
            return None
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify(error="Please log in first."), 401
            return redirect(url_for("auth.login", next=request.path))
        return None

    # ---------- CSRF protection for every POST form ----------
    @app.before_request
    def csrf_protect():
        if request.method == "POST":
            token = session.get("_csrf_token")
            if not token or token != request.form.get("csrf_token"):
                abort(400, description="Your form session expired. Please reload the page and try again.")

    def csrf_token():
        if "_csrf_token" not in session:
            session["_csrf_token"] = secrets.token_hex(16)
        return session["_csrf_token"]

    # ---------- Values available in every template ----------
    @app.context_processor
    def inject_globals():
        from analytics import get_batches
        try:
            batches = get_batches()
        except DatabaseError:
            batches = []
        return {
            "csrf_token": csrf_token,
            "app_name": Config.APP_NAME,
            "all_batches": batches,
            "ongoing_batch": Config.ONGOING_BATCH,
            "current_user": {"username": session.get("username"), "role": session.get("role")},
            "is_admin": session.get("role") == "admin",
        }

    # ---------- Friendly error pages ----------
    @app.errorhandler(DatabaseError)
    def database_error(exc):
        if request.path.startswith("/api/"):
            return jsonify(error=str(exc)), 503
        return render_template("error.html", code=503, title="Database unavailable", message=str(exc)), 503

    @app.errorhandler(400)
    def bad_request(exc):
        return render_template("error.html", code=400, title="Bad request", message=exc.description), 400

    @app.errorhandler(403)
    def forbidden(exc):
        return render_template("error.html", code=403, title="Access denied",
                               message="Your account does not have permission for this action."), 403

    @app.errorhandler(404)
    def not_found(exc):
        if request.path.startswith("/api/"):
            return jsonify(error="Not found"), 404
        return render_template("error.html", code=404, title="Page not found",
                               message="The page you requested does not exist."), 404

    @app.errorhandler(500)
    def server_error(exc):
        return render_template("error.html", code=500, title="Something went wrong",
                               message="An unexpected error occurred. Check the terminal for details."), 500

    return app


app = create_app()

if __name__ == "__main__":
    import webbrowser
    from threading import Timer

    url = "http://127.0.0.1:5000"

    Timer(1.5, lambda: webbrowser.open(url)).start()

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )