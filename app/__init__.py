# app/__init__.py

import os
import json
import logging
import re
from datetime import timedelta

from flask import Flask
from flask_wtf import CSRFProtect

from .config import Config

csrf = CSRFProtect()

_ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_ALLOWED_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}


def _strip_ansi(text: str) -> str:
    if not text:
        return text
    return _ANSI_RE.sub("", text)


class _RequestLogFilter(logging.Filter):
    _SKIP_PATHS = ("/ping", "/csrf-token")

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "werkzeug":
            return True
        msg = _strip_ansi(record.getMessage())
        return not any(f" {path} " in msg for path in self._SKIP_PATHS)


class AnsiStrippingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return _strip_ansi(super().format(record))


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "level": record.levelname,
            "message": _strip_ansi(record.getMessage()),
            "time": self.formatTime(record, self.datefmt),
            "name": record.name,
        }
        return json.dumps(log_record)

def configure_logging():
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    log_level = Config.LOG_LEVEL
    if log_level not in _ALLOWED_LOG_LEVELS:
        log_level = "INFO"
    level = getattr(logging, log_level, logging.INFO)
    root.setLevel(level)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.addFilter(_RequestLogFilter())

    if Config.USE_JSON_LOG:
        console.setFormatter(JsonFormatter())
    else:
        fmt = "%(asctime)s %(levelname)-5s [%(name)s] %(message)s"
        console.setFormatter(AnsiStrippingFormatter(fmt))

    root.addHandler(console)

    for name in ("werkzeug", "waitress"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True

def create_app():
    # Validate critical configs
    Config.validate()

    # Path template/static
    this_file = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(this_file))
    template_dir = os.path.join(project_root, "templates")
    static_dir   = os.path.join(project_root, "static")

    flask_app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    
    # Load all configs into Flask app.config
    flask_app.config.from_object(Config)

    # Inject config to all templates
    @flask_app.context_processor
    def inject_config():
        return dict(config=flask_app.config)

    csrf.init_app(flask_app)
    flask_app.permanent_session_lifetime = timedelta(minutes=30)

    configure_logging()
    flask_app.logger.handlers.clear()
    flask_app.logger.propagate = True

    # === IMPORTANT: import routes modules so @routes.route decorators are executed ===
    from .routes import tools_routes          # noqa: F401
    from .routes import github_access_routes  # noqa: F401
    from .routes import repo_scan_routes      # noqa: F401
    # Get blueprint after modules above are imported
    from .routes import routes as routes_bp
    flask_app.register_blueprint(routes_bp)  # no url_prefix

    # Optional debug:
    # print(flask_app.url_map)

    return flask_app
