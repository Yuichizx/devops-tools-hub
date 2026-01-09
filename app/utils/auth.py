import os
import hmac
from flask import request
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

_failed_attempts = {}
MAX_ATTEMPTS = 5
BLOCK_DURATION = timedelta(minutes=1)

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0]
    return request.remote_addr or 'unknown'

def validate_github_access_password(input_password: str) -> bool:
    expected_password = (os.getenv("GITHUB_ACCESS_PASSWORD") or "").strip()
    if not expected_password:
        return False
    return hmac.compare_digest(input_password or "", expected_password)

def is_access_password_configured() -> bool:
    return bool((os.getenv("GITHUB_ACCESS_PASSWORD") or "").strip())

def is_ip_blocked(ip: str) -> bool:
    entry = _failed_attempts.get(ip)
    if not entry:
        return False

    blocked_until = entry.get("blocked_until")
    if blocked_until and datetime.utcnow() < blocked_until:
        return True

    # Jika sudah lewat waktu blokir, reset percobaan
    if blocked_until and datetime.utcnow() >= blocked_until:
        _failed_attempts[ip] = {"count": 0, "last_failed_at": None, "blocked_until": None}
    return False

def record_failed_attempt(ip: str):
    now = datetime.utcnow()
    entry = _failed_attempts.get(ip, {"count": 0, "last_failed_at": None, "blocked_until": None})
    entry["count"] += 1
    entry["last_failed_at"] = now

    if entry["count"] >= MAX_ATTEMPTS:
        entry["blocked_until"] = now + BLOCK_DURATION

    _failed_attempts[ip] = entry

def reset_failed_attempts(ip: str):
    if ip in _failed_attempts:
        _failed_attempts[ip] = {"count": 0, "last_failed_at": None, "blocked_until": None}

def log_access_attempt(success: bool):
    ip = get_client_ip()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "SUCCESS" if success else "FAILED"
    log_line = f"[{now}] [{ip}] Login attempt: {status}\n"
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, "github_access.log"), "a") as f:
        f.write(log_line)
