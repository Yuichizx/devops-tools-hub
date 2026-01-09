import os
from dotenv import load_dotenv

# Load .env file at startup
load_dotenv()

class Config:
    """Centralized configuration for the application."""
    
    # Flask Security
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "").strip()

    # UI Customization
    APP_TITLE = os.getenv("APP_TITLE", "DevOps Tools Hub")
    APP_LOGO = os.getenv("APP_LOGO", "/static/images/logo.png")
    APP_FAVICON = os.getenv("APP_FAVICON", "/static/images/favicon.png")
    APP_DESCRIPTION = os.getenv("APP_DESCRIPTION", "Platform terpusat untuk automasi, monitoring, keamanan, dan utilitas developer.")
    
    # SonarQube Scanner Configs
    SONAR_HOST_URL = os.getenv("SONAR_HOST_URL")
    SONAR_LOGIN_TOKEN = os.getenv("SONAR_LOGIN_TOKEN")
    SONAR_EXCLUSIONS = os.getenv("SONAR_EXCLUSIONS", "")
    
    # JVM / Performance Configs
    SCANNER_HEAP_MIN = os.getenv("SCANNER_HEAP_MIN", "-Xms512m")
    SCANNER_HEAP_LIMIT = os.getenv("SCANNER_HEAP_LIMIT", "-Xmx1900m")
    CPU_NICE_ADJUSTMENT = int(os.getenv("CPU_NICE_ADJUSTMENT", "0"))
    CPU_AFFINITY = os.getenv("CPU_AFFINITY", "")
    SONAR_CPD_MINIMUM_TOKENS = os.getenv("SONAR_CPD_MINIMUM_TOKENS")
    SONAR_DEBUG = os.getenv("SONAR_DEBUG", "false").lower() in {"1", "true", "yes", "on"}
    
    # SonarQube Web / Screenshot Configs (for Playwright)
    SONARQUBE_WEB_URL = os.getenv("SONARQUBE_WEB_URL")
    SONAR_USERNAME = os.getenv("SONAR_USERNAME")
    SONAR_PASSWORD = os.getenv("SONAR_PASSWORD")
    SCREENSHOT_TTL_HOURS = os.getenv("SCREENSHOT_TTL_HOURS", "24")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    USE_JSON_LOG = os.getenv("USE_JSON_LOG", "true").lower() == "true"
    
    # Redirect URLs for Tools
    REPO_AUTOMATION_FE_URL = os.getenv("REPO_AUTOMATION_FE_URL")
    FILE_COMPRESSOR_URL = os.getenv("FILE_COMPRESSOR_URL")
    STIRLING_STUDIO_URL = os.getenv("STIRLING_STUDIO_URL") or os.getenv("PDF_REDIRECT_URL")
    
    # GitHub Access Password
    GITHUB_ACCESS_PASSWORD = os.getenv("GITHUB_ACCESS_PASSWORD")
    
    # GitHub API Token (Optional, alternative to .netrc)
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

    @classmethod
    def validate(cls):
        """Simple check to ensure mandatory configs are present."""
        if not cls.SECRET_KEY:
            raise RuntimeError("FLASK_SECRET_KEY is missing!")
        if not cls.SONAR_HOST_URL:
            print("Warning: SONAR_HOST_URL is not set. Repo Scanner will fail.")
