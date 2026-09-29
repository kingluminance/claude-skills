---
name: "daily-log"
description: "Obsidian 볼트(~/Desktop/brain)에서 오늘 수정된 노트를 보고 daily/YYYY-MM-DD.md에 3줄 작업 로그를 링크와 함께 자동 작성. '오늘 정리해줘', '데일리 써줘', '오늘 뭐 했는지 기록' 요청 시 사용."
---

# daily-log

그날 볼트에서 바뀐 것을 모아 `~/Desktop/brain/daily/YYYY-MM-DD.md`에 짧은 로그를 남긴다. INDEX.md 규칙: **데일리는 길게 쓰지 않는다 — 나중에 검색될 키워드와 링크면 충분.**

## 1. 날짜

- 기본은 오늘(Asia/Seoul). "어제 거"처럼 날짜를 주면 그날.
- `TZ=Asia/Seoul date +%Y-%m-%d`

## 2. 바뀐 노트 모으기

```bash
cd ~/Desktop/brain && TZ=Asia/Seoul find . -name "*.md" -newermt "<날짜> 00:00" ! -newermt "<다음날> 00:00" \
  -not -path "./.obsidian/*" -not -path "./_templates/*" -not -path "./daily/*" | sort
```

- 경로로 묶는다: `projects/<이름>` / `school/<과목>` / `resources/concepts` / 구조 파일(INDEX.md, */overview.md, inbox.md).
- 묶음마다 파일을 훑어(제목·헤딩·최근 추가된 부분 위주) **무엇을 했는지 키워드 한 줄**로 요약한다. 변경 내용을 알 수 없으면 "수정"이라고만 쓴다 — 지어내지 않는다.
- 구조 파일만 바뀐 날은 "볼트 정리" 한 줄로 합친다.
- 이 대화에서 한 작업(코딩, 과제 등 볼트 밖 일)이 보이면 같이 넣는다.

## 3. 쓰기

양식 (`_templates/daily.md` 기반):

```markdown
# YYYY-MM-DD

- [[projects/<이름>/overview|<이름>]]: <한 일 키워드>
- [[school/overview|학교]] <과목>: <한 일> — [[노트 전체경로|표시명]]
- 볼트 정리: <무엇>

**배운 것 1줄:** <오늘 만든 개념 노트 링크, 없으면 한 줄 또는 생략>
```

- 항목은 **최대 5줄**, 항목당 한 줄. 프로젝트·과목별로 한 줄씩 묶는다.
- 링크는 **볼트 루트 기준 전체경로 + 표시명**. 프로젝트는 허브(INDEX.md "현재 진행 중인 프로젝트"에 적힌 경로 — dog-adoption은 `보호소-커넥트-인덱스`)를 링크하고, 특정 노트가 핵심이면 그 노트를 링크.
- 오늘 만든 개념 노트가 있으면 "배운 것"에 링크한다.

**파일이 이미 있으면**: 기존 내용은 바꾸지 않는다. 이미 적힌 항목과 겹치지 않는 것만 목록 끝에 추가한다.

## 4. 마무리

- 쓴 내용을 그대로 보여주고 "빠진 거 있으면 말해주세요"로 끝낸다. 사용자가 보태면 한 줄 추가.
- `python3 ~/Desktop/brain/_scripts/vault-health.py ~/Desktop/brain`로 깨진 링크 없는지 확인.