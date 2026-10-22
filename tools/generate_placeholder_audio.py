#!/usr/bin/env python3
"""THE LAST SIN: The Sin-Eater - M1

Generates the PLACEHOLDER ambience/foley set (TLS-SND-002/010/012) as real
.wav files under 04_Audio/, using only the Python standard library.

Honesty note: these are procedurally synthesized placeholders (filtered
noise, decaying partials) - NOT field recordings and NOT final assets.
They exist so the audio import path (02_import_and_calibrate.bat) has a
real, licensed-by-construction set to exercise, and so the slice is audible
before any recording session. The final ambience/foley is an M3 concern per
the milestone plan. The in-engine runtime also generates equivalent audio
procedurally (TLSProceduralAudio) so the slice works even before import.

Run:  python3 tools/generate_placeholder_audio.py [--force]
Output: 04_Audio/{ambience,foley,ui}/*.wav + 04_Audio/manifest_audio.json
"""

import json
import math
import os
import random
import struct
import sys
import wave

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
AUDIO_ROOT = os.path.join(REPO_ROOT, "04_Audio")

SAMPLE_RATE = 44100


def write_wav(path, samples):
    """16-bit mono PCM."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for s in samples:
            s = max(-1.0, min(1.0, s))
            frames += struct.pack("<h", int(s * 32767.0))
        handle.writeframes(bytes(frames))


def synth_wind(seconds=6.0, seed=1337):
    """Low-passed noise with a slow breathing LFO (valley wind)."""
    rng = random.Random(seed)
    out = []
    low = 0.0
    for i in range(int(seconds * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        white = rng.uniform(-1.0, 1.0)
        low = low * 0.985 + white * 0.015          # one-pole low-pass
        breath = 0.55 + 0.45 * math.sin(t * 0.6 * 2.0 * math.pi / 6.0)
        # gentle fade in/out so the loop point is soft
        edge = min(1.0, t / 0.5, (seconds - t) / 0.5)
        out.append(low * 4.0 * breath * edge)
    return out


def synth_rain(seconds=6.0, seed=7331):
    """High-passed hiss with sparse droplet ticks."""
    rng = random.Random(seed)
    out = []
    prev = 0.0
    for i in range(int(seconds * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        white = rng.uniform(-1.0, 1.0)
        filtered = white - 0.15 * prev                            # high-pass
        prev = white
        edge = min(1.0, t / 0.5, (seconds - t) / 0.5)
        out.append(filtered * 0.55 * edge)
    # sparse droplets
    next_drop = 0.0
    for i in range(len(out)):
        t = i / SAMPLE_RATE
        if t >= next_drop:
            next_drop = t + rng.uniform(0.02, 0.12)
            freq = rng.uniform(1800.0, 3600.0)
            for k in range(0, 220):
                if i + k < len(out):
                    decay = math.exp(-k / 40.0)
                    out[i + k] += 0.22 * decay * math.sin(2.0 * math.pi * freq * k / SAMPLE_RATE)
    return out


def synth_footstep(seconds=0.35, seed=42):
    """A short gravel-on-stone scuff (band-passed noise burst)."""
    rng = random.Random(seed)
    out = []
    prev = 0.0
    for i in range(int(seconds * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        white = rng.uniform(-1.0, 1.0)
        band = white - 0.6 * prev
        prev = white
        env = math.exp(-t * 26.0) * min(1.0, t / 0.004)
        out.append(band * 0.9 * env)
    return out


def synth_page_turn(seconds=0.8, seed=99):
    """Paper rasp: rising noise sweep with a soft flick."""
    rng = random.Random(seed)
    out = []
    prev = 0.0
    n = int(seconds * SAMPLE_RATE)
    for i in range(n):
        t = i / SAMPLE_RATE
        white = rng.uniform(-1.0, 1.0)
        band = white - 0.4 * prev
        prev = white
        sweep = 0.3 + 0.7 * (t / seconds)
        env = math.sin(math.pi * min(1.0, t / seconds)) ** 2
        out.append(band * 0.5 * sweep * env)
    return out


def synth_bell(seconds=2.4, seed=1):
    """St. Cynog's funeral bell: three decaying partials, low strike."""
    partials = [(138.6, 0.55, 0.8), (277.2, 0.30, 0.55), (415.3, 0.12, 0.35)]
    out = []
    for i in range(int(seconds * SAMPLE_RATE)):
        t = i / SAMPLE_RATE
        s = 0.0
        for freq, amp, decay in partials:
            s += amp * math.exp(-t * decay) * math.sin(2.0 * math.pi * freq * t)
        out.append(s * 0.8)
    return out


def main():
    force = "--force" in sys.argv

    manifest = {
        "schema": "tls.audio.placeholder.v1",
        "note": "PLACEHOLDER set - procedurally synthesized (stdlib only). "
                "Final ambience/foley is an M3 concern. In-engine runtime "
                "equivalent: TLSProceduralAudio (USoundWaveProcedural).",
        "generated_by": "tools/generate_placeholder_audio.py",
        "sample_rate": SAMPLE_RATE,
        "channels": 1,
        "format": "16-bit PCM",
        "files": [],
    }

    # filenames follow the registry's TLS-SND-<nnn>_<name> convention
    targets = [
        ("ambience/tls_snd_002_wind.wav", synth_wind, "TLS-SND-002", "wind ambience placeholder (loopable layer 1)"),
        ("ambience/tls_snd_002_rain.wav", synth_rain, "TLS-SND-002", "rain ambience placeholder (loopable layer 2)"),
        ("foley/tls_snd_010_footsteps.wav", synth_footstep, "TLS-SND-010", "stone footstep placeholder"),
        ("foley/tls_snd_012_page_turn.wav", synth_page_turn, "TLS-SND-012", "ledger page turn placeholder"),
        ("ui/tls_snd_002_bell_cynog.wav", synth_bell, "TLS-SND-002", "St. Cynog's bell placeholder (ambience layer)"),
    ]

    for relative, synth, asset_id, note in targets:
        path = os.path.join(AUDIO_ROOT, relative)
        if os.path.isfile(path) and not force:
            print("exists (kept): {}".format(relative))
            manifest["files"].append({"path": relative, "asset": asset_id, "note": note, "status": "kept"})
            continue
        samples = synth()
        write_wav(path, samples)
        size = os.path.getsize(path)
        print("wrote: {} ({} bytes, {:.1f}s)".format(relative, size, len(samples) / SAMPLE_RATE))
        manifest["files"].append(
            {"path": relative, "asset": asset_id, "note": note, "status": "generated",
             "bytes": size, "seconds": round(len(samples) / SAMPLE_RATE, 2)})

    manifest_path = os.path.join(AUDIO_ROOT, "manifest_audio.json")
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    print("manifest: {}".format(manifest_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
