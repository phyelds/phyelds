## [8.0.0](https://github.com/phyelds/phyelds/compare/7.7.0...8.0.0) (2026-10-19)

### ⚠ BREAKING CHANGES

* `pip install phyelds` no longer installs the
simulator. Install `phyelds-simulator` (or
`phyelds-simulator[jupyter]`, which replaces `phyelds[jupyter]`); it
brings a compatible phyelds, and `phyelds.simulator` imports as before.

* ci: lint, build and release phyelds-simulator with the core

The simulator is linted and its distribution built in CI, as when it
was part of src. semantic-release gives it the version of the core,
writes its changelog, and publishes it after the core and before
phyelds-vmas, which depends on it.

* docs: install the simulator from phyelds-simulator

The installation instructions point to phyelds-simulator, which brings
phyelds with it, for whoever wants to simulate, and to phyelds alone
for the core; the jupyter extra is now the simulator's. The simulator
is no longer called bundled, and CLAUDE.md describes the new layout and
the lint command of CI.

* refactor(micropython): drop what the simulator split left unused

The MicroPython build excluded the simulator from the copy of
phyelds, and redirected pkgutil to a stand-in: the core no longer has
a simulator, and declares its namespace with __import__("pkgutil") in a
try block, which needs no stand-in. Both go. The check that the core
does not load the simulator's dependencies now covers the codec too.

* test: cover the phyelds namespace, with and without pkgutil

The package extends its path to the simulator and the other packages
of the namespace, and stays a plain package where pkgutil is missing,
as on MicroPython: that branch was never run on CPython.

* ci: measure coverage by folder, the simulator included

Coverage of the phyelds package does not follow the namespace into
packages/phyelds-simulator for modules that no test imports, so the
simulator's actions and exporter dropped out of the report instead of
counting as uncovered. Coverage is now measured on the source folders
of the core and of the simulator.

### Features

* move the simulator to the phyelds-simulator package ([#12](https://github.com/phyelds/phyelds/issues/12)) ([53cae73](https://github.com/phyelds/phyelds/commit/53cae73655ba511e0bd512229b30ea5d8255d63f))
