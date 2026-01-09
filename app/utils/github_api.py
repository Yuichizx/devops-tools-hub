# app/utils/github_api.py

import os
import requests
import netrc
import logging
from typing import Dict, Optional

# Setup logger
logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"

def _get_token_from_netrc() -> Optional[str]:
    """Mencoba mengambil token dari file ~/.netrc"""
    try:
        netrc_path = os.path.expanduser("~/.netrc")
        if os.path.exists(netrc_path):
            auth_data = netrc.netrc(netrc_path)
            # Cari entry untuk machine 'github.com'
            authenticators = auth_data.authenticators("github.com")
            if authenticators:
                return authenticators[2]
        else:
            logger.debug(f".netrc file not found at {netrc_path}")
            
    except Exception as e:
        logger.warning(f"Failed to read .netrc: {e}")
    return None

def _get_auth_headers() -> Dict[str, str]:
    """
    Membungkus pembuatan header.
    Prioritas:
    1. Environment Variable GITHUB_TOKEN
    2. File ~/.netrc
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
    }

    # 1. Cek Environment Variable
    token = os.getenv("GITHUB_TOKEN")

    # 2. Jika tidak ada di env, cek .netrc
    if not token:
        token = _get_token_from_netrc()

    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        logger.warning("No GitHub Token found in Env ('GITHUB_TOKEN') or .netrc. API calls might fail or be rate-limited.")

    return headers

def add_collaborator_to_repo(owner: str, repo: str, username: str, permission: str = "push") -> dict:
    """
    Mengundang atau mengupdate user sebagai kolaborator di sebuah repositori.
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/collaborators/{username}"
    
    # Header diambil dari .netrc
    headers = _get_auth_headers()
    data = {"permission": permission}

    try:
        response = requests.put(url, headers=headers, json=data, timeout=10)

        # Kasus sukses: Pengguna baru diundang
        if response.status_code == 201:
            return {
                "ok": True,
                "status": "invited",
                "message": f"User '{username}' successfully invited.",
                "role": permission
            }
        
        # Kasus sukses: Izin pengguna yang sudah ada diupdate
        elif response.status_code == 204:
            return {
                "ok": True,
                "status": "updated",
                "message": f"Permissions for '{username}' successfully updated.",
                "role": permission
            }
            
        # Kasus lain (kemungkinan error)
        else:
            try:
                error_msg = response.json().get("message", "An unknown error occurred.")
            except requests.exceptions.JSONDecodeError:
                error_msg = response.text
                
            return {
                "ok": False,
                "status": "failed",
                "message": f"Failed with status {response.status_code}: {error_msg}",
                "role": None
            }

    except requests.RequestException as e:
        return {
            "ok": False,
            "status": "failed",
            "message": f"Network error: {str(e)}",
            "role": None
        }

def is_user_already_invited(owner: str, repo: str, username: str) -> bool:
    """
    Mengecek apakah seorang pengguna sudah menjadi kolaborator.
    """
    url = f"{GITHUB_API_URL}/repos/{owner}/{repo}/collaborators/{username}"
    headers = _get_auth_headers()

    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.status_code == 204
    except requests.RequestException:
        return False
