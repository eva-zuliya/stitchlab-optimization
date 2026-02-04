import os
from dotenv import load_dotenv


class SolverConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            if cls._instance is None:
                load_dotenv()  # load .env
                cls._instance = super().__new__(cls)
                cls._instance._load_env()

        return cls._instance

    def _load_env(self):
        self.TRUE_THRESHOLD = float(os.getenv("TRUE_THRESHOLD", 0.5))
        self.APPLY_HEURISTICS = os.getenv("APPLY_HEURISTICS", "True").lower() in ("true", "1", "yes")
        self.MODEL_SOLVER_VERBOSE = os.getenv("MODEL_SOLVER_VERBOSE", "False").lower() in ("true", "1", "yes")

        self.LIMIT_TIME_MINUTES_HEURISTICS = float(os.getenv("LIMIT_TIME_MINUTES_HEURISTICS", 3))
        self.LIMIT_TIME_MINUTES_DETERMINISTIC = float(os.getenv("LIMIT_TIME_MINUTES_DETERMINISTIC", 3))
        self.LIMIT_OPTIMALITY_GAP_DETERMINISTIC = float(os.getenv("LIMIT_OPTIMALITY_GAP_DETERMINISTIC", 0.35))
        self.LIMIT_OPTIMALITY_GAP_HEURISTICS = float(os.getenv("LIMIT_OPTIMALITY_GAP_HEURISTICS", 0.75))
        self.LIMIT_MEMORY_MB = int(os.getenv("LIMIT_MEMORY_MB", 1024*8))
        self.LIMIT_MULTI_THREAD = int(os.getenv("LIMIT_MULTI_THREAD", 6))

        self.SOLVER_PARAMETER = {
            "limit_minutes_heuristics": self.LIMIT_TIME_MINUTES_HEURISTICS,
            "limit_minutes_deterministic": self.LIMIT_TIME_MINUTES_DETERMINISTIC,
            "limit_optimality_gap_deterministic": self.LIMIT_OPTIMALITY_GAP_DETERMINISTIC,
            "limit_optimality_gap_heuristics": self.LIMIT_OPTIMALITY_GAP_HEURISTICS,
            "limit_memory_mb": self.LIMIT_MEMORY_MB,
            "limit_multi_thread": self.LIMIT_MULTI_THREAD,
            "apply_heuristics": self.APPLY_HEURISTICS,
        }

        self.MONITOR_EXECUTION = os.getenv("MONITOR_EXECUTION", "False").lower() in ("true", "1", "yes")
        self.MONITOR_RESOURCE = os.getenv("MONITOR_RESOURCE", "False").lower() in ("true", "1", "yes")
        self.MONITOR_RESOURCE_INTERVAL_SECONDS = int(os.getenv("MONITOR_RESOURCE_INTERVAL_SECONDS", 60))

        self.SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "log.sqlite")
        self.EXPORT_DIRECTORY = os.getenv("EXPORT_DIRECTORY", "export")

        self._load_gurobi_credentials()

    
    def _load_gurobi_credentials(self):
        self.GUROBI_ENV = None

        GUROBI_KEYS = {
            "WLSAccessID": os.getenv("WLSACCESSID", None),
            "WLSSecret": os.getenv("WLSSECRET", None),
            "LicenseID": int(os.getenv("LICENSEID", 0)),
        }

        if GUROBI_KEYS["WLSAccessID"] is not None and GUROBI_KEYS["WLSSecret"] is not None:
            import gurobipy as gp

            self.GUROBI_ENV = gp.Env(params=GUROBI_KEYS)

