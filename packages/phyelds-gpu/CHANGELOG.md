## [10.4.0](https://github.com/phyelds/phyelds/compare/10.3.0...10.4.0) (2026-11-23)

### Features

* **ros2:** run aggregate programs on gazebo robots ([#102](https://github.com/phyelds/phyelds/issues/102)) ([db578bf](https://github.com/phyelds/phyelds/commit/db578bfd8556e8f9cd245edc99f6eb292691e456)), closes [#100](https://github.com/phyelds/phyelds/issues/100) [#100](https://github.com/phyelds/phyelds/issues/100) [#100](https://github.com/phyelds/phyelds/issues/100) [#100](https://github.com/phyelds/phyelds/issues/100) [#100](https://github.com/phyelds/phyelds/issues/100)
* **ros2:** run aggregate programs on ROS 2 robots ([#101](https://github.com/phyelds/phyelds/issues/101)) ([5483c30](https://github.com/phyelds/phyelds/commit/5483c30a96f75f444dc7111f538928f7b5fbd946)), closes [#100](https://github.com/phyelds/phyelds/issues/100) [#100](https://github.com/phyelds/phyelds/issues/100) [#100](https://github.com/phyelds/phyelds/issues/100) [#100](https://github.com/phyelds/phyelds/issues/100) [#100](https://github.com/phyelds/phyelds/issues/100) [#100](https://github.com/phyelds/phyelds/issues/100) [#100](https://github.com/phyelds/phyelds/issues/100) [#100](https://github.com/phyelds/phyelds/issues/100) [#100](https://github.com/phyelds/phyelds/issues/100) [#100](https://github.com/phyelds/phyelds/issues/100)

### Build and continuous integration

* **deps-dev:** bump the npm group with 2 updates ([#115](https://github.com/phyelds/phyelds/issues/115)) ([da640ae](https://github.com/phyelds/phyelds/commit/da640ae72fe5de43a6eacdf591239e59ebb28600))

## [10.3.0](https://github.com/phyelds/phyelds/compare/10.2.0...10.3.0) (2026-11-16)

### Features

* **gpu:** support anisotropic exchange in batch runtimes ([#99](https://github.com/phyelds/phyelds/issues/99)) ([50f5f2c](https://github.com/phyelds/phyelds/commit/50f5f2cf4b59eeb87363dc761edf23440dd9dbfd)), closes [#98](https://github.com/phyelds/phyelds/issues/98) [#98](https://github.com/phyelds/phyelds/issues/98) [#98](https://github.com/phyelds/phyelds/issues/98) [#98](https://github.com/phyelds/phyelds/issues/98) [#98](https://github.com/phyelds/phyelds/issues/98) [#98](https://github.com/phyelds/phyelds/issues/98) [#98](https://github.com/phyelds/phyelds/issues/98) [#98](https://github.com/phyelds/phyelds/issues/98)

## [10.2.0](https://github.com/phyelds/phyelds/compare/10.1.0...10.2.0) (2026-11-13)

### Features

* **calculus:** rewrite aggregate functions for vectorized engines ([#91](https://github.com/phyelds/phyelds/issues/91)) ([3df21ec](https://github.com/phyelds/phyelds/commit/3df21ecdaf9abdc6b10ab2f90214b8ef61cb3c21)), closes [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37)
* **data:** pass device values to map and restrict fields for batch engines ([#92](https://github.com/phyelds/phyelds/issues/92)) ([a65dd9b](https://github.com/phyelds/phyelds/commit/a65dd9bf779c78fa75b60a4572941e1a55a7872a)), closes [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37)
* **experimental:** add the wavefront simulation with clocks and channels ([#87](https://github.com/phyelds/phyelds/issues/87)) ([bb3f89d](https://github.com/phyelds/phyelds/commit/bb3f89df95b53705ca167ab29c55660a93dd2b54)), closes [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37)
* **gpu:** add the communication graph of devices as tensors ([#89](https://github.com/phyelds/phyelds/issues/89)) ([62fbbb3](https://github.com/phyelds/phyelds/commit/62fbbb31b284a2668b7a72a4aaab2507339db043)), closes [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37)
* **gpu:** run aggregate programs on every device at once ([#93](https://github.com/phyelds/phyelds/issues/93)) ([661347a](https://github.com/phyelds/phyelds/commit/661347aa43ed512b5472e73917eaa0e94943bbc0)), closes [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37)
* **gpu:** run wavefronts of devices on a torch device ([#94](https://github.com/phyelds/phyelds/issues/94)) ([06f7a36](https://github.com/phyelds/phyelds/commit/06f7a36a77ab0bbe16a312e2964de98f9f63a211)), closes [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37)
* **vm:** let engines read state, build neighbor fields and branch ([#90](https://github.com/phyelds/phyelds/issues/90)) ([1ff6da6](https://github.com/phyelds/phyelds/commit/1ff6da6587dd00197b45dc4b086ae9b453f6a8be)), closes [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37)

### Documentation

* **gpu:** document and release the PyTorch backend ([#95](https://github.com/phyelds/phyelds/issues/95)) ([68fcb46](https://github.com/phyelds/phyelds/commit/68fcb46222459797f7d1e7e65378c894eced3fb2)), closes [#37](https://github.com/phyelds/phyelds/issues/37) [#37](https://github.com/phyelds/phyelds/issues/37)

### Build and continuous integration

* check pull requests to any branch, for stacked pull requests ([#96](https://github.com/phyelds/phyelds/issues/96)) ([fe1bd8c](https://github.com/phyelds/phyelds/commit/fe1bd8cd14c4d70f5d2ac0625f68132f34d6ff3c))
