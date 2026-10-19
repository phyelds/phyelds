import sys

from phyelds.micropython.__main__ import main


def test_main_builds_the_programs_given_on_the_command_line(tmp_path, monkeypatch):
    program = tmp_path / "program.py"
    program.write_text("x: int = 1\n")
    monkeypatch.setattr(sys, "argv", ["phyelds.micropython", str(program), "-o", str(tmp_path / "dist")])

    main()

    assert (tmp_path / "dist" / "program.py").read_text().endswith("\nx = 1\n")
    assert (tmp_path / "dist" / "phyelds" / "__init__.py").exists()
