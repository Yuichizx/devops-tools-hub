# app/utils/github_role_checker.py

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import current_app

# [PERUBAHAN] Import helper auth dari file sebelah agar konsisten & support .netrc
from app.utils.github_api import _get_auth_headers

def fetch_all_pages(url, headers):
    """Helper function to fetch all pages of a GitHub API endpoint."""
    all_items = []
    page = 1

    while True:
        # Menangani URL yang mungkin sudah ada query params (misal ?foo=bar)
        separator = "&" if "?" in url else "?"
        full_url = f"{url}{separator}per_page=100&page={page}"
        
        try:
            resp = requests.get(full_url, headers=headers, timeout=10)
        except requests.RequestException as e:
            raise RuntimeError(f"Network error fetching page {page}: {e}")

        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch page {page}: {resp.status_code} - {resp.text}")

        items = resp.json()
        if not isinstance(items, list):
            # Kadang jika error, GitHub return dict message, bukan list
            raise ValueError(f"Unexpected response format at page {page}: {items}")

        if not items:
            break  # No more data

        all_items.extend(items)
        page += 1

    return all_items

def fetch_repositories(org, mode, team_slugs):
    """Fetch repos based on mode: all repos or team repos."""
    
    # [PERUBAHAN] Ambil headers dari central config (Env / .netrc)
    headers = _get_auth_headers()

    if mode == "all":
        return fetch_all_pages(f"https://api.github.com/orgs/{org}/repos", headers)

    elif mode == "team":
        if not team_slugs:
            raise ValueError("Team slug(s) required for team mode.")

        all_repos = []
        for slug in team_slugs:
            # Menggunakan set untuk mencegah duplikasi repo
            team_repos = fetch_all_pages(f"https://api.github.com/orgs/{org}/teams/{slug}/repos", headers)
            all_repos.extend(team_repos)
        
        # Deduplikasi repo berdasarkan ID (jika satu repo ada di >1 team)
        unique_repos = {r['id']: r for r in all_repos}.values()
        return list(unique_repos)

    else:
        raise ValueError("Invalid mode. Must be 'all' or 'team'.")

def check_user_permissions(org, username, repos, max_workers=10):
    """Check user's role across repositories using multithreading."""

    # [PERUBAHAN] Ambil headers dari central config (Env / .netrc)
    headers = _get_auth_headers()

    def check_repo(repo_name):
        url = f"https://api.github.com/repos/{org}/{repo_name}/collaborators/{username}/permission"
        try:
            # Timeout penting untuk thread worker
            resp = requests.get(url, headers=headers, timeout=10)

            if resp.status_code == 200:
                perm = resp.json().get("permission", "-")
                return {
                    "repo": repo_name,
                    "status": "found",
                    "role": perm
                }
            elif resp.status_code == 404:
                return {
                    "repo": repo_name,
                    "status": "not_found",
                    "role": "-"
                }
            else:
                return {
                    "repo": repo_name,
                    "status": "error",
                    "role": f"Error {resp.status_code}"
                }
        except Exception as e:
            return {
                "repo": repo_name,
                "status": "error",
                "role": f"NetError: {str(e)}"
            }

    results = []
    
    # Threading untuk mempercepat pengecekan banyak repo
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Mapping future ke nama repo untuk error handling
        future_to_repo = {
            executor.submit(check_repo, r.get("name")): r.get("name") 
            for r in repos if r.get("name")
        }

        for future in as_completed(future_to_repo):
            try:
                results.append(future.result())
            except Exception as e:
                repo_name = future_to_repo[future]
                current_app.logger.error(f"❌ Error checking permission for {repo_name}: {e}")
                results.append({
                    "repo": repo_name,
                    "status": "error",
                    "role": "WorkerError"
                })

    return results