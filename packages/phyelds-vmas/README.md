# phyelds-vmas

VMAS integration for [phyelds](https://pypi.org/project/phyelds/).

## Installation

```bash
pip install phyelds-vmas
```

`phyelds-vmas` installs compatible `phyelds` and `phyelds-simulator` releases, and VMAS.

## Usage

```python
from phyelds.simulator import Simulator
from phyelds.simulator.runner import schedule_program_for_all
from phyelds.calculus import aggregate
from phyelds.vmas import VmasEnvironment, action, vmas_runner

@aggregate
def move_right():
    action.send([1, 0])
```

Programs share the typed sensors `observations`, `rewards`, `dones`, `infos` and
`agent`, and the actuator `action`, with the host. Existing string names such as
`sense("observations")` and `store("action", [1, 0])` remain supported. An action
has the meaning assigned by the VMAS scenario (for example a force or a discrete
choice).

Readings and positions select environment 0; `agent` exposes the VMAS agent with
its full batched state. `observations` is a tensor, `rewards` a scalar tensor
(initially zero), `dones` a Python bool (initially false), and `infos` a dictionary
of tensors sliced to environment 0 (initially empty). The runner repeats actions
across all VMAS environments.

Each program must send an action every round. If it has not run yet or sent no
action, `vmas_runner` raises a `ValueError` naming the node before stepping VMAS.

## Release

`phyelds-vmas` follows the same version as `phyelds`. The root semantic-release
workflow calculates the release version, writes it to both package manifests,
and publishes both distributions together.
