"""
구글 이미지 크롤링 웹 서버

Flask 기반 웹 인터페이스로 구글 이미지를 검색하고 다운로드합니다.
"""

import os
import logging
import shutil
import zipfile
import io
import uuid
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from crawler import GoogleImageCrawler, ImageSearcher, ImageDownloader

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 다운로드 기본 디렉토리
BASE_DOWNLOAD_DIR = Path("downloads")
BASE_DOWNLOAD_DIR.mkdir(exist_ok=True)

# Google API 키 (환경변수에서 로드, 없으면 크롤링 모드만 사용)
GOOGLE_API_KEY = os.environ.get("GOOGLE_SEARCH_API_KEY", "")
GOOGLE_SEARCH_ENGINE_ID = os.environ.get("GOOGLE_SEARCH_ENGINE_ID", "")


@app.route("/")
def index():
    """메인 페이지"""
    has_api = bool(GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID)
    return render_template("index.html", has_api=has_api)


@app.route("/api/search", methods=["POST"])
def api_search():
    """이미지 검색 API"""
    data = request.get_json()
    keyword = data.get("keyword", "").strip()
    count = int(data.get("count", 20))
    mode = data.get("mode", "crawl")  # "crawl" 또는 "api"

    if not keyword:
        return jsonify({"error": "검색 키워드를 입력해주세요."}), 400

    count = max(1, min(count, 50))

    try:
        if mode == "api" and GOOGLE_API_KEY and GOOGLE_SEARCH_ENGINE_ID:
            searcher = ImageSearcher(GOOGLE_API_KEY, GOOGLE_SEARCH_ENGINE_ID)
            urls = searcher.search_images(keyword, count=min(count, 10))
        else:
            crawler = GoogleImageCrawler()
            urls = crawler.search_images(keyword, count=count)

        return jsonify({
            "success": True,
            "keyword": keyword,
            "mode": mode,
            "urls": urls,
            "count": len(urls),
        })

    except Exception as e:
        logger.error(f"검색 오류: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/download", methods=["POST"])
def api_download():
    """이미지 다운로드 API"""
    data = request.get_json()
    urls = data.get("urls", [])
    keyword = data.get("keyword", "images")

    if not urls:
        return jsonify({"error": "다운로드할 URL이 없습니다."}), 400

    # 세션별 고유 폴더 생성
    session_id = str(uuid.uuid4())[:8]
    safe_keyword = "".join(c for c in keyword if c.isalnum() or c in (' ', '-', '_')).strip()[:30]
    folder_name = f"{safe_keyword}_{session_id}"
    save_dir = BASE_DOWNLOAD_DIR / folder_name
    save_dir.mkdir(parents=True, exist_ok=True)

    try:
        downloader = ImageDownloader(str(save_dir))
        downloaded = downloader.download_images(urls, save_dir=str(save_dir))

        results = []
        for fp in downloaded:
            p = Path(fp)
            results.append({
                "filename": p.name,
                "size_mb": round(p.stat().st_size / (1024 * 1024), 2),
                "path": f"/downloads/{folder_name}/{p.name}",
            })

        return jsonify({
            "success": True,
            "folder": folder_name,
            "downloaded": len(downloaded),
            "total": len(urls),
            "files": results,
        })

    except Exception as e:
        logger.error(f"다운로드 오류: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/download-zip", methods=["POST"])
def api_download_zip():
    """다운로드된 이미지를 ZIP으로 묶어 반환"""
    data = request.get_json()
    folder_name = data.get("folder", "")

    if not folder_name:
        return jsonify({"error": "폴더명이 없습니다."}), 400

    folder_path = BASE_DOWNLOAD_DIR / folder_name
    if not folder_path.exists():
        return jsonify({"error": "폴더를 찾을 수 없습니다."}), 404

    # ZIP 파일 생성 (메모리)
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for img_file in folder_path.iterdir():
            if img_file.is_file() and img_file.suffix.lower() in ('.jpg', '.jpeg', '.png'):
                zf.write(img_file, img_file.name)

    zip_buffer.seek(0)

    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{folder_name}.zip",
    )


@app.route("/downloads/<path:filepath>")
def serve_download(filepath):
    """다운로드된 이미지 서빙"""
    return send_from_directory(str(BASE_DOWNLOAD_DIR), filepath)


@app.route("/api/cleanup", methods=["POST"])
def api_cleanup():
    """다운로드 폴더 정리"""
    data = request.get_json()
    folder_name = data.get("folder", "")

    if folder_name:
        folder_path = BASE_DOWNLOAD_DIR / folder_name
        if folder_path.exists():
            shutil.rmtree(folder_path)
            return jsonify({"success": True, "message": f"'{folder_name}' 삭제 완료"})
        return jsonify({"error": "폴더를 찾을 수 없습니다."}), 404

    # 전체 정리
    count = 0
    for item in BASE_DOWNLOAD_DIR.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
            count += 1
    return jsonify({"success": True, "message": f"{count}개 폴더 삭제 완료"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    logger.info(f"서버 시작: http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=debug)
