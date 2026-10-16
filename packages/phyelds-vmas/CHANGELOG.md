## [7.6.2](https://github.com/phyelds/phyelds/compare/7.6.1...7.6.2) (2026-10-16)

### Documentation

* **walkthrough:** add interactive 3D step-by-step field and channel explorer ([87d019a](https://github.com/phyelds/phyelds/commit/87d019aa4045f75e1f5016293c0c483de8c5df53))
* **walkthrough:** keep a few neighbors per device as devices are added ([98d7a03](https://github.com/phyelds/phyelds/commit/98d7a03052956f40f013749b80e7bcb956c53aee))
* **walkthrough:** redesign the walkthrough around one field at a time ([d24383b](https://github.com/phyelds/phyelds/commit/d24383bada1f4a6c780939cb6c9e2f38a21dd93a))
* **walkthrough:** turn 3D walkthrough into a full-viewport standalone page ([d028942](https://github.com/phyelds/phyelds/commit/d028942b1a1bd2d73600788b00bff13f48f4fd89))

### Tests

* **examples:** check that the walkthrough references existing files ([ffcba48](https://github.com/phyelds/phyelds/commit/ffcba4814034dbd6eefd090dd5b3a512ba2dde34))

### Refactoring

* **docs:** publish only the walkthrough page from the hook ([78549f2](https://github.com/phyelds/phyelds/commit/78549f254765073a59276d608de439a3de90ada1))

## [7.6.1](https://github.com/phyelds/phyelds/compare/7.6.0...7.6.1) (2026-10-16)

### Documentation

* **assets:** improve remember state evolution diagram across rounds ([c309263](https://github.com/phyelds/phyelds/commit/c3092634423530db785f8bcb2099ffad79c868b5))
* **assets:** replace inline SVGs with matplotlib-rendered conceptual figures ([099f5ae](https://github.com/phyelds/phyelds/commit/099f5ae78277f21aa5bc390378fae7ccbd6d9ca4))
* **concepts:** add visual diagrams and progressive intro to aggregate programs ([4b9d5a2](https://github.com/phyelds/phyelds/commit/4b9d5a2367f0b5182f616e9f18b34b14230716db))
* **concepts:** enrich state, neighborhood-field, alignment, and pitfalls with diagrams ([7ab3c48](https://github.com/phyelds/phyelds/commit/7ab3c48d48a68f0ac2f69f6bcc8c4bd0542fd4df))
* **examples:** add leaders and bubbles playground examples and animations ([815cfc3](https://github.com/phyelds/phyelds/commit/815cfc38376cf5b0492bcdebd068cad6212090ce))
* **libraries:** restructure standard libraries into thematic guides and linearize nav ([843334f](https://github.com/phyelds/phyelds/commit/843334f13186f1b4be665d2b5ee25a5f32ab944a))
* **mkdocs:** enable footer navigation, code annotations, and mermaid diagrams ([3caf59f](https://github.com/phyelds/phyelds/commit/3caf59fab597317130eda137070aa5a60bc3e68d))
* replace mermaid blocks with custom theme-aware SVG diagrams and cards ([5f2237d](https://github.com/phyelds/phyelds/commit/5f2237d8a6c6795c60f1559492dca85e5efdd9f7))
* **tutorial:** expand tutorial with diagrams, annotations, and channel composition ([a87c660](https://github.com/phyelds/phyelds/commit/a87c66076e6f2ac3705a71c6a26efd9f439024a5))

## [7.6.0](https://github.com/phyelds/phyelds/compare/7.5.0...7.6.0) (2026-10-16)

### Features

* **libraries:** add multi_path collect strategy and gossip_mean from FCPP ([76d330a](https://github.com/phyelds/phyelds/commit/76d330a8c2c801cf5566d1a83890a11717f160ba))
* **libraries:** add SLCS spatial logic and Past-CTL temporal logic from FCPP ([7fec617](https://github.com/phyelds/phyelds/commit/7fec6176c183ab3209c2f876ae704cba77341adb))

### Documentation

* **libraries:** document spatial/temporal logic, multi_path collect, and gossip_mean ([1657716](https://github.com/phyelds/phyelds/commit/16577165cea8067c1e4cdf4b07abe37b56351cb2))
* **readme:** add project heritage, main contributors, and acknowledgments ([e750522](https://github.com/phyelds/phyelds/commit/e75052294ab0e7a9db09dde4935c5768955b0802))

## [7.5.0](https://github.com/phyelds/phyelds/compare/7.4.0...7.5.0) (2026-10-16)

### Features

* **libraries:** add [@process](https://github.com/process) decorator, guard functions, and bubble context manager ([84595c2](https://github.com/phyelds/phyelds/commit/84595c233b2eb1a8b80cc74207e9243843c2bcd7))
* **libraries:** add distance_between, channel, and summarize blocks from ScaFi ([7734cc2](https://github.com/phyelds/phyelds/commit/7734cc2c2b3024476b8b33eaa0df5f442880d5ff))
* **libraries:** add reactive state and time operators from ScaFi ([5b1d02e](https://github.com/phyelds/phyelds/commit/5b1d02e27c13c905712ba6fe954895b5cce9aad2))
* **libraries:** add ScaFi-style aggregate processes (spawn) with lifecycle management ([dd3068f](https://github.com/phyelds/phyelds/commit/dd3068f92771f4ce353dbbd8cf2c4d7c3b724068))

### Documentation

* **libraries:** document aggregate processes, channel, summarize, and reactive operators ([ea0f976](https://github.com/phyelds/phyelds/commit/ea0f97655c3e641c2a1ad4d542730739f84cc310))

## [7.4.0](https://github.com/phyelds/phyelds/compare/7.3.0...7.4.0) (2026-10-16)

### Features

* **data:** add collapse and transformation methods to NeighborhoodField ([c710812](https://github.com/phyelds/phyelds/commit/c7108126fd90f56ab1950f41c55efadafcbc8909))
* **libraries:** add delta_time, shared_clock, timer, and time_replicated ([398182b](https://github.com/phyelds/phyelds/commit/398182b0cdcb781f8297efe3ccc860a4d0216fbd))
* **libraries:** add PathValue, non_looping_paths, and path_coherence utilities ([9b6fe81](https://github.com/phyelds/phyelds/commit/9b6fe81b2b576c5d8ca43f72557b171ccc1fe7f3))
* **libraries:** add pluggable gossip strategies, key selector, and any_node ([09f5224](https://github.com/phyelds/phyelds/commit/09f52244959b89a6f87ab95d592102419f518499))
* **libraries:** add pluggable leader election with loop-free candidacy and finite area check ([2c1302f](https://github.com/phyelds/phyelds/commit/2c1302fc8d875e15e7ba7340510e22970dc03236))
* **libraries:** add pluggable spreading strategies and path_coherent gradient ([c9a0394](https://github.com/phyelds/phyelds/commit/c9a0394dff4b7816a261a47923e5b1af1045d72f))
* **libraries:** add point_to_point collect strategy, mean_values, and find_parents ([07525b4](https://github.com/phyelds/phyelds/commit/07525b4d755733135e0cb49ded842fc134b69089))
* **libraries:** support n-dimensional and custom positions in neighbors_distances ([ea821ae](https://github.com/phyelds/phyelds/commit/ea821aeaa83159e39a6f06c48292d292ed0a0694))

### Bug Fixes

* **libraries:** track replica spawn_time in time_replicated to prevent multi-hop timer drift ([5ba9bcc](https://github.com/phyelds/phyelds/commit/5ba9bcc35e6d6a2e546d3e1a0146d749b51f70f2))

### Documentation

* **libraries:** document pluggable strategies and NeighborhoodField collapse methods ([479867f](https://github.com/phyelds/phyelds/commit/479867fdcf6e276c7acc7cd7b5439d4852cce6f8))

## [7.3.0](https://github.com/phyelds/phyelds/compare/7.2.0...7.3.0) (2026-10-16)

### Features

* **calculus:** add exchange operator for anisotropic state and messaging ([5aa200b](https://github.com/phyelds/phyelds/commit/5aa200b92aa7f91f71904f86b14dc79fb081d406))
* **data:** add default value and per-node lookup to NeighborhoodField ([e47fdd1](https://github.com/phyelds/phyelds/commit/e47fdd1eb98665d2934b4e9efeee6022b1270ba5))

### Documentation

* **calculus:** document the exchange operator and NeighborhoodField.for_node ([be9c925](https://github.com/phyelds/phyelds/commit/be9c925a41c97f4006566ef48986e42c0c042876))

## [7.2.0](https://github.com/phyelds/phyelds/compare/7.1.8...7.2.0) (2026-10-13)

### Features

* **calculus:** align the branches of conditional expressions ([927e84e](https://github.com/phyelds/phyelds/commit/927e84e1cbce43e8a088170972e99f522be678be))

### Documentation

* describe the alignment of conditional expressions ([ed9fcb5](https://github.com/phyelds/phyelds/commit/ed9fcb518edbfd4ec354095f92d41e59b77f2507))

## [7.1.8](https://github.com/phyelds/phyelds/compare/7.1.7...7.1.8) (2026-10-13)

### Documentation

* highlight the code in the playground editor ([7e3937c](https://github.com/phyelds/phyelds/commit/7e3937c339d29c9d1abc477ff2b0a714319d1c17))

## [7.1.7](https://github.com/phyelds/phyelds/compare/7.1.6...7.1.7) (2026-10-13)

### Bug Fixes

* **simulator:** import IPython lazily in render ([6cc59c3](https://github.com/phyelds/phyelds/commit/6cc59c3009ece80cfa73727baa08b2dfd95e865f))

### Documentation

* add a playground that runs phyelds in the browser ([e959b4c](https://github.com/phyelds/phyelds/commit/e959b4c584722bf7dc0094edcb1b9a738e13a820))
* add the examples of the playground ([9153afe](https://github.com/phyelds/phyelds/commit/9153afeeba8bdae533d366ad984063049e0b2556))
* add the python runner of the browser playground ([73ca075](https://github.com/phyelds/phyelds/commit/73ca075a292ac83ac019429a490521866a926366))
* link the docs to the playground examples ([50184e0](https://github.com/phyelds/phyelds/commit/50184e0d537018989f90c8ff458adc36306a3df0))
* publish phyelds and the examples for the playground ([668af73](https://github.com/phyelds/phyelds/commit/668af7329da94e2ffe7a7ad8be45fb018a6b000e))

### Tests

* bound the playground examples in rounds, not seconds ([8dbfa4f](https://github.com/phyelds/phyelds/commit/8dbfa4fd7dfa60b68916c968370837441151308d))

### Build and continuous integration

* make ipython an optional jupyter extra ([4f09c9a](https://github.com/phyelds/phyelds/commit/4f09c9a4d85fc224cc5f0b657843c0fb9fd1feeb))
* move pre-commit to the dev dependency group ([c858205](https://github.com/phyelds/phyelds/commit/c8582051b23046bf9554d1d7365662e3207d7004))

### Style improvements

* **simulator:** allow pylint to miss the optional IPython ([eeb496e](https://github.com/phyelds/phyelds/commit/eeb496e799b9df7f44f065447653660546d814b3))

## [7.1.6](https://github.com/phyelds/phyelds/compare/7.1.5...7.1.6) (2026-10-13)

### Documentation

* colour the site with the palette of the logo ([f7248d6](https://github.com/phyelds/phyelds/commit/f7248d6b6f5a26597a252a3d97f561d8c5c40b8d))
* draw the gradient animations with the plasma colormap ([4d95bdd](https://github.com/phyelds/phyelds/commit/4d95bdddbd0451ec1a17b5cb2143e2bd27da34c8))

## [7.1.5](https://github.com/phyelds/phyelds/compare/7.1.4...7.1.5) (2026-10-13)

### Documentation

* use the phyelds logo in the documentation site ([e70d3f0](https://github.com/phyelds/phyelds/commit/e70d3f06a0f9d5b18217a6725bcca243ddad21f0))

## [7.1.4](https://github.com/phyelds/phyelds/compare/7.1.3...7.1.4) (2026-10-13)

### Documentation

* improve README and prepare docs site ([#10](https://github.com/phyelds/phyelds/issues/10)) ([79e1607](https://github.com/phyelds/phyelds/commit/79e16070e3de41575fae4553877815ab7bf4938b))

## [7.1.3](https://github.com/phyelds/phyelds/compare/7.1.2...7.1.3) (2026-10-13)

### Documentation

* add CLAUDE.md with tdd, commit and style guidelines ([66e5113](https://github.com/phyelds/phyelds/commit/66e5113811399aec129a38fcb09341c0081910b5))

## [7.1.2](https://github.com/phyelds/phyelds/compare/7.1.1...7.1.2) (2026-10-12)

### Bug Fixes

* do not re-apply decorators stacked above [@aggregate](https://github.com/aggregate) ([#8](https://github.com/phyelds/phyelds/issues/8)) ([3cb43c6](https://github.com/phyelds/phyelds/commit/3cb43c6db338a99d581e79162f6030bca0a7b6a7))
* keep the name and docs of [@aggregate](https://github.com/aggregate) functions ([#9](https://github.com/phyelds/phyelds/issues/9)) ([b1e400a](https://github.com/phyelds/phyelds/commit/b1e400aaac2ccef8affbd417b1d127b0844bd5a8))

## [7.1.1](https://github.com/phyelds/phyelds/compare/7.1.0...7.1.1) (2026-09-03)

### Documentation

* update description to reflect large scale systems ([b05ae1b](https://github.com/phyelds/phyelds/commit/b05ae1b5c12f89a7f0c888484acaeec5b84a0e28))

## [7.1.0](https://github.com/phyelds/phyelds/compare/7.0.0...7.1.0) (2026-08-07)

### Features

* release also vmas ([9bb07ac](https://github.com/phyelds/phyelds/commit/9bb07ac5ef89317e5cbdc0d6ad4ea97c7393a882))

# Changelog

All notable changes to `phyelds-vmas` are documented in this file.
