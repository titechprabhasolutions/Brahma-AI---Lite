import math
from typing import Iterable, Optional


def estimate_gesture_state(
    landmarks: Optional[Iterable[tuple[float, float, float]]],
    prev_pinch: bool = False,
) -> dict:
    """Translate hand landmarks into a simplified gesture state.

    The implementation intentionally keeps the logic lightweight so it can be
    reused in tests and in the UI without depending on Qt.
    """
    if not landmarks or len(landmarks) < 21:
        return {
            "hand_detected": False,
            "cursor": None,
            "pinch": False,
            "pinch_triggered": False,
        }

    # landmarks are expected as normalized coordinates (x,y,z) in range [0..1]
    index_tip = landmarks[8]
    thumb_tip = landmarks[4]
    dx = thumb_tip[0] - index_tip[0]
    dy = thumb_tip[1] - index_tip[1]
    distance = math.hypot(dx, dy)
    pinch = distance < 0.06

    # Return normalized cursor (0..1) for easier mapping to any screen
    cursor = (float(index_tip[0]), float(index_tip[1]))

    return {
        "hand_detected": True,
        "cursor": cursor,
        "pinch": pinch,
        "pinch_triggered": bool(pinch and not prev_pinch),
    }
