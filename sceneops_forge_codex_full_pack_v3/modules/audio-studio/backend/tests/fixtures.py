"""Explicit deterministic mock media fixtures; no live or cached media is represented here."""
import struct


def mock_key_pickup_wav() -> bytes:
    """One second, mono, 16-bit PCM at -6.02 dBFS peak and approximately -9.03 dBFS RMS."""
    rate = 8_000
    samples = [16_384 if index % 2 == 0 else -16_384 for index in range(rate)]
    pcm = struct.pack("<" + "h" * len(samples), *samples)
    return (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(pcm)) + pcm)


def malformed_wav() -> bytes:
    return b"RIFF\x00\x00\x00\x00WAVE"


def mock_hot_quiet_wav() -> bytes:
    rate = 8_000
    samples = [32_767, -32_767] + [0] * (rate - 2)
    pcm = struct.pack("<" + "h" * len(samples), *samples)
    return (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(pcm)) + pcm)


def mock_short_wav() -> bytes:
    rate = 8
    samples = [16_384, -16_384, 0, 0]
    pcm = struct.pack("<" + "h" * len(samples), *samples)
    return (b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
            + b"data" + struct.pack("<I", len(pcm)) + pcm)
