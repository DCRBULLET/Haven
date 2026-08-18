import numpy as np

from haven_visuals import HavenVisuals


def test_render_frame_is_deterministic_for_same_seed_and_frame():
    first = HavenVisuals(width=320, height=180, fps=24, duration=10, seed=42)
    second = HavenVisuals(width=320, height=180, fps=24, duration=10, seed=42)

    first_frame = np.array(first.render_frame(12, "#08080c", "#7dd3c4"))
    second_frame = np.array(second.render_frame(12, "#08080c", "#7dd3c4"))

    assert first_frame.shape == (180, 320, 3)
    assert np.array_equal(first_frame, second_frame)


def test_render_frame_changes_over_time():
    visuals = HavenVisuals(width=320, height=180, fps=24, duration=10, seed=42)

    first_frame = np.array(visuals.render_frame(0, "#08080c", "#7dd3c4"), dtype=np.int16)
    later_frame = np.array(visuals.render_frame(24, "#08080c", "#7dd3c4"), dtype=np.int16)

    difference = np.mean(np.abs(first_frame - later_frame))
    assert difference > 1.0
