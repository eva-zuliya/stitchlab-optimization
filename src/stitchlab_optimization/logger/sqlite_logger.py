from .manager import LogManager, ModelLog
import sqlite3
import pandas as pd


class SQLiteLogManager(LogManager):
    db_path: str

    def __init__(self, db_path: str, is_monitor_optimality: bool = True, is_monitor_resource: bool = False):
        self.db_path = db_path
        self.is_monitor_optimality = is_monitor_optimality
        self.is_monitor_resource = is_monitor_resource
    
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            if self.is_monitor_optimality:
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self._dir_model_execution_log} (
                        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                        solver_engine      TEXT,            -- gurobi / ortools / routing
                        model_id           TEXT,
                        model_name         TEXT,
                        problem_size_vars  INTEGER,         -- number of decision variables
                        problem_size_cons  INTEGER,         -- number of constraints
                        optimality_gap     REAL,            -- % or absolute gap
                        objective_value    REAL,
                        status             TEXT,            -- START / DONE / ERROR
                        message            TEXT,            -- optional note
                        runtime_sec        REAL,            -- optional
                        created_at         TEXT
                    );
                """)

                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self._dir_workflow_execution_log} (
                        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id         TEXT,
                        model_ids          TEXT,      -- store list of str as JSON string
                        payload            TEXT,      -- store JSON payload as string
                        solver_parameter   TEXT,      -- store JSON solver parameter as string
                        message            TEXT,      -- store error message
                        start_timestamp    TEXT,      -- store start timestamp
                        end_timestamp      TEXT,      -- store end timestamp
                        runtime_sec        REAL
                    );
                """)

            if self.is_monitor_resource:
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self._dir_resource_occupation_log} (
                        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                        machine_id         TEXT,
                        model_id           TEXT,
                        cpu_percent        REAL,
                        num_cores          INTEGER,
                        limit_thread       INTEGER,
                        memory_mb          REAL,
                        limit_memory_mb    REAL,
                        timestamp          TEXT
                    );
                """)

            conn.commit()

    def put_model_log(self, model_log: ModelLog):
        """Insert a DataFrame into SQLite."""

        with sqlite3.connect(self.db_path) as conn:
            data = pd.DataFrame([model_log.to_sql_log()])
            data.to_sql(self._dir_model_execution_log, conn, if_exists="append", index=False)