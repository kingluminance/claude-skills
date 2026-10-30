"""LMMS 1.2(.mmp) 프로젝트 생성/읽기/렌더 도구. 표준 라이브러리만 쓴다(write_midi만 pretty_midi 필요).

틱 단위: 4분음표 = 48틱, 4/4 한 마디 = 192틱.
key는 MIDI 번호(60 = 가운데 도)로 다루고, 파일에 쓸 때 LMMS 번호(MIDI-12)로 변환한다.

트랙 = dict(name=, notes=[note(...)], inst=<악기>, fx=[<이펙트>], env=adsr(...), filt=filt(...),
           vol=, pan=, fxch=<믹서 채널 번호>, split=<패턴 분할 틱>)
악기: sf2(), triosc(), afp(), kicker(), lb302(), raw_inst()   (inst를 안 주고 patch/bank만 주면 sf2)
이펙트: bitcrush(), distort(), dualfilter(), delay(), reverb(), amp(), bassboost(), stereo(), raw_fx()
오토메이션: 어떤 파라미터 값 자리에든 Auto([(틱, 값), ...]) 를 넣으면 오토메이션 트랙이 자동 생성된다.

사용 예:
    import os, sys; sys.path.insert(0, os.path.expanduser("~/.claude/skills/lmms-compose/scripts"))
    from mmp import *
    write_project("song.mmp", [
        dict(name="Lead", inst=triosc(osc("saw"), osc("saw", detune=8)), notes=[note(60, 0, Q)],
             env=adsr(0.005, 0.2, 0.3, 0.1), fx=[distort(4), reverb(0.6)]),
        dict(name="Piano", notes=[note(48, 0, BAR)], patch=0),
    ], bpm=100)
    render("song.mmp")
"""
import base64
import itertools
import math
import os
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET
from xml.sax.saxutils import quoteattr

# 경로는 환경변수로 덮어쓸 수 있다.
SF2 = os.environ.get("SF2_PATH") or os.path.expanduser("~/tools/soundfonts/GeneralUser-GS.sf2").replace("\\", "/")
LMMS = os.environ.get("LMMS_EXE") or shutil.which("lmms") or next(
    (p for p in (r"C:\Program Files\LMMS\lmms.exe", r"C:\Program Files (x86)\LMMS\lmms.exe",
                 "/Applications/LMMS.app/Contents/MacOS/lmms", "/usr/bin/lmms") if os.path.exists(p)),
    "lmms")
Q = 48                       # 4분음표
BAR = Q * 4                  # 4/4 한 마디
E, S, T = Q // 2, Q // 4, Q // 8   # 8분, 16분, 32분
ORIG = 69                    # afp(샘플)를 원래 피치로 재생하는 key (LMMS 기본 basenote = A4)


def note(key, pos, length, vol=100):
    """key: MIDI 번호, pos/length: 틱, vol: 0~200 (100이 기본)."""
    return (key, pos, length, vol)


def ticks_to_sec(ticks, bpm):
    return ticks * 60 / bpm / Q


# ───────────────────────── 오토메이션 ─────────────────────────
_ids = itertools.count(910000)


class Auto:
    """파라미터 값 자리에 넣는 오토메이션. points=[(절대틱, 값), ...]
    interp: 'step'(계단) | 'linear' | 'smooth'. 값의 단위는 그 파라미터 원래 단위와 같다."""
    INTERP = {"step": 0, "linear": 1, "smooth": 2}

    def __init__(self, points, interp="linear", name=None):
        self.points = sorted(points)
        self.interp = interp
        self.name = name
        self.id = next(_ids)

    @property
    def first(self):
        return self.points[0][1]


_autos = {}   # id → Auto. write_project가 XML에 실제로 쓰인 id만 골라 오토메이션 트랙을 만든다


def _a(attrs):
    """속성 dict → (속성 문자열, 자식 요소 문자열). Auto 값은 id 달린 자식 요소로 쓴다."""
    plain, kids = [], []
    for k, v in attrs.items():
        if isinstance(v, Auto):
            if v.name is None:
                v.name = k
            _autos[v.id] = v
            kids.append(f'<{k} id="{v.id}" value="{_fmt(v.first)}" scale_type="linear"/>')
        else:
            plain.append(f"{k}={quoteattr(_fmt(v))}")
    return " ".join(plain), "".join(kids)


def _fmt(v):
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def _el(tag, attrs, inner=""):
    a, kids = _a(attrs)
    body = kids + inner
    return f"<{tag} {a}>{body}</{tag}>" if body else f"<{tag} {a}/>"


