# 팀 Git · Jira 컨벤션

| | |
|---|---|
| 출처 | Notion 「특화 프로젝트 / 팀 규칙」 하위 4개 문서 |
| 원본 | https://app.notion.com/p/3dad538568e880d2b861cc22676fd398 |
| 옮긴 날 | 2026-09-15 |
| Jira 프로젝트 키 | `S15P21E203` |

**원본이 기준이다.** 이 파일은 매번 Notion 을 열지 않으려고 옮겨 둔 사본이다.
규칙이 바뀌면 원본이 먼저 바뀌므로, 어긋나면 원본을 확인한다.

---

## 1. 브랜치

```
{작업 유형}/{작업 영역}/{Jira 이슈 키}-{기능명}

feature/ai/S15P21E203-251-llm-stage1
chore/infra/S15P21E203-27-deploy-setting
fix/ai/S15P21E203-54-login-token
```

| 작업 유형 | 용도 | | 작업 영역 | 대상 |
|---|---|---|---|---|
| `feature/` | 신규 기능 | | `fe` | 프론트 화면·상태·API 연동 |
| `fix/` | 버그 수정 | | `be` | 백엔드 API·로직·DB 스키마 |
| `refactor/` | 기능 변경 없는 개선 | | `ai` | AI 모델·추천 로직·데이터 전처리 |
| `docs/` | 문서·GitLab 템플릿 | | `infra` | **Docker · Jenkins · 배포 · 서버 · 네트워크** |
| `test/` | 테스트 코드 | | `common` | 공통 문서·팀 규칙·루트 설정 |
| `chore/` | **설정 · 의존성 · 빌드 · 개발 환경** | | | |

- Jira 이슈 키는 **대문자**. 기능명은 **영문 소문자 + 하이픈**
- **모든 작업 브랜치는 최신 `develop` 에서 만든다**
- **1 Jira 이슈 = 1 브랜치 = 1 MR**
- 하나의 브랜치에서 관련 없는 기능을 함께 개발하지 않는다
- 1~3일 안에 병합한다. 크면 여러 이슈로 나눈다
- 병합 후 작업 브랜치는 삭제한다

```bash
git switch develop && git pull origin develop
git switch -c feature/ai/S15P21E203-000-기능명
```

---

## 2. 커밋

```
{타입}: {작업 내용}

feat: 자연어 기반 향수 추천 API 구현
fix: 로그인 토큰 갱신 오류 수정
chore: Docker Compose 설정 추가
docs: API 명세서 수정
```

| 타입 | 의미 |
|---|---|
| `feat` | 새로운 기능 |
| `fix` | 버그 수정 |
| `refactor` | 기능 변화 없는 코드 개선 |
| `design` | UI/CSS 수정 |
| `docs` | 문서 수정 |
| `test` | 테스트 코드 |
| `chore` | **설정 · 패키지 · 빌드 등** |
| `remove` | 파일·코드 삭제 |

- **Jira 이슈 키를 커밋 메시지에 넣지 않는다** (2026-09-09 개정). 브랜치와 MR 로 연결한다
- **문장 끝에 마침표를 쓰지 않는다**
- **1 커밋 = 1개의 의미 있는 작업**
- `Co-Authored-By` 를 붙이지 않는다

### ⚠ 문서 두 곳이 어긋난다 — `{타입}:` 이 맞다

`Jira 이슈 관리 규칙` 4장은 커밋을 `feat(be):` 로 적었지만, `깃 컨벤션 규칙` 3장은
`{타입}: {작업 내용}` 이고 예시에 scope 가 없다. **저장소의 실제 커밋도 scope 가 없다.**

```
feat: 향 사전 v1.8 반영과 단독 조건 표시
fix: 브랜드·향수 이름의 앞뒤 공백 제거
```

→ **scope 를 쓰지 않는다.**

---

## 3. Merge Request

```
제목  [Jira 이슈 키][타입] 작업 내용

[S15P21E203-42][feat] 자연어 기반 향수 추천 기능 구현
```

### 본문 템플릿 — **저장소 파일이 기준이다**

실제로 적용되는 것은 팀 저장소의 `.gitlab/merge_request_templates/Default.md` 다.
MR 을 새로 만들면 GitLab 이 이걸 본문에 자동으로 채운다.

```markdown
## 작업 내용

*

## 테스트 결과

* [ ] 로컬 환경에서 정상 동작을 확인했습니다.
* [ ] 기존 기능에 영향을 주지 않는지 확인했습니다.
* [ ] 필요한 테스트 코드를 작성하고 통과했습니다.

## 리뷰 요청 사항

*
```

맨 아래에 GitLab 의 Jira 연동이 이런 줄을 붙여 준다. **직접 쓰지 않아도 된다.**

```
Closes [S15P21E203-000](https://ssafy.atlassian.net/browse/S15P21E203-000?...)
```

#### 채울 때

- **템플릿의 `<!-- ... -->` 안내 주석은 빼고 채운다.** 작성자에게 주는 안내라
  내용이 들어가면 역할이 끝난다. 특히 맨 위의
  `<!-- Jira 이슈는 브랜치명의 이슈 키를 기준으로 자동 연결됩니다. -->` 는 남기지 않는다
- **네 개의 `##` 제목은 그대로 둔다.** 리뷰어가 같은 자리에서 같은 것을 찾는다
- **체크박스를 사실대로 둔다.** 확인하지 못한 항목은 비우고 **왜 못 했는지 적는다.**
  체크 하나가 리뷰어의 확인 동선을 바꾼다 — "로컬에서 확인했습니다" 를 체크하면
  리뷰어는 그 부분을 보지 않는다
