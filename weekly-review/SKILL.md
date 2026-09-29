---
name: "weekly-review"
description: "Obsidian 볼트(~/Desktop/brain)의 일주일치 데일리와 수정 기록을 모아 프로젝트별 진행 상황을 정리하고, 멈춘 프로젝트의 archive 이동을 제안. '주간 리뷰', '이번 주 정리', 'weekly review' 요청 시 사용."
---

# weekly-review

한 주를 돌아보고 `~/Desktop/brain/daily/YYYY-Www.md`(예: `2026-W40.md`)에 주간 리뷰를 남긴다. 이 스킬은 PARA가 무너지지 않게 하는 정기 점검이다. **정리는 자동, 파일 이동은 승인 후에만.**

## 1. 기간

- 기본은 이번 주 월요일~오늘 (Asia/Seoul, ISO 주차). "지난주"라고 하면 지난 월~일.
- `TZ=Asia/Seoul date +%G-W%V`로 파일명을 정한다.

## 2. 모으기

1. 기간 내 `daily/YYYY-MM-DD.md`를 전부 읽는다 (짧으니 통째로).
2. 기간 내 수정된 노트 목록:
   ```bash
   cd ~/Desktop/brain && TZ=Asia/Seoul find . -name "*.md" -newermt "<월요일> 00:00" \
     -not -path "./.obsidian/*" -not -path "./_templates/*" | sort
   ```
3. `INDEX.md` "현재 진행 중인 프로젝트" 목록을 읽는다.
4. 프로젝트별 **마지막 수정일**:
   ```bash
   cd ~/Desktop/brain && for d in projects/*/; do echo "$d $(find "$d" -name '*.md' -exec stat -f '%Sm' -t '%Y-%m-%d' {} + 2>/dev/null | sort | tail -1)"; done
   ```
   (macOS `stat -f`. 리눅스면 `stat -c %y`)
5. 기간 내 새로 생긴 `resources/concepts/` 노트.
6. `inbox.md` 줄 수.
7. `python3 ~/Desktop/brain/_scripts/vault-health.py ~/Desktop/brain` 결과.

## 3. 쓰기

```markdown
# YYYY-Www 주간 리뷰 (MM-DD ~ MM-DD)

## 프로젝트
- [[projects/<이름>/overview|<이름>]]: <이번 주 진행 1~2줄> — 다음: <다음에 할 것, 노트에 적혀 있을 때만>
- <이번 주 변화 없음>: 마지막 수정 MM-DD

## 학교
- <과목>: <이번 주 한 것>

## 새 개념 노트
- [[resources/concepts/...|...]]

## 볼트 상태
- inbox: N줄 / 점검: 깨진 링크 N, 허브 누락 N (없으면 "깨끗함")

## 이번 주 데일리
- [[daily/YYYY-MM-DD|MM-DD]] · [[daily/...|...]]
```

- 데일리 노트에 없는 내용을 지어내지 않는다. 근거는 데일리와 실제 노트 내용뿐.
- 링크는 볼트 루트 기준 전체경로 + 표시명. 허브 경로는 INDEX.md 목록을 따른다.
- 파일이 이미 있으면 덮어쓰지 말고 보여주고 물어본다.

## 4. 제안 (승인 필요)

리뷰를 쓴 뒤 필요한 것만 짧게 물는다:

- **14일 넘게 수정 없는 프로젝트** → "archive로 옮길까요?" 승인하면 `archive/overview.md`의 "옮기는 법" 절차를 따른다 (폴더째 `archive/`로 이동 → INDEX.md 목록에서 빼고 archive/overview.md에 추가 → `graph-colorize` 실행 안내). 옮기면 링크가 깨질 수 있으니 가능하면 Obsidian 안에서 옮기도록 안내하고, 직접 옮겼으면 vault-health로 깨진 링크를 확인·수정한다.
- inbox가 10줄 넘으면 → `inbox-sort` 스킬 실행 제안.
- 이번 주 수업 노트가 있는데 개념 노트가 없으면 → `concept-extract` 제안 (노트 1~2개 지목).
- vault-health에 문제가 있으면 → `vault-health`로 고칠지 제안.

제안이 하나도 없으면 "이번 주는 정리할 것 없음"으로 끝낸다.