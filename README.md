# auto-aiming-trashcan

A trashcan that turns to face whoever (or whatever) is in front of it.

## What's here

| Path | What it is |
|---|---|
| `config.py`, `environment.py`, `main.py`, `physics.py`, `simulation.py`, `trajectory.py`, `trash_can.py` | PyBullet physics simulation - models the trashcan catching thrown objects, no real hardware involved |
| `hardware/uno_q_app/` | Real-hardware version: Arduino UNO Q + USB camera running live object/person detection, wired to steer the trashcan's motors toward whatever it sees |

The simulation and the hardware app are independent - the simulation doesn't
need a UNO Q, and the hardware app doesn't need PyBullet. See
[`hardware/uno_q_app/README.md`](hardware/uno_q_app/README.md) for how
detection reaches the motors and what to check before flashing.

## Running the simulation

```bash
python main.py
```

## Running the hardware app

Open `hardware/uno_q_app/` in Arduino App Lab with a UNO Q connected over
USB and deploy - see that folder's README for wiring notes and known
unknowns (pin names haven't been verified against real hardware yet).
