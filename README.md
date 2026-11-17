# CVSP Lab 홈페이지 관리 안내

부산대학교 컴퓨터비전 및 신호처리 연구실(CVSP) 홈페이지 저장소입니다.
GitHub Pages로 무료 호스팅되며, **`_data/` 폴더의 파일만 고치면 내용이 바뀝니다.** HTML을 몰라도 됩니다.

파일을 고치고 저장(commit)하면 1~2분 뒤 사이트에 자동으로 반영됩니다.
진행 상황은 저장소의 **Actions** 탭에서 볼 수 있습니다.

---

## 1. 무엇을 고치려면 어떤 파일을 여나요?

| 하고 싶은 일 | 고칠 파일 |
|---|---|
| 멤버 추가·졸업 처리 | `_data/members.yml` |
| 국제 논문 추가 | `_data/publications_international.yml` |
| 국내 논문 추가 | `_data/publications_domestic.yml` |
| 논문 대표 그림 | `images/publications/international/` 에 `논문id.png` (예: `C55.png`) |
| 과제 추가, 진행 중 → 완료 | `_data/projects.yml` |
| 소식(News) 추가 | `_data/news.yml` |
| 갤러리 사진 추가 | `_data/gallery.yml` + `images/gallery/` 에 사진 |
| 모집 안내·Contact (Join Us 페이지) | `_data/join.yml` |
| 장비·세미나·강의 | `_data/lab.yml` |
| 홈 화면 연구 분야 소개 | `_data/research.yml` |
| 상단 메뉴 | `_data/navigation.yml` |
| 연락처·주소·사이트 이름 | `_config.yml` |
| 색상 | `assets/css/main.css` 맨 위 `:root` 부분 |
| 메인 화면 산지니 (입체 가우시안) | `images/logo/sanjini.png` 교체 후 `pip install pillow numpy scipy` → `python3 tools/make_mascot_data.py images/logo/sanjini.png` 실행 |

각 파일 맨 위에 형식 설명이 주석(`#`)으로 적혀 있습니다.

## 2. 가장 쉬운 방법: GitHub 웹에서 바로 고치기

1. GitHub 저장소 페이지에서 고칠 파일(예: `_data/news.yml`)을 엽니다.
2. 오른쪽 위 연필(✏️) 아이콘을 누릅니다.
3. 기존 항목 한 줄을 복사해서 맨 위에 붙여넣고 내용만 바꿉니다.
4. **Commit changes** 를 누릅니다. 끝입니다.

### 예시: 소식 추가
```yaml
- {date: "2026.11", category: Paper, text: "Two papers accepted to CVPR 2027."}
```
`category` 는 `Paper`, `Award`, `Service`, `People` 중 하나를 쓰세요. 색이 자동으로 달라집니다.

### 예시: 논문 추가 (`publications_international.yml` 맨 위)
```yaml
- id: C56
  type: conference          # 저널이면 journal
  year: 2027
  title: "논문 제목"
  venue: "IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR), Jun. 2027"
  authors: ["Gildong Hong*", "Kyeongbo Kong†"]   # * 제1저자, † 교신저자
  tags: [World Modeling, Gaussian Splatting]
  note: "Top-tier · acceptance rate 22%"        # 없으면 줄 삭제
  selected: true            # 홈 화면 대표 논문에 띄우려면 (최대 6개 표시)
  paper: https://arxiv.org/abs/xxxx
  project: https://paper.pnu-cvsp.com/xxx/
  code: https://github.com/cvsp-lab/xxx
```
- `tags` 에 `World Modeling`, `Efficient`, `Robotics` 가 들어가면 홈 화면 연구 분야 카드에 자동으로 연결됩니다.
- 교수님 이름(`Kyeongbo Kong`, `공경보`)은 자동으로 굵게 표시됩니다.
- 편수(32편, 55편 등)는 자동으로 계산되니 따로 고칠 필요 없습니다.

