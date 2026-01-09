# app/utils/git_sonar.py

import os
import re
import subprocess
import tempfile
import shutil
import logging
import queue
import threading
from dataclasses import dataclass
from concurrent.futures import Future
from typing import List, Dict, Any, Optional, Tuple

from app.config import Config

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


class QualityGateFailed(Exception):
    """
    Dilemparkan saat SonarScanner keluar dengan kode 2 (Quality Gate gagal).
    Membawa URL dashboard di .url
    """
    def __init__(self, url: str):
        super().__init__("Quality Gate failed")
        self.url = url


# Detect common token leaks in repo URL (prevent future incidents)
_TOKEN_PATTERNS = [
    r"ghp_[A-Za-z0-9]{20,}",
    r"github_pat_[A-Za-z0-9_]{20,}",
    r"gho_[A-Za-z0-9]{20,}",
    r"ghu_[A-Za-z0-9]{20,}",
    r"ghs_[A-Za-z0-9]{20,}",
    r"ghr_[A-Za-z0-9]{20,}",
]


def _looks_like_credentialed_url(repo_url: str) -> bool:
    # URL basic-auth usually contains "@"
    if "@" in repo_url:
        return True
    for pat in _TOKEN_PATTERNS:
        if re.search(pat, repo_url):
            return True
    return False


def _git_env() -> Dict[str, str]:
    """
    Pastikan git tidak meminta input interaktif.
    Git akan otomatis mencari .netrc di $HOME/.netrc (default behavior).
    """
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def limited_clone(repo_url: str, branch_name: str) -> str:
    """
    Clone repo ke direktori sementara.
    Auth murni mengandalkan ~/.netrc di folder user.
    """
    if _looks_like_credentialed_url(repo_url):
        raise ValueError("repo_url contains credential/token. Use clean https URL and rely on .netrc.")

    tmp_dir = tempfile.mkdtemp()
    logger.info("Cloning %s into %s", repo_url, tmp_dir)

    try:
        cmd = [
            "git",
            "-c", "credential.helper=", # Matikan helper lain, paksa baca config/netrc
            "clone",
            "--quiet",
            "--depth", "1",
            "--branch", branch_name,
            "--", # Security: prevent argument injection
            repo_url,
            tmp_dir,
        ]

        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            env=_git_env(),
        )

        logger.info("Clone successful (branch=%s).", branch_name)
        return tmp_dir

    except subprocess.CalledProcessError as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)

        stderr = (e.stderr or "").strip()
        stdout = (e.stdout or "").strip()
        detail = stderr or stdout or "unknown git error"
        hint = ""
        if "could not read Username" in detail:
            hint = "Check .netrc in HOME and its permissions (600)."
            detail = f"{detail}. {hint}"

        logger.error("Git operation failed for %s. Detail: %s", repo_url, detail)
        raise RuntimeError(f"Git operation failed: {detail}") from e


def _get_sonar_config() -> Dict[str, Any]:
    """
    [HELPER] Mengumpulkan semua konfigurasi dari Config class.
    """
    return {
        "host_url": Config.SONAR_HOST_URL,
        "login_token": Config.SONAR_LOGIN_TOKEN,
        "heap_min": Config.SCANNER_HEAP_MIN,
        "heap_max": Config.SCANNER_HEAP_LIMIT,
        "nice_adj": Config.CPU_NICE_ADJUSTMENT,
        "affinity_str": Config.CPU_AFFINITY,
        "cache_dir": os.getenv("SONAR_USER_HOME", "/cache"),
        "default_exclusions": Config.SONAR_EXCLUSIONS,
        "cpd_min_tokens": Config.SONAR_CPD_MINIMUM_TOKENS,
        "sonar_debug": Config.SONAR_DEBUG,
    }


def _append_coverage_args(cmd: List[str], tmp_dir: str) -> None:
    coverage_paths = {
        "python": ("-Dsonar.python.coverage.reportPaths=", "coverage.xml"),
        "java": ("-Dsonar.coverage.jacoco.xmlReportPaths=", "target/site/jacoco/jacoco.xml"),
        "javascript": ("-Dsonar.javascript.lcov.reportPaths=", "coverage/lcov.info"),
        "go": ("-Dsonar.go.coverage.reportPaths=", "coverage.out"),
    }

    for lang, (param, path) in coverage_paths.items():
        if os.path.exists(os.path.join(tmp_dir, path)):
            logger.info("Found %s coverage report, adding to scanner command.", lang)
            cmd.append(f"{param}{path}")
            if lang == "java" and os.path.exists(os.path.join(tmp_dir, "target/classes")):
                cmd.append("-Dsonar.java.binaries=target/classes")
            return

    logger.warning("No coverage report found. Skipping coverage metrics.")


def _append_cpd_min_tokens(cmd: List[str], config: Dict[str, Any]) -> None:
    min_tokens = config.get("cpd_min_tokens")
    if min_tokens:
        cmd.append(f"-Dsonar.cpd.minimumTokens={min_tokens}")
        logger.info("CPD minimumTokens=%s", min_tokens)


