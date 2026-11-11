import json
import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS patient(pid TEXT PRIMARY KEY, name TEXT, dob TEXT);
CREATE TABLE IF NOT EXISTS lab(
  pid TEXT, date TEXT, code TEXT, value REAL,
  ref_low REAL, ref_high REAL, source TEXT,
  PRIMARY KEY(pid, date, code));
CREATE TABLE IF NOT EXISTS checkin(
  pid TEXT, date TEXT, temp REAL, symptoms TEXT,
  PRIMARY KEY(pid, date));
"""


class Store:
    """RareGuard 时序数据写入层（家庭端本地/院内单机部署）。"""

    def __init__(self, path: str):
        # FastAPI TestClient/uvicorn 在工作线程执行请求，需跨线程共享连接
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_SCHEMA)

    def add_patient(self, pid, name, dob):
        self.conn.execute(
            "INSERT OR REPLACE INTO patient VALUES(?,?,?)", (pid, name, dob))
        self.conn.commit()

    def add_lab(self, pid, date, code, value, ref_low, ref_high, source="synth"):
        self.conn.execute(
            "INSERT OR REPLACE INTO lab VALUES(?,?,?,?,?,?,?)",
            (pid, date, code, value, ref_low, ref_high, source))
        self.conn.commit()

    def add_checkin(self, pid, date, temp, symptoms):
        self.conn.execute(
            "INSERT OR REPLACE INTO checkin VALUES(?,?,?,?)",
            (pid, date, temp, json.dumps(symptoms, ensure_ascii=False)))
        self.conn.commit()

    def rows(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def close(self):
        self.conn.close()
