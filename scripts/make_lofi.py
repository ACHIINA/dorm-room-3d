"""ターンテーブル用のオリジナル曲(ローファイ・ジャズ風ループ)を合成して WAV に書く。
Blender 同梱の Python(numpy あり)で実行: blender -b --factory-startup --python scripts/make_lofi.py -- 出力.wav
"""
import sys, wave
import numpy as np

OUT = sys.argv[sys.argv.index("--") + 1]
SR = 44100
BPM = 76
BEAT = 60 / BPM
BARS = 32
rng = np.random.default_rng(7)
N = int(SR * BEAT * 4 * BARS) + SR * 2
L = np.zeros(N)
R = np.zeros(N)


def hz(m):
    return 440 * 2 ** ((m - 69) / 12)


def add(sig, t0, pan=0.0, gain=1.0):
    i = int(t0 * SR)
    j = min(N, i + len(sig))
    s = sig[: j - i] * gain
    L[i:j] += s * (1 - max(0, pan))
    R[i:j] += s * (1 + min(0, pan))


def epiano(m, dur, vel=0.5):
    t = np.arange(int(SR * (dur + 1.2))) / SR
    f = hz(m)
    env = np.exp(-t * 2.2) * (1 - np.exp(-t * 300))
    rel = np.clip(1 - (t - dur) / 1.2, 0, 1) ** 2
    trem = 1 + 0.12 * np.sin(2 * np.pi * 4.5 * t)
    tone = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 4) + 0.12 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 6)
    tine = 0.25 * np.sin(2 * np.pi * 7.1 * f * t) * np.exp(-t * 30)
    return (tone + tine) * env * rel * trem * vel


def bass(m, dur):
    t = np.arange(int(SR * (dur + 0.3))) / SR
    f = hz(m)
    env = (1 - np.exp(-t * 60)) * np.exp(-t * 1.2) * np.clip(1 - (t - dur) / 0.3, 0, 1)
    return (np.sin(2 * np.pi * f * t) + 0.2 * np.sin(2 * np.pi * 2 * f * t)) * env * 0.55


def kick():
    t = np.arange(int(SR * 0.4)) / SR
    f = 50 + 70 * np.exp(-t * 25)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) * 0.9


def snare():
    t = np.arange(int(SR * 0.25)) / SR
    n = rng.standard_normal(len(t))
    return (0.5 * n * np.exp(-t * 22) + 0.3 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30)) * 0.35


def hat(open_=False):
    t = np.arange(int(SR * (0.18 if open_ else 0.05))) / SR
    n = rng.standard_normal(len(t))
    n = np.diff(np.concatenate([[0], n]))  # 高域寄りに
    return n * np.exp(-t * (18 if open_ else 70)) * 0.12


# コード(MIDI): Fmaj7 / Em7 / Dm7 / Cmaj7(9)
CHORDS = [([53, 57, 60, 64], 41), ([52, 55, 59, 62], 40), ([50, 53, 57, 60], 38), ([48, 52, 55, 59, 62], 36)]
SCALE = [60, 62, 64, 67, 69, 72, 74, 76]
swing = BEAT * 0.17

for bar in range(BARS):
    t0 = bar * 4 * BEAT
    notes, root = CHORDS[bar % 4]
    # 和音: 1拍目と 2拍裏
    for k, n in enumerate(notes):
        add(epiano(n, BEAT * 1.6, 0.16), t0 + k * 0.012, pan=-0.3 + 0.15 * k)
    for k, n in enumerate(notes[1:]):
        add(epiano(n + 12 * (k == 3), BEAT * 1.2, 0.10), t0 + BEAT * 2.5 + swing + k * 0.01, pan=0.2)
    # ベース
    add(bass(root, BEAT * 1.8), t0)
    add(bass(root + 7, BEAT * 0.8), t0 + BEAT * 2.5 + swing)
    add(bass(root + 12 if bar % 2 else root, BEAT * 0.9), t0 + BEAT * 3.5 + swing)
    # ドラム(最初の 2 小節は鍵盤だけ)
    if bar >= 2:
        add(kick(), t0)
        add(kick(), t0 + BEAT * 2.5 + swing, gain=0.7)
        add(snare(), t0 + BEAT, pan=0.1)
        add(snare(), t0 + BEAT * 3, pan=0.1)
        for e in range(8):
            add(hat(e == 7), t0 + e * BEAT / 2 + (swing if e % 2 else 0), pan=0.35, gain=0.8 if e % 2 else 1.0)
    # まばらなメロディ(後半)
    if bar >= 8 and bar % 2 == 0:
        for k in range(rng.integers(2, 5)):
            m = int(rng.choice(SCALE)) + (12 if bar >= 20 else 0)
            add(epiano(m, BEAT * 0.8, 0.13), t0 + BEAT * rng.choice([0.5, 1.5, 2, 3, 3.5]) + swing, pan=0.15)

mix = np.stack([L, R], 1)

# 暖かい音へ: FFT でゆるいローパス(6.5kHz)とローカット(35Hz)
spec = np.fft.rfft(mix, axis=0)
fq = np.fft.rfftfreq(N, 1 / SR)
h = 1 / np.sqrt(1 + (fq / 6500) ** 4) * (1 - 1 / np.sqrt(1 + (fq / 35) ** 4))
mix = np.fft.irfft(spec * h[:, None], n=N, axis=0)

# レコードのヒスノイズとパチパチ
hiss = rng.standard_normal((N, 2))
hs = np.fft.rfft(hiss, axis=0)
hiss = np.fft.irfft(hs * (1 / np.sqrt(1 + (fq / 3000) ** 2))[:, None], n=N, axis=0) * 0.004
clicks = np.zeros((N, 2))
idx = rng.integers(0, N - 200, int(N / SR * 7))
for i in idx:
    a = rng.uniform(0.02, 0.12) * rng.choice([-1, 1])
    clicks[i:i + 30, :] += a * np.exp(-np.arange(30) / 4)[:, None]
mix = mix + hiss + clicks

# 頭とお尻をなめらかに、-1dBFS に正規化
fade = int(SR * 1.5)
mix[:fade] *= np.linspace(0, 1, fade)[:, None]
mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
mix = np.tanh(mix / np.max(np.abs(mix)) * 1.3) / np.tanh(1.3) * 0.89
pcm = (mix * 32767).astype("<i2")
with wave.open(OUT, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("lofi written", OUT, round(N / SR, 1), "s")
