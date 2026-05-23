#!/Volumes/ext/moss-tts/env/bin/python
"""Synthesize cs58_sentences_20260514.txt with the fiabo (Fabio) voice via
MOSS-TTS, then concatenate to three mp3s with short/medium/long gaps.

Reuses the same gradio_client + reference.wav + gen-params as the prior
fabio_commencement batch (see /Users/chatsign/Desktop/fabio_commencement/_synth.py).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

from gradio_client import Client, handle_file

TEXT_FILE = Path("/Users/chatsign/Desktop/cs58_sentences_20260514.txt")
OUT_DIR = Path("/Users/chatsign/Desktop/cs58_sentences_20260514")
WAV_DIR = OUT_DIR / "wavs"
REF = "/Volumes/ext/moss-tts/voices/fiabo/reference.wav"
SERVICE_URL = "http://127.0.0.1:7860/"
GAPS = {"short": 0.3, "medium": 0.6, "long": 1.0}


def load_sentences() -> list[str]:
    return [
        line.strip()
        for line in TEXT_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def synth_all(sentences: list[str]) -> list[Path]:
    WAV_DIR.mkdir(parents=True, exist_ok=True)
    client = Client(SERVICE_URL, verbose=False)

    total_t0 = time.monotonic()
    ok = skipped = 0
    failed: list[tuple[int, str]] = []
    paths: list[Path] = []

    for i, text in enumerate(sentences, start=1):
        out = WAV_DIR / f"{i:03d}.wav"
        paths.append(out)
        if out.exists() and out.stat().st_size > 0:
            print(f"[{i:03d}/{len(sentences)}] skip", flush=True)
            skipped += 1
            continue
        t0 = time.monotonic()
        try:
            audio_path, _status = client.predict(
                text=text,
                reference_audio=handle_file(REF),
                mode_with_reference="Clone",
                duration_control_enabled=False,
                duration_tokens=1,
                temperature=1.7,
                top_p=0.8,
                top_k=25,
                repetition_penalty=1.0,
                max_new_tokens=4096,
                api_name="/lambda",
            )
            try:
                shutil.move(audio_path, out)
            except OSError:
                shutil.copy(audio_path, out)
            preview = (text[:70] + "...") if len(text) > 70 else text
            print(
                f"[{i:03d}/{len(sentences)}] ok {time.monotonic()-t0:.1f}s — {preview}",
                flush=True,
            )
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"[{i:03d}/{len(sentences)}] FAIL — {e!r}", flush=True)
            failed.append((i, str(e)))

    elapsed = (time.monotonic() - total_t0) / 60
    print(
        f"\nsynth done in {elapsed:.1f} min — ok={ok} skipped={skipped} failed={len(failed)}",
        flush=True,
    )
    if failed:
        for i, err in failed:
            print(f"  {i:03d}: {err}", flush=True)
        raise SystemExit(1)
    return paths


def concat_with_gap(wavs: list[Path], gap_sec: float, label: str) -> Path:
    silence = OUT_DIR / f"_silence_{label}.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            f"{gap_sec}",
            "-c:a",
            "pcm_s16le",
            str(silence),
        ],
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
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(full_wav),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(full_wav),
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "0",
            str(full_mp3),
        ],
        check=True,
    )
    silence.unlink(missing_ok=True)
    list_path.unlink(missing_ok=True)
    print(
        f"concat[{label}] {gap_sec}s gap: "
        f"{full_wav.name} ({full_wav.stat().st_size//1024}KB) + "
        f"{full_mp3.name} ({full_mp3.stat().st_size//1024}KB)",
        flush=True,
    )
    return full_mp3


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sentences = load_sentences()
    print(f"sentences: {len(sentences)} | output: {OUT_DIR}", flush=True)

    wavs = synth_all(sentences)

    for label, gap in GAPS.items():
        concat_with_gap(wavs, gap, label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
