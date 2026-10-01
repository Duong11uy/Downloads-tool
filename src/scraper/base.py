import asyncio
import logging
import random
import urllib.request
import urllib.error
from typing import Optional, Dict
from src.core.config import DEFAULT_USER_AGENT, REQUEST_TIMEOUT, MAX_RETRIES

logger = logging.getLogger("scraper.base")

# Check if curl_cffi is available
CURL_CFFI_AVAILABLE = False
try:
    from curl_cffi.requests import AsyncSession as CurlSession
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CurlSession = None

# Check if httpx is available
try:
    import httpx
except ImportError:
    httpx = None

# Check if requests is available
try:
    import requests
except ImportError:
    requests = None


class BaseScraperSession:
    """
    Asynchronous HTTP session wrapper that handles Anti-Bot bypass,
    automatic retries, and browser impersonation with multi-engine fallback
    (curl_cffi -> httpx -> requests -> urllib).
    """
    def __init__(self, headers: Optional[Dict[str, str]] = None, cookie: Optional[str] = None, use_curl_cffi: bool = True):
        self.default_headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "vi,en-US;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        if headers:
            self.default_headers.update(headers)
        if cookie:
            clean_c = cookie.strip()
            if clean_c:
                if not clean_c.startswith("cf_clearance=") and "=" not in clean_c:
                    clean_c = f"cf_clearance={clean_c}"
                self.default_headers["Cookie"] = clean_c

        self.use_curl = use_curl_cffi and CURL_CFFI_AVAILABLE
        self._curl_session = None
        self._httpx_client = None
        self._requests_session = None

    async def __aenter__(self):
        if self.use_curl:
            try:
                self._curl_session = CurlSession(
                    impersonate="chrome120",
                    headers=self.default_headers,
                    timeout=REQUEST_TIMEOUT
                )
            except Exception as e:
                logger.warning(f"Failed to initialize curl_cffi session: {e}. Falling back.")
                self.use_curl = False

        if httpx:
            try:
                # Do NOT pass http2=True to avoid missing 'h2' and SSL EOF issues
                self._httpx_client = httpx.AsyncClient(
                    headers=self.default_headers,
                    timeout=REQUEST_TIMEOUT,
                    follow_redirects=True
                )
            except Exception as e:
                logger.warning(f"Failed to initialize httpx client: {e}")
                self._httpx_client = None

        if requests:
            try:
                self._requests_session = requests.Session()
                self._requests_session.headers.update(self.default_headers)
            except Exception as e:
                logger.warning(f"Failed to initialize requests session: {e}")
                self._requests_session = None

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._curl_session:
            try:
                await self._curl_session.close()
            except Exception:
                pass
        if self._httpx_client:
            try:
                await self._httpx_client.aclose()
            except Exception:
                pass
        if self._requests_session:
            try:
                self._requests_session.close()
            except Exception:
                pass

    def _sync_requests_get(self, url: str, headers: Dict[str, str]) -> str:
        s = self._requests_session or requests.Session()
        resp = s.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text

    def _sync_requests_get_bytes(self, url: str, headers: Dict[str, str]) -> bytes:
        s = self._requests_session or requests.Session()
        resp = s.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.content

    def _sync_urllib_get(self, url: str, headers: Dict[str, str]) -> bytes:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            return response.read()

    def _sync_requests_post(self, url: str, data: Dict[str, Any], headers: Dict[str, str]) -> str:
        s = self._requests_session or requests.Session()
        resp = s.post(url, data=data, headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        if not resp.encoding or resp.encoding.lower() == "iso-8859-1":
            resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text

    def _sync_urllib_post(self, url: str, data: Dict[str, Any], headers: Dict[str, str]) -> bytes:
        import urllib.parse
        encoded_data = urllib.parse.urlencode(data).encode("utf-8")
        req_headers = {**headers, "Content-Type": "application/x-www-form-urlencoded"}
        req = urllib.request.Request(url, data=encoded_data, headers=req_headers)
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            return response.read()

    async def post_form(self, url: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None, retries: int = MAX_RETRIES) -> str:
        attempt = 0
        req_headers = {**self.default_headers, **(headers or {})}
        while attempt < retries:
            attempt += 1
            if self.use_curl and self._curl_session:
                try:
                    resp = await self._curl_session.post(url, data=data, headers=req_headers)
                    if resp.status_code == 200:
                        return resp.text
                except Exception as ce:
                    logger.warning(f"curl_cffi POST error ({attempt}/{retries}): {ce}")

            if self._httpx_client:
                try:
                    resp = await self._httpx_client.post(url, data=data, headers=req_headers)
                    if resp.status_code == 200:
                        return resp.text
                except Exception as he:
                    logger.warning(f"httpx POST error ({attempt}/{retries}): {he}")

            if requests:
                try:
                    return await asyncio.to_thread(self._sync_requests_post, url, data, req_headers)
                except Exception as re_err:
                    logger.warning(f"requests POST error ({attempt}/{retries}): {re_err}")

            try:
                raw_bytes = await asyncio.to_thread(self._sync_urllib_post, url, data, req_headers)
                return raw_bytes.decode("utf-8", errors="replace")
            except Exception as ue:
                logger.warning(f"urllib POST error ({attempt}/{retries}): {ue}")

            if attempt >= retries:
                raise Exception(f"POST {url} thất bại sau {retries} lần thử.")
            await asyncio.sleep(0.5)
        raise Exception(f"POST {url} thất bại")

    async def get_html(self, url: str, headers: Optional[Dict[str, str]] = None, retries: int = MAX_RETRIES) -> str:
        """
        Fetch HTML content from a URL with multi-client cascade and automatic retries.
        """
        attempt = 0
        req_headers = {**self.default_headers, **(headers or {})}

        while attempt < retries:
            attempt += 1
            last_error = None
            is_rate_limited = False

            # 1. Try curl_cffi
            if self.use_curl and self._curl_session:
                try:
                    resp = await self._curl_session.get(url, headers=req_headers)
                    if resp.status_code == 200:
                        return resp.text
                    if resp.status_code in [429, 503, 520]:
                        is_rate_limited = True
                    last_error = f"status {resp.status_code}"
                except Exception as ce:
                    last_error = str(ce)

            # 2. Try httpx
            if self._httpx_client:
                try:
                    resp = await self._httpx_client.get(url, headers=req_headers)
                    if resp.status_code == 200:
                        return resp.text
                    if resp.status_code in [429, 503, 520]:
                        is_rate_limited = True
                    last_error = f"status {resp.status_code}"
                except Exception as he:
                    last_error = str(he)

            # 3. Try requests (sync in thread, rock solid with TLS)
            if requests:
                try:
                    return await asyncio.to_thread(self._sync_requests_get, url, req_headers)
                except Exception as re_err:
                    err_msg = str(re_err).lower()
                    if "429" in err_msg or "too many requests" in err_msg or "503" in err_msg:
                        is_rate_limited = True
                    last_error = str(re_err)

            # 4. Fallback to urllib
            try:
                raw_bytes = await asyncio.to_thread(self._sync_urllib_get, url, req_headers)
                return raw_bytes.decode("utf-8", errors="replace")
            except Exception as ue:
                last_error = str(ue)

            if attempt >= retries:
                raise Exception(f"Không thể kết nối đến {url} sau {retries} lần thử ({last_error or 'kiểm tra mạng hoặc tường lửa web'}).")

            # Progressive backoff with jitter
            backoff = min(7.0, (1.4 ** attempt) + random.uniform(0.3, 0.8))
            if is_rate_limited:
                backoff += 2.0
            await asyncio.sleep(backoff)

        raise Exception(f"Không thể tải HTML từ {url}")

    async def get_binary(self, url: str, retries: int = 2) -> Optional[bytes]:
        """
        Download binary data like cover images.
        """
        attempt = 0
        while attempt < retries:
            attempt += 1
            if self.use_curl and self._curl_session:
                try:
                    resp = await self._curl_session.get(url)
                    if resp.status_code == 200:
                        return resp.content
                except Exception:
                    pass

            if self._httpx_client:
                try:
                    resp = await self._httpx_client.get(url)
                    if resp.status_code == 200:
                        return resp.content
                except Exception:
                    pass

            if requests:
                try:
                    return await asyncio.to_thread(self._sync_requests_get_bytes, url, self.default_headers)
                except Exception:
                    pass

            try:
                return await asyncio.to_thread(self._sync_urllib_get, url, self.default_headers)
            except Exception as e:
                logger.warning(f"Error fetching binary {url} (Attempt {attempt}): {e}")

            await asyncio.sleep(0.5)
        return None
