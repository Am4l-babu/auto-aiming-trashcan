import os
import queue
import socket
import struct
import threading
import urllib.parse
import urllib.request
import wave
from collections import deque
from datetime import datetime, UTC
from pathlib import Path

from arduino.app_utils import App
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_objectdetection import VideoObjectDetection

# ---- ESP32 actuator link -----------------------------------------------------
# The ESP32 drives the wheels and the lid servo. It joins the same WiFi and
# serves commands over HTTP - see hardware/esp32_actuators/src/main.cpp.
ESP32_HOST = os.environ.get("ESP32_HOST", "http://trashcan.local")
ESP32_TIMEOUT_SEC = 1.0

# Audio streaming: clips live here on the UNO Q's own storage (plenty of
# room for minutes of audio, unlike the ESP32's flash) and are streamed live
# to the ESP32's speaker over a raw TCP socket - see the "Audio streaming"
# section in hardware/esp32_actuators/src/main.cpp for the wire protocol.
ESP32_AUDIO_HOST = os.environ.get("ESP32_AUDIO_HOST", ESP32_HOST.split("://")[-1])
ESP32_AUDIO_PORT = 8081
SOUNDS_DIR = Path(__file__).parent / "sounds"

# Played automatically when the lid slams on a throw, if the file exists.
# Silently skipped otherwise - a missing sound effect should never be the
# reason the throw-refusal itself fails to happen.
THROWN_SOUND = "denied"

# How long after the last "person" sighting we still consider a human present.
PERSON_HOLD_SEC = 3.0
MAX_RECENT = 20

# Offsets smaller than this (fraction of frame width, -1..1) count as
# "centered enough" - stops the trashcan hunting left/right for a target that
# is already roughly in front of it.
AIM_DEADZONE = 0.15

# COCO classes a person might plausibly lob at a bin. Anything in here is
# treated as incoming rubbish rather than as scenery.
THROWABLE = {
    "bottle", "cup", "wine glass", "bowl", "banana", "apple", "orange",
    "sandwich", "donut", "cake", "sports ball", "book", "cell phone",
    "remote", "scissors", "toothbrush", "fork", "knife", "spoon",
}

# When a throwable object's bounding box covers at least this fraction of the
# frame it is close enough to count as actually thrown at us - that is the cue
# to slam the lid. Single camera, no depth: apparent size is the proxy for
# "incoming". Raise it if the lid slams too early, lower it if it slams late.
THROW_AREA_FRAC = 0.06

# The lid stays shut for ~4s on the ESP32 side; do not re-trigger during that.
THROW_COOLDOWN_SEC = 6.0

ui = WebUI()

# YoloX-nano is trained on COCO: it detects "person" plus 79 everyday object classes,
# so a single model covers both human detection and generic object detection.
detector = VideoObjectDetection(confidence=0.5, debounce_sec=1.0)

_res = detector._camera.resolution or (640, 480)
FRAME_WIDTH, FRAME_HEIGHT = _res[0], _res[1]
FRAME_AREA = float(FRAME_WIDTH * FRAME_HEIGHT)

lock = threading.Lock()
recent = deque(maxlen=MAX_RECENT)
last_person_seen = None
last_throw_at = None
last_command = "none"

# Commands go out on a worker thread: a slow or dead ESP32 must never stall
# the detection loop.
_commands: "queue.Queue[str]" = queue.Queue(maxsize=8)


def _command_worker():
    global last_command
    while True:
        cmd = _commands.get()
        url = f"{ESP32_HOST}/cmd?c={urllib.parse.quote(cmd)}"
        try:
            with urllib.request.urlopen(url, timeout=ESP32_TIMEOUT_SEC) as resp:
                reply = resp.read().decode("utf-8", "replace").strip()
        except Exception as e:
            reply = f"unreachable ({e})"
        with lock:
            last_command = f"{cmd} -> {reply}"


threading.Thread(target=_command_worker, name="esp32-commands", daemon=True).start()


def send(cmd: str):
    """Queues a command for the ESP32, dropping it if the queue is backed up.
    Aim updates are worthless once stale, so dropping beats blocking."""
    try:
        _commands.put_nowait(cmd)
    except queue.Full:
        pass


# Audio plays on its own worker, separate from _commands: a multi-minute
# clip must never make AIM updates back up behind it.
_audio_queue: "queue.Queue[str]" = queue.Queue(maxsize=2)
last_audio = "none"


