---
name: lmms-compose
description: LMMS(무료 DAW)로 작곡/편곡/사운드 디자인. Claude가 .mmp 프로젝트 파일을 직접 써서 트랙·악기·음표·이펙트·오토메이션을 만들고, 사용자는 LMMS UI(피아노롤)에서 열어 듣고 고친다. 내장 신스(TripleOscillator, LB302, Kicker), 샘플러(브레이크 슬라이스), GM 사운드폰트, 이펙트(디스토션, 비트크러시, 필터, 리버브, 딜레이), 믹서 버스, 파라미터·템포 오토메이션, 스템 렌더, 게임용 이음매 없는 루프와 OGG 루프 태그를 지원한다. '작곡해줘', '곡 만들어줘', 'LMMS', '.mmp', '편곡', '비트 만들어줘', '브레이크코어', 'EDM', '게임 BGM', '루프', '멜로디 써줘', 'BGM' 요청 시 사용(작곡 요청의 기본값). 악보가 주목적이거나 .mid/MuseScore를 원하면 midi-compose를 쓴다.
---

# LMMS 작곡 스킬

Claude는 LMMS 화면을 클릭하지 않는다. **.mmp(XML) 파일을 직접 쓰고 읽는다.** 사용자는 같은 파일을 LMMS UI에서 열어 재생·편집한다.

## 필요한 환경
| 항목 | 기본 위치 (환경변수로 변경 가능) |
|---|---|
| LMMS 1.2.x | 표준 설치 위치 자동 탐색 (`LMMS_EXE`) |
| 사운드폰트 GeneralUser GS | `~/tools/soundfonts/GeneralUser-GS.sf2` (`SF2_PATH`) — sf2() 악기를 쓸 때만 |
| `scripts/mmp.py` | 프로젝트 생성/읽기/렌더. **표준 라이브러리만** (write_midi만 pretty_midi) |
| `scripts/audio.py` | 슬라이스·루프·노멀라이즈는 표준 라이브러리만. `to_pcm16`, `ogg_loop`은 `soundfile mutagen numpy` |

**새 PC에서 처음 쓸 때 먼저 확인**:
`python -c "import os,sys; sys.path.insert(0, os.path.expanduser('~/.claude/skills/lmms-compose/scripts')); import mmp; print(mmp.LMMS, os.path.exists(mmp.LMMS)); print(mmp.SF2, os.path.exists(mmp.SF2))"`
없으면 사용자에게 알리고 설치: LMMS(`winget install LMMS.LMMS` / `brew install --cask lmms`), 사운드폰트(`https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2` → `~/tools/soundfonts/`), 필요 시 `pip install soundfile mutagen numpy pretty_midi`.
PC에 Python이 여러 개면 패키지가 깔린 쪽을 쓴다 (`python -c "import soundfile"`로 확인).

기본 작업 폴더는 `~/Documents/music/<곡이름>/`. 생성 스크립트 `build.py`, 샘플 `samples/`, 결과 `out/`.

## 워크플로
1. **요구 파악 / 기획서 확인**: 폴더에 `기획서.md`가 있으면 먼저 읽고 따른다. 없으면 장르, 분위기, BPM, 길이, 조성, 악기를 묻거나 합리적 기본값을 정해 알린다.
2. **구조 설계**: 섹션과 마디 수, 코드 진행을 먼저 짧게 보여준다.
3. **`build.py` 작성** → `write_project()`. 섹션별 함수(예: `section_a(start)`)가 note 목록을 돌려주게 하면 수정이 쉽다.
4. **짧게 먼저**: 대표 구간(4~16마디)만 만들어 렌더하고 사용자에게 들려준 뒤 방향을 확정하고 전체로 확장한다.
5. **검증**: `render()` → `wav_stats()`. 피크 0.99 이상이면 클리핑이니 vol/mastervol/master_fx amp를 낮춘다. 0.1 미만이면 올린다. 무음이면 실패로 보고. 트랙 밸런스는 `render_tracks()` 스템 피크로 본다.
6. **열기**: `open_in_lmms()`. 사용자는 스페이스바로 재생, 트랙 이름 더블클릭으로 피아노롤, 오토메이션 트랙 더블클릭으로 곡선 편집.
7. **반복**: **사용자가 LMMS에서 고쳐 저장했다면** 덮어쓰기 전에 `read_project()`로 읽어 반영한다. `read_project()`는 음표와 악기 원문(`xml`)만 보존하고 이펙트·엔벨로프·오토메이션은 보존하지 않는다. 그런 걸 고쳤다면 사용자에게 알리고 새 파일명(`_v2`)으로 저장하거나 .mmp 원문을 직접 편집한다.

