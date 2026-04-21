"""Multiprocessing worker pool for asynchronous episode NLP tasks."""

from __future__ import annotations
import multiprocessing as mp
import queue
import threading
import uuid
from typing import Any

from .config import settings
from .logger import app_logger as logger

_LOCK = threading.Lock()
_VALID_START_METHODS = set(mp.get_all_start_methods())
_START_METHOD = settings.nlp_worker_start_method if settings.nlp_worker_start_method in _VALID_START_METHODS else "spawn"
if settings.nlp_worker_start_method not in _VALID_START_METHODS:
    logger.warning(
        "⚠️ 非法 NLP_WORKER_START_METHOD={}，已回退为 spawn（可选值：{}）",
        settings.nlp_worker_start_method,
        sorted(_VALID_START_METHODS),
    )
_CTX = mp.get_context(_START_METHOD)
_TASK_QUEUE: mp.Queue | None = None
_WORKERS: list[mp.Process] = []
_STARTED = False


def _nlp_worker(worker_id: int, task_queue: mp.Queue) -> None:
    """Worker loop that consumes queued NLP tasks and executes processing."""
    from .tasks import run_episode_nlp_analysis

    logger.info("👷 NLP 打工人 {} 已就绪，等待任务...", worker_id)
    while True:
        task = task_queue.get()
        if task is None:
            logger.warning("👷 NLP 打工人 {} 收到下班指令，正在退出...", worker_id)
            break

        season_id_raw = task.get("season_id")
        episode_raw = task.get("episode_number")
        if season_id_raw is None or episode_raw is None:
            logger.error("❌ NLP 任务缺少必要字段: {}", task)
            continue

        season_id = int(season_id_raw)
        episode_number = int(episode_raw)
        cid = task.get("cid")
        task_id = task.get("task_id")

        try:
            logger.info(
                "👷 NLP 打工人 {} 开始处理 task_id={} season_id={} episode={}",
                worker_id,
                task_id,
                season_id,
                episode_number,
            )
            run_episode_nlp_analysis(season_id=season_id, episode_number=episode_number, cid=cid)
            logger.success(
                "✅ NLP 打工人 {} 完成 task_id={} season_id={} episode={}",
                worker_id,
                task_id,
                season_id,
                episode_number,
            )
        except Exception as exc:
            logger.exception(
                "❌ NLP 打工人 {} 处理失败 task_id={} season_id={} episode={} error={}",
                worker_id,
                task_id,
                season_id,
                episode_number,
                exc,
            )


def start_nlp_worker_pool() -> None:
    """Start NLP worker processes and initialize the shared task queue once."""
    global _TASK_QUEUE, _STARTED, _WORKERS
    if not settings.nlp_worker_pool_enabled:
        logger.info("ℹ️ NLP 多进程任务池已禁用，任务将按回退策略执行")
        return

    with _LOCK:
        if _STARTED:
            return

        process_count = max(1, settings.nlp_worker_processes)
        _TASK_QUEUE = _CTX.Queue(maxsize=max(1, settings.nlp_worker_queue_maxsize))

        for i in range(process_count):
            worker = _CTX.Process(target=_nlp_worker, args=(i, _TASK_QUEUE), daemon=True)
            worker.start()
            _WORKERS.append(worker)
        _STARTED = True
        logger.info("✅ NLP 多进程任务池已启动 workers={} start_method={}", process_count, _START_METHOD)


def stop_nlp_worker_pool() -> None:
    """Gracefully stop NLP workers and release queue resources."""
    global _TASK_QUEUE, _STARTED, _WORKERS
    with _LOCK:
        if not _STARTED or _TASK_QUEUE is None:
            return

        for _ in _WORKERS:
            _TASK_QUEUE.put(None)
        for worker in _WORKERS:
            worker.join(timeout=settings.nlp_worker_shutdown_timeout)
            if worker.is_alive():
                logger.warning("⚠️ NLP 打工人 pid={} 超时未退出，强制终止", worker.pid)
                worker.terminate()
                worker.join(timeout=1)
        _WORKERS.clear()
        _TASK_QUEUE.close()
        _TASK_QUEUE.join_thread()
        _TASK_QUEUE = None
        _STARTED = False
        logger.info("✅ NLP 多进程任务池已停止")


def enqueue_nlp_task(season_id: int, episode_number: int, cid: str | None = None) -> str | None:
    """Enqueue an episode NLP task to multiprocessing queue.

    Args:
        season_id: Target season ID.
        episode_number: 1-based episode index in the season.
        cid: Optional episode cid for direct record binding.

    Returns:
        Generated task ID when enqueue succeeds, otherwise None.
    """
    if not settings.nlp_worker_pool_enabled:
        return None
    if not _STARTED or _TASK_QUEUE is None:
        logger.warning("⚠️ NLP 任务池未启动，无法入队")
        return None

    task_id = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "task_id": task_id,
        "season_id": season_id,
        "episode_number": episode_number,
        "cid": cid,
    }
    try:
        _TASK_QUEUE.put_nowait(payload)
        return task_id
    except queue.Full:
        logger.warning(
            "⚠️ NLP 任务队列已满，丢弃异步任务 task_id={} season_id={} episode={}；"
            "请考虑增大 NLP_WORKER_QUEUE_MAXSIZE 或提高 NLP_WORKER_PROCESSES",
            task_id,
            season_id,
            episode_number,
        )
        return None
