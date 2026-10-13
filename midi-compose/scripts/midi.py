"""MIDI 작곡 도구: .mid 쓰기/읽기, FluidSynth로 WAV 렌더, MuseScore로 악보(PDF/MusicXML) 내보내기.

틱 단위는 lmms-compose와 같다: 4분음표 = 48틱, 4/4 한 마디 = 192틱.
note(key, pos, length, vel) 의 key는 MIDI 번호(60 = 가운데 도), vel은 1~127.

사용 예:
    import os, sys; sys.path.insert(0, os.path.expanduser("~/.claude/skills/midi-compose/scripts"))
    from midi import *
    write_midi("song.mid", [dict(name="Piano", notes=[note(60, 0, Q)], program=0)], bpm=100)
    render("song.mid")                 # song.wav
    export_score("song.mid", "song.pdf")
"""
import glob
import os
import shutil
import subprocess

Q = 48          # 4분음표
BAR = Q * 4     # 4/4 한 마디
E, S = Q // 2, Q // 4   # 8분, 16분

# 경로는 환경변수로 덮어쓸 수 있다.
SF2 = os.environ.get("SF2_PATH") or os.path.expanduser("~/tools/soundfonts/GeneralUser-GS.sf2")


def _find(env, names, candidates):
    if os.environ.get(env):
        return os.environ[env]
    for n in names:
        if shutil.which(n):
            return shutil.which(n)
    for pattern in candidates:
        hits = sorted(glob.glob(os.path.expanduser(pattern)))
        if hits:
            return hits[-1]
    return names[0]


FLUIDSYNTH = _find("FLUIDSYNTH_EXE", ["fluidsynth"], [
    "~/tools/fluidsynth/*/bin/fluidsynth.exe", "~/tools/fluidsynth/bin/fluidsynth.exe",
    "/opt/homebrew/bin/fluidsynth", "/usr/local/bin/fluidsynth"])
MUSESCORE = _find("MUSESCORE_EXE", ["MuseScore4", "mscore", "musescore"], [
    r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe", r"C:\Program Files\MuseScore 3\bin\MuseScore3.exe",
    "/Applications/MuseScore 4.app/Contents/MacOS/mscore"])


def note(key, pos, length, vel=100):
    """key: MIDI 번호, pos/length: 틱, vel: 1~127."""
    return (key, pos, length, vel)


def write_midi(path, tracks, bpm=120, ts=(4, 4), key=None):
    """tracks: [dict(name=, notes=[note(...)], program=GM번호(0~127), drum=False)]
    key: 조표 문자열(예: "C", "Am", "Eb", "F#m"). 악보에 조표가 찍힌다."""
    import pretty_midi as pm
    m = pm.PrettyMIDI(initial_tempo=bpm)
    m.time_signature_changes.append(pm.TimeSignature(ts[0], ts[1], 0))
    if key:
        m.key_signature_changes.append(pm.KeySignature(pm.key_name_to_key_number(
            key[:-1] + " minor" if key.endswith("m") else key + " Major"), 0))
    sec = 60 / bpm / Q
    for t in tracks:
        inst = pm.Instrument(program=t.get("program", 0), is_drum=t.get("drum", False), name=t["name"])
        for k, p, l, v in t["notes"]:
            inst.notes.append(pm.Note(min(127, max(1, int(v))), int(k), p * sec, (p + l) * sec))
        m.instruments.append(inst)
    m.write(path)
    return path


def read_midi(path):
    """.mid를 읽어 write_midi와 같은 모양으로 반환 (틱은 반올림). 첫 템포만 사용.
    MuseScore에서 사용자가 고친 .mscz는 export_score(x.mscz, x.mid)로 먼저 변환한다."""
    import warnings
    import pretty_midi as pm
    with warnings.catch_warnings():  # MuseScore가 내보낸 .mid는 템포를 여러 트랙에 둬서 경고가 난다
        warnings.simplefilter("ignore")
        m = pm.PrettyMIDI(path)
    _, tempi = m.get_tempo_changes()
    bpm = round(float(tempi[0]), 2) if len(tempi) else 120.0
    tick = 60 / bpm / Q
    ts = m.time_signature_changes
    tracks = [dict(name=i.name, program=int(i.program), drum=i.is_drum,
                   notes=sorted(((int(n.pitch), round(n.start / tick), max(1, round((n.end - n.start) / tick)), int(n.velocity))
                                 for n in i.notes), key=lambda n: (n[1], n[0])))
              for i in m.instruments]
    return dict(bpm=bpm, ts=(ts[0].numerator, ts[0].denominator) if ts else (4, 4), tracks=tracks)


def render(mid_path, wav_path=None, gain=0.6):
    """FluidSynth로 WAV 렌더. gain 기본 0.6 (FluidSynth 기본 0.2는 너무 작다)."""
    wav_path = wav_path or os.path.splitext(mid_path)[0] + ".wav"
    subprocess.run([FLUIDSYNTH, "-ni", "-g", str(gain), "-F", wav_path, "-r", "44100", SF2, mid_path],
                   capture_output=True, timeout=600)
    if not os.path.exists(wav_path):
        raise RuntimeError("렌더 실패: " + wav_path)
    return wav_path


def export_score(src, out):
    """MuseScore로 변환. src: .mid/.mscz/.musicxml, out 확장자로 형식 결정: .pdf .musicxml .mscz .mid .png
    MuseScore CLI는 종료 시 segfault가 날 수 있으나 결과 파일은 정상이다. 그래서 반환코드 대신 파일로 확인한다.
    .png는 페이지마다 out-1.png, out-2.png ... 로 생긴다."""
    base, ext = os.path.splitext(out)
    check = f"{base}-1.png" if ext == ".png" else out
    if os.path.exists(check):
        os.remove(check)
    subprocess.run([MUSESCORE, "-o", out, src], capture_output=True, timeout=300)
    if not os.path.exists(check):
        raise RuntimeError("MuseScore 변환 실패: " + out)
    return check


def wav_stats(wav_path):
    """길이(초)와 피크(0~1). 무음/너무 작은 소리 검증용."""
    import array
    import wave
    w = wave.open(wav_path)
    a = array.array("h", w.readframes(w.getnframes()))
    return dict(seconds=w.getnframes() / w.getframerate(), peak=max(map(abs, a[::20]), default=0) / 32768)


def open_in_musescore(path):
    subprocess.Popen([MUSESCORE, os.path.abspath(path)])
