"""
Retorna o DatabaseManager correto:
  - DATABASE_URL definida → PostgreSQL (Supabase)
  - sem DATABASE_URL      → SQLite local
"""
from __future__ import annotations


def get_db(config=None):
    import os
    url = (config.database_url if config else None) or os.environ.get("DATABASE_URL", "")
    if url:
        from database.db_postgres import DatabaseManager
    else:
        from database.db import DatabaseManager
        return DatabaseManager(config.db_path if config else ":memory:")
    return DatabaseManager()
