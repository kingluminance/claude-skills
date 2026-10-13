---
name: lmms-compose
description: LMMS(무료 DAW)로 작곡/편곡. Claude가 .mmp 프로젝트 파일을 직접 써서 트랙·악기·음표를 만들고, 사용자는 LMMS UI(피아노롤)에서 열어 듣고 고친다. 사용자가 저장한 .mmp를 다시 읽어 이어서 작업하고, WAV 렌더와 MIDI/악보 내보내기도 한다. '작곡해줘', '곡 만들어줘', 'LMMS', '.mmp', '편곡', '비트 만들어줘', '멜로디 써줘', 'BGM' 요청 시 사용(작곡 요청의 기본값). 악보가 주목적이거나 .mid/MuseScore를 원하면 midi-compose를 쓴다.
---

# LMMS 작곡 스킬

Claude는 LMMS 화면을 클릭하지 않는다. **.mmp(XML) 파일을 직접 쓰고 읽는다.** 사용자는 같은 파일을 LMMS UI에서 열어 재생·편집한다.

## 필요한 환경
| 항목 | 기본 위치 (환경변수로 변경 가능) |
|---|---|
| LMMS 1.2.x | 표준 설치 위치 자동 탐색 (`LMMS_EXE`) |
| 사운드폰트 GeneralUser GS (GM 전체 + 드럼) | `~/tools/soundfonts/GeneralUser-GS.sf2` (`SF2_PATH`) |
| Python 패키지 | `pretty_midi` (MIDI 내보내기용) |
| 생성기 | `~/.claude/skills/lmms-compose/scripts/mmp.py` |

**새 PC에서 처음 쓸 때 먼저 확인**:
`python -c "import os,sys; sys.path.insert(0, os.path.expanduser('~/.claude/skills/lmms-compose/scripts')); import mmp; print(mmp.LMMS, os.path.exists(mmp.LMMS)); print(mmp.SF2, os.path.exists(mmp.SF2))"`
없는 게 있으면 사용자에게 알리고 설치한다:
- LMMS: Windows `winget install LMMS.LMMS` / macOS `brew install --cask lmms`
- `pip install pretty_midi mido`
- 사운드폰트: `https://raw.githubusercontent.com/mrbumpy409/GeneralUser-GS/main/GeneralUser-GS.sf2` → `~/tools/soundfonts/`
- 악보(PDF)가 필요하면 `midi-compose` 스킬의 MuseScore 설정을 참고한다.

기본 작업 폴더는 `~/Documents/music/` (사용자가 다른 곳을 지정하면 따름). 곡마다 `<곡이름>.py`(생성 스크립트)와 `<곡이름>.mmp`를 둔다.

## 워크플로
1. **요구 파악**: 장르, 분위기, BPM, 길이, 조성, 악기. 빠진 건 합리적 기본값으로 정하고 알린다.
2. **구조 설계**: 섹션(인트로/A/B/후렴/아웃트로)과 마디 수, 코드 진행을 먼저 정해 사용자에게 짧게 보여준다.
3. **생성 스크립트 작성** (`<곡이름>.py`) → `write_project()`로 .mmp 생성. 섹션별 함수로 나누면 수정이 쉽다.
4. **검증**: `render()` 후 `wav_stats()`로 길이와 피크 확인. 피크가 0.1 미만이면 트랙 vol/mastervol을 올린다. 무음이면 실패로 보고.
5. **열기**: `open_in_lmms()`로 사용자에게 띄운다. 사용자는 스페이스바로 재생, 트랙 이름 더블클릭으로 피아노롤.
6. **반복**: 피드백 → 스크립트 수정 → 재생성. **사용자가 LMMS에서 직접 고치고 저장했다면** 스크립트로 덮어쓰기 전에 반드시 `read_project()`로 읽어 변경을 반영한다(덮어쓰면 사용자 편집이 사라짐). 애매하면 새 파일명(`_v2`)으로 저장.
7. **악보가 필요하면**: `write_midi()` → MuseScore로 PDF.

