---
name: "vault-health"
description: "Obsidian 볼트(~/Desktop/brain) 건강 점검 — 깨진 링크, 고립 노트, 허브-스포크 위반, 개념 노트 규칙, 그래프 색 그룹 누락을 찾아 보고. '볼트 점검', '노트 건강', 'vault health' 요청 시 사용."
---

# vault-health

볼트 `~/Desktop/brain`이 `INDEX.md`에 적힌 규칙(PARA, 허브-스포크, 개념 노트, 그래프 색 그룹)을 지키고 있는지 점검한다.

**기본은 읽기 전용.** 점검하고 보고만 한다. 수정은 사용자가 항목을 골라 승인한 뒤에만 한다.

## 1. 점검 실행

```bash
python3 ~/Desktop/brain/_scripts/vault-health.py ~/Desktop/brain
```

스크립트가 JSON을 출력한다. 스크립트가 없으면 사용자에게 알리고 멈춘다(임의로 새로 쓰지 않는다).

| 키 | 의미 |
|---|---|
| `broken` | 깨진 링크 `[노트, 링크 대상]` |
| `orphans` | 들어오는 링크도 나가는 링크도 없는 노트 |
| `no_backlinks` | 아무도 링크하지 않는 노트 (INDEX 제외) |
| `hub_issues` | 프로젝트 허브(`overview.md` 또는 INDEX가 가리키는 허브)로 돌아가는 링크가 없는 노트 `[노트, 허브]` |
| `missing_index` | INDEX.md "현재 진행 중인 프로젝트"에 없는 `projects/` 폴더 |
| `concept` | 규칙 위반 개념 노트 (출처 없음 / 다른 개념 연결 없음 / resources/overview 목록 누락) |
| `color_missing` | `.obsidian/graph.json` colorGroups에 없는 프로젝트·PARA 폴더 |
| `inbox_lines` | inbox.md에 쌓인 줄 수 |

제외 대상: `_templates/`, `AI-Context/`(구조 참고용 메타 템플릿), `*.excalidraw.md`, `attachments/`, `.obsidian/`.

## 2. 보고

한국어로 짧게. 문제 없는 항목은 한 줄로 "없음". 문제 있는 항목만 목록으로, 각 항목에 **고치는 방법 한 줄**을 붙인다. 예:

- 허브 링크 누락 `projects/rounds-card-game/game-design.md` → 맨 위에 `← [[projects/rounds-card-game/overview|개요로]]` 추가
- `no_backlinks`의 데일리 노트는 정상일 수 있음(데일리는 보통 링크를 받지 않음) — 참고로만 표시
- `inbox_lines`가 10줄 넘으면 inbox 정리를 제안

마지막에 "고칠 항목 번호를 골라주세요"로 끝낸다.

## 3. 수정 (승인된 항목만)

- 링크 추가는 노트 맨 위(제목 바로 아래) 또는 `## 관련 노트` 섹션에 한 줄 추가. 기존 내용은 바꾸지 않는다.
- 고립 노트는 가장 관련 있는 허브를 골라 **허브 쪽에서** 링크한다.
- INDEX.md, resources/overview.md 목록 누락은 해당 목록에 한 줄 추가.
- **색 그룹 누락은 직접 고치지 않는다** → `graph-colorize` 스킬 실행을 안내. 스킬이 없으면 `.obsidian/graph.json`을 `graph.json.backup-<YYYYMMDD-HHMM>`으로 백업한 뒤 catch-all(`-path:` 그룹) 앞에 추가하고, INDEX.md 색 표도 같이 갱신.
- 파일 이동·삭제는 하지 않는다.
- 수정 후 스크립트를 다시 돌려서 해당 항목이 사라졌는지 확인하고 결과를 보고한다.