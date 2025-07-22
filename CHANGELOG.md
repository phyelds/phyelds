## [2.6.0](https://github.com/phyelds/phyelds/compare/2.5.0...2.6.0) (2025-07-22)

### Features

* add monitors to execute actions before and after the simulation ([9cc08e1](https://github.com/phyelds/phyelds/commit/9cc08e1032638252d65bdd900fa0bde3e1bf07dc))

### Bug Fixes

* add simultor as monitor parameter ([afc5ffa](https://github.com/phyelds/phyelds/commit/afc5ffaa15971dddef521613b389d725aa75bf10))

### General maintenance

* add docstrings ([c030544](https://github.com/phyelds/phyelds/commit/c030544f8200599b56ced9d9b9f8c9962aa6153b))
* fix pylint ([ce8c395](https://github.com/phyelds/phyelds/commit/ce8c395968c86c758e09deb0f838bfed7e21f730))

## [2.5.0](https://github.com/phyelds/phyelds/compare/2.4.0...2.5.0) (2025-06-17)

### Features

* add any and all in Field ([6c93c62](https://github.com/phyelds/phyelds/commit/6c93c623ef88314c6bd60089c41a93d2d51a48f7))

### Tests

* add test about not healing factor of normal gossip ([c095157](https://github.com/phyelds/phyelds/commit/c0951579ba61c4adc45e9acf5eec7c66c2013234))

## [2.4.0](https://github.com/phyelds/phyelds/compare/2.3.1...2.4.0) (2025-05-25)

### Features

* add gossip functions ([9f84ab2](https://github.com/phyelds/phyelds/commit/9f84ab2adf7793f5c557ad00301c91b6ebb6cb38))

### Bug Fixes

* avoid to run aggregate program when a node it is not in the environment ([9ece149](https://github.com/phyelds/phyelds/commit/9ece14944bfa87a21b37d5f96769bde6b6274f2f))

### General maintenance

* fix pre commit ([f49a2c2](https://github.com/phyelds/phyelds/commit/f49a2c21cfc8a2d92c08ad28bc9528e5a7e70003))

### Style improvements

* add a space in simulator ([f6956f5](https://github.com/phyelds/phyelds/commit/f6956f58c26f8fabe47ac3a490a2f36ad446082a))

## [2.3.1](https://github.com/phyelds/phyelds/compare/2.3.0...2.3.1) (2025-05-19)

### Bug Fixes

* remove useless prints ([984d46d](https://github.com/phyelds/phyelds/commit/984d46d71a9ad900ffad6d27ab657b8621f3591e))

## [2.3.0](https://github.com/phyelds/phyelds/compare/2.2.1...2.3.0) (2025-05-19)

### Features

* implement csv exporter to export simulation data ([83daedf](https://github.com/phyelds/phyelds/commit/83daedfe9dd9e8d9ca7c55dc6899bd4982636d76))

### Dependency updates

* **deps:** add pandas dependency ([477203d](https://github.com/phyelds/phyelds/commit/477203d0035cf40739241bd67970b18679dbf162))
* **deps:** add pre-commit dependecy ([6d6ea96](https://github.com/phyelds/phyelds/commit/6d6ea96c47b567f270dbeae4e28025462295ee8f))

### Bug Fixes

* add node outputs in node data ([802bc84](https://github.com/phyelds/phyelds/commit/802bc84241b9ddb22dfa8d492fa857ccb8e21021))

### General maintenance

* add pre-commit configuration to install verification hook ([33aad23](https://github.com/phyelds/phyelds/commit/33aad238fb0d0e04ee61438359859ad70a125167))
* overview of phyelds performance ([260ea6a](https://github.com/phyelds/phyelds/commit/260ea6ac4426e8bef1ad68e0880624261545c74a))

## [2.2.1](https://github.com/phyelds/phyelds/compare/2.2.0...2.2.1) (2025-05-15)

### Bug Fixes

* passing parameters to aggregate program also in rounds after the first ([e490684](https://github.com/phyelds/phyelds/commit/e490684185b6ae99829d13eb63c99da3c1d3beb2))

## [2.2.0](https://github.com/phyelds/phyelds/compare/2.1.0...2.2.0) (2025-05-15)

### Features

* now it is possible to pass arguments to the aggregate program ([bedbeaf](https://github.com/phyelds/phyelds/commit/bedbeaf4cba2694d88023c4cf94b4c33b24b5d6c))

## [2.1.0](https://github.com/phyelds/phyelds/compare/2.0.0...2.1.0) (2025-05-15)

### Features

* add store operation as device abstraction ([abbc5f4](https://github.com/phyelds/phyelds/commit/abbc5f4219269165d20ad0bb469c7cce537a2678))

### Style improvements

* better style for linters:) ([bb77d92](https://github.com/phyelds/phyelds/commit/bb77d92699211dc0bf0af6c44a126def1184cc72))

## [2.0.0](https://github.com/phyelds/phyelds/compare/1.6.0...2.0.0) (2025-05-14)

### ⚠ BREAKING CHANGES

* change elect_leader in elect_leaders

### Features

* add map in Field ([d955e5f](https://github.com/phyelds/phyelds/commit/d955e5fe279b75f6e3f7fc9ebf3c6c65189f82d0))
* change elect_leader in elect_leaders ([b9ef4d3](https://github.com/phyelds/phyelds/commit/b9ef4d3cfc7c015bbc75dac0f58ed268149a9b48))

## [1.6.0](https://github.com/phyelds/phyelds/compare/1.5.0...1.6.0) (2025-05-13)

### Features

* change neighbors distance in order to do not need position ([a07282a](https://github.com/phyelds/phyelds/commit/a07282a1d15b18c6b711bb645170039b8e49e4db))

## [1.5.0](https://github.com/phyelds/phyelds/compare/1.4.0...1.5.0) (2025-05-13)

### Features

* add schedule_progra_for_all ([dccddb1](https://github.com/phyelds/phyelds/commit/dccddb132aae51e0d07a6478af53227d175279ed))

## [1.4.0](https://github.com/phyelds/phyelds/compare/1.3.0...1.4.0) (2025-05-13)

### Features

* avoid global variable but prefer context variable for thread safety ([17c43f0](https://github.com/phyelds/phyelds/commit/17c43f0cebf106e2092fe3871f2e3d9d60758bd9))
* clean-up engine state and mutable engine ([4b60e9a](https://github.com/phyelds/phyelds/commit/4b60e9a9c6a18855c9161c8e84bb61b723b9bdf7))

### Refactoring

* prefer using set inside the runner ([66452f0](https://github.com/phyelds/phyelds/commit/66452f0f14aeafe2f8c2a5f47a5b78e609628a3a))

## [1.3.0](https://github.com/phyelds/phyelds/compare/1.2.4...1.3.0) (2025-05-13)

### Features

* add data for all node in the environment ([0d65c3d](https://github.com/phyelds/phyelds/commit/0d65c3daa6e61bb8134aa5d483dfeda4aad07735))

## [1.2.4](https://github.com/phyelds/phyelds/compare/1.2.3...1.2.4) (2025-05-13)

### Bug Fixes

* **tests:** remove useless test about no neighborhood ([e8e56c6](https://github.com/phyelds/phyelds/commit/e8e56c69385021239a62fc0901e77b69407a96c1))

### Tests

* add more on test_runner ([28ea491](https://github.com/phyelds/phyelds/commit/28ea49125dd252e2a8728b5d8728304331a8c52f))
* minor on test ([5ed7448](https://github.com/phyelds/phyelds/commit/5ed7448033788faa15cc3fe0f1de714162dd4579))

### Build and continuous integration

* add linting checks also with flake8 ([33a67de](https://github.com/phyelds/phyelds/commit/33a67de91343bd5444c270d8da99c13cbf29eb37))

### Style improvements

* fix unused imports from calculus ([98f6a1a](https://github.com/phyelds/phyelds/commit/98f6a1a8a422d5d43d448f51c5f305f439dd5e0a))
* follow flake8 guidelines ([f340934](https://github.com/phyelds/phyelds/commit/f340934f6ca05c6147bfa32fb96fcbe1957748ce))
* reduce pylint problems ([f1fb55a](https://github.com/phyelds/phyelds/commit/f1fb55aabf5fafe9917339b31af43048d6853ed7))
* remove unused imports ([d17aea6](https://github.com/phyelds/phyelds/commit/d17aea65a9ae09269b2483a9a758ba2e8779479c))
* remove unused variable ([5babb4a](https://github.com/phyelds/phyelds/commit/5babb4a5e707580762047f1f2c424211dd40b9cb))

### Refactoring

* **library:** move the distances to a proper library ([261c372](https://github.com/phyelds/phyelds/commit/261c372a912d5f063a84056b86c698cd8b48078e))

## [1.2.3](https://github.com/phyelds/phyelds/compare/1.2.2...1.2.3) (2025-05-13)

### Bug Fixes

* remove context from leader election, now using new API ([93facbe](https://github.com/phyelds/phyelds/commit/93facbea61ae08f77bce218b069db945723397e5))

## [1.2.2](https://github.com/phyelds/phyelds/compare/1.2.1...1.2.2) (2025-05-12)

### Bug Fixes

* add more test for deployments ([f28311e](https://github.com/phyelds/phyelds/commit/f28311e2af45b831e296326e1d72c784412dac4b))
* remove src from package in test ([af695b1](https://github.com/phyelds/phyelds/commit/af695b17e31116e6d5b4d148a5e090c1e12911c0))

### Tests

* add test to main abstraction of simulator ([811310b](https://github.com/phyelds/phyelds/commit/811310bcb452718335c264faffb0575646937812))

## [1.2.1](https://github.com/phyelds/phyelds/compare/1.2.0...1.2.1) (2025-05-12)

### Documentation

* better README ([249c731](https://github.com/phyelds/phyelds/commit/249c7318394615dbcd88023524af84e33030f255))

## [1.2.0](https://github.com/phyelds/phyelds/compare/1.1.4...1.2.0) (2025-05-12)

### Features

* add context as an implicit input of the program (simplify all the other operations) ([08d97e4](https://github.com/phyelds/phyelds/commit/08d97e452fceb0d67587996656543834912bc0d9))
* add reset_engine in core library ([137bd24](https://github.com/phyelds/phyelds/commit/137bd242cbae7f8477b76d65825e725caccefbc1))

### Bug Fixes

* rmeove global reset index, minors on style ([57e8fed](https://github.com/phyelds/phyelds/commit/57e8fedf35ecc7b7ae7bd2e6f47f41f167eb8d35))

### Tests

* add fixure for tests ([c1c9e3d](https://github.com/phyelds/phyelds/commit/c1c9e3da930625505feab41a3f3efae7b4df2892))

### General maintenance

* remove example in core phyelds ([72947c4](https://github.com/phyelds/phyelds/commit/72947c478e1caa4e0bd3a20e6af110c9852001c1))

## [1.1.4](https://github.com/phyelds/phyelds/compare/1.1.3...1.1.4) (2025-05-12)

### Bug Fixes

* update gradient if I'm the leader ([237e14a](https://github.com/phyelds/phyelds/commit/237e14a29c9d2a37d6a6e61935d0ae00564550b7))

## [1.1.3](https://github.com/phyelds/phyelds/compare/1.1.2...1.1.3) (2025-05-12)

### Bug Fixes

* elect leader now works ([07ef7ba](https://github.com/phyelds/phyelds/commit/07ef7ba9b97e9aac682f0288dea6154409dfb3c7))

### Style improvements

* better style for pylint :) ([d217c4c](https://github.com/phyelds/phyelds/commit/d217c4cf1ba8cccf40139b45779ec4e1667e0649))

## [1.1.2](https://github.com/phyelds/phyelds/compare/1.1.1...1.1.2) (2025-05-12)

### Bug Fixes

* fix min with default, now it works with any data structure ([2613ec3](https://github.com/phyelds/phyelds/commit/2613ec338ff078facbd17f2ec305cbbf1b0ea122))

### Tests

* add tests for min_with_default functionality ([da68ac7](https://github.com/phyelds/phyelds/commit/da68ac7194047f6f8ed2922719af594faa15bad2))

### General maintenance

* **test:** remove useless print ([ba532f0](https://github.com/phyelds/phyelds/commit/ba532f0577484661d59b7b6b19219a13391fdf2b))

### Style improvements

* better style for pylint :) ([314d3b8](https://github.com/phyelds/phyelds/commit/314d3b8288ecfc6a198890fbdc5718efe67e313d))

## [1.1.1](https://github.com/phyelds/phyelds/compare/1.1.0...1.1.1) (2025-05-09)

### Bug Fixes

* min_with_default now works ([5b2a516](https://github.com/phyelds/phyelds/commit/5b2a516eec5dd1f11edbc423dfcc5fbcdefbfcc0))

### General maintenance

* update name in readme ([e07a1e3](https://github.com/phyelds/phyelds/commit/e07a1e334fdf5510283ef0d9d1514d9dcd07b8a4))

## [1.1.0](https://github.com/phyelds/phyelds/compare/1.0.0...1.1.0) (2025-05-09)

### Features

* implement empty neighborhood ([3ee1468](https://github.com/phyelds/phyelds/commit/3ee146817d67dd2df433cae2b54baa371a5aeae5))

## 1.0.0 (2025-05-09)

### Features

* a working version of fieldpy ([f0466d6](https://github.com/phyelds/phyelds/commit/f0466d6ab3e52d443590c4900015162894da9fd8))
* add poetry requirement ([a79f80d](https://github.com/phyelds/phyelds/commit/a79f80d4a21eb27fd9aafaa1053b466ad9990d0b))
* add semantic release ([24a0318](https://github.com/phyelds/phyelds/commit/24a0318548710530e5a753b96234b2a049dc2e25))
* rename project, fieldpy --> phyelds ([8009d73](https://github.com/phyelds/phyelds/commit/8009d7373b57e94b414dee5036f8d4f875ead49b))

### Bug Fixes

* fix poetry config ([3b4dfdf](https://github.com/phyelds/phyelds/commit/3b4dfdf2b270458ee0e1bee26b20c79a8ec72df9))

### Tests

* add more on remember ([e053eee](https://github.com/phyelds/phyelds/commit/e053eeeecfedd44207b9df420a74eba7234c6f4e))
* add simple remember tests ([2a31b71](https://github.com/phyelds/phyelds/commit/2a31b710ab3ff2b15716aea363d75f3148dfaca2))
* fix wrong tests ([87299f6](https://github.com/phyelds/phyelds/commit/87299f69c8d0ffc8d98e3b4d0354f81e705cae12))
* more on Field testing ([3406649](https://github.com/phyelds/phyelds/commit/34066498f00c3970480bec1b15f907c72cacf6d3))
* more on neighbors ([0a2d8dd](https://github.com/phyelds/phyelds/commit/0a2d8dd824bac5dbcf21d24e269b1d787c1c92f4))

### Build and continuous integration

* add coverage ([74836b6](https://github.com/phyelds/phyelds/commit/74836b66511d3f82e7bab363ed32688887eea059))
* add linters ([b28fda7](https://github.com/phyelds/phyelds/commit/b28fda75032778e1474c2d308194862e41e9cbd0))
* add src pacakge ([2be1f60](https://github.com/phyelds/phyelds/commit/2be1f60e195d1438731653e418eaa7ca83e7dffc))
* add tentative ci ([bff49ab](https://github.com/phyelds/phyelds/commit/bff49ab609d7de33992a355d56762be2cf509722))
* fix pylint ([796abe5](https://github.com/phyelds/phyelds/commit/796abe5bb450f75ea042cacbf4fbc3ac06cb2f5c))
* fix python version ([64ab360](https://github.com/phyelds/phyelds/commit/64ab360de63993874fefffb66386d0c30ad6367e))
* init poetry ([79cd343](https://github.com/phyelds/phyelds/commit/79cd343d8a1fcaad9a0e2701d35a150dbb1f0555))
* put the right supported version ([f034807](https://github.com/phyelds/phyelds/commit/f034807f1690e4e921ad5a44016c27d9ec4d6ee6))
* setup CI to release on pypi ([558bacf](https://github.com/phyelds/phyelds/commit/558bacfa8e7d0582dc9f587e45b65d06788e41d8))

### General maintenance

* add changelog ([77e027d](https://github.com/phyelds/phyelds/commit/77e027d80a3cde03abb1ccc5547d7d8574dc6ec2))
* add classifiers ([231b02e](https://github.com/phyelds/phyelds/commit/231b02ebb6eba304467ef7d75535823142560a49))
* add license ([ca6cacf](https://github.com/phyelds/phyelds/commit/ca6cacfdf1a4716f7538552463a19a0f4ab57e1c))
* add requirements in tracking ([02e1666](https://github.com/phyelds/phyelds/commit/02e16663d663e2afcf98cd1b595dd27efc5eca01))
* put a description in the readme for features ([9b540ad](https://github.com/phyelds/phyelds/commit/9b540ada934010b90a5c5e72b50d94362cea0f59))
* remove example from codebase ([77aef27](https://github.com/phyelds/phyelds/commit/77aef276be5a502eea010b6e3dac843876138811))

### Style improvements

* add flake8 ([c71b3cf](https://github.com/phyelds/phyelds/commit/c71b3cfe2b50ff6f7761061991179f67c752771f))
* fix all pylint rules ([e822d5e](https://github.com/phyelds/phyelds/commit/e822d5e732e9fd25ee463848897843d750265b45))
* linting using ruff ([949f25d](https://github.com/phyelds/phyelds/commit/949f25de4aa1f48b12da4ecf4b57671d309d6f90))
* remove unused imports ([d6d684c](https://github.com/phyelds/phyelds/commit/d6d684c7717269c8ef5dfa925e49dd9901c13459))
* remove useless print ([ddd1872](https://github.com/phyelds/phyelds/commit/ddd18725bc9aade332ce45b9c0f6b348a467359e))

### Refactoring

* better names, better style, better engine ([10e8a88](https://github.com/phyelds/phyelds/commit/10e8a8879881bf5d7ad3a5a5efeb13414a9013b2))

# CHANGELOG
