"""ドアをノックする音(3 回)を合成して WAV に書く。
Blender 同梱の Python で実行: blender -b --factory-startup --python scripts/make_knock.py -- 出力.wav
"""
import sys, wave
import numpy as np

OUT = sys.argv[sys.argv.index("--") + 1]
SR = 44100
N = int(SR * 1.2)
rng = np.random.default_rng(3)
out = np.zeros(N)
for k, t0 in enumerate((0.0, 0.26, 0.52)):
    i = int(t0 * SR)
    L = int(SR * 0.18)
    t = np.arange(L) / SR
    body = np.sin(2 * np.pi * (150 + 10 * k) * t) * np.exp(-t * 38)          # 木の板の低い響き
    click = rng.standard_normal(L) * np.exp(-t * 400) * 0.6                   # 拳が当たる瞬間
    wood = np.sin(2 * np.pi * 620 * t) * np.exp(-t * 90) * 0.25
    out[i:i + L] += (body + click + wood) * (0.9 if k < 2 else 1.0)
fq = np.fft.rfftfreq(N, 1 / SR)
out = np.fft.irfft(np.fft.rfft(out) / np.sqrt(1 + (fq / 2500) ** 4), n=N)
out = out / np.abs(out).max() * 0.8
pcm = (np.stack([out, out], 1) * 32767).astype("<i2")
with wave.open(OUT, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("knock written", OUT)
