---
name: moss-tts-voice-cloning
description: Local zero-shot voice cloning on this Mac (Apple Silicon, MPS) via MOSS-TTS 1.7B. Enrolls a person's voice from any audio/video file using silero-vad to auto-pick a clean 15s reference, then generates speech in that voice from arbitrary text. Use when the user wants to "save someone's voice", "clone a voice", "say X in Y's voice", or "list enrolled voices".
version: 1.0.0
author: hermes-agent local install
license: MIT (skill); MOSS-TTS upstream license applies to model usage
dependencies: [MOSS-TTS local install at /Volumes/ext/moss-tts, ffmpeg (Homebrew), silero-vad, gradio_client]
metadata:
  hermes:
    tags: [Voice Cloning, TTS, Speech Synthesis, MOSS-TTS, Apple Silicon, MPS, Local Inference]

---

# Voice Cloning (MOSS-TTS, local on Mac)

Zero-shot voice cloning capability backed by **MOSS-TTS 1.7B Local-Transformer** running locally on Apple Silicon MPS. Two-step workflow: **enroll** a voice once from any audio/video, then **generate** speech in that voice on demand.

> "Zero-shot" = no per-person training. Enrollment just stores a clean ~15s reference clip; the model conditions on it at generation time.

## When to use this skill

Trigger phrases (any of these → use this skill):

| Intent | Examples (zh / en) |
|---|---|
| **Enroll a voice** | "把这段录音存为张三的声音", "记住这是 X 的声音", "save this as Alice's voice", "register this voice" |
| **Generate speech** | "用张三的声音读：……", "让 X 念这段：……", "say this in Alice's voice", "TTS as X" |
| **List voices** | "现在有哪些人的声音", "列出语音样本", "what voices do we have" |
| **Inspect / delete** | "X 的语音详情", "删除 X 的语音", "remove X's voice" |

If the user asks about something else (text-to-speech without a specific person, music generation, transcription) — this is the wrong skill. Use whisper for ASR or audiocraft for music.

## Install layout (this Mac specifically)

Everything lives on the external SSD because the root disk is small:

```
/Volumes/ext/moss-tts/
  code/                   git clone of OpenMOSS/MOSS-TTS, with patches
  env/                    conda env (python 3.12, torch 2.9.1 + MPS, transformers 5.0.0)
  hf-home/                HuggingFace cache (model weights ~6.8GB)
  voices/<name>/          enrolled voice library
    reference.wav         24kHz mono, ~10-20s
    metadata.json         source, segment range, selection method, note
  generated/<name>/       output wavs from `voice-clone generate`
  logs/gradio_local.log   service log
  bin/
    moss-tts              service lifecycle wrapper (up/down/status/logs/restart)
    voice-clone           user-facing CLI
```

`~/.cache/huggingface` is symlinked to `/Volumes/ext/hf-cache` so other HF-using projects on this Mac still work.

## CLI: how the agent invokes capabilities

All commands return exit 0 on success, non-zero on error. Stderr carries diagnostics.

### Enroll a voice

```bash
/Volumes/ext/moss-tts/bin/voice-clone enroll <name> <audio-or-video-path> [--note "..."] [--force]
```

- `<name>`: free text, may contain CJK; used as folder name (path-bad chars sanitized)
- `<source>`: any format ffmpeg can read (mp3, wav, m4a, mp4, mov, mkv, ...)
- Default behavior: **silero-vad** auto-picks the cleanest ~15s window of voiced audio
- Manual override: `--start S --duration N` (skips VAD)
- **Conflict policy**: if `<name>` already exists, the command **refuses** (exit 2) and tells the user to pass `--force`. Always relay this refusal to the user — never silently re-enroll. When the user confirms intent to overwrite, retry with `--force`.

Output (success): single block of `enrolled: <name>` plus segment/source info on stderr.

### Generate speech

```bash
/Volumes/ext/moss-tts/bin/voice-clone generate <name> "<text>" [--out path]
                                                [--mode Clone|Continuation|Continuation+Clone]
                                                [--temperature 1.7] [--top-p 0.8] [--top-k 25]
                                                [--max-new-tokens 4096]
```

- The CLI **auto-starts** the MOSS-TTS service if it's down (`moss-tts up` is invoked transparently). First cold start after reboot takes ~1 minute (model load to MPS); subsequent calls reuse the warm service.
- Default output path: `/Volumes/ext/moss-tts/generated/<name>/<YYYYMMDD-HHMMSS>.wav`
- Generation latency on M4: roughly **10× real-time** (e.g. ~30s of compute for ~3s of audio). Tell the user to expect ~30s for short utterances.
- `--ephemeral` exists for the rare "do not leave any process running" requirement: it cold-loads the model in-process, generates, exits. Slow (~1 min/call) — only use if the user explicitly asks.

### List enrolled voices

```bash
/Volumes/ext/moss-tts/bin/voice-clone list
```

Tabulated: name, segment duration, source filename, created_at, note. Returns "(no voices enrolled)" when empty.

### Inspect / delete

```bash
/Volumes/ext/moss-tts/bin/voice-clone info <name>     # prints metadata.json + file listing
/Volumes/ext/moss-tts/bin/voice-clone delete <name> [--force]  # interactive y/N unless --force
```

When deleting on behalf of the user, pass `--force` (the user already confirmed via the chat).

## Service lifecycle (rarely needed by agent)

The `voice-clone` CLI handles the service implicitly. Manual control if needed:

