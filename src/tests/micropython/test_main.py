import sys

from phyelds.micropython.__main__ import main


def test_main_builds_the_programs_given_on_the_command_line(tmp_path, monkeypatch):
    program = tmp_path / "program.py"
    program.write_text("x: int = 1\n")
    monkeypatch.setattr(sys, "argv", ["phyelds.micropython", str(program), "-o", str(tmp_path / "dist")])

    main()

    assert (tmp_path / "dist" / "program.py").read_text().endswith("\nx = 1\n")
    assert (tmp_path / "dist" / "phyelds" / "__init__.py").exists()


def test_main_includes_the_modules_given_by_name(tmp_path, monkeypatch):
    program = tmp_path / "program.py"
    program.write_text("x = 1\n")
    monkeypatch.setattr(sys, "argv", [
        "phyelds.micropython", str(program), "-o", str(tmp_path / "dist"),
        "--include", "phyelds.libraries.gossip", "--include", "phyelds.libraries.time",
    ])

    main()

    assert (tmp_path / "dist" / "phyelds" / "libraries" / "gossip.py").exists()
    assert (tmp_path / "dist" / "phyelds" / "libraries" / "time.py").exists()