# ───────────────────────── 악기 ─────────────────────────
def sf2(patch=0, bank=0, reverb=True, gain=1.0, src=None):
    """사운드폰트(GM). 드럼은 bank=128."""
    return _el("instrument", {"name": "sf2player"}, _el("sf2player", dict(
        src=src or SF2, bank=bank, patch=patch, gain=gain, reverbOn=reverb, reverbRoomSize=0.3,
        reverbDamping=0.3, reverbWidth=0.5, reverbLevel=0.6, chorusOn=0, chorusNum=3, chorusLevel=2,
        chorusSpeed=0.3, chorusDepth=8)))


WAVES = dict(sine=0, triangle=1, saw=2, square=3, moogsaw=4, exp=5, noise=6)
MODS = dict(pm=0, am=1, mix=2, sync=3, fm=4)


def osc(wave="saw", vol=33, coarse=0, detune=0, pan=0, phase=0):
    """TripleOscillator 오실레이터 하나. wave: sine/triangle/saw/square/moogsaw/exp/noise,
    coarse: 반음, detune: 센트(좌우 반대로 벌려 스테레오 폭), vol: 0~200."""
    return dict(wave=wave, vol=vol, coarse=coarse, detune=detune, pan=pan, phase=phase)


def triosc(o1=None, o2=None, o3=None, mod="mix"):
    """LMMS 내장 감산 신스. 리드/스탭/베이스/패드에 쓴다. mod: 1→2, 2→3 변조 방식 (mix/am/fm/pm/sync)."""
    oscs = [o1 or osc("saw"), o2 or osc("saw", vol=0), o3 or osc("saw", vol=0)]
    attrs = {}
    for i, o in enumerate(oscs):
        attrs.update({f"wavetype{i}": WAVES[o["wave"]], f"vol{i}": o["vol"], f"coarse{i}": o["coarse"],
                      f"finel{i}": -o["detune"], f"finer{i}": o["detune"], f"pan{i}": o["pan"],
                      f"phoffset{i}": o["phase"], f"stphdetun{i}": 0, f"userwavefile{i}": ""})
    attrs.update(modalgo1=MODS[mod], modalgo2=MODS[mod], modalgo3=2)
    return _el("instrument", {"name": "tripleoscillator"}, _el("tripleoscillator", attrs))


def afp(src, start=0.0, end=1.0, reverse=False, loop=False, amp=100, interp=1):
    """AudioFileProcessor: 샘플(WAV/OGG) 재생. start/end는 파일 전체 길이 대비 비율(0~1)로, 슬라이스에 쓴다.
    key=ORIG(69)에서 원래 피치. 한 옥타브 아래로 = 57. loop: False/True/'pingpong'."""
    lp = {False: 0, True: 1, "pingpong": 2}[loop]
    return _el("instrument", {"name": "audiofileprocessor"}, _el("audiofileprocessor", dict(
        src=os.path.abspath(src).replace("\\", "/"), sframe=start, eframe=end, lframe=start,
        reversed=reverse, looped=lp, amp=amp, stutter=0, interp=interp)))


def kicker(start=150, end=40, decay=300, dist=0.0, gain=1.0, click=0.4, noise=0.0, slope=0.06, env=1.0,
           startnote=False, endnote=False):
    """합성 킥/808/타격음. start→end Hz로 피치가 떨어지고, decay는 ms. dist(0~100)로 찌그러뜨린다.
    startnote=True면 시작 주파수를 연주한 음 높이로 쓴다 (808 베이스처럼 음정 있는 타격)."""
    return _el("instrument", {"name": "kicker"}, _el("kicker", dict(
        startfreq=start, endfreq=end, decay=decay, dist=dist, distend=dist, gain=gain, click=click,
        noise=noise, slope=slope, env=env, startnote=startnote, endnote=endnote, version=1)))


def lb302(cut=0.3, res=0.8, env_mod=0.5, decay=0.3, dist=0.0, shape="saw", slide=False, db24=False):
    """TB-303 스타일 애시드 베이스. shape: saw/triangle/square/roundsquare/moog/sine/exp/noise."""
    shapes = dict(saw=0, triangle=1, square=2, roundsquare=3, moog=4, sine=5, exp=6, noise=7)
    return _el("instrument", {"name": "lb302"}, _el("lb302", dict(
        vcf_cut=cut, vcf_res=res, vcf_mod=env_mod, vcf_dec=decay, dist=dist, shape=shapes[shape],
        slide=slide, slide_dec=0.6, db24=db24, dead=0)))


