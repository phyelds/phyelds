"""Tests for compiling and loading the native C extension."""

from pathlib import Path
import shutil
import sys

import pytest

from phyelds.accel import build as accel_build


def test_build_extension_compiles_into_explicit_directory(tmp_path: Path):
    binary = accel_build.build_extension(tmp_path)

    assert binary.is_file()
    assert binary.parent == tmp_path.resolve()


def test_build_main_prints_compiled_path(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["phyelds.accel.build", "--build-dir", str(tmp_path)])

    accel_build.main()

    printed = Path(capsys.readouterr().out.strip())
    assert printed.is_file()


def test_compiler_command_falls_back_or_raises_when_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CC", "nonexistent-cc-binary")
    cmd = accel_build._compiler_command(tmp_path / "a.c", tmp_path / "a.so")  # pylint: disable=protected-access
    assert Path(cmd[0]).name in {"gcc", "clang", "cc"}

    monkeypatch.setattr(shutil, "which", lambda _name: None)
    with pytest.raises(FileNotFoundError, match="no C compiler"):
        accel_build._compiler_command(tmp_path / "a.c", tmp_path / "a.so")  # pylint: disable=protected-access


def test_build_extension_reports_missing_headers_and_compiler_errors(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(accel_build.sysconfig, "get_path", lambda _key: str(tmp_path))
    with pytest.raises(FileNotFoundError, match="Python development headers"):
        accel_build.build_extension(tmp_path)


def test_build_extension_surfaces_compiler_failure(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CC", "false")
    with pytest.raises(RuntimeError, match="failed to compile"):
        accel_build.build_extension(tmp_path)