## mmp.py API
```python
import os, sys; sys.path.insert(0, os.path.expanduser("~/.claude/skills/lmms-compose/scripts"))
from mmp import *
from audio import *

# 틱: Q=48(4분) E=24(8분) S=12(16분) T=6(32분) BAR=192. 셋잇단 8분=16, 셋잇단 16분=8
# note(key=MIDI번호, pos=시작틱, length=길이틱, vol=0~200)   ticks_to_sec(ticks, bpm)
write_project("song.mmp", tracks, bpm=195, mastervol=100,
              mixer=[dict(name="Drums", fx=[...]), dict(name="Synths", fx=[...])],  # 채널 1, 2 → 트랙 fxch=1/2
              master_fx=[amp(80)], loop=(start_tick, end_tick))
```
**트랙 dict 키**: `name, notes, inst, fx=[...], env=adsr(...), filt=filt(...), vol(0~200), pan(-100~100), fxch, pitch(센트), split(틱: 이 간격으로 패턴을 나눠 LMMS에서 보기 좋게, 예: BAR*8), muted`. `inst`가 없으면 `patch`/`bank`로 sf2.

### 악기
| 함수 | 용도 |
|---|---|
| `sf2(patch, bank=0)` | GM 사운드폰트. 드럼은 bank=128 (아래 GM 표) |
| `triosc(osc(...), osc(...), osc(...), mod="mix")` | 내장 감산 신스. `osc(wave, vol=33, coarse=반음, detune=센트, pan)`. wave: sine/triangle/saw/square/moogsaw/exp/noise. mod: mix/am/fm/pm/sync. **세 osc vol 합은 100 이하로** (넘으면 쉽게 클리핑) |
| `afp(src, start=0, end=1, reverse, loop, amp)` | 샘플러. start/end는 파일 길이 대비 비율. **key=ORIG(69)가 원래 피치**, 57은 한 옥타브 아래 |
| `kicker(start=Hz, end=Hz, decay=ms, dist, click, noise, startnote)` | 합성 킥/808 붐/타격. `startnote=True`면 연주한 음 높이에서 시작(음정 있는 808 베이스) |
| `lb302(cut, res, env_mod, decay, dist, shape, slide)` | 303 애시드 베이스 |
| `raw_inst(name, attrs)` | 그 밖의 LMMS 악기(nes, sid, bitinvader, organic, monstro, watsyn...). 속성은 LMMS `data/presets`의 .xpf에서 확인 |

`env=adsr(att, dec, sus, rel, hold)`: 시간은 초, **sus는 레벨(0~1)**. 스탭은 `adsr(0.002, 0.12, 0.0, 0.05)`, 패드는 `adsr(0.5, 1, 0.8, 1.5)`.
`filt=filt(type, cut, res)`: 트랙 자체 필터. type: lowpass/highpass/bandpass/notch/moog/formant/sv_lowpass/... (`FILTERS` 참고).

### 이펙트 (트랙 `fx=[...]`, 믹서 채널 `fx`, `master_fx`)
| 함수 | 용도 |
|---|---|
| `distort(drive=1~20, outgain)` | tanh 웨이브셰이퍼. 베이스/스탭을 두껍고 더럽게 |
| `bitcrush(rate=Hz, bits=1~8)` | 샘플레이트·비트 깎기. 글리치/로파이 |
| `dualfilter(cut, res, type, cut2=..., mix)` | 필터 이펙트. 스윕은 cut에 Auto |
| `reverb(size, color, wet)` / `delay(time초, feedback, wet)` | 공간감. 195BPM 8분 딜레이 = `ticks_to_sec(E, 195)` |
| `amp(volume%, pan)` / `bassboost(freq, gain)` / `stereo(width)` | 레벨·저음·스테레오 폭 |
| `raw_fx(name, ctrl_tag, attrs)` | flanger, multitapecho, eq 등. 속성은 LMMS `data/projects` 데모에서 확인 |