- **측정값에는 조건을 붙인다.** `약 162MB (Windows 기준)` 처럼. 조건 없이 적으면
  검증된 수치로 읽힌다

> **⚠ Notion 과 다르다.** Notion 「Jira와 GitLab 연동」 문서의 템플릿에는
> `## 관련 Jira 이슈` 절과 `Closes S15P21E203-` 가 있지만 **저장소 템플릿에는 없다.**
> GitLab 이 실제로 적용하는 것은 저장소 파일이므로 그쪽을 따른다.

### 규칙

- 작업 브랜치 → `develop` 으로 MR 을 만든다
- **파트 담당자 최소 1명의 리뷰**를 받는다
- **AI 파트의 MR 은 가능하면 백엔드 담당자 1명이 추가로 리뷰**한다
- 빌드·테스트를 통과한 뒤 병합한다
- **Delete source branch 를 체크한다** (병합 후 작업 브랜치는 삭제한다)
- MR 을 만들면 Jira 이슈를 `In Review` 로 옮긴다
- AI 코드 리뷰는 사람 리뷰를 보조하는 용도로만 쓴다

### MR 은 CLI 로 만들 수 없다

`glab` 이 설치돼 있지 않고 API 토큰도 없다. 브랜치를 푸시해도 **MR 은 만들어지지 않는다.**
푸시 응답의 *"To create a merge request ... visit:"* 는 만들라는 안내이지 만들어졌다는
뜻이 아니다. 제목·소스·타깃이 채워진 링크를 만들어 사람에게 넘긴다.

```
https://lab.ssafy.com/s15-bigdata-recom-sub1/S15P21E203/-/merge_requests/new
  ?merge_request[source_branch]=<브랜치>
  &merge_request[target_branch]=develop
  &merge_request[title]=<제목>
```

MR 이 실제로 있는지는 토큰 없이도 확인할 수 있다. GitLab 이 모든 MR 의 head 를
`refs/merge-requests/*/head` 로 노출한다.

```bash
git ls-remote origin 'refs/merge-requests/*/head' | grep <커밋 SHA 앞자리>
```

---

## 4. 브랜치 보호 — `master` · `develop`

| 설정 | `master` | `develop` |
|---|---|---|
| Push and merge 허용 | **No one** | **No one** |
| Merge 허용 | Maintainers | Developers + Maintainers |
| Force push | 비활성화 | 비활성화 |
| MR 승인 | 1명 이상 | 1명 이상 |
| 모든 리뷰 스레드 해결 | 필수 | 필수 |
| Pipeline 성공 후 병합 | 비활성화 | 비활성화 |

**`master` · `develop` 에 직접 push 하지 않는다.** 전부 MR 로 병합한다.
긴급 수정도 장기 `hotfix` 브랜치 대신 `fix/*` 를 만든다.

---

## 5. Jira

```
Epic   큰 기능 또는 목표      [모듈] 작업 내용
Story  실제 개발 작업         [모듈][작업종류] 작업 내용
```

```
[AI][Feature] 낙상 판단 로직 구현
[INFRA][Chore] GitLab CI 설정
[COMMON][Docs] 프로젝트 실행 방법 작성
```

| 모듈 | 의미 | | 작업 종류 |
|---|---|---|---|
| `ai` | AI 서버·모델·추론 로직 | | Feature / Fix / Refactor |
| `be` | 백엔드 API·DB | | Test / Docs / Chore / Design |
| `fe` | 화면·사용자 기능 | | |
| `infra` | **서버·배포·Docker·CI/CD** | | |
| `common` | 공통 문서·협업 규칙·전체 설정 | | |

Story 본문 형식

```
한 줄 목표: 이 기능이 해결하는 것 한 문장

작업 범위:
- 핵심 작업 2~4개

완료 조건:
- [ ]
- [ ]
```

- Story 마다 담당자 1명
- **하나의 Story = 하나의 브랜치 = 하나의 MR**
- 1~2일 안에 끝낼 크기로 나눈다

### 작업 상태

```
To Do → In Progress → In Review → Done
```

| 상태 | 기준 |
|---|---|
| To Do | 작업 시작 전 |
| **In Progress** | **브랜치를 만들고 작업 중** |
| **In Review** | **MR 을 생성하고 리뷰 중** |
| Done | MR 승인 후 `develop` 병합 완료 |

막히면 `blocked` 라벨을 단다.

### 우선순위 · 스토리 포인트

| 우선순위 | 기준 | | 포인트 | 기준 |
|---|---|---|---|---|
| Highest | 없으면 발표·데모 불가 | | 1 | 1~2시간 |
| High | 반드시 필요한 핵심 기능 | | 2 | 반나절 |
| Medium | 필요하지만 대체 가능 | | 3 | 0.5~1일 |
| Low | 시간이 남으면 | | 5 | 1~2일 |

---

## 6. 충돌 방지

- **작업 시작 전과 MR 생성 전에 최신 `develop` 을 반영한다**
- 공통 파일을 고칠 때는 담당자끼리 범위를 미리 공유한다
- 충돌은 그 코드를 쓴 사람이 해결한다
- **팀이 `rebase` 에 익숙하지 않으면 merge 로 통일한다**

```bash
git switch feature/ai/S15P21E203-000-기능명
git fetch origin
git merge origin/develop
```

---

## 7. 이 저장소에서 추가로 지키는 것

Notion 에 없지만 이 프로젝트에서 합의한 것.

- 팀 저장소 `S15P21E203` 에서는 **`ai/` 밖을 건드리지 않는다.**
  `backend/` · `frontend/` · `Jenkinsfile` 은 다른 담당이다
- **커밋과 푸시는 요청받았을 때만 한다**
- API 키를 코드·문서·커밋 어디에도 적지 않는다