def raw_inst(name, attrs, tag=None):
    """다른 LMMS 악기(nes, sid, bitinvader, organic, monstro, ...)를 속성 그대로 쓴다.
    속성 이름은 LMMS 데모/프리셋(.xpf)에서 확인한다."""
    return _el("instrument", {"name": name}, _el(tag or name, attrs))


# ───────────────────────── 엔벨로프/필터 ─────────────────────────
def adsr(att=0.0, dec=0.5, sus=1.0, rel=0.1, hold=0.0, amt=1.0):
    """볼륨 엔벨로프. 시간은 초(0~2), sus는 서스테인 레벨(0~1)."""
    return dict(att=att, dec=dec, sus=sus, rel=rel, hold=hold, amt=amt)


FILTERS = dict(lowpass=0, highpass=1, bandpass=2, bandpass2=3, notch=4, allpass=5, moog=6, lowpass2x=7,
               rc_lowpass=8, rc_bandpass=9, rc_highpass=10, rc_lowpass24=11, rc_bandpass24=12,
               rc_highpass24=13, formant=14, moog2x=15, sv_lowpass=16, sv_bandpass=17, sv_highpass=18,
               sv_notch=19, fast_formant=20, tripole=21)


def filt(type="lowpass", cut=14000, res=0.5):
    """악기 자체 필터 (트랙 필터). cut Hz, res 0.01~10."""
    return dict(ftype=FILTERS[type], fcut=cut, fres=res)


def _eldata(env, flt):
    env = env or {}
    f = flt or {}
    vol = dict(pdel=0, att=env.get("att", 0), hold=env.get("hold", 0.5 if not env else 0), dec=env.get("dec", 0.5),
               sus=round(1 - env.get("sus", 0.5), 4), rel=env.get("rel", 0.1), amt=env.get("amt", 0) if env else 0,
               lpdel=0, latt=0, lspd=0.1, lshp=0, lamt=0, x100=0)
    flat = dict(pdel=0, att=0, hold=0.5, dec=0.5, sus=0.5, rel=0.1, amt=0, lpdel=0, latt=0, lspd=0.1, lshp=0,
                lamt=0, x100=0)
    inner = _el("elvol", vol) + _el("elcut", flat) + _el("elres", flat)
    return _el("eldata", dict(ftype=f.get("ftype", 0), fcut=f.get("fcut", 14000), fres=f.get("fres", 0.5),
                              fwet=1 if flt else 0), inner)


# ───────────────────────── 이펙트 ─────────────────────────
def _fx(name, ctrl_tag, attrs, wet=1.0, on=True):
    return _el("effect", dict(name=name, on=on, wet=wet, gate=0, autoquit=1, autoquit_numerator=4,
                              autoquit_denominator=4, syncmode=0), _el(ctrl_tag, attrs) + "<key/>")


def bitcrush(rate=11025, bits=6, ingain=0, outgain=0, noise=0, clip=0, stereodiff=0, wet=1.0):
    """샘플레이트/비트 깎기. rate 20~44100 Hz, bits 1~8 (levels=2^bits). 글리치/로파이 핵심."""
    levels = bits if isinstance(bits, Auto) else 2 ** bits
    return _fx("bitcrush", "bitcrushcontrols", dict(
        rate=rate, levels=levels, ingain=ingain, outgain=outgain, innoise=noise, outclip=clip,
        stereodiff=stereodiff, rateon=1, depthon=1), wet)


def _curve(drive):
    pts = [math.tanh(drive * (i + 1) / 200) / math.tanh(drive) for i in range(200)]
    return base64.b64encode(struct.pack("<200f", *pts)).decode()


def distort(drive=4.0, ingain=1.0, outgain=0.8, wet=1.0):
    """웨이브셰이퍼 tanh 디스토션. drive 1(약함)~20(박살). 베이스/스탭을 두껍고 더럽게."""
    return _fx("waveshaper", "waveshapercontrols", dict(
        inputGain=ingain, outputGain=outgain, clipInput=1, waveShape=_curve(drive)), wet)


