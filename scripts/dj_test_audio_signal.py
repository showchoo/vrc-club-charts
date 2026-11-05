"""Verify a distinctive four-tone audio test sequence in private PCM data.

This is an OFFLINE signal detector, not evidence of VRChat operation on its
own. An independent, permissioned recording of an owner-controlled test
session is required to draw even a limited audio-playback conclusion.
"""
from __future__ import annotations

from array import array
import math
import sys

SAMPLE_RATE = 8000
TONES = (523, 659, 784, 1046)
TONE_DURATION = 2.0
WINDOW = 6000
HOP = 4000
MIN_NORMALIZED_POWER = 0.09
MIN_PEAK_RATIO = 2.5


def _normalized_power(samples: array, frequency: int) -> float:
    """Goertzel energy, normalized against the same window's total energy."""
    n = len(samples)
    energy = sum(float(value) * value for value in samples)
    if energy < n * 16.0:
        return 0.0
    coefficient = 2.0 * math.cos(2.0 * math.pi * frequency / SAMPLE_RATE)
    prev = 0.0
    prev2 = 0.0
    for value in samples:
        current = value + coefficient * prev - prev2
        prev2, prev = prev, current
    power = prev * prev + prev2 * prev2 - coefficient * prev * prev2
    return max(0.0, power / (n * energy))


def tone_windows(pcm: bytes) -> list[dict]:
    if len(pcm) % 2 or len(pcm) > SAMPLE_RATE * 2 * 35:
        raise ValueError("Expected bounded 16-bit mono PCM samples")
    sample_buffer = array("h")
    sample_buffer.frombytes(pcm)
    if sys.byteorder != "little":
        sample_buffer.byteswap()
    windows = []
    for offset in range(0, len(sample_buffer) - WINDOW + 1, HOP):
        frame = sample_buffer[offset:offset + WINDOW]
        strengths = sorted(
            ((hz, _normalized_power(frame, hz)) for hz in TONES),
            key=lambda x: x[1], reverse=True,
        )
        best, strength = strengths[0]
        second = strengths[1][1]
        detected = (
            best if strength >= MIN_NORMALIZED_POWER
            and strength >= max(second, 0.0001) * MIN_PEAK_RATIO
            else None
        )
        windows.append({
            "second": round(offset / SAMPLE_RATE, 2),
            "toneHz": detected, "strength": round(strength, 4),
        })
    return windows


def match_test_sequence(pcm: bytes) -> dict:
    windows = tone_windows(pcm)
    observed = {tone for row in windows if (tone := row["toneHz"]) is not None}
    found = False
    # The source clip has 2-second steps; an independent recording may start
    # at an arbitrary offset, with some lost or delayed samples.
    for row in windows:
        if row["toneHz"] != TONES[0]:
            continue
        begin = row["second"]
        if all(
            any(item["toneHz"] == tone
                and abs(item["second"] - (begin + index * TONE_DURATION)) <= 0.75
                for item in windows)
            for index, tone in enumerate(TONES)
        ):
            found = True
            break
    return {
        "matched": found,
        "testPattern": "four_step_523_659_784_1046_Hz_2s_each",
        "totalSampleWindows": len(windows),
        "frequenciesDetected": sorted(observed),
        "thresholdNormalizedPower": MIN_NORMALIZED_POWER,
        "actualVRChatSourceAuthenticated": False,
        "otherVisitorAudioVerified": False,
        "liveStreamingVerified": False,
        "equipmentFunctionalityVerified": False,
    }
