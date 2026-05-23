#!/Volumes/ext/moss-tts/env/bin/python
"""Re-synthesize sentence #2 ("abu dhabi") with stricter caps to prevent
the runaway babble that occurred on the first pass (327s output).

Strategy: try several attempts with smaller max_new_tokens, pick the
shortest non-trivial result, then re-concat all three gap versions.
"""
from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

from gradio_client import Client, handle_file

OUT_DIR = Path("/Users/chatsign/Desktop/cs58_sentences_20260514")
WAV_DIR = OUT_DIR / "wavs"
TARGET = WAV_DIR / "002.wav"
TEXT = "abu dhabi"
REF = "/Volumes/ext/moss-tts/voices/fiabo/reference.wav"
SERVICE_URL = "http://127.0.0.1:7860/"
GAPS = {"short": 0.3, "medium": 0.6, "long": 1.0}

# A few short attempts; keep the one closest to a reasonable duration (1-3s).
ATTEMPTS = [
    dict(max_new_tokens=256, temperature=0.9, top_p=0.8, top_k=25),
    dict(max_new_tokens=256, temperature=1.2, top_p=0.8, top_k=25),
    dict(max_new_tokens=384, temperature=1.0, top_p=0.9, top_k=30),
]


def wav_duration(p: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(p)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip() or 0)


def synth_attempt(client: Client, params: dict, out: Path) -> float:
    audio_path, _status = client.predict(
        text=TEXT,
        reference_audio=handle_file(REF),
        mode_with_reference="Clone",
        duration_control_enabled=False,
        duration_tokens=1,
        repetition_penalty=1.0,
        **params,
        api_name="/lambda",
    )
    try:
        shutil.move(audio_path, out)
    except OSError:
        shutil.copy(audio_path, out)
    return wav_duration(out)


def main() -> int:
    print(f"removing bad 002.wav (duration before: {wav_duration(TARGET):.1f}s)", flush=True)
    TARGET.unlink(missing_ok=True)

    client = Client(SERVICE_URL, verbose=False)

    best: tuple[float, Path] | None = None
    candidates_dir = WAV_DIR / "_002_candidates"
    candidates_dir.mkdir(exist_ok=True)

    for i, params in enumerate(ATTEMPTS, start=1):
        cand = candidates_dir / f"try_{i}.wav"
        t0 = time.monotonic()
        try:
            dur = synth_attempt(client, params, cand)
        except Exception as e:  # noqa: BLE001
            print(f"  try {i} FAIL {e!r}", flush=True)
            continue
        print(f"  try {i} {params} -> {dur:.2f}s in {time.monotonic()-t0:.1f}s", flush=True)
        # Pick first candidate that's plausible (0.4-4s for "abu dhabi"),
        # else fall back to the shortest.
        if 0.4 <= dur <= 4.0:
            best = (dur, cand)
            break
        if best is None or dur < best[0]:
            best = (dur, cand)

    if best is None:
        print("ALL ATTEMPTS FAILED", flush=True)
        return 1

    dur, cand = best
    shutil.copy(cand, TARGET)
    print(f"picked {cand.name} ({dur:.2f}s) -> 002.wav", flush=True)

    # Re-concat all three gap versions
    wavs = sorted(WAV_DIR.glob("[0-9][0-9][0-9].wav"))
    print(f"re-concatenating {len(wavs)} wavs", flush=True)
    for label, gap in GAPS.items():
        silence = OUT_DIR / f"_silence_{label}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
             "-t", f"{gap}", "-c:a", "pcm_s16le", str(silence)],
            check=True,
        )
        list_path = OUT_DIR / f"_concat_{label}.txt"
        with open(list_path, "w") as f:
            for j, w in enumerate(wavs):
                f.write(f"file '{w.resolve()}'\n")
                if j < len(wavs) - 1:
                    f.write(f"file '{silence.resolve()}'\n")
        full_wav = OUT_DIR / f"cs58_{label}.wav"
        full_mp3 = OUT_DIR / f"cs58_{label}.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-f", "concat", "-safe", "0", "-i", str(list_path),
             "-c", "copy", str(full_wav)],
            check=True,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-i", str(full_wav),
             "-codec:a", "libmp3lame", "-q:a", "0", str(full_mp3)],
            check=True,
        )
        silence.unlink(missing_ok=True)
        list_path.unlink(missing_ok=True)
        print(f"  [{label}] {gap}s gap: "
              f"{full_wav.name} ({full_wav.stat().st_size//1024}KB) + "
              f"{full_mp3.name} ({full_mp3.stat().st_size//1024}KB)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
