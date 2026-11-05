"""Four-tone calibration detector: positive/negative synthetic PCM examples."""
import math
import struct
import unittest

from scripts import dj_test_audio_signal as audio


def tone_pcm(order, *, seconds=2):
    values = []
    for frequency in order:
        for n in range(seconds * audio.SAMPLE_RATE):
            amplitude = 7000 * math.sin(2 * math.pi * frequency * n / audio.SAMPLE_RATE)
            values.append(int(amplitude))
    return struct.pack("<" + "h" * len(values), *values)


class AudioSignatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = tone_pcm(audio.TONES)

    def test_original_four_tone_sequence_detected(self):
        result = audio.match_test_sequence(self.reference)
        self.assertTrue(result["matched"])
        self.assertEqual(result["frequenciesDetected"], list(audio.TONES))
        self.assertFalse(result["actualVRChatSourceAuthenticated"])
        self.assertFalse(result["equipmentFunctionalityVerified"])

    def test_capture_with_initial_silence_detected(self):
        silent = b"\0" * (audio.SAMPLE_RATE * 2)
        result = audio.match_test_sequence(silent + self.reference)
        self.assertTrue(result["matched"])

    def test_absent_reversed_or_wrong_tones_not_detected(self):
        for pcm in [
            b"\0" * (audio.SAMPLE_RATE * 2 * 8),
            tone_pcm((440, 440, 440, 440)),
            tone_pcm(tuple(reversed(audio.TONES))),
            tone_pcm((523, 659, 784, 784)),
        ]:
            with self.subTest(case=len(pcm) + sum(pcm[:128])):
                self.assertFalse(audio.match_test_sequence(pcm)["matched"])

    def test_short_and_malformed_audio_never_reports_positive(self):
        self.assertFalse(audio.match_test_sequence(b"")["matched"])
        self.assertFalse(audio.match_test_sequence(b"\0" * 10000)["matched"])
        with self.assertRaises(ValueError):
            audio.match_test_sequence(b"x")
        with self.assertRaises(ValueError):
            audio.match_test_sequence(b"\0" * (audio.SAMPLE_RATE * 2 * 36))


if __name__ == "__main__":
    unittest.main()
