# app/routes/github_access_routes.py
from flask import render_template, request, redirect, url_for, session, jsonify, current_app
from app.routes import routes
from app.utils.constants import (
    GITHUB_ACCESS_LOGIN_ROUTE,
    GITHUB_ACCESS_DASHBOARD_ROUTE
)
from app.utils.github_role_checker import (
    fetch_all_pages,
    fetch_repositories,
    check_user_permissions
)
from app.utils.auth import (
    validate_github_access_password,
    is_access_password_configured,
    log_access_attempt,
    get_client_ip,
    is_ip_blocked,
    record_failed_attempt,
    reset_failed_attempts
)
from app.utils.github_access import process_github_access_form, GitHubAccessError, parse_repositories
from app.utils.github_api import add_collaborator_to_repo, _get_auth_headers

ERROR_INTERNAL_SERVER = "Terjadi kesalahan internal pada server"
GITHUB_ACCESS_LOGIN_TEMPLATE = "github-access/github-access-login.html"

##########################################
#   GitHub Access (Form & Logic)         #
##########################################

@routes.route('/github-access')
def github_access():
    if not session.get('access_granted'):
        session['next_url'] = url_for('routes.github_access')
        return redirect(url_for(GITHUB_ACCESS_LOGIN_ROUTE))
    return render_template('github-access/github-access.html')

@routes.route('/github-access-submit', methods=['POST'])
def github_access_submit():
    if not session.get('access_granted'):
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    try:
        form_data    = request.form.to_dict()
        result       = process_github_access_form(form_data)
        identifier   = result['github_identifier']
        organization = result['organization']
        access_role  = result['access_role']
        repos        = result['repositories']

        github_results = []
        for repo in repos:
            api_result = add_collaborator_to_repo(
                owner=organization, repo=repo, username=identifier, permission=access_role
            )
            github_results.append({"repo": repo, **api_result})

        return jsonify({"success": True, "github_response": github_results}), 200
    except GitHubAccessError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception:
        current_app.logger.error("❌ Unhandled exception during GitHub Access Submit", exc_info=True)
        return jsonify({"success": False, "error": ERROR_INTERNAL_SERVER}), 500

@routes.route('/github-access/edit', methods=['POST'])
def github_access_edit_page():
    if not session.get('access_granted'):
        session['next_url'] = url_for('routes.github_access')
        return redirect(url_for(GITHUB_ACCESS_LOGIN_ROUTE))
    try:
        identifier   = request.form.get("github_identifier")
        repos_input  = request.form.get("repositories")
        organization = request.form.get("organization")
        if not all([identifier, repos_input, organization]):
            return "Username, Repositories, and Organization are required.", 400

        repo_list = parse_repositories(repos_input)
        return render_template(
            'github-access/github-access-edit-per-repo.html',
            username=identifier, repos=repo_list, org=organization,
            body_class="github-access-page",
        )
    except GitHubAccessError as e:
        return f"Error parsing repositories: {e}", 400

@routes.route('/github-access/apply-roles', methods=['POST'])
def github_access_apply_roles():
    if not session.get('access_granted'):
        return jsonify({"success": False, "error": "Not authenticated"}), 401
    try:
        identifier   = request.form.get("github_identifier")
        organization = request.form.get("organization")
        repos        = request.form.getlist("repositories")
        roles        = request.form.getlist("roles")

        if len(repos) != len(roles):
            raise GitHubAccessError("Mismatch between repositories and roles count.")

        github_results = []
        for repo_name, role_for_repo in zip(repos, roles):
            api_result = add_collaborator_to_repo(
                owner=organization, repo=repo_name, username=identifier, permission=role_for_repo
            )
            github_results.append({"repo": repo_name, **api_result})

        return jsonify({"success": True, "github_response": github_results})
    except GitHubAccessError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception:
        current_app.logger.error("❌ Error applying roles per repo", exc_info=True)
        return jsonify({"success": False, "error": ERROR_INTERNAL_SERVER}), 500

##########################################
#           Auth (Login)                 #
##########################################

@routes.route('/github-access-login', methods=['GET', 'POST'])
def github_access_login():
    error = None
    ip    = get_client_ip()

    if session.get('access_granted'):
        return redirect(url_for(GITHUB_ACCESS_DASHBOARD_ROUTE))

    password_configured = is_access_password_configured()
    if not password_configured:
        return render_template(GITHUB_ACCESS_LOGIN_TEMPLATE, error=None, password_configured=password_configured)

    if is_ip_blocked(ip):
        error = "Too many failed attempts. Try again in 1 minute."
        log_access_attempt(success=False)
        return render_template(GITHUB_ACCESS_LOGIN_TEMPLATE, error=error, password_configured=password_configured)

    if request.method == 'POST':
        password = request.form.get('password')
        if validate_github_access_password(password):
            session.permanent         = True
            session['access_granted'] = True
            reset_failed_attempts(ip)
            log_access_attempt(success=True)

            next_url = session.pop('next_url', None)
            return redirect(next_url or url_for(GITHUB_ACCESS_DASHBOARD_ROUTE))
        else:
            record_failed_attempt(ip)
            error = 'Incorrect password'
            log_access_attempt(success=False)

    return render_template(GITHUB_ACCESS_LOGIN_TEMPLATE, error=error, password_configured=password_configured)

##########################################
#       GitHub Role Checker              #
##########################################

@routes.route('/github-access-check-form', methods=['GET'])
def github_access_check_form():
    if not session.get('access_granted'):
        session['next_url'] = url_for('routes.github_access_check_form')
        return redirect(url_for(GITHUB_ACCESS_LOGIN_ROUTE))
    return render_template('github-access/github-access-check.html')

@routes.route('/github-access-check', methods=['POST'])
def github_access_check():
    if not session.get('access_granted'):
        session['next_url'] = url_for('routes.github_access_check_form')
        return redirect(url_for(GITHUB_ACCESS_LOGIN_ROUTE))

    username   = request.form.get("username", "").strip()
    org        = request.form.get("organization", "").strip()
    mode       = request.form.get("mode")
    team_slugs = request.form.getlist("team_slug")

    if not username or not org:
        return "Username and organization are required.", 400

    try:
        repos   = fetch_repositories(org, mode, team_slugs)
        results = check_user_permissions(org, username, repos)
        filtered_results = [
            r for r in results
            if not (r["status"] == "found" and (r["role"] is None or r["role"] == "-" or r["role"].lower() == "none"))
        ]
        return render_template(
            "github-access/github-access-result.html",
            username=username, org=org, mode=mode, team_slug=team_slugs, results=filtered_results
        )
    except Exception:
        current_app.logger.error("❌ Error during GitHub Access Check", exc_info=True)
        return ERROR_INTERNAL_SERVER, 500

@routes.route('/github-teams', methods=['GET'])
def github_teams():
    org = request.args.get("org")
    if not org:
        return jsonify({"error": "Organization is required."}), 400

    # [PERUBAHAN] Gunakan helper central, jangan hardcode Env variable
    headers = _get_auth_headers()

    try:
        teams = fetch_all_pages(f"https://api.github.com/orgs/{org}/teams", headers=headers)
        return jsonify([
            {"slug": team["slug"], "name": team["name"]}
            for team in teams if "slug" in team and "name" in team
        ])
    except Exception:
        current_app.logger.error("❌ Error fetching GitHub teams", exc_info=True)
        return jsonify({"error": "Terjadi kesalahan internal pada server"}), 500
