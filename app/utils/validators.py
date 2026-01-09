import re

GITHUB_URL_PATTERN = re.compile(r'^(https?://)?(www\.)?github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(\.git)?/?$')
BRANCH_PATTERN = re.compile(r'^(?!-)(?!\/)(?!.*\/\/)(?!.*\.\.)(?!.*\/$)[A-Za-z0-9._/-]+$')
PROJECT_KEY_PATTERN = re.compile(r'^[A-Za-z0-9._-]+$')

def extract_form_data(request):
    repo_url = request.form.get('repo_url', '').strip()
    branch_name = request.form.get('branch_name', '').strip()
    project_key = request.form.get('project_key', '').strip()
    return repo_url, branch_name, project_key

def validate_request(repo_url, branch_name, project_key):
    if not GITHUB_URL_PATTERN.match(repo_url):
        return False, "Invalid repository URL."
    if not BRANCH_PATTERN.match(branch_name):
        return False, "Invalid branch name."
    project_key = project_key.strip()
    if not project_key:
        return False, "Invalid project key."
    if not PROJECT_KEY_PATTERN.match(project_key):
        return False, "Invalid project key."
        
    return True, None
