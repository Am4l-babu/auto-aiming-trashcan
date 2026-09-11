# ESP32 actuators

Drives the wheels (L298N) and the lid servo. Takes commands over WiFi from
the UNO Q, which does the camera work. Serial accepts the same commands as a
fallback and for bench testing.

## The gag

The lid sits open, inviting. When the UNO Q decides something has actually
been thrown at the bin, it sends `THROWN`, and the lid slams shut in 180 ms
and refuses the rubbish. Four seconds later it reopens to bait the next
person.

## Commands

| Command | Effect |
|---|---|
| `AIM <offset>` | Steer the wheels. `-1.0` = target hard left, `+1.0` = hard right, `0` = straight ahead |
| `THROWN` | Slam the lid shut and stop the wheels |
| `OPEN` | Reopen the lid |
| `STOP` | Stop the wheels |
| `LID <angle>` | Drive the servo to a raw angle - use this to find your real open/closed angles |
| `BEEP` | Play a short built-in test tone through the speaker |
| `PLAY <name>` | Play `/<name>.wav` from this board's own flash (see Audio below) |
| `PING` | Replies `PONG` |

Over WiFi: `GET http://trashcan.local/cmd?c=THROWN` (or use the board's IP).
`GET /` serves a control page that works from a phone - buttons plus a lid
angle slider, which is the easy way to calibrate the servo while standing at
the machine. `GET /status` returns lid angle, current aim and RSSI as JSON.

Over serial: type the command at 115200 baud.

## Wiring

| Signal | Pin |
|---|---|
| L298N ENA / ENB | 18 / 19 |
| L298N IN1 / IN2 (motor A) | 27 / 26 |
| L298N IN3 / IN4 (motor B) | 25 / 33 |
| Lid servo signal | 17 |
| MAX98357A DIN / BCLK / LRC | 23 / 22 / 21 |

The servo needs its own 5 V supply - not the ESP32's 3V3 pin - with grounds
tied together. Same for the motor supply and the speaker amp's VIN: shared
rails brown the board out and drop it off WiFi mid-demo.

## Audio

Two ways to make sound, for two different sizes of clip:

**Small clips baked onto this board** - `PLAY <name>` plays `/<name>.wav`
from this board's own LittleFS flash partition. Good for a handful of short
effects; the partition only has a couple MB, so this is not for anything
long. Upload clips with:

```bash
mkdir -p data && cp your_clip.wav data/your_clip.wav
pio run -t uploadfs --upload-port COM6
```

**Large or many clips, kept on the UNO Q** - the UNO Q has real storage and
keeps the actual files; it streams raw PCM to this board's TCP port 8081
live, so nothing is ever copied onto the ESP32 and there is no size limit
beyond the UNO Q's own disk. See `hardware/uno_q_app/python/sounds/` for
where those files go and `stream_test.py` in this folder for a minimal
example of the wire protocol (5-byte header, then raw 16-bit PCM until the
socket closes) if you want to stream from something other than the UNO Q.

Streaming runs on the ESP32's second CPU core, independent of the motor/servo
loop - a multi-minute clip playing will never delay the wheels stopping on
command.

## Build

```bash
cp src/secrets.h.example src/secrets.h   # then fill in your WiFi
pio run -t upload
pio device monitor                        # prints the board's IP on boot
```

`secrets.h` is gitignored so WiFi credentials never reach the repo.

## Calibration

1. Flash, open the serial monitor, note the IP printed at boot.
2. Open that IP on your phone, drag the lid slider to find the angle where
   the lid is fully open, then where it is fully shut.
3. Put those two numbers in `LID_OPEN_ANGLE` / `LID_CLOSED_ANGLE` and reflash.

`MOTOR_B_TRIM` compensates for the two motors running at different speeds at
equal duty. Raise it above 1.00 until both wheels turn at the same rate.