def _stream_wav(path: Path) -> str:
    with wave.open(str(path), "rb") as w:
        channels = w.getnchannels()
        rate = w.getframerate()
        width = w.getsampwidth()
        if width != 2:
            return f"ERR {path.name} is not 16-bit PCM (got {width * 8}-bit)"
        if channels not in (1, 2):
            return f"ERR {path.name} has unsupported channel count {channels}"

        header = struct.pack("<IB", rate, channels)
        with socket.create_connection((ESP32_AUDIO_HOST, ESP32_AUDIO_PORT), timeout=5) as s:
            s.sendall(header)
            chunk = w.readframes(4096)
            while chunk:
                s.sendall(chunk)
                chunk = w.readframes(4096)
        return f"OK streamed {path.name} ({rate}Hz, {channels}ch)"


def _audio_worker():
    global last_audio
    while True:
        name = _audio_queue.get()
        path = SOUNDS_DIR / f"{name}.wav"
        try:
            if not path.exists():
                last_audio = f"{name} -> ERR file not found: {path}"
                continue
            last_audio = f"{name} -> {_stream_wav(path)}"
        except Exception as e:
            last_audio = f"{name} -> ERR {e}"


threading.Thread(target=_audio_worker, name="esp32-audio", daemon=True).start()


def play_sound(name: str):
    """Queues a clip by name (sounds/<name>.wav) for streaming to the ESP32.
    Drops the request if a clip is already queued - never blocks the caller,
    and never worth playing two clips on top of each other anyway."""
    try:
        _audio_queue.put_nowait(name)
    except queue.Full:
        pass


def _area_frac(bbox) -> float:
    x1, y1, x2, y2 = bbox
    return (abs(x2 - x1) * abs(y2 - y1)) / FRAME_AREA if FRAME_AREA else 0.0


def _offset(bbox) -> float:
    """Horizontal position of a box center, normalized to -1 (left) .. +1 (right)."""
    x1, _, x2, _ = bbox
    center_x = (x1 + x2) / 2.0
    offset = (center_x / FRAME_WIDTH) * 2.0 - 1.0
    return 0.0 if abs(offset) < AIM_DEADZONE else offset


def _flatten(detections: dict) -> list:
    out = []
    for label, values in detections.items():
        for value in values:
            out.append({"label": label, **value})
    return out


def _pick_target(flat: list) -> dict | None:
    """Incoming rubbish outranks people: the machine aims at what is being
    thrown so it can make a show of catching it, then refuse at the last
    moment. Falls back to the most confident person, then to anything."""
    throwables = [d for d in flat if d["label"] in THROWABLE]
    if throwables:
        return max(throwables, key=lambda d: _area_frac(d["bounding_box_xyxy"]))
    people = [d for d in flat if d["label"] == "person"]
    if people:
        return max(people, key=lambda d: d["confidence"])
    return max(flat, key=lambda d: d["confidence"]) if flat else None


def on_detections(detections: dict):
    global last_person_seen, last_throw_at
    now = datetime.now(UTC)

    with lock:
        for label, values in detections.items():
            for value in values:
                recent.appendleft(
                    {
                        "label": label,
                        "confidence": value.get("confidence"),
                        "is_person": label == "person",
                        "timestamp": now.isoformat(),
                    }
                )
            if label == "person":
                last_person_seen = now
        throw_ready = (
            last_throw_at is None
            or (now - last_throw_at).total_seconds() >= THROW_COOLDOWN_SEC
        )

    flat = _flatten(detections)
    target = _pick_target(flat)
    if target is None:
        send("STOP")
        return

    bbox = target["bounding_box_xyxy"]

    # Close enough, and it is something someone would actually throw: refuse it.
    if (
        throw_ready
        and target["label"] in THROWABLE
        and _area_frac(bbox) >= THROW_AREA_FRAC
    ):
        with lock:
            last_throw_at = now
        send("THROWN")
        play_sound(THROWN_SOUND)
        return

    send(f"AIM {_offset(bbox):.3f}")


detector.on_detect_all(on_detections)


def get_detections():
    now = datetime.now(UTC)
    with lock:
        person_present = (
            last_person_seen is not None
            and (now - last_person_seen).total_seconds() <= PERSON_HOLD_SEC
        )
        return {
            "person_present": person_present,
            "last_person_seen": last_person_seen.isoformat() if last_person_seen else None,
            "last_throw": last_throw_at.isoformat() if last_throw_at else None,
            "esp32": {"host": ESP32_HOST, "last_command": last_command},
            "audio": {"host": ESP32_AUDIO_HOST, "port": ESP32_AUDIO_PORT, "last_clip": last_audio},
            "detections": list(recent),
        }


def set_confidence(value: float):
    detector.override_threshold(value)
    return {"confidence": value}


def lid_open():
    send("OPEN")
    return {"sent": "OPEN"}


def play(name: str):
    play_sound(name)
    return {"queued": name}


ui.expose_api("GET", "/detections", get_detections)
ui.expose_api("GET", "/confidence", set_confidence)
ui.expose_api("GET", "/open", lid_open)
ui.expose_api("GET", "/play", play)

App.run()
