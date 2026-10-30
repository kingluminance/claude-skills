"""오디오 파일 도구: 브레이크 슬라이스, 게임 루프 제작, OGG 루프 태그.
WAV 처리는 표준 라이브러리(wave, array)만 쓴다. ogg_loop()만 soundfile + mutagen 필요.

    from audio import *
    cuts = onsets("amen.wav")                       # 타격 시작 지점(0~1 비율) 자동 감지
    kit = break_kit("amen.wav", cuts, names=[...])  # 슬라이스별 afp 악기 dict
    make_loop("loop_raw.wav", "loop.wav", loop_sec) # 루프 꼬리를 앞에 겹쳐 이음매 제거
"""
import array
import os
import wave

from mmp import afp


def _read(path):
    """→ (채널 수, 샘플레이트, 샘플 배열(int16 인터리브)). 16bit PCM WAV만."""
    w = wave.open(path)
    if w.getsampwidth() != 2:
        raise ValueError("16bit PCM WAV만 지원: " + path)
    raw = w.readframes(w.getnframes())
    ch = w.getnchannels()
    raw = raw[:len(raw) - len(raw) % (2 * ch)]   # 마지막 프레임이 잘린 파일 대비
    return ch, w.getframerate(), array.array("h", raw)


read_pcm = _read   # 공개 이름: (채널 수, 샘플레이트, int16 배열)


def _write(path, ch, sr, a):
    w = wave.open(path, "wb")
    w.setnchannels(ch)
    w.setsampwidth(2)
    w.setframerate(sr)
    w.writeframes(a.tobytes())
    w.close()
    return path


def info(path):
    ch, sr, a = _read(path)
    frames = len(a) // ch
    return dict(channels=ch, samplerate=sr, frames=frames, seconds=frames / sr)


def to_pcm16(src, dst):
    """WAV(float/24bit 포함)·FLAC·OGG를 16bit WAV로 변환 (soundfile 필요). 받은 샘플이 16bit가 아닐 때."""
    import soundfile as sf
    data, sr = sf.read(src, dtype="int16", always_2d=True)
    sf.write(dst, data, sr, subtype="PCM_16")
    return dst


def onsets(path, sensitivity=1.6, min_gap=0.06, hop=256):
    """타격(onset) 시작 지점을 파일 길이 대비 비율(0~1) 목록으로. 첫 지점은 항상 0.
    sensitivity를 낮추면(1.2) 더 많이, 높이면(2.5) 큰 타격만 잡는다. min_gap: 최소 간격(초)."""
    ch, sr, a = _read(path)
    frames = len(a) // ch
    env = []
    for i in range(0, frames - hop, hop):
        seg = a[i * ch:(i + hop) * ch:ch]
        env.append(sum(x * x for x in seg) / hop)
    flux = [max(0.0, env[i] - env[i - 1]) for i in range(1, len(env))]
    found, last = [0.0], -1e9
    win = max(1, int(0.25 * sr / hop))
    for i in range(1, len(flux) - 1):
        local = flux[max(0, i - win):i + win]
        mean = sum(local) / len(local)
        if flux[i] > sensitivity * mean and flux[i] >= flux[i - 1] and flux[i] >= flux[i + 1] and flux[i] > 0:
            t = (i + 1) * hop / sr
            if t - last >= min_gap and t > min_gap:
                found.append((i + 1) * hop / frames)
                last = t
    return found


