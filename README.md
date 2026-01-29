# Google Image Crawler

구글 이미지 검색 및 다운로드 웹 서비스

## 구조

```
구글 크롤링/
├── app.py              # Flask 웹 서버 (API + 웹 UI)
├── crawler.py          # 이미지 검색/크롤링/다운로드 모듈
├── templates/
│   └── index.html      # 웹 UI
├── requirements.txt    # Python 의존성
├── Dockerfile          # Docker 배포
├── Procfile            # Render/Heroku 배포
├── render.yaml         # Render 자동 배포 설정
└── .env.example        # 환경변수 템플릿
```

## 로컬 실행

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정 (선택)
cp .env.example .env

# 3. 서버 실행
python app.py
```

브라우저에서 `http://localhost:5000` 접속

## 검색 모드

| 모드 | 설명 | API 키 필요 |
|------|------|-------------|
| 크롤링 | 구글 이미지 페이지 직접 크롤링 | 불필요 |
| API | Google Custom Search API 사용 | 필요 |

API 키 없이도 크롤링 모드로 동작합니다.

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/` | 웹 UI |
| POST | `/api/search` | 이미지 검색 (URL 반환) |
| POST | `/api/download` | 이미지 다운로드 |
| POST | `/api/download-zip` | ZIP 파일 다운로드 |
| POST | `/api/cleanup` | 다운로드 폴더 정리 |

### 검색 예시

```bash
curl -X POST http://localhost:5000/api/search \
  -H "Content-Type: application/json" \
  -d '{"keyword": "한국 풍경", "count": 10, "mode": "crawl"}'
```

### 다운로드 예시

```bash
curl -X POST http://localhost:5000/api/download \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com/image.jpg"], "keyword": "test"}'
```

## 무료 클라우드 배포

### Render (권장)

1. GitHub에 코드 push
2. [render.com](https://render.com) 가입
3. **New > Web Service** 선택
4. GitHub 저장소 연결
5. `render.yaml`이 자동 인식됨
6. 환경변수 설정 (선택):
   - `GOOGLE_SEARCH_API_KEY`
   - `GOOGLE_SEARCH_ENGINE_ID`
7. **Deploy** 클릭

### Railway

1. [railway.app](https://railway.app) 가입
2. **New Project > Deploy from GitHub**
3. 저장소 선택 후 자동 배포

### Docker

```bash
docker build -t google-crawler .
docker run -p 5000:5000 google-crawler
```

## 환경변수

| 변수 | 필수 | 기본값 | 설명 |
|------|------|--------|------|
| `PORT` | X | 5000 | 서버 포트 |
| `FLASK_DEBUG` | X | false | 디버그 모드 |
| `GOOGLE_SEARCH_API_KEY` | X | - | Google API 키 |
| `GOOGLE_SEARCH_ENGINE_ID` | X | - | Custom Search Engine ID |
