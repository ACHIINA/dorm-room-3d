"""集中モードの区切りで鳴らす、やわらかいベルの音(2 音)を合成して WAV に書く。
Blender 同梱の Python で実行: blender -b --factory-startup --python scripts/make_chime.py -- 出力.wav
"""
import sys, wave
import numpy as np

OUT = sys.argv[sys.argv.index("--") + 1]
SR = 44100
N = int(SR * 3.2)
t = np.arange(N) / SR
out = np.zeros(N)


def bell(f0, start, amp):
    tt = t - start
    on = tt >= 0
    tt = np.where(on, tt, 0)
    s = np.zeros(N)
    # 金属の鐘らしい非整数倍音。高い倍音ほど早く消える
    for ratio, a, decay in ((1.0, 1.0, 1.6), (2.76, 0.35, 3.2), (5.40, 0.12, 6.0), (8.93, 0.05, 9.0)):
        s += a * np.sin(2 * np.pi * f0 * ratio * tt) * np.exp(-tt * decay)
    attack = 1 - np.exp(-tt * 400)
    return np.where(on, s * attack * amp, 0)


out += bell(880.0, 0.0, 0.45)    # A5
out += bell(1318.5, 0.32, 0.35)  # E6
out = out / np.max(np.abs(out)) * 0.7
fade = int(SR * 0.4)
out[-fade:] *= np.linspace(1, 0, fade)
pcm = (np.stack([out, out], 1) * 32767).astype("<i2")
with wave.open(OUT, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("chime written", OUT)
