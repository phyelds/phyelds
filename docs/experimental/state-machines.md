# Collective state machines

!!! warning "Experimental"
    This is a [study in progress](index.md): its API will probably change.

A collective state machine is a finite state machine run by a whole collective: its
states are collective behaviours (*explore*, *defend*), its transitions are collective
agreements. A device senses an event and proposes a transition; the network makes it a
decision of everyone. It comes from the paper *Macroscopic Design of Swarms with
Collective State Machines*, and from [its experiments in
ScaFi](https://github.com/cric96/experiments-2025-collective-state-machines).

```python
from phyelds.experimental.state_machines import Next, collective_state_machine
```

---

## How it works

`collective_state_machine(initial, transition)` runs in every round of every device:

1. **Propose.** `transition` gets the current state and returns the next one: the same
   state to stay, another one to move. It runs [aligned](../concepts/alignment.md) on
   the current state, so a state can use `remember`, `neighbors` and the libraries on its
   own: a timer started in a state restarts when the machine enters it again.
2. **Share.** Each device keeps the history of the transitions its machine went
   through, and sends it to its neighbors.
3. **Agree.** It adopts the most advanced history among its own and its neighbors': a
   longer history wins over its own prefix, so a transition spreads to the whole
   network, hop by hop.

Two devices can propose different transitions at once: the histories diverge, and the
first transition that differs decides. The one with the higher **priority** wins, then
the **greater state**. A bare state has the lowest priority; `Next(state, priority=...)`
raises it:

```python
return Next(Mission.DEFEND, priority=math.inf)  # wins over any other transition
```

States are compared with `==` and, to settle conflicts, with `<`: use ints, strings or an
`IntEnum`.

---

## Example: a search-and-rescue mission

The case study of the paper, without the movement: a swarm of drones waits at the base
(bottom left), explores when an alarm goes off, rescues when a drone finds the target
(top right), and defends the base when it is attacked. Each event is sensed by one drone
only:

```python
--8<-- "mission.py:mission"
```

![Drones agree on the state of a mission: explore, defend while the target is found, rescue, wait](../assets/state-machine.gif#only-light){ width="480" }
![Drones agree on the state of a mission: explore, defend while the target is found, rescue, wait](../assets/state-machine-dark.gif#only-dark){ width="480" }

Blue is *wait*, orange *explore*, green *rescue*, red *defend*. The alarm at the base
spreads *explore*; then the base is attacked just as the target is found, and both
transitions spread from opposite corners: *defend* has the higher priority, and takes
over the drones that had moved to *rescue*. Once the base is safe, the swarm waits,
explores again, rescues the target, and waits.

The complete example is
[`docs/examples/mission.py`](https://github.com/phyelds/phyelds/blob/master/docs/examples/mission.py).

---

## Bounded memory

The history grows with every transition, and so do the messages. With
`memory=n`, each device remembers only its last `n` transitions, and counts those it
forgot, so that two histories are still compared from the first transition both
remember:

```python
collective_state_machine(Mission.WAIT, step, memory=8)
```

Two histories that diverged before what both remember are told apart by their last
transitions only, so a short memory can settle a conflict differently from a full one.

---

## Differences from the original

- **Transitions only.** The original history also has an entry for staying in a state,
  refreshed at every round. A transition proposed at the same position competes with
  that entry, and with the same priority loses to it when the new state is the smaller
  one; here the history holds transitions only, so a transition always wins over staying.
- **Memory in transitions.** The original forgets the transitions older than a time
  window, which needs the clocks of the devices to agree; here the memory is a number of
  transitions.
- **No payload in the states.** In the original, a state also carries what the drone does
  in it (its velocity). Here the machine returns the state, and the program acts on it.