## mmp.py API
```python
import os, sys; sys.path.insert(0, os.path.expanduser("~/.claude/skills/lmms-compose/scripts"))
from mmp import *   # note, write_project, read_project, write_midi, render, wav_stats, open_in_lmms, Q, BAR, E, S

# 틱: Q=48(4분), E=24(8분), S=12(16분), BAR=192(4/4 한 마디). 점4분 = Q+E, 셋잇단 8분 = 16
# note(key=MIDI번호, pos=시작틱, length=길이틱, vol=0~200, 기본 100)
write_project("song.mmp", [
    dict(name="Piano", notes=[...], patch=0),                  # GM 프로그램 번호
    dict(name="Drums", notes=[...], patch=0, bank=128),         # 드럼은 bank=128
    dict(name="Bass",  notes=[...], patch=33, vol=90, pan=-20, reverb=False),
], bpm=100, ts=(4, 4), mastervol=100)

render("song.mmp")                  # -> song.wav
wav_stats("song.wav")               # {'seconds':..., 'peak':0~1}
proj = read_project("song.mmp")     # 사용자 편집본 읽기 (.mmpz도 가능)
write_midi("song.mid", proj)        # 악보/다른 DAW용
open_in_lmms("song.mmp")
```
악보 PDF: `write_midi()`로 만든 .mid를 `midi-compose` 스킬의 `export_score()`에 넘긴다.

## 자주 쓰는 GM 번호 (patch, 0부터)
피아노 0, 일렉피아노 4, 오르간 16, 나일론기타 24, 스틸기타 25, 클린일렉기타 27, 오버드라이브 29, 디스토션 30,
어쿠스틱베이스 32, 핑거베이스 33, 피크베이스 34, 신스베이스 38, 바이올린 40, 첼로 42, 현악앙상블 48, 신스스트링 50,
합창 52, 트럼펫 56, 트롬본 57, 브라스섹션 61, 색소폰(알토) 65, 클라리넷 71, 플루트 73, 팬플루트 75,
신스리드(사각) 80, 신스리드(톱니) 81, 신스패드(뉴에이지) 88, 패드(따뜻함) 89, 패드(콰이어) 91, 하프 46, 팀파니 47, 마림바 12, 비브라폰 11, 뮤직박스 10, 첼레스타 8.

## GM 드럼 키 (bank=128 트랙에서 key)
킥 36, 사이드스틱 37, 스네어 38, 클랩 39, 스네어2 40, 로우탐 41/45, 미드탐 47/48, 하이탐 50,
클로즈드 햇 42, 페달 햇 44, 오픈 햇 46, 크래시 49/57, 라이드 51, 라이드벨 53, 탬버린 54, 카우벨 56, 셰이커 70.

## 작곡 품질 가이드
- **벨로시티에 변화를 준다**: 강박 100~110, 약박 70~90, 하이햇은 교대로(예: 80/60). 전부 100이면 기계적으로 들린다.
- **음 길이**: 레가토는 간격 없이 붙이고, 스타카토는 길이의 50%. 0.95배 같은 애매한 축소는 MuseScore에서 스타카토 점이 붙으니 피한다.
- **음역 분리**: 베이스 E1~G2(28~43), 코드/패드 C3~C5(48~72), 멜로디 C4~C6(60~84). 베이스와 코드 최저음이 겹치지 않게 한다.
- **보이스 리딩**: 코드 전환 시 가까운 전위를 써서 윗성부가 크게 뛰지 않게 한다.
- **반복과 변주**: 모티프를 만들고 반복하되 2~4마디마다 리듬이나 끝음을 바꾼다. 후렴은 음역을 올리고 악기를 더한다.
- **드럼**: 섹션 끝 마디에 필인(탐, 스네어 16분)을 넣고, 다음 섹션 첫 박에 크래시를 친다.
- **휴먼라이즈(선택)**: pos에 ±2틱, vol에 ±8 랜덤. 드럼 킥과 스네어는 정박을 유지한다.

## 주의 / 알려진 문제
- 렌더할 때 `fluidsynth: warning: No preset found on channel N` 경고가 나와도 정상이다.
- 기본 출력이 작다(피크 약 0.2). 크게 하려면 mastervol을 120~150으로 하거나 트랙 vol을 올린다. 피크 0.9 이상이면 클리핑 위험.
- 이 생성기는 트랙마다 패턴 하나에 음표를 전부 넣는다. 사용자가 LMMS에서 패턴을 쪼개거나 다른 신스(TripleOscillator 등)로 바꾼 트랙은 `read_project()`로 음표는 읽히지만, 다시 `write_project()`하면 sf2player 트랙으로 바뀐다. 이 경우 사용자에게 먼저 알린다.
- LMMS 1.2.2는 .mmp(비압축)를 연다. 사용자가 .mmpz로 저장했어도 읽을 수 있지만, 쓸 때는 .mmp로 쓴다.
- LMMS가 이미 그 파일을 열고 있으면 파일을 다시 써도 화면에 반영되지 않는다. 사용자에게 "파일 → 다시 열기"를 안내하거나 새 파일명으로 저장한다.
