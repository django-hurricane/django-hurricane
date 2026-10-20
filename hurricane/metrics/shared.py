import os
import struct
import threading
from multiprocessing import shared_memory
from typing import Optional

_SHM_LOCK = threading.Lock()
_SHM_INSTANCE: Optional[shared_memory.SharedMemory] = None

# Offsets in shared memory buffer:
# 0..8:   uint64  requests_count
# 8..16:  double  response_time_sum
# 16..24: uint64  response_time_count
# 24..32: double  startup_time
# 32..40: int64   queue_length
# 40..48: int64   health (1=True, 0=False, -1=Unset)
# 48..56: int64   readiness (1=True, 0=False, -1=Unset)
# 56..64: int64   active_requests
SHM_SIZE = 72


def _get_shm_name() -> str:
    name = os.environ.get("HURRICANE_SHM_NAME")
    if not name:
        name = f"hurricane_shm_{os.getpid()}"
        os.environ["HURRICANE_SHM_NAME"] = name
    return name


def cleanup_shm():
    global _SHM_INSTANCE
    if _SHM_INSTANCE is not None:
        try:
            _SHM_INSTANCE.close()
            _SHM_INSTANCE.unlink()
        except Exception:
            pass
        _SHM_INSTANCE = None


def _get_shm() -> Optional[shared_memory.SharedMemory]:
    global _SHM_INSTANCE
    if _SHM_INSTANCE is not None:
        try:
            if _SHM_INSTANCE.buf is not None and len(_SHM_INSTANCE.buf) >= SHM_SIZE:
                return _SHM_INSTANCE
        except Exception:
            _SHM_INSTANCE = None

    shm_name = _get_shm_name()
    try:
        _SHM_INSTANCE = shared_memory.SharedMemory(name=shm_name, create=True, size=SHM_SIZE)
        if _SHM_INSTANCE.buf is not None:
            struct.pack_into("QdQdqqqq", _SHM_INSTANCE.buf, 0, 0, 0.0, 0, 0.0, 0, -1, -1, 0)
    except FileExistsError:
        try:
            _SHM_INSTANCE = shared_memory.SharedMemory(name=shm_name, create=False, size=SHM_SIZE)
        except Exception:
            return None
    except Exception:
        return None
    return _SHM_INSTANCE


class SharedMetrics:
    @classmethod
    def track_request_start(cls, max_threads: int) -> int:
        shm = _get_shm()
        if not shm or shm.buf is None:
            return 0
        buf = shm.buf
        with _SHM_LOCK:
            active = struct.unpack_from("q", buf, 56)[0] + 1
            struct.pack_into("q", buf, 56, active)
            backlog = max(0, active - max_threads + 1) if active >= max_threads else 0
            struct.pack_into("q", buf, 32, backlog)
            return backlog

    @classmethod
    def track_request_end(cls, max_threads: int) -> int:
        shm = _get_shm()
        if not shm or shm.buf is None:
            return 0
        buf = shm.buf
        with _SHM_LOCK:
            active = max(0, struct.unpack_from("q", buf, 56)[0] - 1)
            struct.pack_into("q", buf, 56, active)
            backlog = max(0, active - max_threads + 1) if active >= max_threads else 0
            struct.pack_into("q", buf, 32, backlog)
            return backlog

    @classmethod
    def increment_requests(cls) -> int:
        shm = _get_shm()
        if not shm or shm.buf is None:
            return 1
        buf = shm.buf
        with _SHM_LOCK:
            val = struct.unpack_from("Q", buf, 0)[0] + 1
            struct.pack_into("Q", buf, 0, val)
            return val

    @classmethod
    def get_requests(cls) -> int:
        shm = _get_shm()
        if not shm or shm.buf is None:
            return 0
        buf = shm.buf
        with _SHM_LOCK:
            return struct.unpack_from("Q", buf, 0)[0]

    @classmethod
    def add_response_time(cls, elapsed_ms: float) -> float:
        shm = _get_shm()
        if not shm or shm.buf is None:
            return elapsed_ms
        buf = shm.buf
        with _SHM_LOCK:
            cur_sum, cur_cnt = struct.unpack_from("dQ", buf, 8)
            new_sum = cur_sum + elapsed_ms
            new_cnt = cur_cnt + 1
            struct.pack_into("dQ", buf, 8, new_sum, new_cnt)
            return new_sum / new_cnt

    @classmethod
    def get_average_response_time(cls) -> float:
        shm = _get_shm()
        if not shm or shm.buf is None:
            return 0.0
        buf = shm.buf
        with _SHM_LOCK:
            cur_sum, cur_cnt = struct.unpack_from("dQ", buf, 8)
            if cur_cnt == 0:
                return 0.0
            return cur_sum / cur_cnt

    @classmethod
    def set_startup_time(cls, time_elapsed: float):
        shm = _get_shm()
        if not shm or shm.buf is None:
            return
        buf = shm.buf
        with _SHM_LOCK:
            struct.pack_into("d", buf, 24, float(time_elapsed))

    @classmethod
    def get_startup_time(cls) -> Optional[float]:
        shm = _get_shm()
        if not shm or shm.buf is None:
            return None
        buf = shm.buf
        with _SHM_LOCK:
            val = struct.unpack_from("d", buf, 24)[0]
            return val if val > 0.0 else None

    @classmethod
    def set_queue_length(cls, length: int):
        shm = _get_shm()
        if not shm or shm.buf is None:
            return
        buf = shm.buf
        with _SHM_LOCK:
            struct.pack_into("q", buf, 32, int(length))

    @classmethod
    def get_queue_length(cls) -> int:
        shm = _get_shm()
        if not shm or shm.buf is None:
            return 0
        buf = shm.buf
        with _SHM_LOCK:
            return struct.unpack_from("q", buf, 32)[0]

    @classmethod
    def set_health(cls, health: bool):
        shm = _get_shm()
        if not shm or shm.buf is None:
            return
        buf = shm.buf
        with _SHM_LOCK:
            struct.pack_into("q", buf, 40, 1 if health else 0)

    @classmethod
    def get_health(cls) -> Optional[bool]:
        shm = _get_shm()
        if not shm or shm.buf is None:
            return None
        buf = shm.buf
        with _SHM_LOCK:
            val = struct.unpack_from("q", buf, 40)[0]
            if val == -1:
                return None
            return bool(val)

    @classmethod
    def set_readiness(cls, readiness: bool):
        shm = _get_shm()
        if not shm or shm.buf is None:
            return
        buf = shm.buf
        with _SHM_LOCK:
            struct.pack_into("q", buf, 48, 1 if readiness else 0)

    @classmethod
    def get_readiness(cls) -> Optional[bool]:
        shm = _get_shm()
        if not shm or shm.buf is None:
            return None
        buf = shm.buf
        with _SHM_LOCK:
            val = struct.unpack_from("q", buf, 48)[0]
            if val == -1:
                return None
            return bool(val)
