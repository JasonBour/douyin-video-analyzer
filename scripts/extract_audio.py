#!/usr/bin/env python3
"""从视频文件提取 16kHz 单声道 s16 WAV 音频（正确重采样）。

⚠️ 不要用 frame.rate=16000 直接改帧率——那不会真正重采样，会把音频变调损坏。
必须用 AudioResampler 重采样到 16k 单声道，否则任何转写引擎（通义/faster-whisper）都会输出乱码。

用法：
    python extract_audio.py <input_video.mp4> <output_audio.wav>

依赖：PyAV (pip install av)
"""

import sys
import os
import av


def extract_audio(video_path, wav_path):
    container = av.open(video_path)
    audio_stream = next((s for s in container.streams if s.type == 'audio'), None)
    if audio_stream is None:
        raise RuntimeError(f"视频中无音轨: {video_path}")

    resampler = av.AudioResampler(format='s16', layout='mono', rate=16000)

    out = av.open(wav_path, 'w')
    out_stream = out.add_stream('pcm_s16le', rate=16000)
    out_stream.codec_context.layout = 'mono'
    out_stream.codec_context.format = 's16'

    n = 0
    for frame in container.decode(audio_stream):
        for rframe in resampler.resample(frame):
            rframe.pts = None
            for packet in out_stream.encode(rframe):
                out.mux(packet)
                n += 1

    for rframe in resampler.resample(None):
        rframe.pts = None
        for packet in out_stream.encode(rframe):
            out.mux(packet)
            n += 1

    for packet in out_stream.encode(None):
        out.mux(packet)

    out.close()
    container.close()
    size_mb = os.path.getsize(wav_path) / 1024 / 1024
    print(f"OK: {wav_path} ({size_mb:.1f} MB)", file=sys.stderr)
    return wav_path


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法: python extract_audio.py <input_video> <output_wav>", file=sys.stderr)
        sys.exit(1)
    try:
        extract_audio(sys.argv[1], sys.argv[2])
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
