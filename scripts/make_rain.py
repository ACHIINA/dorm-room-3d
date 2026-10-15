"""窓の外の雨音(24 秒でつながるループ)を合成して WAV に書く。
Blender 同梱の Python で実行: blender -b --factory-startup --python scripts/make_rain.py -- 出力.wav
"""
import sys, wave
import numpy as np

OUT = sys.argv[sys.argv.index("--") + 1]
SR = 44100
SEC = 24
N = SR * SEC
rng = np.random.default_rng(11)
fq = np.fft.rfftfreq(N, 1 / SR)


def shaped(noise, lo, hi, tilt):
    sp = np.fft.rfft(noise)
    h = (1 - 1 / np.sqrt(1 + (fq / lo) ** 4)) / np.sqrt(1 + (fq / hi) ** 4) / np.maximum(fq, 20) ** tilt
    # 周波数領域で作ると周期的になり、ループのつなぎ目が出ない
    return np.fft.irfft(sp * h, n=N)


bed = shaped(rng.standard_normal(N), 250, 5000, 0.35)        # 屋根や地面に当たるざーっという音
far = shaped(rng.standard_normal(N), 80, 900, 0.6)            # 遠くの低いうなり
drops = np.zeros(N)
for i in rng.integers(0, N - 2000, SEC * 70):                  # 窓や雨どいに当たる粒の音
    L = rng.integers(200, 900)
    env = np.exp(-np.arange(L) / rng.uniform(40, 160))
    drops[i:i + L] += rng.standard_normal(L) * env * rng.uniform(0.2, 1.0)
drops = shaped(drops, 900, 7000, 0.0)
mix = bed / np.abs(bed).max() * 0.55 + far / np.abs(far).max() * 0.25 + drops / np.abs(drops).max() * 0.3
mix *= 1 + 0.08 * np.sin(2 * np.pi * np.arange(N) / N * 3)   # 強弱のゆらぎ(ループに合わせた周期)
mix = mix / np.abs(mix).max() * 0.6
L_ch = mix
R_ch = np.roll(mix, int(SR * 0.013))                          # わずかにずらして広がりを出す
pcm = (np.stack([L_ch, R_ch], 1) * 32767).astype("<i2")
with wave.open(OUT, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("rain written", OUT, SEC, "s")
