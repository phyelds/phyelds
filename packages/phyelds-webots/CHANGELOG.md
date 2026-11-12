## [10.0.4](https://github.com/phyelds/phyelds/compare/10.0.3...10.0.4) (2026-11-12)

### Performance improvements

* **vm:** speed up compact paths, engine rounds and sorted fields ([#84](https://github.com/phyelds/phyelds/issues/84)) ([35c4790](https://github.com/phyelds/phyelds/commit/35c479051ef11946c2d1a3e8958fce81c96077dc)), closes [#37](https://github.com/phyelds/phyelds/issues/37)

## [10.0.3](https://github.com/phyelds/phyelds/compare/10.0.2...10.0.3) (2026-11-12)

### Performance improvements

* **simulator:** index adaptive_range and k_nearest_neighbors ([#83](https://github.com/phyelds/phyelds/issues/83)) ([e0d9c09](https://github.com/phyelds/phyelds/commit/e0d9c09f2f7271621a06c556273280d64b2d4da3)), closes [#37](https://github.com/phyelds/phyelds/issues/37)

## [10.0.2](https://github.com/phyelds/phyelds/compare/10.0.1...10.0.2) (2026-11-12)

### Performance improvements

* **simulator:** write csv metrics with csv and drop pandas ([#82](https://github.com/phyelds/phyelds/issues/82)) ([5f46457](https://github.com/phyelds/phyelds/commit/5f4645786b39e8b1ea0830eb89e5cc3f0c3a2371)), closes [#37](https://github.com/phyelds/phyelds/issues/37)

## [10.0.1](https://github.com/phyelds/phyelds/compare/10.0.0...10.0.1) (2026-11-10)

### Documentation

* **assets:** redraw the remember figure with the (value, update) order ([#81](https://github.com/phyelds/phyelds/issues/81)) ([db57167](https://github.com/phyelds/phyelds/commit/db571672bba2b4dd12dd6e6a964257e77437a365))

## [10.0.0](https://github.com/phyelds/phyelds/compare/9.5.2...10.0.0) (2026-11-10)

### ⚠ BREAKING CHANGES

* **calculus:** distance_to returns a float, not a State, with the default strategy
* **calculus:** gossip, gossip_max, gossip_min and any_node return the value, not a State, with the default, monotonic and time-replicated strategies
* **calculus:** exchange returns (local, field, send) instead of (set_field, field)

* feat(calculus)!: return plain values and update from remember
* **calculus:** remember returns (value, set_state) with a plain value instead of (set_state, State), and State is removed

* docs: update state, exchange and micropython documentation

* chore(deps): update poetry.lock after removing wrapt

* test(libraries): cover all past-ctl scopes and simplify ast unpack check

### Features

* **calculus:** return plain values from remember and (local, field, send) from exchange ([#79](https://github.com/phyelds/phyelds/issues/79)) ([ba00371](https://github.com/phyelds/phyelds/commit/ba003715ff03b0b0034be480dc37e9660b304837)), closes [#61](https://github.com/phyelds/phyelds/issues/61) [#61](https://github.com/phyelds/phyelds/issues/61) [#61](https://github.com/phyelds/phyelds/issues/61) [#61](https://github.com/phyelds/phyelds/issues/61) [#61](https://github.com/phyelds/phyelds/issues/61) [#61](https://github.com/phyelds/phyelds/issues/61) [#68](https://github.com/phyelds/phyelds/issues/68) [#75](https://github.com/phyelds/phyelds/issues/75) [#76](https://github.com/phyelds/phyelds/issues/76)
* **vm:** run synchronous and asynchronous rounds of many devices ([#66](https://github.com/phyelds/phyelds/issues/66)) ([e76de83](https://github.com/phyelds/phyelds/commit/e76de83cf736130ef2967df22a99c6b6720626b2)), closes [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37)

### Performance improvements

* **simulator:** find the neighbors within a radius through a uniform grid ([#67](https://github.com/phyelds/phyelds/issues/67)) ([232b149](https://github.com/phyelds/phyelds/commit/232b1497b04b96238b9807f0fa73c0fabfe0efc8)), closes [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37)

### Build and continuous integration

* auto-merge major dependabot updates too ([#73](https://github.com/phyelds/phyelds/issues/73)) ([47ea56c](https://github.com/phyelds/phyelds/commit/47ea56c758c768150c06efe67b2931ec5dd00088))
* **deps-dev:** bump the npm group across 1 directory with 2 updates ([#70](https://github.com/phyelds/phyelds/issues/70)) ([98c8a1e](https://github.com/phyelds/phyelds/commit/98c8a1e7fcc7df6e9d67f847624343f4bc623e40))
* **deps-dev:** bump virtualenv from 21.14.11 to 21.14.13 ([#27](https://github.com/phyelds/phyelds/issues/27)) ([feed209](https://github.com/phyelds/phyelds/commit/feed209fdb08bc5045b086fb0acaa4984dab4087))
* **deps:** bump the actions group across 1 directory with 8 updates ([#19](https://github.com/phyelds/phyelds/issues/19)) ([fc403e8](https://github.com/phyelds/phyelds/commit/fc403e8ec4ddfd114d93d45aa34b142cabe89610))
* merge dependabot updates automatically once the checks pass ([#72](https://github.com/phyelds/phyelds/issues/72)) ([8552a8a](https://github.com/phyelds/phyelds/commit/8552a8a26513b9d0d04259907f06dcb6cd4b75b5))
* use the release token for checkout credentials ([#80](https://github.com/phyelds/phyelds/issues/80)) ([3d5c7b0](https://github.com/phyelds/phyelds/commit/3d5c7b05d123a947a4cd60b6324ad93ecc9350db))

### Style improvements

* clean up useless comments ([#71](https://github.com/phyelds/phyelds/issues/71)) ([12594c5](https://github.com/phyelds/phyelds/commit/12594c57d120956f1386863ff28e3aeae252f887))

## [9.5.2](https://github.com/phyelds/phyelds/compare/9.5.1...9.5.2) (2026-11-03)

### Bug Fixes

* **calculus:** mangle the private names of aggregate methods as python does ([#69](https://github.com/phyelds/phyelds/issues/69)) ([4fa5cb3](https://github.com/phyelds/phyelds/commit/4fa5cb3e2edaebc12e9ada31c16c8196d2aeb59c))

## [9.5.1](https://github.com/phyelds/phyelds/compare/9.5.0...9.5.1) (2026-11-02)

### Performance improvements

* **calculus:** rewrite each aggregate function once, not at each call ([#64](https://github.com/phyelds/phyelds/issues/64)) ([bae80ab](https://github.com/phyelds/phyelds/commit/bae80aba2077ee35c57fe50a5a6a19897a975258)), closes [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37)

## [9.5.0](https://github.com/phyelds/phyelds/compare/9.4.2...9.5.0) (2026-11-02)

### Features

* support python 3.14 ([#65](https://github.com/phyelds/phyelds/issues/65)) ([09941da](https://github.com/phyelds/phyelds/commit/09941dab64ec9130d04797ad2e5166f1e7b4a002))

## [9.4.2](https://github.com/phyelds/phyelds/compare/9.4.1...9.4.2) (2026-11-01)

### Documentation

* **integration:** show the baseline of the benchmarks on a page ([#62](https://github.com/phyelds/phyelds/issues/62)) ([52b71bf](https://github.com/phyelds/phyelds/commit/52b71bfc29f077d9683482a2ea091f81c16aa889)), closes [#36](https://github.com/phyelds/phyelds/issues/36) [#36](https://github.com/phyelds/phyelds/issues/36)

### General maintenance

* **pre-commit:** lint the paths that ci lints, not the staged files ([#63](https://github.com/phyelds/phyelds/issues/63)) ([e2834d7](https://github.com/phyelds/phyelds/commit/e2834d76dcc31d57d448a641fc143c27a05e388e))
* **release:** 9.4.2 [skip ci] ([38a5658](https://github.com/phyelds/phyelds/commit/38a565855abd37f915dba50dae50e1dc85ba39c1)), closes [#36](https://github.com/phyelds/phyelds/issues/36) [#36](https://github.com/phyelds/phyelds/issues/36)

## [9.4.2](https://github.com/phyelds/phyelds/compare/9.4.1...9.4.2) (2026-11-01)

### Documentation

* **integration:** show the baseline of the benchmarks on a page ([#62](https://github.com/phyelds/phyelds/issues/62)) ([52b71bf](https://github.com/phyelds/phyelds/commit/52b71bfc29f077d9683482a2ea091f81c16aa889)), closes [#36](https://github.com/phyelds/phyelds/issues/36) [#36](https://github.com/phyelds/phyelds/issues/36)

## [9.4.1](https://github.com/phyelds/phyelds/compare/9.4.0...9.4.1) (2026-11-01)

### Documentation

* **integration:** state the round semantics of each host ([#58](https://github.com/phyelds/phyelds/issues/58)) ([b1cf236](https://github.com/phyelds/phyelds/commit/b1cf23639f95d84904ecf172783f07e0b79a1f73)), closes [#35](https://github.com/phyelds/phyelds/issues/35) [#35](https://github.com/phyelds/phyelds/issues/35) [#35](https://github.com/phyelds/phyelds/issues/35) [#35](https://github.com/phyelds/phyelds/issues/35)

### General maintenance

* **benchmarks:** measure hosts, adapters and phyelds with many agents ([#59](https://github.com/phyelds/phyelds/issues/59)) ([7fe72db](https://github.com/phyelds/phyelds/commit/7fe72db500b1276781de8594ed76d27bca21ae81)), closes [#36](https://github.com/phyelds/phyelds/issues/36) [#36](https://github.com/phyelds/phyelds/issues/36) [#36](https://github.com/phyelds/phyelds/issues/36) [#36](https://github.com/phyelds/phyelds/issues/36) [#36](https://github.com/phyelds/phyelds/issues/36)

## [9.4.0](https://github.com/phyelds/phyelds/compare/9.3.1...9.4.0) (2026-11-01)

### Features

* **vm:** snapshot and restore the state and messages of a device ([#60](https://github.com/phyelds/phyelds/issues/60)) ([fa0294c](https://github.com/phyelds/phyelds/commit/fa0294c0be4aabee8989528484b05c990159accd)), closes [#38](https://github.com/phyelds/phyelds/issues/38) [#38](https://github.com/phyelds/phyelds/issues/38)

## [9.3.1](https://github.com/phyelds/phyelds/compare/9.3.0...9.3.1) (2026-10-31)

### Bug Fixes

* **release:** require the core of their own release in all packages ([#57](https://github.com/phyelds/phyelds/issues/57)) ([38b5b28](https://github.com/phyelds/phyelds/commit/38b5b28097ac78b26d86f358b31934c7f3eeb02a)), closes [#56](https://github.com/phyelds/phyelds/issues/56)

## [9.3.0](https://github.com/phyelds/phyelds/compare/9.2.0...9.3.0) (2026-10-30)

### Features

* **codec:** add a compact binary wire format ([#55](https://github.com/phyelds/phyelds/issues/55)) ([0ec5049](https://github.com/phyelds/phyelds/commit/0ec5049549cb76954be2793fa10405753258e677)), closes [#47](https://github.com/phyelds/phyelds/issues/47) [#47](https://github.com/phyelds/phyelds/issues/47) [#47](https://github.com/phyelds/phyelds/issues/47) [#47](https://github.com/phyelds/phyelds/issues/47) [#47](https://github.com/phyelds/phyelds/issues/47) [#47](https://github.com/phyelds/phyelds/issues/47) [#47](https://github.com/phyelds/phyelds/issues/47)

### Bug Fixes

* **processes:** enter the key of a process through the path encoding ([#54](https://github.com/phyelds/phyelds/issues/54)) ([3709159](https://github.com/phyelds/phyelds/commit/3709159bd919467ba814bd50cfc5c84703e5effc))

## [9.2.0](https://github.com/phyelds/phyelds/compare/9.1.0...9.2.0) (2026-10-30)

### Features

* **vm:** send each neighbor its own value of a field ([#53](https://github.com/phyelds/phyelds/issues/53)) ([a725cd4](https://github.com/phyelds/phyelds/commit/a725cd477260dad3dd5658f40a08479df28d68bc))

## [9.1.0](https://github.com/phyelds/phyelds/compare/9.0.0...9.1.0) (2026-10-30)

### Features

* **micropython:** smaller builds for small targets ([#49](https://github.com/phyelds/phyelds/issues/49)) ([c60532f](https://github.com/phyelds/phyelds/commit/c60532ffc3d74a46617796e09cd09a1c3af9442c)), closes [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48) [#48](https://github.com/phyelds/phyelds/issues/48)

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

## [8.8.7](https://github.com/phyelds/phyelds/compare/8.8.6...8.8.7) (2026-10-25)

### Documentation

* space the buttons of the home page when they wrap ([133cf04](https://github.com/phyelds/phyelds/commit/133cf042a3bd7813957c4f31f55955d174a36081))

## [8.8.6](https://github.com/phyelds/phyelds/compare/8.8.5...8.8.6) (2026-10-25)

### Documentation

* only the p in the logo square, and whole nodes in the wordmark ([010af14](https://github.com/phyelds/phyelds/commit/010af14190a47b9b6b5c8e9bb6e1ead006e791bb))

## [8.8.5](https://github.com/phyelds/phyelds/compare/8.8.4...8.8.5) (2026-10-25)

### Documentation

* the logo square and the name again in the header ([785dfd5](https://github.com/phyelds/phyelds/commit/785dfd514d9031bf6d3352d05c158c85ba5a37e9))

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
