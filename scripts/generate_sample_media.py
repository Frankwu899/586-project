#!/usr/bin/env python3
"""Generate the fictional LumaCup reference: vector shapes, bitmap text, and tones.

Python's standard library and ffmpeg with libx264/AAC are the only requirements.
No footage, voice, product performance, or externally licensed assets are used.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import wave

WIDTH, HEIGHT, FPS, DURATION = 640, 360, 20, 10
SAMPLE_KEY = "lumacup_shapes_v1"
# A deliberately small original 5x7 bitmap alphabet keeps generation font-independent.
GLYPHS = {
    "A": [14,17,17,31,17,17,17], "B": [30,17,17,30,17,17,30],
    "C": [14,17,16,16,16,17,14], "D": [30,17,17,17,17,17,30],
    "E": [31,16,16,30,16,16,31], "F": [31,16,16,30,16,16,16],
    "G": [14,17,16,23,17,17,15], "H": [17,17,17,31,17,17,17],
    "I": [31,4,4,4,4,4,31], "J": [7,2,2,2,18,18,12],
    "K": [17,18,20,24,20,18,17], "L": [16,16,16,16,16,16,31],
    "M": [17,27,21,21,17,17,17], "N": [17,25,21,19,17,17,17],
    "O": [14,17,17,17,17,17,14], "P": [30,17,17,30,16,16,16],
    "Q": [14,17,17,17,21,18,13], "R": [30,17,17,30,20,18,17],
    "S": [15,16,16,14,1,1,30], "T": [31,4,4,4,4,4,4],
    "U": [17,17,17,17,17,17,14], "V": [17,17,17,17,17,10,4],
    "W": [17,17,17,21,21,21,10], "X": [17,17,10,4,10,17,17],
    "Y": [17,17,10,4,4,4,4], "Z": [31,1,2,4,8,16,31],
    " ": [0]*7, "-": [0,0,0,31,0,0,0],
}


def rectangle(frame: bytearray, x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
    row = bytes(color) * w
    for py in range(y, y + h):
        start = (py * WIDTH + x) * 3
        frame[start:start + w * 3] = row


def text(frame: bytearray, label: str, y: int, scale: int = 3) -> None:
    x = (WIDTH - len(label) * 6 * scale) // 2
    for char in label:
        for row, bits in enumerate(GLYPHS[char]):
            for col in range(5):
                if bits & (1 << (4-col)):
                    rectangle(frame, x + col*scale, y + row*scale, scale, scale, (239,244,249))
        x += 6 * scale


def frame_at(seconds: float) -> bytearray:
    frame = bytearray(bytes((24,36,53)) * (WIDTH * HEIGHT))
    text(frame, "SYNTHETIC DEMO - NO REAL PRODUCT CLAIMS", 330, 2)
    if seconds < 7:
        text(frame, "LUMACUP" if seconds < 3 else "REMOVABLE LID", 30, 4)
        if seconds < 3:
            text(frame, "FICTIONAL SAMPLE", 73, 2)
        rectangle(frame, 245, 165, 150, 130, (55,156,207))
        rectangle(frame, 395, 185, 35, 70, (55,156,207))
        rectangle(frame, 395, 199, 20, 42, (24,36,53))
        lid_y = 149 if seconds < 3 else 149-int(min(seconds-3, 1) * 45)
        rectangle(frame, 235, lid_y, 170, 16, (249,171,74))
    else:
        text(frame, "EXPLORE THE COLORS", 35, 4)
        for x, color in [(105,(55,156,207)),(265,(239,142,163)),(425,(111,195,143))]:
            rectangle(frame, x, 170, 110, 125, color)
            rectangle(frame, x-5, 155, 120, 15, (249,171,74))
    return frame


def write_audio(path: Path) -> None:
    rate = 44100
    samples = bytearray()
    for index in range(rate * DURATION):
        t = index / rate
        frequency = (220.0, 277.18, 329.63, 277.18)[int(t) % 4]
        # Short fade at each note edge avoids treating clicks as observations.
        envelope = min(1.0, (t % 1) * 100, (1 - t % 1) * 100)
        value = 0.07 * envelope * math.sin(2 * math.pi * frequency * t)
        for onset in (3, 7):
            if onset <= t < onset + .25:
                local = t-onset
                value += .15 * math.sin(math.pi * local / .25) * math.sin(2*math.pi*880*t)
        samples.extend(struct.pack("<h", int(value * 32767)))
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(samples)


def generate_sample_media(output: Path, ffmpeg: str = "ffmpeg") -> Path:
    if shutil.which(ffmpeg) is None:
        raise RuntimeError("ffmpeg is required to generate the matching synthetic sample video.")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="video-anatomy-sample-") as temp:
        audio_path = Path(temp) / "tones.wav"
        write_audio(audio_path)
        command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                   "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", f"{WIDTH}x{HEIGHT}",
                   "-framerate", str(FPS), "-i", "pipe:0", "-i", str(audio_path),
                   "-map", "0:v:0", "-map", "1:a:0", "-c:v", "libx264", "-preset", "veryfast",
                   "-crf", "28", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k",
                   "-movflags", "+faststart", "-t", str(DURATION), str(output)]
        with tempfile.TemporaryFile() as error_log:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=error_log)
            try:
                assert process.stdin is not None
                for index in range(FPS * DURATION):
                    process.stdin.write(frame_at(index/FPS))
                process.stdin.close()
                result = process.wait(timeout=60)
                if result:
                    error_log.seek(0)
                    raise RuntimeError("Sample encoding failed: " + error_log.read().decode()[-1000:])
            except BaseException:
                process.kill()
                process.wait()
                output.unlink(missing_ok=True)
                raise
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".local-data/sample/lumacup_shapes_v1.mp4"))
    args = parser.parse_args()
    result = generate_sample_media(args.output)
    print(f"Generated fictional sample: {result} ({result.stat().st_size} bytes)")