### 오토메이션
**어떤 파라미터 값 자리에든** `Auto([(절대틱, 값), ...], interp="linear"|"step"|"smooth", name=)`을 넣으면 오토메이션 트랙이 자동으로 생긴다. 예:
- 필터 스윕: `dualfilter(cut=Auto([(0, 200), (BAR*8, 16000)], interp="smooth"))`
- 글리치 구간만 크러시: `bitcrush(rate=Auto([(0, 44100), (BAR*16, 3000), (BAR*17, 44100)], interp="step"))`
- 템포 변화: `write_project(..., bpm=Auto([(0, 195), (BAR*40, 97.5), (BAR*44, 195)], interp="step"))`
- 페이드: 트랙 `vol=Auto([(0, 0), (BAR*4, 100)])`

### 패턴 도우미
```python
grid("K.s.|..sK|.ks.|S.ss", {"k": "Kick", "s": "Snare"}, step=S, keys={"k": ORIG})  # → {"Kick": [...], "Snare": [...]}
# 한 글자 = step 틱, 대문자 = 악센트, '.'/'-' 쉼, '|' 무시. merge(d1, d2)로 합친다
stutter(key, pos, length, div=T, vol=100, decay=0.3)  # 같은 음 연타 (롤/스터터)
shift(notes, ticks=BAR*4, semis=-12)                  # 이동/조옮김
```

### 렌더·출력
```python
render("song.mmp", "out/song.wav")        # fmt은 확장자로 (wav/ogg/flac/mp3)
render_tracks("song.mmp", "out/stems")    # 트랙별 스템
wav_stats("out/song.wav")                 # {'seconds', 'peak'}
read_project("song.mmp"); write_midi("song.mid", proj); open_in_lmms("song.mmp")
```

## audio.py: 샘플과 게임 루프
```python
to_pcm16("break.ogg", "samples/break.wav")      # 받은 샘플을 16bit WAV로 (soundfile 필요)
cuts = onsets("samples/break.wav")              # 타격 지점 자동 감지(0~1 비율). sensitivity로 조절
cuts = even_slices(16)                           # 원본이 박에 딱 맞으면 16등분이 더 정확
kit = break_kit("samples/break.wav", cuts, names=["kick", "hat", "snare", ...], reverse_too=True)
tracks += [dict(**k, notes=chops.get(k["name"], []), fxch=1) for k in kit]   # 슬라이스 = 트랙 하나
```
**브레이크 촙 요령**: 원본 BPM과 곡 BPM이 다르면 슬라이스를 원래 피치(ORIG)로 쓰고 위치만 새 그리드에 놓는다(타임스트레치 불필요). 피치를 내리면 길어지고 어두워진다(ORIG-5, ORIG-12). 리버스 슬라이스는 다음 박 직전에 끝나게 배치한다.

**게임용 이음매 없는 루프**:
1. 루프 구간만 담은 프로젝트를 렌더한다. 루프 뒤에 빈 마디 2개를 두어 리버브 꼬리가 녹음되게 한다(마지막에 아주 작은 더미 음표 `note(0, end+BAR*2-1, 1, 1)`).
2. `make_loop("loop_raw.wav", "out/loop.wav", ticks_to_sec(loop_ticks, bpm))`: 꼬리를 루프 앞에 겹친다.
3. `seam_check("out/loop.wav")` → `ok`가 True인지 확인. `concat([loop]*3, "check.wav")`로 이어 붙인 파일도 들어본다.
4. 인트로는 `cut()`으로 잘라낸다. 인트로 끝 1/16박을 비워 두면 꼬리 문제가 없다.
5. `normalize([(intro, intro_n), (loop, loop_n)], -1.0)`: **같은 게인**으로 -1dBFS.
6. `ogg_loop(intro_n, loop_n, "out/game.ogg")`: LOOPSTART/LOOPLENGTH 태그. 반환된 루프 지점을 `loop_points.txt`에 적는다.

