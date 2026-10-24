"""Disk cache: one JSON file per normalized topic in data/cache/<slug>.json."""
import json
import re
from pathlib import Path

ALIASES = {
    "fridge": "refrigerators", "fridges": "refrigerators", "refrigerator": "refrigerators",
    "standing desk": "standing desks", "sit stand desk": "standing desks", "sit-stand desks": "standing desks",
    "e-bike": "e-bikes", "ebike": "e-bikes", "ebikes": "e-bikes", "electric bikes": "e-bikes", "electric bike": "e-bikes",
}


def normalize_topic(topic: str) -> str:
    t = re.sub(r"\s+", " ", (topic or "").strip().lower())
    return ALIASES.get(t, t)


def slugify(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize_topic(topic)).strip("-") or "topic"


class Cache:
    def __init__(self, cache_dir: Path):
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def path(self, topic):
        return self.dir / f"{slugify(topic)}.json"

    def get(self, topic):
        p = self.path(topic)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def put(self, topic, data):
        p = self.path(topic)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)
        return p

    def list(self):
        out = []
        for p in sorted(self.dir.glob("*.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                out.append({"topic": d["topic"], "slug": p.stem, "kept": d["stats"]["kept"],
                            "source": d.get("source"), "generated_at": d.get("generated_at")})
            except Exception:
                continue
        return out
