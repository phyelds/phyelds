## [9.0.0](https://github.com/phyelds/phyelds/compare/8.13.1...9.0.0) (2026-10-30)

### ⚠ BREAKING CHANGES

* **vm:** compact keys are hashed otherwise, in small integers: devices in compact mode must all run this version or later.

### Features

* **vm:** encode alignment paths as the program enters them ([#51](https://github.com/phyelds/phyelds/issues/51)) ([d12c24a](https://github.com/phyelds/phyelds/commit/d12c24a739af5fa929d85fe4e5360ddf60e7c64b)), closes [#50](https://github.com/phyelds/phyelds/issues/50) [#50](https://github.com/phyelds/phyelds/issues/50) [#50](https://github.com/phyelds/phyelds/issues/50) [#50](https://github.com/phyelds/phyelds/issues/50) [#50](https://github.com/phyelds/phyelds/issues/50)

## [8.13.1](https://github.com/phyelds/phyelds/compare/8.13.0...8.13.1) (2026-10-26)

### Bug Fixes

* **argos:** remove time, which local_time already reads ([#46](https://github.com/phyelds/phyelds/issues/46)) ([8ff9609](https://github.com/phyelds/phyelds/commit/8ff9609fe834466df4dd53bcf102e391c082821c)), closes [#34](https://github.com/phyelds/phyelds/issues/34) [#34](https://github.com/phyelds/phyelds/issues/34) [#34](https://github.com/phyelds/phyelds/issues/34)

## [8.13.0](https://github.com/phyelds/phyelds/compare/8.12.0...8.13.0) (2026-10-26)

### Features

* **webots:** run and test the controller on every wheeled robot of webots ([#45](https://github.com/phyelds/phyelds/issues/45)) ([3b9c3bd](https://github.com/phyelds/phyelds/commit/3b9c3bd0f110a903494be4545111914b6363f33b))

## [8.12.0](https://github.com/phyelds/phyelds/compare/8.11.1...8.12.0) (2026-10-26)

### Features

* **webots:** one controller for any robot, with the sensors and actuators of argos ([#44](https://github.com/phyelds/phyelds/issues/44)) ([0cb6876](https://github.com/phyelds/phyelds/commit/0cb6876b03831763aa2b7cee43e1d7c141efef4c)), closes [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33) [#33](https://github.com/phyelds/phyelds/issues/33)

## [8.11.1](https://github.com/phyelds/phyelds/compare/8.11.0...8.11.1) (2026-10-26)

### Documentation

* ask to check and close related issues ([0679623](https://github.com/phyelds/phyelds/commit/06796236684026cff908adb535905eb0b8483e58))
* drop the body from commit messages ([128e7d8](https://github.com/phyelds/phyelds/commit/128e7d853621f52917f0b1f8bb4b5c5df1eed13d))

## [8.11.0](https://github.com/phyelds/phyelds/compare/8.10.0...8.11.0) (2026-10-25)

### Features

* **vmas:** share typed sensors and actions with programs ([ef264e7](https://github.com/phyelds/phyelds/commit/ef264e70a2195b2bbf1eab03f5c344b8e7922b62))

### Bug Fixes

* **vmas:** keep sensor types stable and select environment zero ([b19e58a](https://github.com/phyelds/phyelds/commit/b19e58ab552d1e7df82e9388b201706f913b2a51))
* **vmas:** name the node when an action is missing ([6c40762](https://github.com/phyelds/phyelds/commit/6c407626feab4bfa920bdca0725e28b0052d1419))

### Refactoring

* **vmas:** document and annotate the sensor adapter ([518e618](https://github.com/phyelds/phyelds/commit/518e61802cca03709a260e8e75ad5b9461c03f09))

## [8.10.0](https://github.com/phyelds/phyelds/compare/8.9.1...8.10.0) (2026-10-25)

### Features

* **argos:** name the sensors and actuators of the robots once ([#31](https://github.com/phyelds/phyelds/issues/31)) ([f686fa2](https://github.com/phyelds/phyelds/commit/f686fa2146842950f59295be5c44a76747558e5e))

## [8.9.1](https://github.com/phyelds/phyelds/compare/8.9.0...8.9.1) (2026-10-25)

### Bug Fixes

* **argos:** reconfigure a build directory made from other sources ([#30](https://github.com/phyelds/phyelds/issues/30)) ([74867c3](https://github.com/phyelds/phyelds/commit/74867c353e973819ebef444fa942be79419bbd60))

## [8.9.0](https://github.com/phyelds/phyelds/compare/8.8.7...8.9.0) (2026-10-25)

### Features

* run phyelds programs on any ARGoS robot ([#29](https://github.com/phyelds/phyelds/issues/29)) ([6d5e8dc](https://github.com/phyelds/phyelds/commit/6d5e8dcd3b82524ef264df2c266df93b2dc4c625))
