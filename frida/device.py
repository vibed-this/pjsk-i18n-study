"""Connect to Frida through adb-forwarded emulator."""

import subprocess
import time
from pathlib import Path

import frida

PACKAGE = "com.sega.pjsekai"
ADB_SERIAL = None  # auto-detect first online device
FRIDA_HOST = "127.0.0.1:27042"
FRIDA_PORT = 27042
SDK_ADB = r"D:\SDK\Android\platform-tools\adb.exe"


def _adb_bin() -> str:
    return SDK_ADB if Path(SDK_ADB).exists() else "adb"


def _detect_serial() -> str:
    if ADB_SERIAL:
        return ADB_SERIAL
    proc = subprocess.run(
        [_adb_bin(), "devices"],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in proc.stdout.splitlines()[1:]:
        if "\tdevice" in line:
            return line.split("\t")[0]
    raise RuntimeError("no adb device online")


def _adb(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    serial = _detect_serial()
    return subprocess.run(
        [_adb_bin(), "-s", serial, *args],
        capture_output=True,
        text=True,
        check=check,
    )


def wait_for_device(timeout: float = 60) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        proc = _adb("get-state")
        if proc.returncode == 0 and "device" in proc.stdout:
            return
        subprocess.run(["adb", "wait-for-device"], capture_output=True)
        time.sleep(1)
    raise RuntimeError(f"{ADB_SERIAL} not online after {timeout}s")


def ensure_adb_forward(port: int = FRIDA_PORT) -> None:
    wait_for_device()
    for _ in range(5):
        proc = _adb("forward", f"tcp:{port}", f"tcp:{port}")
        if proc.returncode == 0:
            return
        time.sleep(2)
        wait_for_device()
    raise RuntimeError(f"adb forward tcp:{port} failed: {proc.stderr.strip()}")


def get_device(host: str = FRIDA_HOST):
    ensure_adb_forward()
    manager = frida.get_device_manager()
    device_id = f"socket@{host}"
    for dev in manager.enumerate_devices():
        if dev.id == device_id:
            return dev
    return manager.add_remote_device(host)