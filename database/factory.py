"""
Retorna o DatabaseManager correto:
  - SUPABASE_URL definida → Supabase via HTTP (supabase-py)
  - DATABASE_URL definida → PostgreSQL direto (psycopg2)
  - nenhuma              → SQLite local
"""
from __future__ import annotations


def get_db(config=None):
    import os
    if os.environ.get("SUPABASE_URL"):
        from database.db_supabase import DatabaseManager
        return DatabaseManager()
    if (config and config.database_url) or os.environ.get("DATABASE_URL"):
        from database.db_postgres import DatabaseManager
        return DatabaseManager()
    from database.db import DatabaseManager
    return DatabaseManager(config.db_path if config else ":memory:")
