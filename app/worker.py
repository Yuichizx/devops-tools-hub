import threading
from queue import Queue
from .tasks import process_repository

task_queue = Queue()
task_statuses = {}

def worker():
    while True:
        task = task_queue.get()
        if task is None:
            break
        task_id, repo_url, branch_name, project_key = task
        try:
            process_repository(repo_url, branch_name, project_key, task_id)
        except Exception as e:
            task_statuses[task_id] = {
                "status": f"Failed: {str(e)}",
                "sonar_url": None,
                "repo_url": repo_url
            }
        finally:
            task_queue.task_done()

worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()