def _build_sonar_command(
    config: Dict[str, Any],
    project_key: str,
    exclusions: Optional[str],
    inclusions: Optional[str],
    tmp_dir: str
) -> List[str]:
    """
    Build command WITHOUT putting token in argv.
    Token akan dikirim via env SONAR_TOKEN di _run_scanner_process().
    """
    host_url = (config.get("host_url") or "").strip()
    if not host_url:
        raise RuntimeError("Missing SONAR_HOST_URL")

    cmd = [
        "sonar-scanner",
        f"-Dsonar.projectKey={project_key}",
        "-Dsonar.sources=.",
        f"-Dsonar.host.url={host_url}",
    ]
    if config.get("sonar_debug"):
        cmd[1:1] = ["-X", "-Dsonar.verbose=true"]

    exclusions_pattern = exclusions or config["default_exclusions"]
    if exclusions_pattern:
        cmd.append(f"-Dsonar.exclusions={exclusions_pattern}")
        logger.info("Using Sonar exclusions: %s", exclusions_pattern)

    if inclusions:
        cmd.append(f"-Dsonar.inclusions={inclusions}")
        logger.info("Using Sonar inclusions: %s", inclusions)

    _append_coverage_args(cmd, tmp_dir)
    _append_cpd_min_tokens(cmd, config)

    return cmd


def _build_scanner_env(
    config: Dict[str, Any],
    custom_cache_dir: Optional[str]
) -> Tuple[Dict[str, str], str]:
    env = os.environ.copy()
    env["SONAR_SCANNER_OPTS"] = f"{config['heap_min']} {config['heap_max']}"

    final_cache_dir = custom_cache_dir if custom_cache_dir else config["cache_dir"]
    env["SONAR_USER_HOME"] = final_cache_dir

    token = (config.get("login_token") or "").strip()
    if not token:
        raise RuntimeError("Missing SONAR_LOGIN_TOKEN (required).")
    env["SONAR_TOKEN"] = token

    os.makedirs(final_cache_dir, exist_ok=True)
    return env, final_cache_dir


def _apply_nice(nice_adj: int) -> None:
    try:
        os.nice(nice_adj)
    except Exception:
        pass


def _apply_affinity(affinity_str: str) -> None:
    if not affinity_str:
        return
    try:
        cores = {int(c) for c in affinity_str.split(",")}
        os.sched_setaffinity(0, cores)
    except Exception:
        pass


def _build_scanner_preexec(config: Dict[str, Any]):
    nice_adj = config.get("nice_adj", 0)
    affinity_str = config.get("affinity_str") or ""

    def _preexec():
        _apply_nice(nice_adj)
        _apply_affinity(affinity_str)

    return _preexec


def _log_scanner_line(line: str) -> None:
    text = line.strip()
    if text.startswith("INFO:") or "SUCCESS" in text:
        logger.info("[SONAR] %s", text)
    else:
        logger.debug("[SONAR] %s", text)


def _collect_scanner_output(proc: subprocess.Popen) -> List[str]:
    output: List[str] = []
    if not proc.stdout:
        return output
    for line in proc.stdout:
        output.append(line)
        _log_scanner_line(line)
    return output


def _scanner_failure_hint(output: str) -> str:
    if "Not authorized" in output or "401" in output:
        return "Check SONAR_LOGIN_TOKEN and SONAR_HOST_URL."
    if "UnknownHostException" in output or "failed to connect" in output:
        return "Check SONAR_HOST_URL reachability."
    return ""


def _raise_scanner_failure(ret: int, output_lines: List[str]) -> None:
    if ret in (0, 2):
        return
    output = "".join(output_lines)
    hint = _scanner_failure_hint(output)
    if hint:
        output = f"{output}\nHint: {hint}\n"
        logger.error("SonarScanner failed. Hint: %s", hint)
    logger.error("SonarScanner ERROR (exit %d):\n%s", ret, output)
    raise RuntimeError(f"SonarScanner failed (exit {ret})\n\n{output}")


def _run_scanner_process(
    cmd: List[str],
    tmp_dir: str,
    config: Dict[str, Any],
    custom_cache_dir: Optional[str] = None
) -> int:
    env, final_cache_dir = _build_scanner_env(config, custom_cache_dir)

    # Safe to log cmd now (no token inside)
    logger.debug("Final Sonar command arguments: %s", " ".join(cmd))
    logger.debug("Scanner Cache Dir: %s", final_cache_dir)

    proc = subprocess.Popen(
        cmd,
        cwd=tmp_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
        preexec_fn=_build_scanner_preexec(config),
    )

    full_output = _collect_scanner_output(proc)
    ret = proc.wait()
    _raise_scanner_failure(ret, full_output)

    return ret


