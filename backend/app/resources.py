"""Process measurements and admission checks, not an allocator/RSS hard cap."""
import os
import shutil
import sys
from functools import lru_cache


@lru_cache(maxsize=1)
def windows_memory_api():
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [(name, ctypes.c_size_t) for name in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    call = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
    call.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    return ctypes, Counters, kernel.GetCurrentProcess(), call


def memory_bytes():
    if os.name == "nt":
        ctypes, counters_type, handle, call = windows_memory_api()
        counters = counters_type()
        counters.cb = ctypes.sizeof(counters)
        if not call(handle, ctypes.byref(counters), counters.cb):
            raise OSError(ctypes.get_last_error())
        return counters.WorkingSetSize, counters.PeakWorkingSetSize
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    if sys.platform.startswith("linux"):
        with open("/proc/self/statm", encoding="ascii") as stream:
            current = int(stream.read(256).split()[1]) * os.sysconf("SC_PAGE_SIZE")
        return current, peak
    return peak, peak  # Conservative admission on platforms lacking a current-RSS source.


def temporary_bytes(path):
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            if root.endswith("spill") or "spill" in root.split(os.sep) or name.endswith(".tmp"):
                total += (os.path.getsize(os.path.join(root, name)))
    return total


def check_resources(settings, path, pending_bytes=0):
    current, peak = memory_bytes()
    if current > settings.ingestion_memory_mb * 1024**2:
        raise MemoryError("configured ingestion process memory admission budget exceeded")
    if shutil.disk_usage(path).free < settings.ingestion_disk_reserve_bytes + pending_bytes:
        raise OSError("insufficient disk space for the next batch plus configured free-space reserve")
    if temporary_bytes(path) + pending_bytes > settings.ingestion_temp_bytes:
        raise OSError("configured temporary-disk budget exceeded")
    return peak