### 예시: 논문 대표 그림(figure) 넣기
1. 국제 논문은 `images/publications/international/`, 국내 논문은 `images/publications/domestic/` 폴더에 그림을 올립니다.
2. 파일 이름을 논문 `id` 와 똑같이 하면 자동으로 붙습니다. 예: `C55.png`, `J32.jpg`. (yml 은 고칠 필요 없음)
3. 이름을 다르게 하고 싶으면 그 논문에 `figure: 파일이름.png` 줄을 추가하세요.
4. 가로로 긴 그림(대략 16:10), 가로 800px 정도면 충분합니다. 그림이 없으면 학회 이름이 적힌 기본 칸이 보입니다.

### 예시: 멤버 사진 넣기
1. `images/members/` 폴더에서 **Add file → Upload files** 로 사진을 올립니다. 파일 이름은 영어로 (예: `sohyeong-kim.jpg`).
2. `_data/members.yml` 에서 그 사람의 `photo: ""` 를 `photo: sohyeong-kim.jpg` 로 바꿉니다.
3. 사진은 세로 4:5 비율, 가로 800px 정도면 충분합니다. 원본(수 MB)은 그대로 올리지 말고 줄여서 올려 주세요.

### 예시: 졸업 처리
`members.yml` 에서 그 사람 블록(`- name:` 부터 `photo:` 까지)을 잘라내서 맨 아래 `Alumni` 그룹에 붙여넣습니다. 진로는 `note: 회사/학교` 로 적을 수 있습니다.

## 3. YAML 작성 시 주의할 점

- **들여쓰기는 스페이스**로 맞춥니다. 탭(Tab)은 쓰지 마세요.
- 글에 `:` 이나 `#` 이 들어가면 큰따옴표로 감싸세요. 예: `title: "LivingWorld: Interactive 4D ..."`
- 저장 후 Actions 탭에 빨간 ✗ 가 뜨면 형식 오류입니다. 방금 고친 줄의 들여쓰기와 따옴표를 확인하세요. 오류가 나도 기존 사이트는 그대로 유지됩니다.

## 4. 내 컴퓨터에서 미리 보기 (선택)

큰 수정 전에 미리 확인하고 싶을 때만 필요합니다.

```bash
# 최초 1회: Ruby 설치 후
bundle install
# 미리보기 서버 실행
bundle exec jekyll serve
# 브라우저에서 http://localhost:4000 접속
```

## 5. 처음 한 번만 하는 설정 (관리자용)

1. **저장소 Settings → Pages** 에서 Source 를 `Deploy from a branch`, Branch 를 `main` / `(root)` 로 선택합니다.
2. 도메인 연결: 같은 화면의 **Custom domain** 에 `www.pnu-cvsp.com` 을 입력하고, 도메인을 산 곳(가비아 등)의 DNS 설정에서
   - `www` 를 `CNAME` 으로 `<조직이름>.github.io` 에 연결
   - 루트(`@`) 는 `A` 레코드로 `185.199.108.153`, `185.199.109.153`, `185.199.110.153`, `185.199.111.153`
   을 추가합니다. 반영까지 최대 하루 걸릴 수 있고, 그 뒤 **Enforce HTTPS** 를 켜 주세요.
3. 다음 관리자에게 넘길 때는 GitHub Organization 의 **People → Invite member** 로 초대하고 Owner 권한을 주면 됩니다.

## 6. 폴더 구조

```
_config.yml          사이트 기본 정보 (이름, 연락처, 주소)
_data/               ★ 내용은 전부 여기
_layouts/, _includes/  페이지 뼈대 (디자인 바꿀 때만)
assets/css/main.css  디자인 (색은 맨 위 :root)
assets/js/main.js    메뉴, 논문 검색/필터, 메인 화면 3D 애니메이션
images/              사진 (members, gallery, infra, projects, logo)
index.html 외 *.html 각 페이지
```
