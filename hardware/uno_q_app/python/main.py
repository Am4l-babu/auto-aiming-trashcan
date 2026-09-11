import threading
from collections import deque
from datetime import datetime, UTC

from arduino.app_utils import App, notify
from arduino.app_bricks.web_ui import WebUI
from arduino.app_bricks.video_objectdetection import VideoObjectDetection

# How long after the last "person" sighting we still consider a human present.
PERSON_HOLD_SEC = 3.0
MAX_RECENT = 20

# Offsets smaller than this (fraction of frame width, -1..1) are treated as
# "centered enough" - stops the trashcan hunting left/right for a target that
# is already roughly in front of it.
AIM_DEADZONE = 0.15

ui = WebUI()

# YoloX-nano is trained on COCO: it detects "person" plus 79 everyday object classes,
# so a single model covers both human detection and generic object detection.
detector = VideoObjectDetection(confidence=0.5, debounce_sec=1.0)

# Frame width used to turn a bounding box into a normalized horizontal offset.
FRAME_WIDTH = detector._camera.resolution[0] if detector._camera.resolution else 640

lock = threading.Lock()
recent = deque(maxlen=MAX_RECENT)
last_person_seen = None


@notify()
def set_target(offset: float, present: bool):
    """Notifies the MCU sketch of the current aim target (fire-and-forget).

    Matches Bridge.provide_safe("set_target", ...) on the sketch side.

    Args:
        offset: horizontal position of the target's bounding-box center,
            normalized to [-1, 1] - 0 is dead-center, -1 the far left edge,
            +1 the far right edge.
        present: whether any target is currently in view.
    """
    ...


def _pick_target(detections: dict) -> dict | None:
    """Picks which detection to aim at: the highest-confidence 'person', or
    failing that, the highest-confidence detection of any class."""
    best = None
    for label, values in detections.items():
        for value in values:
            candidate = {"label": label, **value}
            if best is None:
                best = candidate
                continue
            candidate_is_person = label == "person"
            best_is_person = best["label"] == "person"
            if candidate_is_person and not best_is_person:
                best = candidate
            elif candidate_is_person == best_is_person and candidate["confidence"] > best["confidence"]:
                best = candidate
    return best


def on_detections(detections: dict):
    global last_person_seen
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

    target = _pick_target(detections)
    if target is None:
        set_target(0.0, False)
        return

    x1, _, x2, _ = target["bounding_box_xyxy"]
    center_x = (x1 + x2) / 2.0
    offset = (center_x / FRAME_WIDTH) * 2.0 - 1.0  # -1 (left) .. +1 (right)
    if abs(offset) < AIM_DEADZONE:
        offset = 0.0
    set_target(offset, True)


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
            "detections": list(recent),
        }


def set_confidence(value: float):
    detector.override_threshold(value)
    return {"confidence": value}


ui.expose_api("GET", "/detections", get_detections)
ui.expose_api("GET", "/confidence", set_confidence)

App.run()
