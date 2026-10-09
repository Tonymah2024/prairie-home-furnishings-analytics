"""Tiny helper for named SQL queries stored in sql/*.sql files ("-- name: query_name" headers)."""
import re
import sqlite3
from functools import lru_cache

import pandas as pd

from src.config import DB_PATH, SQL_DIR


@lru_cache(maxsize=None)
def load_queries(filename: str) -> dict:
    text = (SQL_DIR / filename).read_text()
    parts = re.split(r"^--\s*name:\s*(\S+)\s*$", text, flags=re.M)
    return {parts[i]: parts[i + 1].strip().rstrip(";") for i in range(1, len(parts), 2)}


def connect(path=DB_PATH):
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def query(name: str, filename: str = "analysis_queries.sql", params=None, con=None) -> pd.DataFrame:
    sql = load_queries(filename)[name]
    own = con is None
    con = con or connect()
    try:
        return pd.read_sql_query(sql, con, params=params or {})
    finally:
        if own:
            con.close()
