from flask import Blueprint

# Satu blueprint global bernama 'routes' agar url_for('routes.*') konsisten
routes = Blueprint("routes", __name__)

# === Import sub-route modules di bawah ini ===
# Penting: urutan import boleh bebas, tapi jangan ada import siklikus.
# Pastikan setiap file routes.* melakukan: `from app.routes import routes`
# lalu mendekorasi dengan @routes.route(...)
from . import tools_routes           # noqa: F401, E402
from . import github_access_routes   # noqa: F401, E402
from . import repo_scan_routes       # noqa: F401, E402
# from . import file_compress_routes   # noqa: F401, E402
# Tambahkan modul routes lain di sini:
# from . import repo_scan_routes     # noqa: F401, E402
# from . import yaml_routes          # noqa: F401, E402
