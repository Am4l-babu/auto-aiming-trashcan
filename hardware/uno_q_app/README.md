# Object & Human Detection - UNO Q app

The eyes of the machine. A USB camera feed is analyzed on the UNO Q's
Linux/Qualcomm side with a YOLOX-nano model (COCO classes - person plus 79
everyday objects). The UNO Q decides what to aim at and when rubbish is
incoming, then tells the ESP32 to move.

Actuation lives on a separate board: see [`../esp32_actuators/`](../esp32_actuators/).
Both boards sit on the same WiFi, so nothing is tethered.

```
USB camera -> UNO Q (YOLOX-nano, this folder) --WiFi/HTTP--> ESP32 -> wheels + lid servo
```

## Layout

| Path | Runs on | Purpose |
|---|---|---|
| `python/main.py` | Linux side (App Lab Python brick) | Detection, target selection, throw detection, commands to the ESP32, audio streaming, web UI |
| `python/sounds/` | Linux side | Your WAV files (gitignored) - streamed live to the ESP32's speaker, see its README |
| `sketch/sketch.ino` | STM32 MCU side | Nothing - actuation is on the ESP32. Kept as the place to add UNO Q-attached hardware later |
| `assets/` | Linux side | Web UI frontend (live feed + bounding boxes) |
| `app.yaml` | App Lab | Declares the bricks this app uses (`video_object_detection`, `web_ui`) |

## How a throw becomes a slammed lid

1. `VideoObjectDetection` reports one `bounding_box_xyxy` per detected object per frame.
2. `_pick_target()` picks what to chase. Incoming rubbish outranks people: if
   anything in the `THROWABLE` set is visible the machine aims at that, so it
   makes a show of lining up to catch it. Otherwise it tracks the most
   confident person.
3. Normal case: the target's box center becomes a horizontal offset in
   `[-1, 1]` and goes out as `AIM <offset>`, steering the wheels.
4. When a throwable object's box covers `THROW_AREA_FRAC` of the frame it is
   close enough to count as actually thrown - `THROWN` goes out and the ESP32
   slams the lid. Single camera, no depth, so apparent size is the proxy for
   "incoming".
5. `THROW_COOLDOWN_SEC` (6 s) covers the ESP32's 4 s shut-and-reopen cycle so
   one throw cannot re-trigger the lid repeatedly.
6. The same moment `THROWN` goes out, `play_sound(THROWN_SOUND)` queues
   `sounds/denied.wav` for streaming to the ESP32's speaker - silently
   skipped if that file does not exist, so a missing sound effect can never
   be the reason the refusal itself fails to happen.

Commands and audio each go out on their own worker thread and are dropped if
their queue backs up - a slow or missing ESP32 slows nothing down, a stale
aim update is worth less than a fresh one, and a multi-minute clip must never
make aim updates pile up behind it.

## Audio

WAV files in `python/sounds/` are streamed - not copied - to the ESP32's
speaker over a raw TCP socket (port 8081), so there is no practical size
limit; they live on the UNO Q's own storage, which is orders of magnitude
bigger than the ESP32's flash. See `python/sounds/README.md` for the file
format and `play_sound(name)` / `GET /play?name=<name>` to trigger one
manually. `/detections` shows the last clip played and its status under
`audio` - check that first if a sound doesn't play.

## Tuning

| Constant | Meaning |
|---|---|
| `ESP32_HOST` | Where to send commands. Defaults to `http://trashcan.local`; override with the `ESP32_HOST` env var if mDNS is flaky - use the raw IP the ESP32 prints at boot |
| `THROW_AREA_FRAC` | 0.06. Raise it if the lid slams too early, lower it if it slams too late |
| `AIM_DEADZONE` | 0.15. Widen it if the trashcan oscillates around a centered target |
| `THROWABLE` | Which COCO classes count as rubbish rather than scenery |
| `debounce_sec` | 1.0 on the detector, so aim updates cap at ~1/sec. Lower it if the machine reacts too slowly |
| `ESP32_AUDIO_HOST` | Where to stream audio. Defaults to the host part of `ESP32_HOST`; override separately if audio and commands ever need different addresses |
| `THROWN_SOUND` | Clip name (without `.wav`) played automatically on every throw refusal |

## Running it

Open this folder in Arduino App Lab with the UNO Q connected and deploy. The
web UI serves the annotated camera feed, plus `/detections` (includes the
last command sent to the ESP32 and its reply, and the last audio clip played -
the first place to look when nothing moves or nothing plays), `/confidence`,
`/open` and `/play`.

Flash and power the ESP32 first, and confirm `http://trashcan.local/` loads
from your phone. If the web UI shows `unreachable` under `esp32`, the two
boards are not seeing each other and no amount of detection tuning will help.