def dualfilter(cut=2000, res=0.5, type="lowpass", gain=100, cut2=None, res2=0.5, type2="lowpass", mix=None,
               wet=1.0):
    """필터 이펙트 (스윕은 cut에 Auto). 두 번째 필터는 cut2를 줄 때만 켜진다.
    mix: -1 = 1번만, 0 = 반반, 1 = 2번만. 기본은 cut2가 없으면 -1 (0이면 소리가 절반이 된다)."""
    if mix is None:
        mix = 0.0 if cut2 else -1.0
    return _fx("dualfilter", "DualFilterControls", dict(
        enabled1=1, filter1=FILTERS[type], cut1=cut, res1=res, gain1=gain,
        enabled2=1 if cut2 else 0, filter2=FILTERS[type2], cut2=cut2 or 7000, res2=res2, gain2=100,
        mix=mix), wet)


def delay(time=0.25, feedback=0.4, outgain=0, lfo_freq=2, lfo_amt=0, wet=0.5):
    """딜레이. time은 초 (195 BPM 8분 = 60/195/2 ≈ 0.154)."""
    return _fx("delay", "Delay", dict(
        DelayTimeSamples=time, FeebackAmount=feedback, OutGain=outgain, LfoFrequency=lfo_freq,
        LfoAmount=lfo_amt), wet)


def reverb(size=0.85, color=10000, input=0, output=0, wet=0.3):
    """ReverbSC. size 0~1, color(댐핑) Hz, input/output dB."""
    return _fx("reverbsc", "ReverbSCControls", dict(input=input, size=size, color=color, output=output), wet)


def amp(volume=100, pan=0, left=100, right=100):
    """증폭/팬. volume 0~200 (%)."""
    return _fx("amplifier", "AmplifierControls", dict(volume=volume, pan=pan, left=left, right=right))


def bassboost(freq=100, gain=1.0, ratio=2.0):
    return _fx("bassbooster", "bassboostercontrols", dict(freq=freq, gain=gain, ratio=ratio))


def stereo(width=150):
    return _fx("stereoenhancer", "stereoenhancercontrols", dict(width=width))


def raw_fx(name, ctrl_tag, attrs, wet=1.0):
    """다른 LMMS 이펙트를 속성 그대로 쓴다 (예: flanger, multitapecho). 속성 이름은 데모 프로젝트에서 확인."""
    return _fx(name, ctrl_tag, attrs, wet)


def _fxchain(fx):
    fx = fx or []
    return f'<fxchain numofeffects="{len(fx)}" enabled="{1 if fx else 0}">{"".join(fx)}</fxchain>'


# ───────────────────────── 패턴 도우미 ─────────────────────────
def grid(pattern, mapping, step=S, start=0, vol=100, accent=None, keys=None):
    """문자열 그리드 → {트랙이름: [note...]}. 한 글자 = step 틱. '.', '-', ' '는 쉼, '|'는 무시(가독용).
    mapping: {'k': 'Kick', 's': 'Snare'}, keys: {'k': 36} (기본 ORIG). 대문자는 accent 볼륨(기본 vol+25).
    예) grid("k.s.|k.s.", {"k": "Kick", "s": "Snare"})"""
    out = {}
    pos = start
    for ch in pattern:
        if ch == "|":
            continue
        low = ch.lower()
        if low in mapping:
            v = (accent or vol + 25) if ch.isupper() else vol
            out.setdefault(mapping[low], []).append(note((keys or {}).get(low, ORIG), pos, step, v))
        pos += step
    return out


def merge(*dicts):
    """grid() 결과들을 합친다."""
    out = {}
    for d in dicts:
        for k, v in d.items():
            out.setdefault(k, []).extend(v)
    return out


