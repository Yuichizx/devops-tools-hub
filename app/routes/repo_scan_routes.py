# app/routes/repo_scan_routes.py
import os
from typing import Dict, Any, Optional, Tuple

from flask import (
    render_template,
    request,
    jsonify,
    send_from_directory,
    current_app,
    url_for,
)
from flask_wtf.csrf import generate_csrf

from app.routes import routes  # Existing Blueprint
from app.tasks import create_task, task_statuses
from app.utils.validators import extract_form_data, validate_request

# Screenshot directory (inside static/screenshots)
# Use current_app.root_path at runtime for consistency in container/venv

def _screenshot_dir() -> str:
    root = current_app.root_path if current_app else os.getcwd()
    return os.path.join(root, "static", "screenshots")


def _truncate_log(log_text: Optional[str], max_bytes: int = 50_000) -> Tuple[Optional[str], int]:
    """Returns (log_snippet, total_size).
    - For normal response, we don't send full log to save localStorage/quota.
    - FE will show button if has_log=True, and can request include_log=1 if needed.
    """
    if not log_text:
        return None, 0
    encoded = log_text.encode("utf-8", errors="ignore")
    total = len(encoded)
    if total <= max_bytes:
        return log_text, total
    # safe cut per byte then decode back
    truncated = encoded[:max_bytes]
    try:
        snippet = truncated.decode("utf-8", errors="ignore")
    except Exception:
        snippet = None
    return snippet, total


def _shape_screenshot_info(task: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    info = task.get("screenshot_info")
    if not info:
        return None
    filename = info.get("filename")
    if not filename:
        return None
    # display_url to static so it can be opened in new tab (see FE expectation)
    display_url = url_for("static", filename=f"screenshots/{filename}", _external=False)
    return {
        "filename": filename,
        "display_url": display_url,
        # keep other fields from producer if any
        **{k: v for k, v in info.items() if k not in {"filename"}},
    }


##########################################
#           Sonar Repo Scanner           #
##########################################

@routes.route("/repo-scan", methods=["GET", "POST"])
def repo_scan():
    if request.method == "GET":
        return render_template("repo-scan/repo-scan.html")


    # POST (AJAX)
    repo_url, branch_name, project_key = extract_form_data(request)
    valid, error_msg = validate_request(repo_url, branch_name, project_key)
    if not valid:
        return jsonify({"error": error_msg}), 400

    exclusions = (request.form.get("sonar_exclusions") or "").strip()
    inclusions = (request.form.get("sonar_inclusions") or "").strip()

    task_id = create_task(
        repo_url,
        branch_name,
        project_key,
        exclusions=exclusions,
        inclusions=inclusions,
    )

    return jsonify({
        "message": "Task queued successfully.",
        "task_id": task_id,
        "repo_url": repo_url,
    }), 200


@routes.route("/status/<task_id>", methods=["GET"])
def task_status_route(task_id):
    task_info = task_statuses.get(task_id)
    if not task_info:
        return jsonify({"error": "Invalid task ID"}), 404

    # Form screenshot info for FE (has display_url & filename)
    screenshot_info = _shape_screenshot_info(task_info)

    # Handle log: default DO NOT send full log. FE only needs meta to avoid filling localStorage
    include_log = request.args.get("include_log") == "1"
    raw_log = task_info.get("log")
    if include_log:
        # if requested, send log with safe truncation (e.g. 50KB)
        log_snippet, total_size = _truncate_log(raw_log)
        log_payload = log_snippet
    else:
        # do not send log body, only meta
        log_payload = None
        total_size = len(raw_log.encode("utf-8", errors="ignore")) if raw_log else 0

    response = {
        "task_id": task_id,
        "status": task_info.get("status", "Unknown"),
        "sonar_url": task_info.get("sonar_url"),
        "screenshot_info": screenshot_info,
        # Lightweight log meta for FE
        "has_log": bool(raw_log),
        "log_size": total_size,
        # Send log only when include_log=1
        "log": log_payload,
    }
    return jsonify(response)




@routes.route("/download/screenshots/<path:filename>")
def download_screenshot(filename):
    """
    Endpoint to download scan screenshots.
    Path: /download/screenshots/<filename>
    """
    # Point to static/screenshots folder
    directory = os.path.join(current_app.static_folder, "screenshots")
    os.makedirs(directory, exist_ok=True)

    # Ensure file actually exists
    full_path = os.path.join(directory, filename)
    if not os.path.isfile(full_path):
        current_app.logger.warning("Screenshot not found: %s", full_path)
        return "File not found.", 404

    # Send file for download
    return send_from_directory(directory, filename, as_attachment=True)


##########################################
#        Health & CSRF helper routes     #
##########################################

@routes.get("/csrf-token")
def get_csrf_token():
    """Endpoint to refresh CSRF token (used by FE when idle/expired)."""
    return jsonify({"csrf_token": generate_csrf()})


@routes.get("/ping")
def ping():
    """Lightweight endpoint for session keep-alive and connection check."""
    return ("", 204)
