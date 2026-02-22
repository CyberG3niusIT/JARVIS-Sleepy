# JARVIS System-Specific Configuration Notes

**IMPORTANT:** These are Christopher's system-specific settings that differ from defaults.

## TTS Configuration

**Primary:** Kokoro 82M (in-process CPU, 50/50 fable+george blend)
- Auto-downloads from HuggingFace Hub on first run
- No manual path configuration needed

**Fallback:** Piper TTS at:
```
/home/christopher/.local/bin/piper
```

**NOT** at `/usr/bin/piper`

This must be reflected in `config.yaml`:
```yaml
tts:
  piper_bin: "/home/christopher/.local/bin/piper"  # CORRECT
```

**Why this matters:**
- Piper was installed via pip user install, not system-wide
- Using wrong path causes "piper not found" errors
- Piper TTS will fail silently if path is incorrect

## Whisper STT Model

**CURRENT:** Fine-tuned Whisper via faster-whisper (CTranslate2) with GPU acceleration:
```
/mnt/jarvis-models/voice_training/whisper_finetuned_ct2    (production - GPU-optimized CTranslate2 format)
/mnt/jarvis-models/voice_training/whisper_finetuned/final  (source - HuggingFace format, used for conversion)
```

Fallback base model (CPU only):
```
/mnt/jarvis-models/whisper/ggml-base.bin
```

**GPU Performance:** 0.1-0.2s transcription (10-20x faster than CPU)

## LLM Configuration

**Model:** Qwen3-VL-8B (Q5_K_M, self-quantized from F16, vision-capable)
```
/mnt/jarvis-models/llm/Qwen3VL-8B-Instruct-Q5_K_M.gguf
```

**Server:** llama.cpp via systemd service
```
/etc/systemd/system/llama-server.service
```
- Port 8080, ROCm backend, GPU offload
- `systemctl status llama-server` to check
- Qwen3-VL supports native tool calling (web research) and vision (future)

**Fallback:** Claude API (Anthropic) — used when local quality gate fails

## Other System-Specific Paths

### Jarvis Home
```
/home/christopher/jarvis/
```

### Storage Mount
```
/mnt/jarvis-storage/jarvis/
```

### Models
- **Whisper (fine-tuned, production):** `/mnt/jarvis-models/voice_training/whisper_finetuned_ct2`
- **Whisper (fine-tuned, source):** `/mnt/jarvis-models/voice_training/whisper_finetuned/final`
- **Whisper (base fallback):** `/mnt/jarvis-models/whisper/ggml-base.bin`
- **Piper TTS:** `/mnt/jarvis-models/piper/en_GB-northern_english_male-medium.onnx`
- **Qwen LLM:** `/mnt/jarvis-models/llm/Qwen3VL-8B-Instruct-Q5_K_M.gguf`

### Audio Devices
- **Microphone:** FIFINE K669B USB condenser mic (hw:fifine,0 via udev rule)
- **Speakers:** ALCS1200A Analog (plughw:0,0)
- **Secondary mic (unused):** EMEET SmartCam Nova 4K webcam (hw:2,0)

## Configuration Checklist

When updating `config.yaml`, always verify:
- [ ] Piper path is `/home/christopher/.local/bin/piper`
- [ ] Fine-tuned Whisper model path is correct (CTranslate2 format)
- [ ] LLM path points to `Qwen3VL-8B-Instruct-Q5_K_M.gguf`
- [ ] All paths use correct username (christopher, not generic)
- [ ] Model paths point to `/mnt/jarvis-models/`
- [ ] Skills/storage paths point to `/mnt/jarvis-storage/jarvis/`
- [ ] Audio devices are correct (plughw:0,0 for output)
- [ ] llama-server systemd service is running

## Common Mistakes to Avoid

1. ❌ Using `/usr/bin/piper` → Causes TTS failure
2. ❌ Using `ggml-medium.bin` for STT → 10 second delays (too slow!)
3. ❌ Using relative paths for models → Models not found
4. ❌ Hardcoding `/home/user/` → Won't work on this system
5. ❌ Referencing old Qwen2.5-7B model → Replaced by Qwen3-VL-8B (Feb 22)
6. ✅ Always use full absolute paths
7. ✅ Always test TTS after config changes
8. ✅ Fine-tuned Whisper for production, base.bin only as CPU fallback

---

**Last Updated:** February 22, 2026
**System:** ubuntu2404 (Christopher's workstation)
