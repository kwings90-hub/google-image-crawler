"""
이미지 크롤링 모듈 (독립형)

DuckDuckGo 이미지 검색과 Google Custom Search API를 결합하여
고해상도 이미지를 검색하고 다운로드합니다.
"""

import os
import re
import time
import logging
import warnings
import requests
from pathlib import Path
from typing import List, Optional, Dict
from urllib.parse import urlparse, quote_plus
from PIL import Image

# 로거 설정
logger = logging.getLogger(__name__)


class GoogleImageCrawler:
    """
    DuckDuckGo 기반 이미지 검색 클래스

    duckduckgo_search 라이브러리를 사용하여 이미지 URL을 추출합니다.
    (구글 이미지 검색이 JS 렌더링 필수로 변경되어 대체)
    """

    def __init__(self):
        logger.info("GoogleImageCrawler 초기화 완료 (DuckDuckGo 백엔드)")

    def search_images(self, keyword: str, count: int = 20) -> List[str]:
        """
        DuckDuckGo 이미지 검색

        Args:
            keyword: 검색 키워드
            count: 가져올 이미지 개수 (기본값: 20)

        Returns:
            이미지 URL 리스트
        """
        if not keyword:
            logger.warning("검색 키워드가 비어있습니다.")
            return []

        logger.info(f"이미지 검색 시작: '{keyword}' (요청: {count}개)")

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from duckduckgo_search import DDGS

            results = []
            for attempt in range(3):
                try:
                    with DDGS() as ddgs:
                        results = list(ddgs.images(keyword, max_results=count, size='Large'))
                    break
                except Exception as e:
                    if '403' in str(e) or 'Ratelimit' in str(e):
                        wait = 2 * (attempt + 1)
                        logger.warning(f"Rate limit 발생, {wait}초 후 재시도 ({attempt+1}/3)")
                        time.sleep(wait)
                    else:
                        raise

            image_urls = []
            seen = set()
            for item in results:
                url = item.get('image', '')
                if not url or url in seen or len(url) < 20:
                    continue
                seen.add(url)
                image_urls.append(url)

            logger.info(f"검색 완료: {len(image_urls)}개 이미지 URL 발견")
            return image_urls

        except Exception as e:
            logger.error(f"검색 오류: {e}")
            return []

    def search_images_advanced(self, keyword: str, count: int = 20) -> List[str]:
        """
        고급 이미지 검색 (Wallpaper 사이즈 필터)

        Args:
            keyword: 검색 키워드
            count: 가져올 이미지 개수

        Returns:
            이미지 URL 리스트
        """
        if not keyword:
            return []

        logger.info(f"고급 이미지 검색: '{keyword}'")

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from duckduckgo_search import DDGS

            results = []
            for attempt in range(3):
                try:
                    with DDGS() as ddgs:
                        results = list(ddgs.images(keyword, max_results=count, size='Wallpaper'))
                    break
                except Exception as e:
                    if '403' in str(e) or 'Ratelimit' in str(e):
                        wait = 2 * (attempt + 1)
                        logger.warning(f"Rate limit 발생, {wait}초 후 재시도 ({attempt+1}/3)")
                        time.sleep(wait)
                    else:
                        raise

            image_urls = []
            seen = set()
            for item in results:
                url = item.get('image', '')
                if not url or url in seen:
                    continue
                seen.add(url)
                image_urls.append(url)

            logger.info(f"고급 검색 완료: {len(image_urls)}개 URL")
            return image_urls

        except Exception as e:
            logger.error(f"고급 검색 오류: {e}")
            return []


