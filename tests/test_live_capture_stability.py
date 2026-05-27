"""StabilityTracker — pure-logic gate for 'when should OCR fire?'."""
from live_capture import StabilityTracker


def test_first_observation_is_ongoing():
    tracker = StabilityTracker(stable_frames=3)
    assert tracker.observe(b"A") == "ongoing"


def test_reaches_stable_change_after_n_identical():
    tracker = StabilityTracker(stable_frames=3)
    assert tracker.observe(b"A") == "ongoing"
    assert tracker.observe(b"A") == "ongoing"
    assert tracker.observe(b"A") == "stable_change"


def test_further_identical_observations_after_stable_are_no_change():
    tracker = StabilityTracker(stable_frames=3)
    for _ in range(3):
        tracker.observe(b"A")
    # Now A is the emitted hash. More A's should not re-fire.
    assert tracker.observe(b"A") == "no_change"
    assert tracker.observe(b"A") == "no_change"


def test_flicker_resets_seen_count():
    tracker = StabilityTracker(stable_frames=3)
    tracker.observe(b"A")
    tracker.observe(b"A")
    # Flicker — different hash, count resets.
    assert tracker.observe(b"B") == "ongoing"
    assert tracker.observe(b"A") == "ongoing"
    assert tracker.observe(b"A") == "ongoing"
    assert tracker.observe(b"A") == "stable_change"


def test_stable_change_to_different_value():
    tracker = StabilityTracker(stable_frames=2)
    tracker.observe(b"A")
    assert tracker.observe(b"A") == "stable_change"
    # Now content changes and stabilizes on B.
    assert tracker.observe(b"B") == "ongoing"
    assert tracker.observe(b"B") == "stable_change"


def test_empty_rearm_clears_last_emitted():
    tracker = StabilityTracker(stable_frames=2)
    tracker.observe(b"A")
    assert tracker.observe(b"A") == "stable_change"
    tracker.empty_rearm()  # OCR returned no signatures
    # Same hash should fire again now (looking-away-then-back case).
    assert tracker.observe(b"A") == "ongoing"
    assert tracker.observe(b"A") == "stable_change"


def test_reset_clears_all_state():
    tracker = StabilityTracker(stable_frames=2)
    tracker.observe(b"A")
    tracker.observe(b"A")  # stable_change
    tracker.reset()
    # Both last_seen and last_emitted are cleared — A is fresh again.
    assert tracker.observe(b"A") == "ongoing"
    assert tracker.observe(b"A") == "stable_change"
