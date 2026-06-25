from .manager import LogManager, ModelLog, WorkflowLog
import sqlite3
import pandas as pd


class SQLiteLogManager(LogManager):
    db_path: str

    def __init__(self, db_path: str, is_monitor_optimality: bool = True, is_monitor_runtime: bool = True, is_monitor_resource: bool = False):
        self.db_path = db_path
        self.is_monitor_optimality = is_monitor_optimality
        self.is_monitor_resource = is_monitor_resource
        self.is_monitor_runtime = is_monitor_runtime
    
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            if self.is_monitor_optimality:
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self._dir_model_execution_log} (
                        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                        solver_engine      TEXT,            -- gurobi / ortools / routing
                        solver_params      TEXT,            -- store JSON solver parameter as string
                        model_id           TEXT,
                        model_name         TEXT,
                        problem_size_vars  INTEGER,         -- number of decision variables
                        problem_size_cons  INTEGER,         -- number of constraints
                        optimality_gap     REAL,            -- % or absolute gap
                        objective_value    REAL,
                        status             TEXT,            -- START / DONE / ERROR
                        message            TEXT,            -- optional note
                        runtime_sec        REAL,            -- optional
                        resource_stats     TEXT,            -- store JSON resource stats as string
                        created_timestamp  TEXT
                    );
                """)

            if self.is_monitor_runtime:
                conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self._dir_workflow_execution_log} (
                        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                        workflow_id        TEXT,
                        workflow_name      TEXT,
                        model_ids          TEXT,      -- store list of str as JSON string
                        payload            TEXT,      -- store JSON payload as string
                        message            TEXT,      -- store error message
                        start_timestamp    TEXT,      -- store start timestamp
                        end_timestamp      TEXT,      -- store end timestamp
                        runtime_sec        REAL,
                        created_timestamp  TEXT
                    );
                """)

            conn.commit()

    def put_model_log(self, model_log: ModelLog):
        with sqlite3.connect(self.db_path) as conn:
            data = pd.DataFrame([model_log.to_sql_log()])
            data.to_sql(self._dir_model_execution_log, conn, if_exists="append", index=False)

    def put_workflow_log(self, workflow_log: WorkflowLog):
        with sqlite3.connect(self.db_path) as conn:
            data = pd.DataFrame([workflow_log.to_sql_log()])
            data.to_sql(self._dir_workflow_execution_log, conn, if_exists="append", index=False)