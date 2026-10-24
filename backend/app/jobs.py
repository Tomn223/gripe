"""In-process background jobs with stage progress (polled by the frontend)."""
import threading
import time
import uuid


class JobStore:
    def __init__(self):
        self.jobs, self.by_topic, self.lock = {}, {}, threading.Lock()

    def start(self, slug, fn):
        with self.lock:
            jid = self.by_topic.get(slug)
            if jid and self.jobs[jid]["status"] == "running":
                return self.jobs[jid]
            jid = uuid.uuid4().hex[:12]
            job = {"id": jid, "slug": slug, "status": "running", "stages": [], "error": None,
                   "started_at": time.time(), "finished_at": None}
            self.jobs[jid] = job
            self.by_topic[slug] = jid

        def progress(stages):
            job["stages"] = [dict(s) for s in stages]

        def target():
            try:
                fn(progress)
                job["status"] = "done"
            except Exception as e:  # surface a readable error to the UI
                job["status"] = "error"
                job["error"] = str(e)[:500]
            finally:
                job["finished_at"] = time.time()

        threading.Thread(target=target, daemon=True).start()
        return job

    def get(self, jid):
        return self.jobs.get(jid)