class ImageSearcher:
    """
    Google Custom Search API를 사용한 이미지 검색 클래스
    """

    API_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
    DEFAULT_IMAGE_SIZE = "large"
    DEFAULT_IMAGE_TYPE = "photo"
    DEFAULT_SAFE_SEARCH = "active"
    MIN_RESOLUTION = 800
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png'}

    def __init__(self, api_key: str, search_engine_id: str):
        """
        Args:
            api_key: Google Custom Search API 키
            search_engine_id: Google Custom Search Engine ID
        """
        if not api_key or not search_engine_id:
            raise ValueError("API 키와 Search Engine ID가 필요합니다.")

        self.api_key = api_key
        self.search_engine_id = search_engine_id
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        logger.info("ImageSearcher 초기화 완료 (API 모드)")

    def search_images(self, keyword: str, count: int = 10) -> List[str]:
        """
        Google Custom Search API로 이미지 검색

        Args:
            keyword: 검색 키워드 (영문 권장)
            count: 검색 결과 개수 (최대 10)

        Returns:
            이미지 URL 리스트
        """
        if not keyword:
            return []

        count = min(count, 10)
        logger.info(f"API 이미지 검색: '{keyword}' (요청: {count}개)")

        try:
            params = {
                'key': self.api_key,
                'cx': self.search_engine_id,
                'q': keyword,
                'searchType': 'image',
                'num': count,
                'imgSize': self.DEFAULT_IMAGE_SIZE,
                'imgType': self.DEFAULT_IMAGE_TYPE,
                'safe': self.DEFAULT_SAFE_SEARCH,
            }

            response = self.session.get(self.API_ENDPOINT, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            items = data.get('items', [])

            if not items:
                logger.warning(f"검색 결과 없음: '{keyword}'")
                return []

            image_urls = [item.get('link', '') for item in items if item.get('link')]
            validated = [url for url in image_urls if self._validate_url(url)]
            unique = list(dict.fromkeys(validated))

            logger.info(f"API 검색 완료: {len(unique)}개 유효 URL")
            return unique

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.error("API 할당량 초과 또는 권한 없음")
            else:
                logger.error(f"HTTP 오류: {e}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"네트워크 오류: {e}")
            return []
        except Exception as e:
            logger.error(f"검색 오류: {e}")
            return []

    def _validate_url(self, url: str) -> bool:
        """이미지 URL 유효성 검증"""
        if not url:
            return False
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ['http', 'https']:
                return False
            path = parsed.path.lower()
            if any(path.endswith(ext) for ext in self.SUPPORTED_FORMATS):
                return True
            if 'image' in path or 'img' in path:
                return True
            return False
        except Exception:
            return False


class ImageDownloader:
    """
    이미지 다운로드 및 검증 클래스
    """

    DEFAULT_TIMEOUT = 10
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_RETRIES = 3
    MIN_RESOLUTION = (400, 400)

    def __init__(self, save_dir: str = "downloads"):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
        })
        logger.info(f"ImageDownloader 초기화 완료 (저장: {self.save_dir})")

    def download_images(
        self,
        urls: List[str],
        save_dir: Optional[str] = None,
        min_success: int = 0,
    ) -> List[str]:
        """
        이미지 URL 리스트를 일괄 다운로드

        Args:
            urls: 이미지 URL 리스트
            save_dir: 저장 디렉토리 (미지정 시 기본 디렉토리)
            min_success: 최소 성공 개수 (0이면 모두 시도)

        Returns:
            다운로드 성공한 파일 경로 리스트
        """
        if not urls:
            logger.warning("다운로드할 URL이 없습니다.")
            return []

        target_dir = Path(save_dir) if save_dir else self.save_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"이미지 다운로드 시작: {len(urls)}개 URL → {target_dir}")

        downloaded = []
        failed = 0

        for idx, url in enumerate(urls):
            filename = f"image_{idx:03d}.jpg"
            file_path = target_dir / filename

            if file_path.exists():
                timestamp = int(time.time() * 1000)
                filename = f"image_{idx:03d}_{timestamp}.jpg"
                file_path = target_dir / filename

            success = self._download_single(url, str(file_path))

            if success and self._verify_image(str(file_path)):
                downloaded.append(str(file_path))
                size_mb = file_path.stat().st_size / (1024 * 1024)
                logger.info(f"[{len(downloaded)}/{len(urls)}] 성공: {filename} ({size_mb:.2f}MB)")

                if min_success > 0 and len(downloaded) >= min_success:
                    logger.info(f"최소 {min_success}개 달성, 다운로드 종료")
                    break
            else:
                if file_path.exists():
                    file_path.unlink(missing_ok=True)
                failed += 1
                logger.debug(f"[실패] {url[:60]}...")

        logger.info(f"다운로드 완료: 성공 {len(downloaded)}개, 실패 {failed}개")
        return downloaded

    def _download_single(self, url: str, save_path: str) -> bool:
        """단일 이미지 다운로드"""
        if not url:
            return False

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self.session.get(url, timeout=self.DEFAULT_TIMEOUT, stream=True)
                response.raise_for_status()

                content_type = response.headers.get('Content-Type', '')
                if not content_type.startswith('image/'):
                    if attempt < self.MAX_RETRIES:
                        continue
                    return False

                content_length = response.headers.get('Content-Length')
                if content_length and int(content_length) > self.MAX_FILE_SIZE:
                    return False

                total_size = 0
                with open(save_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            total_size += len(chunk)
                            if total_size > self.MAX_FILE_SIZE:
                                f.close()
                                Path(save_path).unlink(missing_ok=True)
                                return False

                return True

            except requests.exceptions.Timeout:
                logger.debug(f"타임아웃 (시도 {attempt}/{self.MAX_RETRIES})")
                time.sleep(1 * attempt)
            except requests.exceptions.RequestException as e:
                logger.debug(f"네트워크 오류 (시도 {attempt}/{self.MAX_RETRIES}): {e}")
                time.sleep(1 * attempt)
            except OSError as e:
                logger.error(f"파일 저장 오류: {e}")
                return False

        return False

    def _verify_image(self, file_path: str) -> bool:
        """이미지 파일 검증 및 형식 변환"""
        if not file_path or not Path(file_path).exists():
            return False

        try:
            is_webp = False
            with Image.open(file_path) as img:
                supported = ['JPEG', 'PNG', 'JPG', 'WEBP']
                if img.format not in supported:
                    return False

                is_webp = img.format == 'WEBP'
                width, height = img.size
                if width < self.MIN_RESOLUTION[0] or height < self.MIN_RESOLUTION[1]:
                    return False

                img.verify()

            # verify() 후 재오픈하여 변환
            with Image.open(file_path) as img:
                if is_webp:
                    img.convert('RGB').save(file_path, 'JPEG', quality=95)
                    return True

                if img.mode == 'RGBA':
                    rgb = Image.new('RGB', img.size, (255, 255, 255))
                    rgb.paste(img, mask=img.split()[3])
                    rgb.save(file_path, 'JPEG', quality=95)
                elif img.mode not in ['RGB', 'L']:
                    img.convert('RGB').save(file_path, 'JPEG', quality=95)

            return True

        except Image.UnidentifiedImageError:
            return False
        except Exception:
            return False
