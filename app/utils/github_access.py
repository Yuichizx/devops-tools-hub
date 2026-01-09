# app/utils/github_access.py

import requests
import re
import os
import netrc
import logging
from typing import List, Dict

# Hapus GITHUB_TOKEN dari import, cukup URL saja
from app.utils.github_api import GITHUB_API_URL 

logger = logging.getLogger(__name__)

class GitHubAccessError(Exception):
    """Custom error for GitHub Access form issues."""
    pass

def _get_auth_header() -> Dict[str, str]:
    """
    [HELPER] Mendapatkan header otentikasi.
    Prioritas:
    1. Environment Variable GITHUB_TOKEN
    2. File ~/.netrc (entry machine 'github.com')
    """
    # 1. Cek Environment Variable
    env_token = os.getenv("GITHUB_TOKEN")
    if env_token:
        logger.debug("Using GitHub credentials from Environment Variable (GITHUB_TOKEN)")
        return {"Authorization": f"Bearer {env_token}"}

    # 2. Cek .netrc
    try:
        # Cari file .netrc di home directory user
        netrc_path = os.path.expanduser("~/.netrc")
        
        if os.path.exists(netrc_path):
            # Parse file .netrc
            auth_data = netrc.netrc(netrc_path)
            
            # Cari kredensial untuk host 'github.com'
            authenticators = auth_data.authenticators("github.com")
            
            if authenticators:
                login, account, password = authenticators
                # Di GitHub, password di .netrc harusnya adalah Personal Access Token (PAT)
                if password:
                    logger.debug("Using GitHub credentials from .netrc")
                    return {"Authorization": f"Bearer {password}"}
        else:
            logger.debug(f".netrc file not found at {netrc_path}")

    except Exception as e:
        logger.warning(f"Failed to read .netrc for API access: {e}")

    # Jika tidak ada auth di .netrc, return kosong (Unauthenticated request)
    # Hati-hati: Rate limit GitHub sangat rendah untuk unauthenticated request (60/jam).
    logger.warning("No GitHub credentials found in Env or .netrc. Requesting anonymously.")
    return {}

def parse_repositories(repo_input: str) -> List[str]:
    """
    Mem-parsing input repositori yang bisa dipisahkan oleh koma, spasi, atau baris baru.
    """
    # Normalisasikan input: ganti baris baru/spasi dengan koma
    normalized_input = re.sub(r'[\s,]+', ',', repo_input)
    raw_list = normalized_input.split(',')
    
    repo_names = []

    for repo in raw_list:
        repo = repo.strip()
        if not repo:
            continue

        if "github.com" in repo:
            # Menggunakan regex untuk mengekstrak nama repo dari URL
            match = re.search(r"github\.com\/[^\/]+\/([^\/\s]+)", repo)
            if match:
                repo_name = match.group(1)
                if repo_name.endswith('.git'):
                    repo_name = repo_name[:-4]
                repo_names.append(repo_name)
            else:
                raise GitHubAccessError(f"Invalid GitHub URL format: {repo}")
        else:
            repo_names.append(repo)

    if not repo_names:
        raise GitHubAccessError("No valid repository names found in input.")

    return list(dict.fromkeys(repo_names)) # Hapus duplikat sambil menjaga urutan

def is_valid_github_repo(org: str, repo_name: str) -> bool:
    """
    Checks if the given repository exists in the GitHub organization.
    """
    # Ambil auth header dari .netrc
    headers = _get_auth_header()
    
    # Header wajib untuk GitHub API modern
    headers["Accept"] = "application/vnd.github+json"

    url = f"{GITHUB_API_URL}/repos/{org}/{repo_name}"

    try:
        # Timeout 10 detik agar worker tidak hang jika GitHub lambat
        response = requests.get(url, headers=headers, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Error checking repo {repo_name}: {e}")
        return False

def process_github_access_form(data: Dict) -> Dict:
    """
    Validates and processes GitHub access form data.
    Raises GitHubAccessError if invalid input or repositories.
    """
    identifier = data.get("github_identifier", "").strip()
    repositories_input = data.get("repositories", "").strip()
    access_role = data.get("accessRole", "").strip()
    organization = data.get("organization", "").strip()

    if not identifier:
        raise GitHubAccessError("GitHub username is required.")

    if not repositories_input:
        raise GitHubAccessError("Repository names must be provided.")

    if not access_role:
        raise GitHubAccessError("Access role must be selected.")

    if not organization:
        raise GitHubAccessError("Organization must be selected.")

    repo_list = parse_repositories(repositories_input)

    # Validate that each repository actually exists
    invalid_repos = []
    for repo in repo_list:
        if not is_valid_github_repo(organization, repo):
            invalid_repos.append(repo)

    if invalid_repos:
        raise GitHubAccessError(
            f"The following repositories were not found under organization '{organization}': "
            f"{', '.join(invalid_repos)}"
        )

    return {
        "github_identifier": identifier,
        "repositories": repo_list,
        "access_role": access_role,
        "organization": organization
    }