"""
Cache local para respostas de APIs abertas.
Evita requisições repetidas e respeita limites das APIs.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


class SkillCache:
    def __init__(self, cache_dir: str, ttl_hours: int = 24) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_hours * 3600

    def _key(self, skill: str, params: dict) -> str:
        raw = f"{skill}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _path(self, skill: str, params: dict) -> Path:
        key = self._key(skill, params)
        subdir = self.cache_dir / skill
        subdir.mkdir(exist_ok=True)
        return subdir / f"{key}.json"

    def get(self, skill: str, params: dict) -> list[dict] | None:
        path = self._path(skill, params)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        age = time.time() - data["cached_at"]
        if age > self.ttl_seconds:
            return None
        return data["result"]

    def set(self, skill: str, params: dict, result: list[dict]) -> None:
        path = self._path(skill, params)
        path.write_text(
            json.dumps(
                {"cached_at": time.time(), "skill": skill, "params": params, "result": result},
                ensure_ascii=False,
                indent=2,
            )
        )

    def invalidate(self, skill: str) -> int:
        subdir = self.cache_dir / skill
        if not subdir.exists():
            return 0
        count = 0
        for f in subdir.glob("*.json"):
            f.unlink()
            count += 1
        return count
