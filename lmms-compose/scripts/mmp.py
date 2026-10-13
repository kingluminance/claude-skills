"""LMMS(.mmp) 프로젝트 생성/읽기/렌더 도구.

틱 단위: 4분음표 = 48틱, 4/4 한 마디 = 192틱.
key는 MIDI 번호(60 = 가운데 도)로 다루고, 파일에 쓸 때 LMMS 번호(MIDI-12)로 변환한다.

사용 예:
    import os, sys; sys.path.insert(0, os.path.expanduser("~/.claude/skills/lmms-compose/scripts"))
    from mmp import *
    write_project("song.mmp", [dict(name="Piano", notes=[note(60, 0, Q)], patch=0)], bpm=100)
    render("song.mmp")          # song.wav
    write_midi("song.mid", read_project("song.mmp"))
    open_in_lmms("song.mmp")
"""
import os
import subprocess
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

import shutil

# 경로는 환경변수로 덮어쓸 수 있다. 기본값은 ~/tools/soundfonts, 표준 설치 위치.
SF2 = os.environ.get("SF2_PATH") or os.path.expanduser("~/tools/soundfonts/GeneralUser-GS.sf2").replace("\\", "/")
LMMS = os.environ.get("LMMS_EXE") or shutil.which("lmms") or next(
    (p for p in (r"C:\Program Files\LMMS\lmms.exe", r"C:\Program Files (x86)\LMMS\lmms.exe",
                 "/Applications/LMMS.app/Contents/MacOS/lmms", "/usr/bin/lmms") if os.path.exists(p)),
    "lmms")
Q = 48          # 4분음표
BAR = Q * 4     # 4/4 한 마디
E, S = Q // 2, Q // 4   # 8분, 16분


def note(key, pos, length, vol=100):
    """key: MIDI 번호, pos/length: 틱, vol: 0~200 (100이 기본)."""
    return (key, pos, length, vol)


