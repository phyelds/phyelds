# phyelds-vmas

VMAS integration for [phyelds](https://pypi.org/project/phyelds/).

## Installation

```bash
pip install phyelds-vmas
```

`phyelds-vmas` installs a compatible `phyelds` release and VMAS.

## Usage

```python
from phyelds.simulator import Simulator
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.vmas import VmasEnvironment, vmas_runner
```

The extension requires `phyelds >=7.0.0,<8.0.0`.

## Release

`phyelds-vmas` follows the same version as `phyelds`. The root semantic-release
workflow calculates the release version, writes it to both package manifests,
and publishes both distributions together.