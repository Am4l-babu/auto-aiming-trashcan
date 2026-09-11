# auto-aiming-trashcan

A trashcan that lines itself up to catch your rubbish, then slams its lid shut
at the last moment and refuses it.

## How it works

Two boards on the same WiFi:

```
USB camera -> UNO Q (YOLOX-nano detection) --WiFi/HTTP--> ESP32 -> wheels + lid servo
```

The UNO Q watches for people and for objects someone might throw. It tracks
whatever is incoming and tells the ESP32 which way to steer, so the bin makes
a convincing show of getting under the throw. When the object's apparent size
says it is about to arrive, the UNO Q sends `THROWN` and the ESP32 shuts the
lid in 180 ms. Four seconds later the lid reopens, ready for the next person.
The same moment, a refusal sound streams live from the UNO Q's storage to the
ESP32's speaker - kept off the ESP32's tiny flash so clips can be as long as
you like.

## What's here

| Path | What it is |
|---|---|
| `hardware/uno_q_app/` | Arduino UNO Q app: USB camera, YOLOX-nano detection, target picking, throw detection, audio streaming, web UI |
| `hardware/esp32_actuators/` | ESP32 firmware: L298N wheels, lid servo on GPIO 17, MAX98357A speaker, WiFi + serial command interface, phone control page |
| `config.py`, `environment.py`, `main.py`, `physics.py`, `simulation.py`, `trajectory.py`, `trash_can.py` | PyBullet physics simulation of the catching problem - no hardware involved, independent of the two folders above |

## Bring-up order

1. **ESP32 first.** `cp src/secrets.h.example src/secrets.h`, fill in your
   WiFi, `pio run -t upload`, then read the IP it prints at boot.
2. **Check it from your phone.** Open that IP in a browser. Use the lid slider
   to find your real open/closed servo angles, set them in `main.cpp`, reflash.
3. **Then the UNO Q.** Open `hardware/uno_q_app/` in Arduino App Lab and
   deploy. Its web UI shows the last command sent to the ESP32 and the reply -
   check that before touching any detection tuning.

Each board is useful alone: the ESP32 takes manual commands from the phone
page with no UNO Q present, and the UNO Q's web UI shows detections with no
ESP32 present.

## Running the simulation

```bash
python main.py
```