def stutter(key, pos, length, div=T, vol=100, decay=0.0):
    """같은 음을 div 간격으로 연타 (브레이크 롤/스터터). decay>0이면 갈수록 작아진다."""
    n = max(1, length // div)
    return [note(key, pos + i * div, div, max(1, int(vol * (1 - decay * i / n)))) for i in range(n)]


def shift(notes, ticks=0, semis=0):
    return [(k + semis, p + ticks, l, v) for k, p, l, v in notes]


# ───────────────────────── 트랙/프로젝트 ─────────────────────────
def _patterns(name, notes, split):
    if not notes:
        return ""
    end = max(p + l for _, p, l, _ in notes)
    if not split:
        groups = {0: notes}
        size = {0: -(-end // BAR) * BAR}
    else:
        groups = {}
        for n in notes:
            groups.setdefault(n[1] // split * split, []).append(n)
        size = {s: split for s in groups}
    out = []
    for start in sorted(groups):
        ns = sorted(groups[start], key=lambda n: (n[1], n[0]))
        length = max(size[start], -(-max(p + l - start for _, p, l, _ in ns) // BAR) * BAR)
        body = "".join(f'<note pan="0" key="{k - 12}" vol="{v}" pos="{p - start}" len="{l}"/>' for k, p, l, v in ns)
        out.append(f'<pattern muted="0" steps="16" name={quoteattr(name)} pos="{start}" len="{length}" type="1">{body}</pattern>')
    return "".join(out)


def _track(name, notes=(), inst=None, patch=0, bank=0, reverb=True, vol=100, pan=0, fx=None, env=None,
           filt=None, fxch=0, pitch=0, pitchrange=None, split=None, muted=False):
    inst = inst or sf2(patch, bank, reverb)
    if pitchrange is None:   # pitch(센트)에 Auto를 쓰면 범위를 자동으로 넓힌다
        vals = [v for _, v in pitch.points] if isinstance(pitch, Auto) else [pitch]
        pitchrange = max(1, min(60, -(-max(abs(v) for v in vals) // 100)))
    it = _el("instrumenttrack", dict(vol=vol, pan=pan, fxch=fxch, pitch=pitch, basenote=57, usemasterpitch=1,
                                     pitchrange=pitchrange),
             inst + _eldata(env, filt) + _fxchain(fx))
    return (f'<track muted="{int(muted)}" type="0" name={quoteattr(name)} solo="0">{it}'
            f'{_patterns(name, list(notes), split)}</track>')


def _auto_tracks(xml):
    import re
    out = []
    for a in (_autos[int(i)] for i in dict.fromkeys(re.findall(r'<\w+ id="(\d+)"', xml)) if int(i) in _autos):
        start = a.points[0][0]
        end = max(a.points[-1][0], start + 1)
        times = "".join(f'<time pos="{p - start}" value="{_fmt(v)}"/>' for p, v in a.points)
        length = max(BAR, -(-(end - start) // BAR) * BAR)
        out.append(f'<track muted="0" type="5" name={quoteattr("Auto: " + a.name)} solo="0"><automationtrack/>'
                   f'<automationpattern name={quoteattr(a.name)} pos="{start}" len="{length}" tens="1" mute="0" '
                   f'prog="{Auto.INTERP[a.interp]}">{times}<object id="{a.id}"/></automationpattern></track>')
    return "".join(out)


def _mixer(channels, master_fx):
    chans = [f'<fxchannel num="0" name="Master" volume="1" muted="0" soloed="0">{_fxchain(master_fx)}</fxchannel>']
    for i, c in enumerate(channels or [], 1):
        vol = c.get("volume", 1.0)
        if not isinstance(vol, Auto) and vol > 2.0:   # LMMS 채널 페이더 최대 2.0 (넘는 값은 무시됨)
            raise ValueError(f"믹서 채널 '{c['name']}' volume {vol} > 2.0: 다른 채널을 낮추고 마스터로 보상할 것")
        a, kids = _a(dict(num=i, name=c["name"], volume=vol, muted=0, soloed=0))
        # send가 없으면 채널 소리가 마스터로 가지 않아 무음이 된다. to=다른 채널 번호로 버스 구성 가능
        send = f'<send channel="{c.get("to", 0)}" amount="1"/>'
        chans.append(f"<fxchannel {a}>{kids}{_fxchain(c.get('fx'))}{send}</fxchannel>")
    return f'<fxmixer visible="1" x="5" y="310" width="550" height="340" maximized="0" minimized="0">{"".join(chans)}</fxmixer>'


def write_project(path, tracks, bpm=120, ts=(4, 4), mastervol=100, mixer=None, master_fx=None, loop=None):
    """tracks: _track 인자 dict 목록 (모듈 docstring 참고).
    mixer: [dict(name="Breaks", fx=[...], volume=1.0), ...] → 채널 번호 1, 2, ... (트랙의 fxch로 보냄)
    master_fx: 마스터 채널 이펙트. bpm/mastervol에도 Auto 사용 가능 (템포 오토메이션).
    loop: (시작틱, 끝틱) LMMS 루프 구간 표시."""
    head = _el("head", dict(timesig_numerator=ts[0], timesig_denominator=ts[1], bpm=bpm, mastervol=mastervol,
                            masterpitch=0))
    body = "".join(_track(**t) for t in tracks)
    mix = _mixer(mixer, master_fx)
    autos = _auto_tracks(head + body + mix)
    song_end = max((p + l for t in tracks for _, p, l, _ in t.get("notes", ())), default=BAR)
    lp = loop or (0, -(-song_end // BAR) * BAR)
    xml = f"""<?xml version="1.0"?>
<!DOCTYPE lmms-project>
<lmms-project version="1.0" creator="LMMS" creatorversion="1.2.2" type="song">
  {head}
  <song>
    <trackcontainer type="song" visible="1" x="5" y="5" width="720" height="300" maximized="0" minimized="0">
{body}{autos}
    </trackcontainer>
    {mix}
    <timeline lp0pos="{lp[0]}" lp1pos="{lp[1]}" lpstate="{1 if loop else 0}"/>
  </song>
</lmms-project>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    return path


def read_project(path):
    """LMMS에서 사용자가 편집/저장한 .mmp(또는 .mmpz)를 읽는다.
    반환: dict(bpm=, ts=, tracks=[dict(name=, notes=[(midi_key, abs_pos, len, vol)], instrument=, patch=, bank=,
    vol=, pan=, xml=<instrument 요소 원문>)])
    instrument 원문(xml)을 같이 돌려주므로, 사용자가 바꾼 신스 설정을 보존하려면 inst=t["xml"]로 다시 쓰면 된다.
    단 이펙트/엔벨로프/오토메이션은 보존하지 않으므로 필요하면 사용자에게 알리고 원문을 직접 편집한다."""
    if path.endswith(".mmpz"):
        import zlib
        with open(path, "rb") as f:
            root = ET.fromstring(zlib.decompress(f.read()[4:]))
    else:
        root = ET.parse(path).getroot()
    head = root.find("head")
    bpm = head.get("bpm") or (head.find("bpm").get("value") if head.find("bpm") is not None else 120)
    out = dict(bpm=float(bpm),
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

        def num(attr, default):
            v = it.get(attr)
            if v is None and it.find(attr) is not None:
                v = it.find(attr).get("value")
            return int(float(v if v is not None else default))
        out["tracks"].append(dict(
            name=tr.get("name"), notes=sorted(notes, key=lambda n: (n[1], n[0])),
            instrument=inst.get("name") if inst is not None else None,
            patch=int(sf.get("patch")) if sf is not None else None,
            bank=int(sf.get("bank")) if sf is not None else None,
            vol=num("vol", 100), pan=num("pan", 0),
            xml=ET.tostring(inst, encoding="unicode") if inst is not None else None))
    return out


def write_midi(path, project):
    """read_project() 결과(또는 같은 모양의 dict)를 .mid로 저장. 악보/다른 DAW용 (pretty_midi 필요).
    sf2가 아닌 트랙(신스, 샘플)은 피아노(0)로 나간다."""
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


def render(mmp_path, out_path=None, fmt=None, loop=False, samplerate=44100, float32=False):
    """LMMS CLI 렌더. fmt: wav/ogg/flac/mp3 (out_path 확장자로 추정).
    loop=True면 LMMS가 루프 렌더(꼬리를 앞에 겹침)를 한다.
    fluidsynth 'No preset found on channel N' 경고는 무시해도 된다."""
    out_path = out_path or os.path.splitext(mmp_path)[0] + ".wav"
    fmt = fmt or os.path.splitext(out_path)[1].lstrip(".") or "wav"
    cmd = [LMMS, "render", mmp_path, "-o", out_path, "-f", fmt, "-s", str(samplerate)]
    if loop:
        cmd.append("-l")
    if float32:
        cmd.append("-a")
    if os.path.exists(out_path):
        os.remove(out_path)
    subprocess.run(cmd, capture_output=True, timeout=1800)
    if not os.path.exists(out_path):
        raise RuntimeError("렌더 실패: " + out_path)
    return out_path


def render_tracks(mmp_path, out_dir):
    """트랙별 스템 WAV (게임 다이나믹 BGM, 믹스 점검용)."""
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run([LMMS, "rendertracks", mmp_path, "-o", out_dir], capture_output=True, timeout=3600)
    return sorted(os.path.join(out_dir, f) for f in os.listdir(out_dir))


def wav_stats(wav_path):
    """길이(초)와 피크(0~1). 무음/너무 작은 소리/클리핑 검증용."""
    import array
    import wave
    w = wave.open(wav_path)
    a = array.array("h", w.readframes(w.getnframes()))
    return dict(seconds=w.getnframes() / w.getframerate(), peak=max(map(abs, a[::7]), default=0) / 32768)


def open_in_lmms(mmp_path):
    subprocess.Popen([LMMS, os.path.abspath(mmp_path)])
