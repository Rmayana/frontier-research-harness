"""Read local training artifacts and compare measurements in their original units."""

import csv
import json
import math
import statistics
import subprocess
from datetime import date, datetime, time
from itertools import islice
from pathlib import Path

from training_runtime import settings


VIDEO_FORMATS = {".mp4": "mov", ".m4v": "mov", ".mov": "mov", ".mkv": "matroska", ".webm": "matroska", ".avi": "avi"}


def inbox_file(filename: str, suffixes: set[str], byte_limit: int) -> Path:
    relative = Path(filename)
    if not filename or relative.is_absolute() or relative.anchor or ":" in filename or ".." in relative.parts:
        raise ValueError("Use a filename relative to the private records/inbox directory")
    records = Path(settings()["records"]).resolve()
    inbox = (records / "inbox").resolve()
    candidate = (inbox / relative).resolve()
    if not inbox.is_relative_to(records) or not candidate.is_relative_to(inbox):
        raise ValueError("File is outside the private inbox")
    if candidate.suffix.lower() not in suffixes or not candidate.is_file():
        raise ValueError("File is missing or has an unsupported extension in the private inbox")
    if candidate.stat().st_size > byte_limit:
        raise ValueError("File exceeds the size limit for this tool")
    return candidate


def media_command(args: list[str]) -> bytes:
    try:
        result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, check=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("Local media decoder failed or exceeded its 30-second limit") from exc
    return result.stdout


def inspect_video(filename: str, seconds: float | None = None) -> dict:
    """Read video metadata and optionally a scaled JPEG frame near a timestamp in seconds."""
    path = inbox_file(filename, set(VIDEO_FORMATS), 4 * 1024**3)
    if seconds is not None and (not math.isfinite(seconds) or seconds < 0):
        raise ValueError("seconds must be finite and nonnegative")
    runtime = settings()
    # Pin the demuxer so a renamed playlist cannot load other local or remote inputs.
    local_input = ["-protocol_whitelist", "file", "-f", VIDEO_FORMATS[path.suffix.lower()]]
    raw = media_command([runtime["ffprobe"], "-v", "error", *local_input, "-select_streams", "V:0",
                         "-show_entries", "stream=index,width,height,avg_frame_rate:format=duration",
                         "-of", "json", str(path)])
    info = json.loads(raw)
    streams = info.get("streams") or []
    if not streams:
        raise ValueError("Container has no playable video stream")
    stream = streams[0]
    duration = info.get("format", {}).get("duration")
    metadata = {"filename": filename, "width": stream["width"], "height": stream["height"],
                "average_frame_rate": stream.get("avg_frame_rate"),
                "duration_seconds": float(duration) if duration not in (None, "N/A") else None}
    if seconds is None:
        return metadata
    if metadata["duration_seconds"] is not None and seconds >= metadata["duration_seconds"]:
        raise ValueError("Requested frame is outside the video duration")
    frame = media_command([runtime["ffmpeg"], "-nostdin", "-v", "error", *local_input,
                           "-ss", str(seconds), "-i", str(path), "-map", f"0:{stream['index']}",
                           "-frames:v", "1", "-vf", "scale=w='min(768,iw)':h='min(768,ih)':force_original_aspect_ratio=decrease",
                           "-c:v", "mjpeg", "-f", "image2pipe", "pipe:1"])
    if not frame.startswith(b"\xff\xd8"):
        raise ValueError("No decodable frame at the requested timestamp")
    metadata.update(requested_seconds=seconds, frame_jpeg=frame)
    return metadata


def json_field(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (tuple, list)):
        return [json_field(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_field(item) for key, item in value.items()}
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def read_activity(filename: str, offset: int = 0, limit: int = 50) -> dict:
    """Read a page of UTF-8 CSV rows or Garmin FIT record messages in recorded order."""
    if not 0 <= offset <= 1000000 or not 1 <= limit <= 100:
        raise ValueError("offset must be 0..1000000 and limit must be 1..100")
    is_csv = Path(filename).suffix.lower() == ".csv"
    path = inbox_file(filename, {".csv", ".fit"}, (32 if is_csv else 8) * 1024**2)
    if is_csv:
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source, strict=True)
            headers = reader.fieldnames or []
            if not headers or len(set(headers)) != len(headers) or not all(headers):
                raise ValueError("CSV must have unique, nonempty column headers")
            rows = list(islice(reader, offset, offset + limit + 1))
            if any(None in row or None in row.values() for row in rows):
                raise ValueError("CSV row length differs from its header")
        kind = "csv"
    else:
        from garmin_fit_sdk import Decoder, Stream

        decoder = Decoder(Stream.from_byte_array(bytearray(path.read_bytes())))
        messages, errors = decoder.read()
        if errors:
            raise ValueError("Invalid or incomplete FIT file")
        rows = messages.get("record_mesgs", [])[offset:offset + limit + 1]
        headers = sorted({key for row in rows[:limit] for key in row})
        kind = "fit_record"
    page = {"filename": filename, "kind": kind, "columns": headers, "offset": offset,
            "rows": json_field(rows[:limit]), "next_offset": offset + limit if len(rows) > limit else None}
    if len(json.dumps(page, ensure_ascii=False).encode("utf-8")) > 65536:
        raise ValueError("Activity page exceeds 64 KiB; reduce the row limit or supply a narrower export")
    return page


def run_analysis(baseline: list[float], followup: list[float], unit: str, paired: bool = False) -> dict:
    """Compare two sets of measurements recorded with the same task, conditions and unit."""
    if not unit.strip() or len(unit) > 64:
        raise ValueError("Provide the common measurement unit (1..64 characters)")
    for series in (baseline, followup):
        if not 1 <= len(series) <= 10000 or any(isinstance(v, bool) or not math.isfinite(v) for v in series):
            raise ValueError("Each series must contain 1..10000 finite measurements")
    if paired and len(baseline) != len(followup):
        raise ValueError("Paired measurements must have matching observations in the same order")

    def summary(series: list[float]) -> dict:
        return {"n": len(series), "mean": statistics.mean(series),
                "min": min(series), "max": max(series),
                "sample_sd": statistics.stdev(series) if len(series) > 1 else None}

    try:
        before, after = summary(baseline), summary(followup)
        result = {"unit": unit, "baseline": before, "followup": after,
                  "mean_change": after["mean"] - before["mean"], "paired": paired}
        if paired:
            result["within_pair_change"] = summary([b - a for a, b in zip(baseline, followup)])
        json.dumps(result, allow_nan=False)
    except (ArithmeticError, ValueError, AttributeError) as exc:
        raise ValueError("Measurement magnitude exceeds the supported numerical range") from exc
    return result