def classify_slices(path, cuts, window=0.08):
    """각 슬라이스 앞부분(window초)의 스펙트럼으로 성격을 추정한다 (numpy 필요).
    반환: [dict(i, kind='kick'|'snare'|'hat', low, high, level), ...]
    kind는 대략적인 추정이다. 킥 찾기는 low 비율 순위로, 햇은 high 비율 순위로 고르는 편이 더 안정적이다."""
    import numpy as np
    ch, sr, a = _read(path)
    x = np.frombuffer(a.tobytes(), dtype=np.int16).reshape(-1, ch).mean(1) / 32768
    n = len(x)
    out = []
    for i, c in enumerate(cuts):
        s = x[int(c * n):int(c * n) + int(window * sr)]
        if len(s) < 64:
            out.append(dict(i=i, kind="?", low=0.0, high=0.0, level=0.0))
            continue
        spec = np.abs(np.fft.rfft(s * np.hanning(len(s))))
        fr = np.fft.rfftfreq(len(s), 1 / sr)
        tot = spec.sum() + 1e-9
        low, high = spec[fr < 150].sum() / tot, spec[fr > 5000].sum() / tot
        kind = "kick" if low > 0.25 else ("hat" if high > 0.35 else "snare")
        out.append(dict(i=i, kind=kind, low=round(float(low), 3), high=round(float(high), 3),
                        level=round(float(np.sqrt(np.mean(s ** 2))), 4)))
    return out


def pick_hits(classes):
    """classify_slices 결과에서 대표 조각 번호를 고른다: kick(저음 비율 최대), snare(중역 슬라이스 중 가장 큼),
    hat(고음 비율 최대), ghost(스네어 성격 중 가장 작은 것). 촙 패턴의 출발점으로 쓴다."""
    used = set()

    def take(pool, key, fn=max):
        pool = [c for c in pool if c["i"] not in used] or [c for c in classes if c["i"] not in used] or classes
        i = fn(pool, key=key)["i"]
        used.add(i)
        return i
    kick = take(classes, lambda c: c["low"])
    hat = take(classes, lambda c: c["high"])
    snares = [c for c in classes if c["kind"] == "snare"]
    snare = take(snares, lambda c: c["level"])
    ghost = take(snares, lambda c: c["level"], min)
    return dict(kick=kick, hat=hat, snare=snare, ghost=ghost)   # 서로 다른 조각


def even_slices(n):
    """원 브레이크가 정확한 박이면 n등분 (예: 1마디 16분 → 16)."""
    return [i / n for i in range(n)]


def break_kit(src, cuts, names=None, reverse_too=False, amp=100):
    """슬라이스 지점(0~1 비율) 목록 → 트랙에 넣을 악기 dict 목록.
    반환: [dict(name="S00 kick", inst=afp(...)), ...]. reverse_too=True면 각 슬라이스의 리버스 버전도 만든다.
    사용: tracks += [dict(**k, notes=notes_for[k["name"]], fxch=1) for k in kit]"""
    cuts = sorted(cuts) + [1.0]
    out = []
    for i in range(len(cuts) - 1):
        label = f"S{i:02d}" + (f" {names[i]}" if names and i < len(names) and names[i] else "")
        out.append(dict(name=label, inst=afp(src, cuts[i], cuts[i + 1], amp=amp)))
        if reverse_too:
            out.append(dict(name=label + " rev", inst=afp(src, cuts[i], cuts[i + 1], reverse=True, amp=amp)))
    return out


def cut(src, dst, start_sec, end_sec=None):
    ch, sr, a = _read(src)
    s = int(start_sec * sr) * ch
    e = len(a) if end_sec is None else int(end_sec * sr) * ch
    return _write(dst, ch, sr, a[s:e])


def concat(srcs, dst):
    parts = [_read(p) for p in srcs]
    ch, sr = parts[0][0], parts[0][1]
    out = array.array("h")
    for c, r, a in parts:
        if (c, r) != (ch, sr):
            raise ValueError("채널/샘플레이트가 다른 파일은 이어 붙일 수 없음")
        out.extend(a)
    return _write(dst, ch, sr, out)


