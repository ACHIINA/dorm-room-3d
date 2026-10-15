"""足音(4 種類)を合成して WAV に書く。
Blender 同梱の Python で実行: blender -b --factory-startup --python scripts/make_steps.py -- 出力フォルダ
"""
import sys, wave, os
import numpy as np

OUT = sys.argv[sys.argv.index("--") + 1]
SR = 44100
for k in range(4):
    rng = np.random.default_rng(100 + k)
    N = int(SR * 0.32)
    t = np.arange(N) / SR
    heel = np.sin(2 * np.pi * (85 + 10 * k) * t) * np.exp(-t * 45)           # かかとの低い当たり
    scuff = rng.standard_normal(N) * np.exp(-((t - 0.05) / 0.035) ** 2) * 0.35   # 靴底がこすれる音
    tap = rng.standard_normal(N) * np.exp(-t * 160) * 0.5
    s = heel + scuff + tap
    fq = np.fft.rfftfreq(N, 1 / SR)
    s = np.fft.irfft(np.fft.rfft(s) / np.sqrt(1 + (fq / (1800 + 300 * k)) ** 4), n=N)
    s = s / np.abs(s).max() * 0.6
    pcm = (np.stack([s, s], 1) * 32767).astype("<i2")
    with wave.open(os.path.join(OUT, f"step_{k}.wav"), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
print("steps written")
