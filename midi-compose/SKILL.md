---
name: midi-compose
description: MIDI 방식 작곡. Claude가 .mid 파일을 직접 쓰고, FluidSynth로 WAV를 렌더하고, MuseScore로 악보(PDF/PNG/MusicXML)를 뽑는다. 사용자가 MuseScore에서 고친 .mscz/.mid를 다시 읽어 이어서 작업한다. 악보가 필요한 곡(피아노곡, 클래식, 합주, 연주용), '.mid', 'MIDI', 'MuseScore', '악보로 줘', '다른 DAW로 옮길 MIDI' 요청 시 사용. DAW 화면에서 트랙을 쌓는 작업(비트, BGM, 전자음악)은 lmms-compose를 쓴다.
---

# MIDI 작곡 스킬

Claude는 .mid 파일을 직접 쓰고 읽는다. 사용자는 결과를 **WAV로 듣고, MuseScore 악보로 본다**. 수정은 MuseScore에서 할 수 있다.
LMMS 화면에서 작업하길 원하면 `lmms-compose`를 쓴다. 두 스킬은 같은 음표 형식(`note(key, pos, length, vol)`, Q=48틱)을 쓰므로 작곡 코드를 그대로 옮길 수 있다.

## 필요한 환경
| 항목 | 기본 위치 (환경변수로 변경 가능) |
|---|---|
| Python 패키지 | `pretty_midi`, `mido` |
| FluidSynth (MIDI→WAV) | PATH 또는 `~/tools/fluidsynth/*/bin/fluidsynth.exe` (`FLUIDSYNTH_EXE`) |
| 사운드폰트 GeneralUser GS | `~/tools/soundfonts/GeneralUser-GS.sf2` (`SF2_PATH`) |
| MuseScore 4 (악보) | 표준 설치 위치 자동 탐색 (`MUSESCORE_EXE`) |
| 도구 | `~/.claude/skills/midi-compose/scripts/midi.py` |

**새 PC에서 처음 쓸 때 먼저 확인**:
`python -c "import os,sys; sys.path.insert(0, os.path.expanduser('~/.claude/skills/midi-compose/scripts')); import midi; [print(p, os.path.exists(p)) for p in (midi.FLUIDSYNTH, midi.SF2, midi.MUSESCORE)]"`
없는 게 있으면 사용자에게 알리고 설치한다:
- `pip install pretty_midi mido`
- FluidSynth: Windows는 `https://github.com/FluidSynth/fluidsynth/releases`의 `win10-x64` zip을 `~/tools/fluidsynth/`에 풀기 (winget에 없음). macOS는 `brew install fluid-synth`.
- 사운드폰트: `https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2` → `~/tools/soundfonts/`
- MuseScore: Windows `winget install Musescore.Musescore`, macOS `brew install --cask musescore`

기본 작업 폴더는 `~/Documents/music/` (사용자가 다른 곳을 지정하면 따름). 곡마다 `<곡이름>.py`(생성 스크립트), `.mid`, `.wav`, `.pdf`를 둔다.

## 워크플로
1. **요구 파악**: 장르, 분위기, BPM, 길이, 조성, 편성. 빠진 건 합리적 기본값으로 정하고 알린다.
2. **구조 설계**: 섹션과 마디 수, 코드 진행을 먼저 짧게 보여준다.
3. **생성 스크립트 작성** (`<곡이름>.py`) → `write_midi()`. 조성을 `key=`로 넘기면 악보에 조표가 찍힌다.
4. **검증**: `render()` → `wav_stats()`로 길이와 피크 확인(피크 0.1 미만이면 gain이나 velocity를 올리고, 무음이면 실패로 보고). `export_score(mid, png)` 후 PNG를 직접 보고 악보가 의도대로인지 확인한다(박자, 조표, 이상한 스타카토나 쉼표).
5. **전달**: WAV와 PDF 경로를 알려준다. 원하면 `open_in_musescore()`로 띄운다.
6. **반복**: 피드백 → 스크립트 수정 → 재생성. **사용자가 MuseScore에서 고쳤다면**(`.mscz` 저장) 덮어쓰기 전에 `export_score(x.mscz, x_edit.mid)` → `read_midi()`로 반영한다. 애매하면 새 파일명(`_v2`)으로 저장.