## 사운드 디자인 레시피
| 소리 | 설정 |
|---|---|
| 808/붐 베이스 타격 | `kicker(start=110, end=38, decay=600, dist=15)` + `distort(5)`. 음정이 필요하면 `startnote=True, endnote=True, gain=0.6` |
| 리스/더티 베이스 | `triosc(osc("saw",35,detune=-12), osc("saw",35,detune=12), osc("square",30,coarse=-12))`, `filt("moog", 800, 1.5)`, `distort(6)` |
| 어두운 스탭 | `triosc(osc("saw",40), osc("square",30,coarse=-12), osc("saw",30,detune=15))`, `adsr(0.002,0.12,0,0.05)`, `filt("moog",3000,2)`, `bitcrush(rate=12000,bits=6)`, `reverb(0.7,wet=0.2)` |
| 슈퍼소 리드 | osc 3개 saw (vol 각 22), detune 0/±15, `stereo(170)`, `delay(ticks_to_sec(E,bpm),0.35,wet=0.3)` |
| 칩튠 | `triosc(osc("square",30))` 또는 `raw_inst("nes", ...)`, `bitcrush(rate=22050,bits=4)` |
| 노이즈 스윕/라이저 | `triosc(osc("noise",50))` + `dualfilter(cut=Auto([...200→16000...]), type="bandpass", res=2)` |
| 글리치 | 같은 슬라이스 `stutter(div=T)` → 짧은 무음 → 피치 내린 리버스, 구간 `bitcrush` step 오토메이션 |

레시피 값은 트랙 하나 기준으로 피크가 약 0.5~0.85다. 여러 트랙을 섞으면 합쳐서 커지므로 트랙 vol을 60~80에서 시작하고 `wav_stats`로 확인한다.

## 자주 쓰는 GM 번호 (sf2 patch, 0부터)
피아노 0, 일렉피아노 4, 오르간 16, 나일론기타 24, 스틸기타 25, 클린일렉기타 27, 오버드라이브 29, 디스토션 30,
어쿠스틱베이스 32, 핑거베이스 33, 피크베이스 34, 신스베이스 38, 바이올린 40, 첼로 42, 현악앙상블 48, 신스스트링 50,
합창 52, 트럼펫 56, 트롬본 57, 브라스섹션 61, 알토색소폰 65, 클라리넷 71, 플루트 73, 팬플루트 75,
신스리드(사각) 80, 신스리드(톱니) 81, 패드 88~95, 하프 46, 팀파니 47, 마림바 12, 비브라폰 11, 뮤직박스 10, 첼레스타 8.

## GM 드럼 키 (sf2 bank=128)
킥 36, 사이드스틱 37, 스네어 38, 클랩 39, 스네어2 40, 로우탐 41/45, 미드탐 47/48, 하이탐 50,
클로즈드 햇 42, 페달 햇 44, 오픈 햇 46, 크래시 49/57, 라이드 51, 라이드벨 53, 탬버린 54, 카우벨 56, 셰이커 70.

## 작곡 품질 가이드
- **벨로시티 변화**: 강박 100~110, 약박 70~90, 고스트 40~60. 전부 100이면 기계적이다.
- **음역 분리**: 베이스 E1~G2(28~43), 코드/패드 C3~C5(48~72), 멜로디 C4~C6(60~84). 서브 대역(~100Hz)은 베이스나 킥 중 **한 번에 하나만** 차지하게 한다.
- **반복과 변주**: 모티프를 2~4마디마다 리듬이나 끝음만 바꿔 반복. 섹션이 바뀌면 악기를 더하거나 빼고 음역을 올린다.
- **대비**: 큰 타격 직전에 1/16~1/8박 무음을 두면 훨씬 세게 들린다. 클라이맥스 전에는 필터 스윕이나 스터터로 빌드업한다.
- **믹스 버스**: 드럼, 베이스, 신스를 믹서 채널로 묶어 버스마다 이펙트를 건다. 마스터에는 `amp()` 정도만 둔다.

## 주의 / 알려진 문제
- 렌더할 때 `fluidsynth: warning: No preset found on channel N` 경고는 정상이다.
- 렌더 길이 = 마지막 패턴 또는 오토메이션 끝 + LMMS가 붙이는 꼬리(약 1마디). 정확한 구간은 `cut()`으로 자른다.
- 이펙트 결과는 피크만으로 판단하기 어렵다(필터를 걸어도 피크가 비슷할 수 있다). 효과를 검증하려면 고정값으로 렌더한 결과와 파형을 비교하거나 직접 들어본다.
- LMMS 1.2에는 자동 슬라이서가 없다. `break_kit()`처럼 **슬라이스마다 트랙 하나**를 쓴다 (트랙이 많아지면 믹서 채널 하나로 모은다).
- LMMS가 이미 그 파일을 열고 있으면 파일을 다시 써도 화면에 반영되지 않는다. 사용자에게 다시 열기를 안내하거나 새 파일명으로 저장한다.
- .mmpz는 읽기만 하고, 쓸 때는 .mmp로 쓴다.
