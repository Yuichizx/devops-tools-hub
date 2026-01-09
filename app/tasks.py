# app/utils/task.py

import threading
import queue
import uuid
import logging
import os
import traceback
from datetime import datetime
from typing import Optional, Dict, Any

from app.utils.git_sonar import clone_and_scan, QualityGateFailed
from app.utils.screenshot_service import take_sonar_screenshot
from app.config import Config

logger = logging.getLogger(__name__)

# Konfigurasi Batas Riwayat Task (Mencegah Memory Leak)
MAX_TASK_HISTORY = 100 

# Status task di-memory
task_statuses: Dict[str, Dict[str, Any]] = {}

# Antrian job
task_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()

# Worker management
_worker_started = False
_worker_lock = threading.Lock()
# Ambil dari Config
_num_workers = int(os.getenv("WORKER_CONCURRENCY", "1"))

# Area screenshot default (px)
DEFAULT_CLIP_RECT = {
    "x": 200,
    "y": 100,
    "width": 1500,
    "height": 840,
}

def _cleanup_old_tasks():
    """
    Menghapus task lama jika jumlah task di memori melebihi MAX_TASK_HISTORY.
    Python 3.7+ dictionary itu ordered, jadi yang pertama masuk = yang pertama dihapus.
    """
    if len(task_statuses) > MAX_TASK_HISTORY:
        # Hitung berapa yang harus dibuang
        excess = len(task_statuses) - MAX_TASK_HISTORY
        keys_to_remove = list(task_statuses.keys())[:excess]
        for k in keys_to_remove:
            del task_statuses[k]
        logger.debug(f"Cleaned up {len(keys_to_remove)} old tasks from memory.")

def _process_job(job: Dict[str, Any]) -> None:
    task_id: str = job["task_id"]
    repo_url: str = job["repo_url"]
    branch_name: str = job["branch_name"]
    project_key: str = job["project_key"]
    exclusions: Optional[str] = job.get("exclusions") or ""
    inclusions: Optional[str] = job.get("inclusions") or ""
    clip_rect: Dict[str, int] = job.get("clip_rect") or DEFAULT_CLIP_RECT

    logger.info(f"--- WORKER START: task={task_id} proj={project_key} branch={branch_name} ---")
    
    # Update status awal
    task_statuses[task_id]["status"] = "Running"
    
    sonar_url = None
    final_status = "Completed" # Default jika sukses
    error_msg = None

    try:
        # 1. Jalankan Scan
        # per_job_cache=True wajib agar aman jika nanti multi-worker
        sonar_url = clone_and_scan(
            repo_url, branch_name, project_key,
            exclusions=exclusions, inclusions=inclusions,
            per_job_cache=True
        )

    except QualityGateFailed as qgf:
        # Scan sukses tapi tidak lolos standar kualitas
        # Kita tetap punya URL dashboard untuk di-screenshot
        sonar_url = qgf.url
        final_status = "Failed: Quality Gate"
        error_msg = "Quality Gate Failed. Please check the SonarQube dashboard."
        logger.warning(f"Task {task_id} Quality Gate Failed.")

    except Exception as e:
        # Error fatal (git error, koneksi putus, scanner crash)
        tb = traceback.format_exc()
        logger.error(f"--- WORKER ERROR: task={task_id} ---\n{tb}")
        task_statuses[task_id]["status"] = "Failed: An error occurred"
        task_statuses[task_id]["log"] = f"Error: {str(e)}\n\n{tb}"
        return # STOP di sini, tidak bisa screenshot

    # 2. Jalankan Screenshot (Hanya jika kita punya sonar_url)
    if sonar_url:
        try:
            task_statuses[task_id]["sonar_url"] = sonar_url
            task_statuses[task_id]["status"] = "Generating Screenshot"
            
            # Jika Quality Gate gagal, simpan pesan lognya
            if error_msg:
                task_statuses[task_id]["log"] = error_msg

            screenshot_info = take_sonar_screenshot(project_key, clip_rect=clip_rect)
            task_statuses[task_id]["screenshot_info"] = screenshot_info
            
            # Set status akhir (Completed atau Failed: Quality Gate)
            task_statuses[task_id]["status"] = final_status
            logger.info(f"--- WORKER DONE: task={task_id} status={final_status} ---")
            
        except Exception as e:
            tb = traceback.format_exc()
            logger.error(f"--- SCREENSHOT ERROR: task={task_id} ---\n{tb}")
            task_statuses[task_id]["status"] = "Failed: Screenshot Error"
            task_statuses[task_id]["log"] = f"Scan success but screenshot failed: {str(e)}\n\n{tb}"


def _worker_loop() -> None:
    while True:
        job = task_queue.get()  # blocking wait
        try:
            _process_job(job)
        finally:
            task_queue.task_done()


def _ensure_workers_started() -> None:
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        for i in range(_num_workers):
            t = threading.Thread(target=_worker_loop, name=f"task-worker-{i+1}", daemon=True)
            t.start()
        _worker_started = True
        logger.info("Task queue workers started: %d worker(s).", _num_workers)


def create_task(
    repo_url: str,
    branch_name: str,
    project_key: str,
    exclusions: str = "",
    inclusions: str = "",
    clip_rect: Dict[str, int] = None,
) -> str:
    """
    Enqueue task ke antrian (FIFO).
    """
    _ensure_workers_started()
    
    # BERSIHKAN MEMORY DULU SEBELUM NAMBAH TASK BARU
    _cleanup_old_tasks()

    task_id = str(uuid.uuid4())
    
    # Struktur data status awal
    task_statuses[task_id] = {
        "task_id": task_id,
        "created_at": datetime.now().isoformat(),
        "status": "Queued",
        "repo_url": repo_url,
        "branch_name": branch_name,
        "project_key": project_key,
        "sonar_url": None,
        "screenshot_info": None,
        "log": None,
    }

    job = {
        "task_id": task_id,
        "repo_url": repo_url,
        "branch_name": branch_name,
        "project_key": project_key,
        "exclusions": exclusions,
        "inclusions": inclusions,
        "clip_rect": clip_rect or DEFAULT_CLIP_RECT,
    }

    task_queue.put(job)
    logger.info(f"Task {task_id} enqueued: repo={repo_url} branch={branch_name}")
    return task_id