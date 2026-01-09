import os
import uuid
import time
import logging
from typing import Tuple, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from app.config import Config

logger = logging.getLogger(__name__)

# Resolve against project root so cwd changes don't break static paths
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SCREENSHOT_DIR = os.path.join(_PROJECT_ROOT, 'static', 'screenshots')


############################################
#   Utils: Ensure directory exists
############################################
def _ensure_screenshot_dir() -> None:
    if not os.path.exists(SCREENSHOT_DIR):
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def _get_screenshot_ttl_seconds() -> int:
    raw = str(Config.SCREENSHOT_TTL_HOURS).strip()
    if not raw:
        return 24 * 60 * 60
    try:
        hours = int(raw)
    except ValueError:
        logger.warning("Invalid SCREENSHOT_TTL_HOURS=%r; using default 24", raw)
        return 24 * 60 * 60
    if hours <= 0:
        return 0
    return hours * 60 * 60


def _cleanup_old_screenshots(ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return
    now = time.time()
    try:
        for entry in os.scandir(SCREENSHOT_DIR):
            if not entry.is_file():
                continue
            if not entry.name.lower().endswith(".png"):
                continue
            try:
                mtime = entry.stat().st_mtime
            except FileNotFoundError:
                continue
            if now - mtime > ttl_seconds:
                os.remove(entry.path)
    except FileNotFoundError:
        return
    except Exception as exc:
        logger.warning("Failed to clean old screenshots: %s", exc)


############################################
#   Utils: Detect badge selector
############################################
def _get_quality_gate_badge_selector(page) -> Optional[str]:
    candidate_selectors = [
        "[data-test='quality-gate-status']",
        "div[data-test='overview__quality-gate-panel'] span",
        "div[data-test='overview__quality-gate-panel'] [class*='QualityGate']",
    ]

    for selector in candidate_selectors:
        try:
            if page.locator(selector).count() > 0:
                logger.info(f"Using Quality Gate badge selector: {selector}")
                return selector
        except Exception:
            continue

    logger.warning("Quality Gate badge selector not found.")
    return None


############################################
#   Polling Logic
############################################
def _wait_for_quality_gate_update(
    page,
    badge_selector: str,
    max_wait_ms: int = 60000,
    interval_ms: int = 2000,
) -> Tuple[bool, Optional[str], int]:
    """
    Polling badge Quality Gate untuk mendeteksi perubahan.
    """
    start = time.time()
    prev_text = None

    try:
        prev_text = page.locator(badge_selector).inner_text().strip()
        latest_text = prev_text
    except Exception as e:
        logger.warning(f"Failed to read initial badge text: {e}")
        return False, None, 0

    logger.info(f"Initial badge text: {prev_text!r}")

    while True:
        elapsed_ms = int((time.time() - start) * 1000)
        if elapsed_ms >= max_wait_ms:
            logger.info(
                f"Polling timeout {elapsed_ms}ms. Using latest: {latest_text!r}"
            )
            return False, latest_text, elapsed_ms

        try:
            latest_text = page.locator(badge_selector).inner_text().strip()
        except Exception:
            pass

        if latest_text != prev_text:
            logger.info(
                f"Badge updated from {prev_text!r} → {latest_text!r} in {elapsed_ms}ms"
            )
            return True, latest_text, elapsed_ms

        page.wait_for_timeout(interval_ms)


############################################
#   MAIN FUNCTION
############################################
def take_sonar_screenshot(
    project_key: str,
    selector: str = None,
    clip_rect: dict = None,
) -> dict | None:
    """
    Ambil screenshot SonarQube:
    - Login
    - Buka project
    - Polling badge Quality Gate
    - Hard wait 30 detik agar benar2 fresh
    - Screenshot
    """
    _ensure_screenshot_dir()
    _cleanup_old_screenshots(_get_screenshot_ttl_seconds())

    sonar_web_url = Config.SONARQUBE_WEB_URL
    sonar_user = Config.SONAR_USERNAME
    sonar_pass = Config.SONAR_PASSWORD

    if not all([sonar_web_url, sonar_user, sonar_pass]):
        logger.error("Config SONARQUBE_WEB_URL/SONAR_USERNAME/SONAR_PASSWORD missing.")
        return None

    target_url = f"{sonar_web_url}/dashboard?id={project_key}"

    # Polling config (tetap, biarkan default)
    max_wait_ms = 60000
    interval_ms = 2000

    # Hard fixed delay 30 detik
    fixed_delay_ms = 30000

    logger.info(
        f"Screenshot config: max_wait={max_wait_ms}ms, interval={interval_ms}ms, fixed_delay={fixed_delay_ms}ms"
    )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1920, "height": 1200})
            page = context.new_page()

            #####################################
            # LOGIN
            #####################################
            try:
                page.goto(sonar_web_url, timeout=60000)
                page.locator('input[name="login"]').fill(sonar_user)
                page.locator('input[name="password"]').fill(sonar_pass)
                page.locator('button[type="submit"]').click()
                page.wait_for_url(f"{sonar_web_url}/projects", timeout=30000)
                logger.info("Login OK.")
            except Exception as e:
                logger.error(f"Login failed: {e}")
                browser.close()
                return None

            #####################################
            # NAVIGATE TO PROJECT
            #####################################
            logger.info(f"Opening Sonar project dashboard: {target_url}")
            page.goto(target_url, wait_until="domcontentloaded", timeout=90000)

            try:
                page.wait_for_selector(
                    "div[data-test='overview__quality-gate-panel']", timeout=90000
                )
                logger.info("Dashboard panel loaded.")
            except Exception:
                logger.warning("Dashboard panel not detected, continue anyway.")

            #####################################
            # POLLING BADGE
            #####################################
            badge_selector = _get_quality_gate_badge_selector(page)

            quality_gate_updated = False
            quality_gate_status = None
            waited_ms = 0

            if badge_selector:
                logger.info("Polling badge update...")
                try:
                    quality_gate_updated, quality_gate_status, waited_ms = (
                        _wait_for_quality_gate_update(
                            page,
                            badge_selector,
                            max_wait_ms=max_wait_ms,
                            interval_ms=interval_ms,
                        )
                    )
                except Exception as e:
                    logger.error(f"Polling crashed: {e}")
            else:
                logger.info("Skipping badge polling (selector not found).")

            #####################################
            # FIXED DELAY 30 SECONDS
            #####################################
            logger.info(f"Waiting {fixed_delay_ms} ms fixed delay (30 seconds)...")
            page.wait_for_timeout(fixed_delay_ms)

            #####################################
            # TAKE SCREENSHOT
            #####################################
            filename = f"{project_key}-{uuid.uuid4()}.png"
            filepath = os.path.join(SCREENSHOT_DIR, filename)

            try:
                if clip_rect and all(k in clip_rect for k in ["x", "y", "width", "height"]):
                    page.screenshot(path=filepath, clip=clip_rect)
                elif selector:
                    try:
                        page.locator(selector).screenshot(path=filepath)
                    except Exception:
                        page.screenshot(path=filepath, full_page=True)
                else:
                    page.screenshot(path=filepath, full_page=True)

                logger.info(f"Screenshot saved: {filepath}")
            finally:
                browser.close()

            return {
                "display_url": f"/static/screenshots/{filename}",
                "filename": filename,
                "quality_gate_updated": quality_gate_updated,
                "quality_gate_status": quality_gate_status,
                "waited_ms": waited_ms,
                "fixed_delay_ms": fixed_delay_ms,
            }

    except Exception as e:
        logger.error(f"Unexpected screenshot error: {e}")
        return None
