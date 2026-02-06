import time, psutil # pyright: ignore[reportMissingModuleSource]
from datetime import datetime
import socket

# from config import (
#     MONITOR_RESOURCE_INTERVAL_SECONDS,
#     LIMIT_MEMORY_MB,
#     LIMIT_MULTI_THREAD
# )

def monitor_resources(exec_id: str, stop_event):
    pass
    # proc = psutil.Process()

    # while not stop_event.is_set():
    #     ts = time.time()
        
    #     cpu = proc.cpu_percent(interval=None)
    #     rss = proc.memory_info().rss / 1024**2
    #     num_cores = len(proc.cpu_affinity()) if hasattr(proc, "cpu_affinity") else psutil.cpu_count(logical=True)

    #     try:
    #         machine_id = socket.gethostname()
    #     except Exception:
    #         machine_id = None

    #     log = {
    #         "id": None,
    #         "machine_id": machine_id,
    #         "exec_id": exec_id,
    #         "cpu_percent": cpu,
    #         "num_cores": num_cores,
    #         "limit_thread": LIMIT_MULTI_THREAD,
    #         "memory_mb": rss,
    #         "limit_memory_mb": LIMIT_MEMORY_MB,
    #         "timestamp": datetime.utcfromtimestamp(ts).isoformat()
    #     }

    #     insert_to_sqlite(table_name="resource_log", data=log)

    #     time.sleep(MONITOR_RESOURCE_INTERVAL_SECONDS)
