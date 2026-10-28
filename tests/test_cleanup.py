import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest


HELPER = Path(__file__).parents[1] / "installer" / "cleanup.py"
spec = importlib.util.spec_from_file_location("installer_cleanup", HELPER)
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)
RELEASE = "release-" + "a" * 32


def test_removes_only_managed_environment(tmp_path):
    environment = tmp_path / "envs" / RELEASE
    environment.mkdir(parents=True)
    (environment / "file.txt").write_text("managed")
    external = tmp_path / "study.txt"
    external.write_text("keep")
    unrelated = tmp_path / "envs" / "other-app"
    unrelated.mkdir()
    cleanup.remove_environment(str(tmp_path), RELEASE)
    cleanup.remove_environment(str(tmp_path), RELEASE)
    assert not environment.exists()
    assert external.read_text() == "keep"
    assert unrelated.is_dir()


@pytest.mark.parametrize("release", ["../study", "release-invalid", "", "release-" + "a" * 32 + "/child"])
def test_rejects_unmanaged_names(tmp_path, release):
    with pytest.raises(ValueError, match="release identifier"):
        cleanup.remove_environment(str(tmp_path), release)


def test_rejects_root_and_relative_install_directory(tmp_path):
    for installation in ("relative-folder", str(Path(tmp_path.anchor))):
        with pytest.raises(ValueError):
            cleanup.remove_environment(installation, RELEASE)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows long paths and readonly files")
def test_removes_deep_readonly_tree(tmp_path):
    environment = tmp_path / "envs" / RELEASE
    deep = environment.joinpath(*(["deep-qt-directory"] * 18))
    os.makedirs(cleanup.extended_path(str(deep)))
    filename = cleanup.extended_path(str(deep / "QmlAssetDownloaderPrivateplugin_init.cpp.obj"))
    with open(filename, "w") as stream:
        stream.write("readonly object")
    os.chmod(filename, stat.S_IREAD)
    assert len(filename) > 260
    result = subprocess.run(
        [sys.executable, "-I", str(HELPER), "--install-directory", str(tmp_path), "--release-name", RELEASE],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not environment.exists()


def test_refuses_python_inside_target(tmp_path, monkeypatch):
    environment = tmp_path / "envs" / RELEASE
    environment.mkdir(parents=True)
    monkeypatch.setattr(sys, "executable", str(environment / "Scripts" / "python.exe"))
    with pytest.raises(ValueError, match="outside the environment"):
        cleanup.remove_environment(str(tmp_path), RELEASE)
    assert environment.is_dir()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junctions")
@pytest.mark.parametrize("location", ["installation", "envs", "release"])
def test_rejects_junction_ancestors(tmp_path, location):
    installation = tmp_path / "app"
    external = tmp_path / "external"
    external.mkdir()
    (external / "keep.txt").write_text("keep")
    link = {"installation": installation, "envs": installation / "envs", "release": installation / "envs" / RELEASE}[location]
    link.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(external)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    try:
        with pytest.raises(ValueError, match="links or junctions"):
            cleanup.remove_environment(str(installation), RELEASE)
        assert (external / "keep.txt").read_text() == "keep"
    finally:
        os.rmdir(link)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junctions")
def test_does_not_follow_nested_junction(tmp_path):
    environment = tmp_path / "envs" / RELEASE
    environment.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    (external / "keep.txt").write_text("keep")
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(environment / "link"), str(external)],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    cleanup.remove_environment(str(tmp_path), RELEASE)
    assert not environment.exists()
    assert (external / "keep.txt").read_text() == "keep"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows exclusive file locks")
def test_locked_file_failure_is_not_ignored(tmp_path):
    import ctypes
    from ctypes import wintypes

    environment = tmp_path / "envs" / RELEASE
    environment.mkdir(parents=True)
    locked = environment / "locked.bin"
    locked.write_bytes(b"locked")
    create_file = ctypes.windll.kernel32.CreateFileW
    create_file.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create_file.restype = wintypes.HANDLE
    close_handle = ctypes.windll.kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    handle = create_file(str(locked), 0x80000000, 0, None, 3, 0, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        with pytest.raises(PermissionError):
            cleanup.remove_environment(str(tmp_path), RELEASE)
        assert environment.is_dir()
    finally:
        close_handle(handle)
    cleanup.remove_environment(str(tmp_path), RELEASE)
    assert not environment.exists()