def make_loop(raw, dst, loop_sec, fade_ms=3):
    """이음매 없는 루프 만들기. raw = 루프 구간만 렌더하고 뒤에 꼬리(리버브 등)가 남도록 빈 마디를 둔 WAV.
    [0, loop_sec) 구간에 loop_sec 이후의 꼬리를 앞부분에 더해 넣는다(tail wrap).
    끝 1~3ms는 클릭 방지를 위해 아주 짧게 페이드한다."""
    ch, sr, a = _read(raw)
    n = int(round(loop_sec * sr))
    body = array.array("h", a[:n * ch])
    tail = a[n * ch:]
    for i in range(min(len(tail), len(body))):
        body[i] = max(-32768, min(32767, body[i] + tail[i]))
    f = int(sr * fade_ms / 1000)
    for j in range(f):
        g = j / f
        for c in range(ch):
            idx = (n - 1 - j) * ch + c
            body[idx] = int(body[idx] * g)
    return _write(dst, ch, sr, body)


def seam_check(loop_wav, ms=5):
    """루프 끝→시작 경계에 클릭이 있는지. 경계의 샘플 점프를 주변(앞뒤 ms) 최대 샘플 간 변화량과 비교한다.
    ratio ≤ 1.5 면 OK(경계가 주변보다 튀지 않음). 첫 박 타격이 커도 파형이 이어지면 ratio는 낮다.
    숫자와 별개로 loop.wav를 concat()으로 2~3번 이어 붙여 직접 들어볼 것."""
    ch, sr, a = _read(loop_wav)
    w = int(sr * ms / 1000)
    frames = len(a) // ch
    worst = 0.0
    for c in range(ch):
        x = [a[i * ch + c] for i in range(frames - w, frames)] + [a[i * ch + c] for i in range(w)]
        steps = [abs(x[i + 1] - x[i]) for i in range(len(x) - 1)]
        seam = steps[w - 1]
        local = max(steps[:w - 1] + steps[w:]) or 1
        worst = max(worst, seam / local)
    return dict(ratio=round(worst, 2), ok=worst <= 1.5)


def normalize(pairs, peak_db=-1.0):
    """[(src, dst), ...] 전체의 최대 피크를 peak_db(dBFS)로 맞춘다. 모든 파일에 **같은 게인**을 적용하므로
    인트로와 루프처럼 이어 재생되는 파일은 반드시 한 번에 넘길 것. 반환: 적용한 게인(배수).
    이미 클리핑된 소리는 되살리지 못하므로, 렌더 피크가 0.99 이상이면 vol/mastervol을 낮춰 다시 렌더할 것."""
    data = [(_read(s), d) for s, d in pairs]
    peak = max(max(map(abs, a)) for (_, _, a), _ in data) or 1
    g = (10 ** (peak_db / 20)) * 32767 / peak
    for (ch, sr, a), d in data:
        _write(d, ch, sr, array.array("h", (max(-32768, min(32767, int(x * g))) for x in a)))
    return g


def ogg_loop(intro_wav, loop_wav, dst_ogg, quality=0.6):
    """인트로+루프를 하나의 OGG로 만들고 LOOPSTART/LOOPLENGTH 태그를 단다 (RPG Maker, Godot 플러그인 등이 인식).
    soundfile + mutagen 필요 (pip install soundfile mutagen numpy). 반환: 루프 지점(샘플 단위)."""
    import numpy as np
    import soundfile as sf
    from mutagen.oggvorbis import OggVorbis
    ia, sr = sf.read(intro_wav, dtype="float32", always_2d=True) if intro_wav else (None, None)
    la, sr2 = sf.read(loop_wav, dtype="float32", always_2d=True)
    data = la if ia is None else np.concatenate([ia, la])
    sf.write(dst_ogg, data, sr2, format="OGG", subtype="VORBIS")
    start = 0 if ia is None else len(ia)
    tags = OggVorbis(dst_ogg)
    tags["LOOPSTART"] = str(start)
    tags["LOOPLENGTH"] = str(len(la))
    tags.save()
    return dict(loop_start=start, loop_length=len(la), samplerate=sr2,
                loop_start_sec=start / sr2, loop_end_sec=(start + len(la)) / sr2)