def limited_sonar_scan(
    tmp_dir: str,
    project_key: str,
    exclusions: Optional[str] = None,
    inclusions: Optional[str] = None,
    custom_cache_dir: Optional[str] = None
) -> str:
    config = _get_sonar_config()
    cmd = _build_sonar_command(config, project_key, exclusions, inclusions, tmp_dir)
    
    # Pass custom_cache_dir ke process runner
    exit_code = _run_scanner_process(cmd, tmp_dir, config, custom_cache_dir=custom_cache_dir)

    sonar_url = f"{config['host_url']}/dashboard?id={project_key}"

    if exit_code == 2:
        logger.warning("🔴 Quality Gate FAILED (exit code 2) for %s", project_key)
        raise QualityGateFailed(sonar_url)

    logger.info("✅ Analysis successful for %s. Dashboard: %s", project_key, sonar_url)
    return sonar_url


def clone_and_scan(
    repo_url: str,
    branch_name: str,
    project_key: str,
    exclusions: Optional[str] = None,
    inclusions: Optional[str] = None,
    per_job_cache: bool = False
) -> str:
    tmp_dir = None
    job_cache_dir = None

    try:
        # --- THREAD SAFE LOGIC ---
        # Hitung path cache secara lokal, JANGAN ubah os.environ global.
        if per_job_cache:
            base_cache = os.getenv("SONAR_USER_HOME", "/cache")
            job_cache_dir = os.path.abspath(os.path.join(base_cache, project_key.replace("/", "_")))
            logger.debug("Using per-job cache path: %s", job_cache_dir)

        tmp_dir = limited_clone(repo_url, branch_name)
        
        # Kirim job_cache_dir ke fungsi scan
        return limited_sonar_scan(
            tmp_dir, 
            project_key, 
            exclusions=exclusions, 
            inclusions=inclusions,
            custom_cache_dir=job_cache_dir
        )
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            logger.debug("Removed temporary directory %s", tmp_dir)


@dataclass
class ScanJob:
    repo_url: str
    branch_name: str
    project_key: str
    exclusions: Optional[str] = None
    inclusions: Optional[str] = None
    per_job_cache: bool = True


class SonarScanQueue:
    def __init__(self, num_workers: int = 1):
        if num_workers < 1:
            raise ValueError("num_workers minimal 1")
        self._num_workers = num_workers
        self._q: "queue.Queue[Tuple[ScanJob, Future]]" = queue.Queue()
        self._threads: List[threading.Thread] = []
        self._stopping = threading.Event()

    def start(self) -> None:
        if self._threads:
            return
        for i in range(self._num_workers):
            t = threading.Thread(target=self._worker, name=f"sonar-worker-{i+1}", daemon=True)
            t.start()
            self._threads.append(t)
        logger.info("SonarScanQueue started with %d worker(s).", self._num_workers)

    def _worker(self) -> None:
        while not self._stopping.is_set():
            try:
                job, fut = self._q.get(timeout=0.5)
            except queue.Empty:
                continue

            if fut.set_running_or_notify_cancel():
                try:
                    url = clone_and_scan(
                        job.repo_url,
                        job.branch_name,
                        job.project_key,
                        job.exclusions,
                        job.inclusions,
                        per_job_cache=job.per_job_cache,
                    )
                    fut.set_result(url)
                except Exception as e:
                    fut.set_exception(e)
                finally:
                    self._q.task_done()

    def enqueue(
        self,
        repo_url: str,
        branch_name: str,
        project_key: str,
        exclusions: Optional[str] = None,
        inclusions: Optional[str] = None,
        per_job_cache: bool = True
    ) -> Future:
        fut: Future = Future()
        job = ScanJob(
            repo_url=repo_url,
            branch_name=branch_name,
            project_key=project_key,
            exclusions=exclusions,
            inclusions=inclusions,
            per_job_cache=per_job_cache,
        )
        self._q.put((job, fut))
        logger.info("Enqueued job project_key=%s branch=%s", project_key, branch_name)
        return fut

    def join(self) -> None:
        self._q.join()

    def stop(self) -> None:
        self._stopping.set()
        for t in self._threads:
            t.join(timeout=1.0)
        self._threads.clear()
        logger.info("SonarScanQueue stopped.")


if __name__ == "__main__":
    jobs = [
        ("https://github.com/org/repo-a.git", "main", "org_repo_a", None, None),
    ]

    # CONFIG: 1 Worker (Sequential Scan)
    queue_ = SonarScanQueue(num_workers=1)
    queue_.start()

    futures: List[Future] = []
    for repo_url, branch, key, exc, inc in jobs:
        f = queue_.enqueue(repo_url, branch, key, exc, inc, per_job_cache=True)
        futures.append(f)

    queue_.join()

    for i, fut in enumerate(futures, 1):
        try:
            url = fut.result()
            print(f"[{i}] SUCCESS -> {url}")
        except QualityGateFailed as qg:
            print(f"[{i}] QUALITY GATE FAILED -> {qg.url}")
        except Exception as e:
            print(f"[{i}] ERROR -> {e!r}")

    queue_.stop()
