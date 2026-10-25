## [8.8.4](https://github.com/phyelds/phyelds/compare/8.8.3...8.8.4) (2026-10-25)

### Documentation

* a larger p in the wordmark ([24dc87c](https://github.com/phyelds/phyelds/commit/24dc87ce9ac8f984a0144bb8bab32892935b4548))

## [8.8.3](https://github.com/phyelds/phyelds/compare/8.8.2...8.8.3) (2026-10-25)

### Documentation

* show the wordmark in the header of the site ([7ac1b73](https://github.com/phyelds/phyelds/commit/7ac1b7317a975400254bdf4b8298eca539118b9a))

### Revert previous changes

* restore the original p of the logo ([2300c6f](https://github.com/phyelds/phyelds/commit/2300c6f844ffc67be279df226761ab8897b8de3d))

## [8.8.2](https://github.com/phyelds/phyelds/compare/8.8.1...8.8.2) (2026-10-25)

### Documentation

* a simpler, bolder p for the logo at small sizes ([886e0fe](https://github.com/phyelds/phyelds/commit/886e0fe609b3e57ead0ac04c74c128493db33ef2))

## [8.8.1](https://github.com/phyelds/phyelds/compare/8.8.0...8.8.1) (2026-10-25)

### Documentation

* use the svg logos and a wordmark with the network p ([435fe5f](https://github.com/phyelds/phyelds/commit/435fe5f2fceb2db523b3faa8f8891d6e1ce53829))

## [8.8.0](https://github.com/phyelds/phyelds/compare/8.7.0...8.8.0) (2026-10-20)

### Features

* **playground:** show the program, the network, or both ([#26](https://github.com/phyelds/phyelds/issues/26)) ([c7b2c35](https://github.com/phyelds/phyelds/commit/c7b2c35501eb3d9372cfe7395cf71b5c66cdffc5))

## [8.7.0](https://github.com/phyelds/phyelds/compare/8.6.0...8.7.0) (2026-10-20)

### Features

* **playground:** grouped, searchable examples and swarms that move ([#25](https://github.com/phyelds/phyelds/issues/25)) ([c0c1cd3](https://github.com/phyelds/phyelds/commit/c0c1cd3132f03ca182ccb88c5b9db338f7842510)), closes [#24](https://github.com/phyelds/phyelds/issues/24)

## [8.6.0](https://github.com/phyelds/phyelds/compare/8.5.0...8.6.0) (2026-10-20)

### Features

* **libraries:** typed sensors and actuators ([#23](https://github.com/phyelds/phyelds/issues/23)) ([4296e0a](https://github.com/phyelds/phyelds/commit/4296e0abca51fad9b971e9b004de0ca33f90154e))

## [8.5.0](https://github.com/phyelds/phyelds/compare/8.4.2...8.5.0) (2026-10-20)

### Features

* **experimental:** swarm movement and formations ([#21](https://github.com/phyelds/phyelds/issues/21)) ([324deea](https://github.com/phyelds/phyelds/commit/324deea0eed7af66cd2776c4cce9309a3494fa3a))

## [8.4.2](https://github.com/phyelds/phyelds/compare/8.4.1...8.4.2) (2026-10-20)

### Documentation

* improve explanation, better rendering for docs ([d105cd8](https://github.com/phyelds/phyelds/commit/d105cd8965f1f0107cfbdd2b250fb2ac865059a1))

## [8.4.1](https://github.com/phyelds/phyelds/compare/8.4.0...8.4.1) (2026-10-20)

### Documentation

* better visual for wlakthrough ([a08a52f](https://github.com/phyelds/phyelds/commit/a08a52fb6d8803d191cb364c05e9e68f7008314d))

## [8.4.0](https://github.com/phyelds/phyelds/compare/8.3.0...8.4.0) (2026-10-19)

### Features

* **simulator:** neighborhoods whose ranges adapt to the crowd ([#22](https://github.com/phyelds/phyelds/issues/22)) ([2e0ea04](https://github.com/phyelds/phyelds/commit/2e0ea046ce353b53b5315a82b76bdfdf8abc121b))

### Build and continuous integration

* **deps-dev:** bump handlebars from 4.7.8 to 4.7.10 ([#17](https://github.com/phyelds/phyelds/issues/17)) ([23d7b4b](https://github.com/phyelds/phyelds/commit/23d7b4be51be6bc66fe09f9a264022d5b748b199))
* fix the dependabot alerts and let dependabot check weekly ([#16](https://github.com/phyelds/phyelds/issues/16)) ([bd42ce0](https://github.com/phyelds/phyelds/commit/bd42ce0ebfca326c011365a86568542237a1c9c0))

## [8.3.0](https://github.com/phyelds/phyelds/compare/8.2.0...8.3.0) (2026-10-19)

### Features

* **experimental:** collective state machines ([#15](https://github.com/phyelds/phyelds/issues/15)) ([a501bc1](https://github.com/phyelds/phyelds/commit/a501bc182f6257b19c8b534915df78cf48ce07a1))

## [8.2.0](https://github.com/phyelds/phyelds/compare/8.1.0...8.2.0) (2026-10-19)

### Features

* run phyelds programs on Webots robots ([#14](https://github.com/phyelds/phyelds/issues/14)) ([dc0dffe](https://github.com/phyelds/phyelds/commit/dc0dffec72ce9d9cb5f1e81a8a378d192e3a5ce3))

## [8.1.0](https://github.com/phyelds/phyelds/compare/8.0.0...8.1.0) (2026-10-19)

### Features

* **mesa:** run phyelds programs on the agents of a Mesa model ([#13](https://github.com/phyelds/phyelds/issues/13)) ([39f031e](https://github.com/phyelds/phyelds/commit/39f031e9ac1c41da59a00389e01bf534b52c3c64))

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
