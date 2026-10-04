"""Ledger-gated narration synthesis. Today: MiniMax T2A (sync HTTP). Standard library only.

Each paid request is reserved in costs.json before it is sent and settled from the
provider's reported usage afterwards. Results are cached by request fingerprint, so a
re-run never pays twice for an unchanged line; an unknown result (timeout, dropped
connection) stays reserved and blocks a blind retry until someone checks it.
The API key comes from the environment or a private file and is never logged.
"""
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
from core import fingerprint, number, read_json, write_json
from costs import reserve, settle

HOSTS = {"global": "https://api.minimax.io", "cn": "https://api.minimaxi.com"}
KEY_FILE = Path("~/.config/minimax/api_key").expanduser()
RETRYABLE = {1001, 1002}  # provider-side timeout / rate limit: no audio, no charge


def api_key():
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key and KEY_FILE.is_file():
        if KEY_FILE.stat().st_mode & 0o077:
            raise ValueError(f"{KEY_FILE} is readable by others; chmod 600 it")
        key = KEY_FILE.read_text(encoding="utf-8").strip()
    if not key:
        raise ValueError(f"No MiniMax key: set MINIMAX_API_KEY or write {KEY_FILE} (chmod 600)")
    return key


def post(host, path, body, timeout=120):
    request = urllib.request.Request(host + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": "Bearer " + api_key(),
                                              "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return {"base_resp": {"status_code": exc.code, "status_msg": exc.reason}}


def status(response):
    base = response.get("base_resp", {})
    return base.get("status_code"), base.get("status_msg", "")


def resolve_host(region="auto"):
    """Keys are region-bound; probe with the free voice listing instead of a paid call."""
    candidates = [HOSTS[region]] if region in HOSTS else list(HOSTS.values())
    for host in candidates:
        if status(post(host, "/v1/get_voice", {"voice_type": "system"}, timeout=30))[0] == 0:
            return host
    raise ValueError("MiniMax rejected the key on every candidate region")


def list_voices(region="auto", contains=""):
    host = resolve_host(region)
    voices = post(host, "/v1/get_voice", {"voice_type": "system"}).get("system_voice", [])
    rows = [{"voice_id": v.get("voice_id"), "name": v.get("voice_name"),
             "description": " ".join(v.get("description") or [])} for v in voices]
    return [r for r in rows if contains.lower() in json.dumps(r, ensure_ascii=False).lower()]


def request_body(text, voice, model, speed, language):
    return {"model": model, "text": text, "stream": False, "language_boost": language,
            "voice_setting": {"voice_id": voice, "speed": speed, "vol": 1.0, "pitch": 0},
            "audio_setting": {"sample_rate": 48000, "bitrate": 256000, "format": "mp3", "channel": 1}}


def synthesize(root, project, items, voice, model="speech-2.8-hd", speed=1.0, language="auto",
               price_per_10k_chars=None, pricing_basis=None, region="auto", poster=None):
    """items: [(line_id, text)]. Returns per-line files; charges only for cache misses."""
    root = Path(root)
    number(speed, "speed", .5)
    if price_per_10k_chars is None or not pricing_basis:
        raise ValueError("State the live price per 10k characters and where it was checked (--price, --pricing-basis)")
    price = number(price_per_10k_chars, "price_per_10k_chars", 0)
    send = poster or post
    host = None
    out_dir = root / "audio" / "narration"
    cache = root / "work" / "tts-cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    results = []
    for line_id, text in items:
        body = request_body(text, voice, model, speed, language)
        key = fingerprint(body)
        cached = cache / f"{key[:24]}.mp3"
        target = out_dir / f"{line_id}.mp3"
        if cached.is_file():
            target.write_bytes(cached.read_bytes())
            results.append({"id": line_id, "path": str(target.relative_to(root)), "charged": False})
            continue
        host = host or (HOSTS["global"] if poster else resolve_host(region))
        # Some accounts bill CJK characters double; reserve the worst case and settle the reported usage.
        maximum = round(max(len(text) * 2, 1) / 10000 * price, 6) or 1e-6
        action = f"tts-{line_id}-{key[:12]}"
        reserve(root, project, action, f"minimax:{model}", key, maximum, pricing_basis)
        for attempt in range(3):
            response = send(host, "/v1/t2a_v2", body)
            code, message = status(response)
            if code in RETRYABLE:
                time.sleep(2 * (attempt + 1))
                continue
            break
        audio = response.get("data", {}).get("audio") if code == 0 else None
        if not audio:
            # Provider answered with a definite failure: nothing was produced, settle at zero.
            settle(root, action, 0, f"error:{code}:{message}")
            raise ValueError(f"MiniMax {code}: {message} (line {line_id})")
        cached.write_bytes(bytes.fromhex(audio))
        target.write_bytes(cached.read_bytes())
        extra = response.get("extra_info", {})
        used = extra.get("usage_characters", len(text))
        settle(root, action, round(used / 10000 * price, 6), response.get("trace_id", action))
        results.append({"id": line_id, "path": str(target.relative_to(root)), "charged": True,
                         "usage_characters": used, "audio_ms": extra.get("audio_length")})
    manifest = root / "work" / "tts-manifest.json"
    prior = read_json(manifest) if manifest.is_file() else {}
    prior.update({r["id"]: dict(r, voice=voice, model=model, speed=speed) for r in results})
    write_json(manifest, prior)
    return {"ok": True, "voice": voice, "model": model, "lines": results,
            "charged_lines": sum(r["charged"] for r in results)}


def narration_items(project, beats=None):
    """Only narration text goes to TTS — never original quotes, captions or notes."""
    wanted = set(beats or [])
    return [(b["id"], b["narration"]) for b in project.get("beats", [])
            if b.get("narration") and (not wanted or b["id"] in wanted)]