## midi.py API
```python
import os, sys; sys.path.insert(0, os.path.expanduser("~/.claude/skills/midi-compose/scripts"))
from midi import *   # note, write_midi, read_midi, render, export_score, wav_stats, open_in_musescore, Q, BAR, E, S

# 틱: Q=48(4분), E=24(8분), S=12(16분), BAR=192(4/4 한 마디). 점4분 = Q+E, 셋잇단 8분 = 16
# note(key=MIDI번호, pos=시작틱, length=길이틱, vel=1~127)
write_midi("song.mid", [
    dict(name="Flute", notes=[...], program=73),     # GM 프로그램 번호
    dict(name="Piano", notes=[...], program=0),
    dict(name="Drums", notes=[...], drum=True),      # 드럼은 drum=True (채널 10)
], bpm=100, ts=(4, 4), key="Am")                     # key: "C", "G", "Eb", "F#m" ...

render("song.mid")                     # -> song.wav (gain=0.6 기본)
wav_stats("song.wav")                  # {'seconds':..., 'peak':0~1}
export_score("song.mid", "song.pdf")   # .pdf / .png(-1.png, -2.png...) / .musicxml / .mscz
export_score("song.mscz", "song_edit.mid"); proj = read_midi("song_edit.mid")   # 사용자 편집본 읽기
open_in_musescore("song.mid")
```
`read_midi()`는 `dict(bpm, ts, tracks=[dict(name, program, drum, notes)])`를 돌려준다. 이 `tracks`는 그대로 `write_midi()`에 다시 넣을 수 있다.

**LMMS로 넘기기**: `lmms-compose`의 `write_project()`에 `dict(name=t["name"], notes=t["notes"], patch=t["program"], bank=128 if t["drum"] else 0)`로 변환해서 넣는다. vol 척도는 LMMS 0~200, MIDI 1~127로 다르지만 100 근처는 그대로 써도 무방하다.

## 자주 쓰는 GM 번호 (program, 0부터)
피아노 0, 일렉피아노 4, 첼레스타 8, 뮤직박스 10, 비브라폰 11, 마림바 12, 오르간 16, 나일론기타 24, 스틸기타 25, 클린일렉기타 27,
어쿠스틱베이스 32, 핑거베이스 33, 신스베이스 38, 바이올린 40, 비올라 41, 첼로 42, 콘트라베이스 43, 하프 46, 팀파니 47,
현악앙상블 48, 합창 52, 트럼펫 56, 트롬본 57, 호른 60, 브라스섹션 61, 알토색소폰 65, 오보에 68, 바순 70, 클라리넷 71, 플루트 73,
신스리드 80/81, 패드 88~95.

## GM 드럼 키 (drum=True 트랙에서 key)
킥 36, 사이드스틱 37, 스네어 38, 클랩 39, 로우탐 41/45, 미드탐 47/48, 하이탐 50,
클로즈드 햇 42, 페달 햇 44, 오픈 햇 46, 크래시 49/57, 라이드 51, 탬버린 54, 셰이커 70.

## 작곡과 악보 품질 가이드
- **악보가 깔끔하려면 박에 맞춘다**: pos와 length를 S(16분) 배수로. 휴먼라이즈(랜덤 오프셋)는 악보를 지저분하게 하므로, 악보가 목적이면 쓰지 않는다. 표현은 velocity로만 준다.
- **음 길이**: 레가토는 정확히 다음 음까지, 스타카토는 정확히 절반. 0.9배 같은 애매한 축소는 MuseScore에서 스타카토 점이나 잔쉼표가 생긴다.
- **트랙 하나 = 악보 한 단**: 피아노 양손을 한 트랙에 넣으면 MuseScore가 높은음/낮은음자리표로 나눠 주지만, 오른손/왼손을 따로 원하면 트랙을 나눈다.
- **음역**: 실제 악기 음역을 지킨다. 플루트 C4~C7(60~96), 바이올린 G3~(55~), 첼로 C2~(36~), 베이스 E1~G3(28~55), 트럼펫 F#3~D6(54~86). 연주용 악보라면 특히 중요하다.
- **벨로시티**: 강박 95~110, 약박 70~85. 프레이즈 정점으로 갈수록 올린다.
- **보이스 리딩, 반복과 변주, 섹션 끝 필인**은 lmms-compose와 같다.

## 주의 / 알려진 문제
- MuseScore CLI는 종료 시 segfault가 날 수 있다. `export_score()`는 파일 존재로 성공을 판단하므로 무시해도 된다.
- 악보의 단 이름이 "Flute, Flute"처럼 두 번 찍힐 수 있다(MuseScore가 트랙 이름과 악기 이름을 같이 씀). 신경 쓰이면 트랙 이름을 악기와 다르게(예: "Melody") 짓는다.
- MuseScore를 거친 .mid를 읽으면 트랙 이름이 "악기, 원래이름"(예: "Flute, Melody")이 되고, 음 길이가 재생용으로 약간 짧아진다(4분음표 48→46틱). 다시 쓸 때는 이름에서 ", " 앞부분을 떼고, 길이를 S(12틱) 단위로 반올림해 정리한다.
- `read_midi()`는 첫 템포만 쓴다. 중간에 템포가 바뀌는 곡은 위치가 어긋날 수 있다.
- FluidSynth는 리버브/코러스를 기본으로 켠다. 음질은 사운드폰트 수준(데모 품질)이다.
