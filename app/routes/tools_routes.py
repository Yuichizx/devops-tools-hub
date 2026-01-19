# app/routes/tools_routes.py
from flask import render_template, request, redirect, url_for, jsonify, current_app
from app import csrf
from app.routes import routes  # gunakan Blueprint yang sama
from app.utils.linter_service import run_yaml_linting, auto_fix_yaml
from app.config import Config

def _clean_url(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned

REPO_AUTOMATION_URL = _clean_url(Config.REPO_AUTOMATION_FE_URL)
FILE_COMPRESSOR_URL = _clean_url(Config.FILE_COMPRESSOR_URL)
STIRLING_STUDIO_URL = _clean_url(Config.STIRLING_STUDIO_URL)

# --- Data Tools ---
TOOLS_DATA = [
    {
        "title": "Repo Scanner",
        "desc": "Pindai repositori GitHub dengan SonarQube.",
        "icon": "bi-search",
        "color": "blue",
        "url_endpoint": "routes.repo_scan",
        "category": "Security",
        "condition": Config.ENABLE_REPO_SCANNER and bool(Config.SONAR_HOST_URL)
    },
    {
        "title": "Stirling PDF",
        "desc": "Konversi & olah dokumen/PDF: merge, split, OCR.",
        "icon": "bi-filetype-pdf",
        "color": "red",
        "external_url": STIRLING_STUDIO_URL, # Special case
        "category": "Utilities",
        "condition": Config.ENABLE_STIRLING_PDF and bool(STIRLING_STUDIO_URL)
    },
    {
        "title": "Base64 Converter",
        "desc": "Encode and decode text to Base64 format.",
        "icon": "bi-arrow-repeat",
        "color": "green",
        "url_endpoint": "routes.base64_converter",
        "category": "Converter"
    },
    {
        "title": "URL Encoder / Decoder",
        "desc": "Encode dan decode teks ke format URL.",
        "icon": "bi-link-45deg",
        "color": "purple",
        "url_endpoint": "routes.url_encoder",
        "category": "Converter"
    },
    {
        "title": "JSON Formatter",
        "desc": "Format, validasi, dan rapikan struktur JSON.",
        "icon": "bi-filetype-json",
        "color": "amber",
        "url_endpoint": "routes.json_formatter",
        "category": "Developer"
    },
    {
        "title": "Diff Checker",
        "desc": "Bandingkan dua teks dan lihat perbedaannya.",
        "icon": "bi-file-diff-fill",
        "color": "sky",
        "url_endpoint": "routes.diff_checker",
        "category": "Developer"
    },
    {
        "title": "Password Generator",
        "desc": "Buat password kuat dengan kustomisasi.",
        "icon": "bi-shield-lock-fill",
        "color": "lime",
        "url_endpoint": "routes.password_generator",
        "category": "Security"
    },
    {
        "title": "JWT Debugger",
        "desc": "Decode dan analisis JSON Web Token secara offline.",
        "icon": "bi-shield-lock",
        "color": "rose",
        "url_endpoint": "routes.jwt_debugger",
        "category": "Security"
    },
    {
        "title": "Dockerfile Generator",
        "desc": "Generate Dockerfile yang dioptimalkan.",
        "icon": "bi-box-seam",
        "color": "blue",
        "url_endpoint": "routes.dockerfile_generator",
        "category": "DevOps"
    },
    {
        "title": "Hash Generator",
        "desc": "Generate MD5, Bcrypt, SHA1, SHA256, SHA512.",
        "icon": "bi-hash",
        "color": "emerald",
        "url_endpoint": "routes.hash_generator",
        "category": "Security"
    },
    {
        "title": "Regex Tester",
        "desc": "Uji pola Regular Expression secara real-time.",
        "icon": "bi-regex",
        "color": "purple",
        "url_endpoint": "routes.regex_tester",
        "category": "Developer"
    },
    {
        "title": "SQL Formatter",
        "desc": "Rapikan (Beautify) atau kecilkan (Minify) SQL.",
        "icon": "bi-file-code",
        "color": "blue",
        "url_endpoint": "routes.sql_formatter",
        "category": "Developer"
    },
    {
        "title": "HTML Viewer",
        "desc": "Lihat, edit, dan render kode HTML.",
        "icon": "bi-filetype-html",
        "color": "sky",
        "url_endpoint": "routes.html_viewer",
        "category": "Developer"
    },
    {
        "title": "GitHub Access Form",
        "desc": "Kelola akses kolaborator ke repositori.",
        "icon": "bi-person-plus-fill",
        "color": "indigo",
        "url_endpoint": "routes.github_access",
        "category": "Access"
    },
    {
        "title": "Cek Role GitHub",
        "desc": "Verifikasi peran pengguna di repositori.",
        "icon": "bi-person-check-fill",
        "color": "purple",
        "url_endpoint": "routes.github_access_check_form",
        "category": "Access"
    },
    {
        "title": "Repo Automation Setup",
        "desc": "Buat file workflow & Helm Values.",
        "icon": "bi-gear-wide-connected",
        "color": "amber",
        "external_url": REPO_AUTOMATION_URL,
        "category": "DevOps",
        "condition": Config.ENABLE_REPO_AUTOMATION and bool(REPO_AUTOMATION_URL)
    },
    {
        "title": "File Compressor",
        "desc": "Kompres ukuran file secara efisien.",
        "icon": "bi-file-zip",
        "color": "emerald",
        "url_endpoint": "routes.file_compressor_redirect",
        "category": "Utilities",
        "condition": Config.ENABLE_FILE_COMPRESSOR and bool(FILE_COMPRESSOR_URL)
    },    {
        "title": "Chmod Calculator",
        "desc": "Hitung izin file sistem Linux.",
        "icon": "bi-key-fill",
        "color": "teal",
        "url_endpoint": "routes.chmod_calculator",
        "category": "DevOps"
    },
    {
        "title": "IP Calculator",
        "desc": "Kalkulator untuk subnetting jaringan.",
        "icon": "bi-diagram-3-fill",
        "color": "cyan",
        "url_endpoint": "routes.ip_calculator",
        "category": "Network"
    },
    {
        "title": "Time Converter",
        "desc": "Konversi format waktu dan timestamp.",
        "icon": "bi-clock-history",
        "color": "orange",
        "url_endpoint": "routes.time_converter",
        "category": "Utilities"
    },
    {
        "title": "Crontab Generator",
        "desc": "Buat dan pahami jadwal cron.",
        "icon": "bi-calendar-check-fill",
        "color": "gray",
        "url_endpoint": "routes.crontab_generator",
        "category": "DevOps"
    },
    {
        "title": "YAML Linter",
        "desc": "Periksa kualitas dan sintaks file YAML.",
        "icon": "bi-file-earmark-code-fill",
        "color": "pink",
        "url_endpoint": "routes.yaml_linter",
        "category": "Developer"
    },
]

##########################################
#           Landing + Tools              #
##########################################

@routes.route('/')
def home_redirect():
    return redirect(url_for('routes.landing'))

@routes.route('/landing')
def landing():
    # Filter tools: Only show tools if 'condition' is True or not present
    active_tools = [t for t in TOOLS_DATA if t.get('condition', True)]
    
    return render_template(
        'landing/landing.html',
        tools=active_tools
    )

@routes.route('/diff-checker')
def diff_checker():
    return render_template('diff-checker/diff-checker.html')

@routes.route('/base64-converter')
def base64_converter():
    return render_template('base64-converter/base64-converter.html')

@routes.route("/tools/url-encoder")
def url_encoder():
    return render_template("tools/url-encoder.html")

@routes.route('/chmod-calculator', methods=['GET'])
def chmod_calculator():
    return render_template('tools/chmod-calculator.html')

@routes.route('/ip-calculator', methods=['GET'])
def ip_calculator():
    return render_template('tools/ip-calculator.html')

@routes.route('/time-converter', methods=['GET'])
def time_converter():
    return render_template('tools/time-converter.html')

@routes.route('/crontab-generator', methods=['GET'])
def crontab_generator():
    return render_template('crontab/crontab-generator.html')

@routes.route("/tools/password-generator")
def password_generator():
    return render_template("tools/password-generator.html")

@routes.route("/tools/jwt-debugger")
def jwt_debugger():
    return render_template("tools/jwt-debugger.html")

@routes.route("/tools/dockerfile-generator")
def dockerfile_generator():
    return render_template("tools/dockerfile-generator.html")

@routes.route("/tools/hash-generator")
def hash_generator():
    return render_template("tools/hash-generator.html")

@routes.route("/tools/regex-tester")
def regex_tester():
    return render_template("tools/regex-tester.html")

@routes.route("/tools/sql-formatter")
def sql_formatter():
    return render_template("tools/sql-formatter.html")

@routes.route("/tools/html-viewer")
def html_viewer():
    return render_template("tools/html-viewer.html")

##########################################
#           Redirect Tools               #
##########################################
@routes.route('/repo-automation')
def repo_automation_redirect():
    if not REPO_AUTOMATION_URL:
        return "Error: URL untuk service Repo Automation tidak dikonfigurasi.", 500
    return redirect(REPO_AUTOMATION_URL)

@routes.route("/file-compressor")
def file_compressor_redirect():
    """
    Redirect ke microservice File Compressor.
    URL ditentukan dari environment variable FILE_COMPRESSOR_URL.
    """
    if not FILE_COMPRESSOR_URL:
        return "Error: URL untuk service File Compressor tidak dikonfigurasi.", 500
    return redirect(FILE_COMPRESSOR_URL)

##########################################
#           JSON Tools                  #
##########################################

@routes.route("/json-formatter")
def json_formatter():
    return render_template("json-formatter/index.html")

@routes.route("/json-formatter/json-to-go")
def json_to_go():
    return render_template("json-formatter/json-to-go.html")

@routes.route("/json-formatter/json-to-c")
def json_to_cs():
    return render_template("json-formatter/json-to-c.html")

@routes.route("/json-formatter/json-to-yaml")
def json_to_yaml():
    return render_template("json-formatter/json-to-yaml.html")

@routes.route("/json-formatter/json-to-sql")
def json_to_sql():
    return render_template("json-formatter/json-to-sql.html")

@routes.route("/json-formatter/json-beautify.html")
def json_beautify():
    return render_template("json-formatter/json-beautify.html")

##########################################
#           YAML Linter                  #
##########################################

@routes.route('/yaml-linter', methods=['GET', 'POST'])
@csrf.exempt
def yaml_linter():
    if request.method == 'GET':
        return render_template('tools/yaml-linter.html', title="YAML Linter")

    # POST
    content = request.json.get('content', '')
    if not content:
        return jsonify({"success": False, "error": "Konten tidak boleh kosong."}), 400
    try:
        results = run_yaml_linting(content)
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "error": f"Terjadi kesalahan internal: {str(e)}"}), 500

@routes.route('/tools/yaml-autofix', methods=['POST'])
@csrf.exempt
def yaml_autofix():
    content = request.json.get('content', '')
    if not content:
        return jsonify({"success": False, "error": "Konten tidak boleh kosong."}), 400
    try:
        fixed_content = auto_fix_yaml(content)
        return jsonify({"success": True, "fixed_content": fixed_content})
    except Exception as e:
        current_app.logger.error("Error during YAML auto-fix", exc_info=True)
        return jsonify({"success": False, "error": f"Gagal memperbaiki: {str(e)}"}), 500