```bash
/Volumes/ext/moss-tts/bin/moss-tts up        # start (waits for HTTP ready, up to 20 min)
/Volumes/ext/moss-tts/bin/moss-tts down      # stop
/Volumes/ext/moss-tts/bin/moss-tts status    # pid / uptime / RSS / port / endpoint
/Volumes/ext/moss-tts/bin/moss-tts logs      # tail -f
/Volumes/ext/moss-tts/bin/moss-tts restart
```

**Auto-shutdown**: the service exits itself after `MOSS_TTS_IDLE_SEC` (default 3600s = 1 hour) of no inference. The watchdog skips the check while a generation is in flight, so long inferences never get killed mid-run. Override with `MOSS_TTS_IDLE_SEC=0 ... up` (disabled) or any other integer.

## Agent-facing examples

**Example 1 — enroll then generate**

User: "我刚录了一段我爸的声音 `~/Downloads/dad.m4a`，存为'爸爸'。"

```bash
/Volumes/ext/moss-tts/bin/voice-clone enroll 爸爸 ~/Downloads/dad.m4a
```

User: "用爸爸的声音读：'今天的菜真好吃'。"

```bash
/Volumes/ext/moss-tts/bin/voice-clone generate 爸爸 "今天的菜真好吃"
```

Tell user the output path printed on stdout (e.g. `/Volumes/ext/moss-tts/generated/爸爸/20260501-103045.wav`).

**Example 2 — handle conflict**

User: "把这段存为'爸爸'。"  *(but '爸爸' already enrolled)*

CLI returns exit 2 with the message `voice 'X' already exists ... pass --force`. Surface that to the user verbatim and ask: "覆盖原有的吗？" If yes → retry with `--force`. If no → ask for a different name.

**Example 3 — inspect**

User: "我有哪些声音样本？"

```bash
/Volumes/ext/moss-tts/bin/voice-clone list
```

Print the table back to the user. If empty, say so plainly.

**Example 4 — source too short**

If the source file is < 8s of audio, `enroll` exits 1 with "source too short". Tell the user we need at least ~10s of clear speech and ask for a longer source.

## Implementation notes (for agent maintenance / debugging)

- **Why VAD over RMS?** silero-vad is robust against background music and intermittent noise — important when source is a video clip with non-speech audio. RMS-only would over-weight loud non-speech segments.
- **Why fallback to whole-source for short inputs?** If the input is between MIN (8s) and MAX (20s) total duration, there's nothing to "pick from"; we just take it all and trust the user gave a clean clip.
- **Why 24kHz mono for reference?** That's what MOSS-TTS's audio_tokenizer expects; mismatched sample rate → silent failures or garbled output.
- **Why patch torchcodec dylibs at install time?** macOS hardened runtime + SIP strips `DYLD_FALLBACK_LIBRARY_PATH` from spawned Python processes, so torchcodec couldn't find Homebrew ffmpeg via env vars. We added `/opt/homebrew/lib` as an `LC_RPATH` to each torchcodec dylib (and re-signed ad-hoc) — permanent, env-free fix. If the env's torchcodec is reinstalled (e.g. `pip install --upgrade torchcodec`), the rpath patch needs to be reapplied. See "Reapply rpath patch" below.

### Reapply rpath patch (after torchcodec reinstall)

```bash
TC=/Volumes/ext/moss-tts/env/lib/python3.12/site-packages/torchcodec
for f in "$TC"/libtorchcodec_*.dylib "$TC"/libtorchcodec_pybind_ops*.so; do
  install_name_tool -add_rpath /opt/homebrew/lib "$f" 2>/dev/null
  codesign --force --sign - "$f"
done
```

### Reapply MPS device patch (after upstream pulls)

The upstream `clis/moss_tts_app.py` hardcodes `--device cuda:0` and falls back to `cpu` if CUDA isn't available — silently ignoring `mps`. Our patches (search `# ---- moss-tts-mac` markers in `clis/moss_tts_app.py`) add: MPS device support, an ffmpeg dylib preload (so torchcodec finds Homebrew libs without `DYLD_*`), an idle auto-shutdown watchdog with `MOSS_TTS_IDLE_SEC`, and an `@_track_active` decorator on `run_inference` that prevents the watchdog from killing in-flight inference. If you `git pull` upstream and lose them, reapply by re-running the install workflow's edit steps (or rebase the patches).

## Known limitations

- First-time service startup downloads ~7GB of weights — takes 30–60 minutes on home internet without `HF_TOKEN`. After that, restarts are ~1 minute (cache-only load to MPS).
- Generation is slow vs. CUDA-class GPUs: ~10× real-time on M4 (i.e. 30s of compute for ~3s of speech). For batches, prefer running them serially without restarting service.
- Apple's MPS backend has occasional op-coverage gaps; if a future upstream model pull triggers `NotImplementedError: ... on MPS`, fallback is `--device cpu` (much slower) until PyTorch closes the gap.
- The voice library is a flat directory under `/Volumes/ext/moss-tts/voices/`. There's no built-in "multiple references per person" or "voice variants" — same name = single reference.
- silero-vad's auto-picked window may still include background noise if the source has continuous music under the speech. For best results, give a source where the target speaker is the dominant audio.

## Resources

- **MOSS-TTS upstream**: https://github.com/OpenMOSS/MOSS-TTS
- **HuggingFace model**: https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Local-Transformer
- **silero-vad**: https://github.com/snakers4/silero-vad
- Local install playbook + Mac-specific gotchas: this file