def _track(name, notes, patch=0, bank=0, vol=100, pan=0, reverb=True):
    end = max((p + l for _, p, l, _ in notes), default=BAR)
    length = -(-end // BAR) * BAR
    note_xml = "\n".join(
        f'          <note pan="0" key="{k - 12}" vol="{v}" pos="{p}" len="{l}"/>'
        for k, p, l, v in sorted(notes, key=lambda n: (n[1], n[0]))
    )
    rv = 1 if reverb else 0
    return f"""      <track muted="0" type="0" name={quoteattr(name)} solo="0">
        <instrumenttrack pan="{pan}" fxch="0" usemasterpitch="1" pitchrange="1" pitch="0" basenote="57" vol="{vol}">
          <instrument name="sf2player">
            <sf2player src="{SF2}" bank="{bank}" patch="{patch}" gain="1" reverbOn="{rv}" reverbRoomSize="0.3" reverbDamping="0.3" reverbWidth="0.5" reverbLevel="0.6" chorusOn="0" chorusNum="3" chorusLevel="2" chorusSpeed="0.3" chorusDepth="8"/>
          </instrument>
          <fxchain numofeffects="0" enabled="0"/>
        </instrumenttrack>
        <pattern muted="0" steps="16" name={quoteattr(name)} pos="0" len="{length}" type="1">
{note_xml}
        </pattern>
      </track>"""


def write_project(path, tracks, bpm=120, ts=(4, 4), mastervol=100):
    """tracks: [dict(name=, notes=[note(...)], patch=GM번호(0~127), bank=0(드럼은 128), vol=, pan=-100~100, reverb=)]"""
    body = "\n".join(_track(**t) for t in tracks)
    song_end = max((p + l for t in tracks for _, p, l, _ in t["notes"]), default=BAR)
    xml = f"""<?xml version="1.0"?>
<!DOCTYPE lmms-project>
<lmms-project version="1.0" creator="LMMS" creatorversion="1.2.2" type="song">
  <head timesig_numerator="{ts[0]}" timesig_denominator="{ts[1]}" bpm="{bpm}" mastervol="{mastervol}" masterpitch="0"/>
  <song>
    <trackcontainer type="song" visible="1" x="5" y="5" width="720" height="300" maximized="0" minimized="0">
{body}
    </trackcontainer>
    <timeline lp0pos="0" lp1pos="{-(-song_end // BAR) * BAR}" lpstate="0"/>
  </song>
</lmms-project>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)


def read_project(path):
    """LMMS에서 사용자가 편집/저장한 .mmp(또는 .mmpz)를 읽는다.
    반환: dict(bpm=, ts=, tracks=[dict(name=, notes=[(midi_key, abs_pos, len, vol)], patch=, bank=, vol=, pan=, instrument=)])
    패턴이 여러 개면 패턴 pos를 더해 절대 위치로 합친다. sf2player가 아닌 트랙은 patch/bank가 None."""
    if path.endswith(".mmpz"):
        import zlib
        with open(path, "rb") as f:
            raw = f.read()
        root = ET.fromstring(zlib.decompress(raw[4:]))
    else:
        root = ET.parse(path).getroot()
    head = root.find("head")
    out = dict(bpm=float(head.get("bpm", 120)),
               ts=(int(head.get("timesig_numerator", 4)), int(head.get("timesig_denominator", 4))),
               tracks=[])
    for tr in root.iter("track"):
        it = tr.find("instrumenttrack")
        if tr.get("type") != "0" or it is None:
            continue
        inst = it.find("instrument")
        sf = inst.find("sf2player") if inst is not None else None
        notes = []
        for pat in tr.findall("pattern"):
            base = int(pat.get("pos", 0))
            for n in pat.findall("note"):
                notes.append((int(n.get("key")) + 12, base + int(n.get("pos")),
                              int(n.get("len")), int(float(n.get("vol", 100)))))
        out["tracks"].append(dict(
            name=tr.get("name"), notes=sorted(notes, key=lambda n: (n[1], n[0])),
            instrument=inst.get("name") if inst is not None else None,
            patch=int(sf.get("patch")) if sf is not None else None,
            bank=int(sf.get("bank")) if sf is not None else None,
            vol=int(float(it.get("vol", 100))), pan=int(float(it.get("pan", 0)))))
    return out


def write_midi(path, project):
    """read_project() 결과(또는 같은 모양의 dict)를 .mid로 저장. MuseScore 악보용."""
    import pretty_midi as pm
    m = pm.PrettyMIDI(initial_tempo=project["bpm"])
    sec = 60 / project["bpm"] / Q
    for t in project["tracks"]:
        drum = t.get("bank") == 128
        inst = pm.Instrument(program=0 if drum else (t.get("patch") or 0), is_drum=drum, name=t["name"])
        for k, p, l, v in t["notes"]:
            inst.notes.append(pm.Note(min(127, max(1, v)), k, p * sec, (p + l) * sec))
        m.instruments.append(inst)
    m.write(path)


def render(mmp_path, wav_path=None):
    """LMMS CLI로 WAV 렌더. fluidsynth 'No preset found on channel N' 경고는 무시해도 된다."""
    wav_path = wav_path or os.path.splitext(mmp_path)[0] + ".wav"
    subprocess.run([LMMS, "-r", mmp_path, "-o", wav_path], capture_output=True, timeout=600)
    if not os.path.exists(wav_path):
        raise RuntimeError("렌더 실패: " + wav_path)
    return wav_path


def wav_stats(wav_path):
    """길이(초)와 피크(0~1). 무음/너무 작은 소리 검증용."""
    import array
    import wave
    w = wave.open(wav_path)
    a = array.array("h", w.readframes(w.getnframes()))
    return dict(seconds=w.getnframes() / w.getframerate(), peak=max(map(abs, a[::20]), default=0) / 32768)


def open_in_lmms(mmp_path):
    subprocess.Popen([LMMS, os.path.abspath(mmp_path)])
