"""Operator tools for the Celery queues (``manage.py celery_queues``)."""

from __future__ import annotations

from django.core.cache import cache

from app.queue_health import priority_keys
from app.queues import FAST_TASKS, QUEUES

# Runs atomically inside Redis, so workers and beat can't interleave. Keys
# come in the order workers drain them; within a list workers pop from the
# right, so the copy that would run first is the one kept. About 2.5s for
# 15k messages on Redis 6; Redis answers BUSY to other clients after 5s.
DEDUPE_LUA = """
local dry = ARGV[1] == "1"
local allowed = {}
for i = 2, #ARGV do allowed[ARGV[i]] = true end
local seen, removed = {}, {}
for _, key in ipairs(KEYS) do
  local items = redis.call("LRANGE", key, 0, -1)
  local keep, dropped = {}, 0
  for i = #items, 1, -1 do
    local ok, msg = pcall(cjson.decode, items[i])
    local h = ok and type(msg) == "table" and msg.headers or nil
    local task = h and h.task
    if type(task) == "string" and allowed[task] then
      local sig = task .. "|" .. tostring(h.argsrepr) .. "|"
        .. tostring(h.kwargsrepr)
      if seen[sig] then
        dropped = dropped + 1
        removed[task] = (removed[task] or 0) + 1
      else
        seen[sig] = true
        keep[i] = true
      end
    else
      keep[i] = true
    end
  end
  if dropped > 0 and not dry then
    local kept = {}
    for i = 1, #items do
      if keep[i] then kept[#kept + 1] = items[i] end
    end
    redis.call("DEL", key)
    for i = 1, #kept, 1000 do
      redis.call("RPUSH", key, unpack(kept, i, math.min(i + 999, #kept)))
    end
  end
end
local out = {}
for task, n in pairs(removed) do
  out[#out + 1] = task
  out[#out + 1] = n
end
return out
"""


def dedupable_task_names(registry) -> list[str]:
    """Tasks whose queued duplicates may be dropped: every task that
    dedupes at queue time, except the fast lane (one-off sends)."""
    return sorted(
        name
        for name, task in registry.items()
        if getattr(task, "dedupe", False) and name not in FAST_TASKS
    )


def dedupe_queued_messages(client, task_names, apply: bool) -> dict[str, int]:
    """Remove queued duplicates, keeping the copy that would run first.
    Returns removed counts per task.

    Copies match on Celery's ``argsrepr``/``kwargsrepr`` headers, so
    ``delay(1)`` and a ``send_task`` with ``args=[1]`` (``(1,)`` vs ``[1]``)
    count as different calls."""
    keys = [key for queue in QUEUES for key in priority_keys(queue)]
    out = client.eval(
        DEDUPE_LUA,
        len(keys),
        *keys,
        "0" if apply else "1",
        *task_names,
    )
    removed = {}
    for name, count in zip(out[::2], out[1::2]):
        name = name.decode() if isinstance(name, bytes) else name
        removed[name] = int(count)
    return removed


def clear_queued_locks(task_name: str | None = None) -> int:
    """Delete AppTask "already queued" locks, e.g. after purging a queue,
    so the purged calls can be queued again right away."""
    delete_pattern = getattr(cache, "delete_pattern", None)
    if delete_pattern is None:
        raise RuntimeError("The cache backend can't delete by pattern")
    pattern = f"task-queued:{task_name}:*" if task_name else "task-queued:*"
    return delete_pattern(pattern)
