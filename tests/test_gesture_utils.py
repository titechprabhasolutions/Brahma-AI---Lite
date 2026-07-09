from gesture_utils import estimate_gesture_state


def test_estimate_gesture_state_reports_no_hand_when_missing_landmarks():
    state = estimate_gesture_state(None, (1920, 1080))
    assert state["hand_detected"] is False
    assert state["cursor"] is None


def test_estimate_gesture_state_detects_pinch_trigger():
    landmarks = [(0.2, 0.2, 0.0)] * 21
    landmarks[4] = (0.2, 0.2, 0.0)
    landmarks[8] = (0.2, 0.2, 0.0)
    state = estimate_gesture_state(landmarks, (1920, 1080), False)
    assert state["pinch"] is True
    assert state["pinch_triggered"] is True
