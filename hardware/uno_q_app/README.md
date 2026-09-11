# Object & Human Detection - UNO Q hardware app

Real-hardware counterpart to the PyBullet simulation in the repo root. Runs
on an Arduino UNO Q: a USB camera feed is analyzed on the Linux/Qualcomm
side with a YOLOX-nano model (COCO classes - person plus 79 everyday
objects), and the result steers two DC motors on the STM32 MCU side so the
trashcan turns toward whatever it's looking at.

## Layout

| Path | Runs on | Purpose |
|---|---|---|
| `python/main.py` | Linux side (App Lab Python brick) | Camera + object detection, web UI, picks a target and reports its horizontal offset |
| `sketch/sketch.ino` | STM32 MCU side | Receives the offset over the Bridge and drives the motors |
| `assets/` | Linux side | Web UI frontend (live feed + bounding boxes) |
| `app.yaml` | App Lab | Declares the bricks this app uses (`video_object_detection`, `web_ui`) |

## How detection reaches the motors

1. `VideoObjectDetection` (`arduino.app_bricks.video_objectdetection`) connects to the onboard model
   runner and reports one `bounding_box_xyxy` per detected object per frame.
2. `on_detections()` in `python/main.py` picks a target - the highest-confidence
   `person`, or failing that, the highest-confidence detection of any class -
   and turns its bounding-box center into a horizontal offset in `[-1, 1]`
   (0 = dead-center of frame).
3. `set_target(offset, present)`, decorated with `@notify()`, sends that offset
   to the MCU over the Bridge (fire-and-forget, matches
   `Bridge.provide_safe("set_target", ...)` in the sketch).
4. The sketch's `loop()` reads the last offset and steers: turn toward a
   target left/right of center, drive straight if centered, stop if nothing
   has been seen recently (`TARGET_TIMEOUT_MS`) - fail-safe against a stalled
   Python side.

## Before you flash this

- **Pin names are unverified.** `D2`/`D3`/`D4`/`D5` in `sketch.ino` follow the
  standard Arduino Uno digital header convention but haven't been confirmed
  against real UNO Q hardware or run on the board. Check them against the
  official UNO Q pinout and your actual H-bridge wiring (IN1-IN4) before
  connecting motors.
- **No PWM/speed control.** Steering is bang-bang (full speed one side,
  reverse the other) - a bring-up starting point, not a tuned drive system.
- **Confidence/debounce** are tuned for the web UI (`confidence=0.5`,
  `debounce_sec=1.0` in `python/main.py`), which caps aim updates at ~1/sec.
  If the trashcan reacts too slowly, lower `debounce_sec` on a second
  `VideoObjectDetection` instance dedicated to aiming, separate from the one
  feeding the web UI.
- **AIM_DEADZONE** (0.15) stops the trashcan hunting left/right when a target
  is already roughly centered - widen it if you see oscillation.

## Running it

Open this folder in Arduino App Lab, connect the UNO Q over USB, and deploy.
The web UI (from the `web_ui` brick) serves the live annotated camera feed
plus `/detections` and `/confidence` endpoints for debugging without needing
the motors connected at all.
