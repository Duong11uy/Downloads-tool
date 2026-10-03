import asyncio
import json
import logging
import math
import re
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, urljoin
from src.core.config import SITES_CONFIG_PATH
from src.scraper.cleaner import clean_chapter_content, clean_text_paragraph, strip_leading_chapter_titles
from src.scraper.fallback_parser import FallbackParser
from src.scraper.base import BaseScraperSession

logger = logging.getLogger("scraper.site_parser")


def make_soup(html_text: str, *args, **kwargs) -> BeautifulSoup:
    try:
        return BeautifulSoup(html_text, "lxml")
    except Exception:
        return BeautifulSoup(html_text, "html.parser")


def normalize_novel_url(url: str) -> str:
    """
    Ensure the URL points to the novel overview page.
    E.g.:
    https://www.truyenyy.co/truyen/tu-la-thien-de-ban-dich/chuong-1:-tan-menh
    -> https://www.truyenyy.co/truyen/tu-la-thien-de-ban-dich
    """
    url = url.strip()
    m = re.match(r"^(https?://(?:www\.)?truyenyy\.(?:co|vip|com)/truyen/[^/?#]+)", url, re.IGNORECASE)
    if m:
        return m.group(1).rstrip("/")
    m_xtruyen = re.match(r"^(https?://(?:www\.)?xtruyen\.vn/truyen/[^/?#]+)", url, re.IGNORECASE)
    if m_xtruyen:
        return m_xtruyen.group(1).rstrip("/") + "/"
    return url.rstrip("/")


class SiteParserManager:
    """
    Manages site-specific configurations and parsing execution.
    """

    def __init__(self, config_path=SITES_CONFIG_PATH):
        self.config_path = config_path
        self.sites = {}
        self.load_config()

    def load_config(self):
        try:
            if self.config_path.exists():
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.sites = data.get("sites", {})
                logger.info(f"Loaded {len(self.sites)} site configs from {self.config_path}")
            else:
                logger.warning(f"Config file not found at {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load config {self.config_path}: {e}")

    def find_site_config(self, url: str) -> Optional[Dict[str, Any]]:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if ":" in domain:
            domain = domain.split(":")[0]

        for key, site in self.sites.items():
            domains = site.get("domains", [])
            for d in domains:
                if d in domain or domain.endswith("." + d):
                    return site
        return None

    def set_site_cookie(self, domain_or_url: str, cookie: str, user_agent: str = ""):
        cfg = self.find_site_config(domain_or_url)
        if not cfg:
            for k, s in self.sites.items():
                if "xtruyen" in k:
                    cfg = s
                    break
        if cfg:
            if "headers" not in cfg:
                cfg["headers"] = {}
            if cookie:
                clean_c = cookie.strip()
                if not clean_c.startswith("cf_clearance=") and "=" not in clean_c:
                    clean_c = f"cf_clearance={clean_c}"
                cfg["headers"]["Cookie"] = clean_c
            if user_agent:
                cfg["headers"]["User-Agent"] = user_agent.strip()
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump({"sites": self.sites}, f, ensure_ascii=False, indent=2)
                logger.info(f"Successfully saved cookie and user-agent for {domain_or_url}")
            except Exception as e:
                logger.warning(f"Failed to persist site cookie: {e}")

    def _select_first(self, soup: BeautifulSoup, selectors: List[str]) -> Optional[Any]:
        for sel in selectors:
            try:
                el = soup.select_one(sel)
                if el:
                    return el
            except Exception:
                continue
        return None

    @staticmethod
    def decompress_xtruyen_content(html: str) -> Optional[List[str]]:
        """
        Extracts and decompresses encrypted chapter content for xtruyen.vn.
        """
        import base64
        import zlib
        m = re.search(r'const\s+data_x\s*=\s*["\']([^"\']+)["\']', html)
        if not m:
            return None
        data_x = m.group(1).strip()
        if not data_x:
            return None

        c_chars = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_"
        s_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

        for trans_from, trans_to in [(c_chars, s_chars), (s_chars, c_chars)]:
            try:
                trans = str.maketrans(trans_from, trans_to)
                b64_str = data_x.translate(trans)
                pad = len(b64_str) % 4
                if pad:
                    b64_str += "=" * (4 - pad)
                raw_bytes = base64.b64decode(b64_str)
                decompressed = None
                for wbits in (15, -15, 32 + 15):
                    try:
                        decompressed = zlib.decompress(raw_bytes, wbits).decode("utf-8", errors="ignore")
                        break
                    except Exception:
                        pass
                if decompressed:
                    soup = make_soup(decompressed)
                    for rm in soup.select("script, style, svg, .ads, .advertisement, .native-stories, .classic-stories, .story-item, button, nav"):
                        rm.decompose()
                    for br in soup.find_all("br"):
                        br.replace_with("\n")
                    text = soup.get_text()
                    lines = text.split("\n")
                    paragraphs = []
                    for line in lines:
                        cleaned = clean_text_paragraph(line)
                        if cleaned:
                            paragraphs.append(cleaned)
                    if paragraphs:
                        return paragraphs
            except Exception as ex:
                logger.debug(f"XTruyen decode attempt error: {ex}")
                continue
        return None

    async def fetch_xtruyen_chapters(
        self,
        session: BaseScraperSession,
        novel_url: str,
        manga_id: str,
        from_idx: int = 1,
        to_idx: int = 100,
        cookie: str = "",
        user_agent: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Fetch chapters from xtruyen.vn API.
        """
        api_url = "https://xtruyen.vn/api/api-chapters.php"
        ua = user_agent.strip() if user_agent else session.default_headers.get("User-Agent", DEFAULT_USER_AGENT)
        headers = {
            "User-Agent": ua,
            "Accept": "*/*",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "X-Requested-With": "XMLHttpRequest",
            "X-Custom-Auth": "abC0000011111",
            "Origin": "https://xtruyen.vn",
            "Referer": novel_url,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"'
        }
        if cookie:
            clean_c = cookie.strip()
            if not clean_c.startswith("cf_clearance=") and "=" not in clean_c:
                clean_c = f"cf_clearance={clean_c}"
            headers["Cookie"] = clean_c
        elif "Cookie" in session.default_headers:
            headers["Cookie"] = session.default_headers["Cookie"]
        data = {
            "manga_id": str(manga_id),
            "from": str(from_idx),
            "to": str(to_idx)
        }
        try:
            res_text = await session.post_form(api_url, data=data, headers=headers)
            items = json.loads(res_text)
            chapters = []
            clean_base = novel_url.rstrip("/") + "/"
            for item in items:
                slug = item.get("s", "").strip().strip("/")
                if not slug:
                    continue
                n = item.get("n", "").strip()
                e = item.get("e", "").strip()
                title = f"{n}: {e}".strip(": ") if e else n
                if not title:
                    title = slug

                idx = None
                m_slug = re.search(r'chuong-(\d+)', slug, re.IGNORECASE)
                if m_slug:
                    idx = int(m_slug.group(1))
                else:
                    m_n = re.search(r'(\d+)', n)
                    if m_n:
                        idx = int(m_n.group(1))
                    else:
                        idx = len(chapters) + 1

                full_url = f"{clean_base}{slug}/"
                chapters.append({
                    "index": idx,
                    "title": clean_text_paragraph(title),
                    "url": full_url,
                    "is_vip": False
                })
            return chapters
        except Exception as err:
            logger.warning(f"Error fetching xtruyen chapters ({from_idx}-{to_idx}): {err}")
            return []

    async def _fetch_xtruyen_chapter_list(
        self,
        session: BaseScraperSession,
        novel_url: str,
        expected_total: int = 0,
        start_page: int = 1,
        end_page: Optional[int] = None,
        target_start_chap: int = 1,
        target_end_chap: int = 99999,
        cookie: str = "",
        user_agent: str = ""
    ) -> tuple[List[Dict[str, Any]], int]:
        clean_base = novel_url.rstrip("/") + "/"
        page_size = 100

        site_cfg = self.find_site_config(clean_base)
        headers = dict(site_cfg.get("headers", {})) if site_cfg else {}
        if not cookie and site_cfg and "headers" in site_cfg:
            cookie = site_cfg["headers"].get("Cookie", "")
        if not user_agent and site_cfg and "headers" in site_cfg:
            user_agent = site_cfg["headers"].get("User-Agent", "")

        if cookie:
            clean_c = cookie.strip()
            if not clean_c.startswith("cf_clearance=") and "=" not in clean_c:
                clean_c = f"cf_clearance={clean_c}"
            headers["Cookie"] = clean_c
        if user_agent:
            headers["User-Agent"] = user_agent.strip()

        home_html = await session.get_html(clean_base, headers=headers)
        manga_id = None
        m_id = re.search(r'id="manga-chapters-holder"\s+data-id="(\d+)"', home_html)
        if m_id:
            manga_id = m_id.group(1)
        if not manga_id:
            m_btn = re.search(r'data-post="(\d+)"', home_html)
            if m_btn:
                manga_id = m_btn.group(1)
        if not manga_id:
            m_cls = re.search(r'post-(\d+)', home_html)
            if m_cls:
                manga_id = m_cls.group(1)

        if expected_total == 0:
            m_lc = re.search(r'chuong-(\d+)[^"]*"\s+class="c-btn[^"]*">\s*Chương cuối', home_html, re.IGNORECASE)
            if m_lc:
                expected_total = int(m_lc.group(1))
            if expected_total == 0:
                m_sc = re.search(r'class="chapter-title[^"]*"[^>]*href="[^"]*chuong-(\d+)', home_html, re.IGNORECASE)
                if m_sc:
                    expected_total = int(m_sc.group(1))

        if not manga_id:
            logger.warning("Could not find manga_id for xtruyen.vn")
            return [], expected_total

        # Fast preview for analyze_novel (only page 1)
        if start_page == 1 and end_page == 1 and target_end_chap >= 99999:
            p_chaps = await self.fetch_xtruyen_chapters(
                session=session,
                novel_url=clean_base,
                manga_id=manga_id,
                from_idx=1,
                to_idx=100,
                cookie=cookie,
                user_agent=user_agent
            )
            return p_chaps, expected_total

        # For downloading: determine starting page offset
        # Note: in XTruyen database row index != chapter number (e.g. row 100 is chapter 94)
        # So we start 1 page earlier to ensure no missing chapters
        curr_p = max(1, (target_start_chap - 1) // page_size)
        all_chapters = []
        seen_indices = {}

        while True:
            f_idx = (curr_p - 1) * page_size + 1
            t_idx = curr_p * page_size
            p_chaps = await self.fetch_xtruyen_chapters(
                session=session,
                novel_url=clean_base,
                manga_id=manga_id,
                from_idx=f_idx,
                to_idx=t_idx,
                cookie=cookie,
                user_agent=user_agent
            )
            if not p_chaps:
                break

            for ch in p_chaps:
                ch_idx = ch.get("index")
                if ch_idx is None:
                    continue
                if ch_idx not in seen_indices:
                    seen_indices[ch_idx] = len(all_chapters)
                    all_chapters.append(ch)
                else:
                    # If this chapter has a more descriptive title, replace earlier duplicate
                    pos = seen_indices[ch_idx]
                    if len(ch.get("title", "")) > len(all_chapters[pos].get("title", "")):
                        all_chapters[pos] = ch

            max_idx = max((ch.get("index", 0) for ch in all_chapters), default=0)
            if max_idx >= target_end_chap:
                break
            if expected_total > 0 and max_idx >= expected_total:
                break
            if curr_p > 500:
                break

            curr_p += 1
            await asyncio.sleep(0.2)

        return all_chapters, expected_total

    async def analyze_novel(
        self,
        session: BaseScraperSession,
        url: str,
        max_pages_to_fetch: int = 1,
        cookie: str = "",
        user_agent: str = ""
    ) -> Dict[str, Any]:
        """
        Analyze a novel homepage: extract title, author, cover, description,
        and fetch initial chapter list.
        """
        clean_url = normalize_novel_url(url)
        site_cfg = self.find_site_config(clean_url)
        headers = dict(site_cfg.get("headers", {})) if site_cfg else {}
        if cookie:
            clean_c = cookie.strip()
            if not clean_c.startswith("cf_clearance=") and "=" not in clean_c:
                clean_c = f"cf_clearance={clean_c}"
            headers["Cookie"] = clean_c
            self.set_site_cookie(clean_url, cookie, user_agent)
        if user_agent:
            headers["User-Agent"] = user_agent.strip()
        html = await session.get_html(clean_url, headers=headers)
        if "xtruyen.vn" in clean_url:
            try:
                with open("debug_xtruyen.html", "w", encoding="utf-8") as df:
                    df.write(html)
            except Exception:
                pass
        soup = make_soup(html)

        if not site_cfg:
            logger.info(f"No specific site config found for {clean_url}. Using FallbackParser.")
            info = FallbackParser.parse_novel_info(html, clean_url)
            return info

        selectors = site_cfg.get("selectors", {})

        # 1. Title
        title = ""
        title_el = self._select_first(soup, selectors.get("title", []))
        if title_el:
            if title_el.name == "meta":
                title = title_el.get("content", "").strip()
            else:
                title = title_el.get_text().strip()

        # 2. Author
        author = "Không rõ"
        author_el = self._select_first(soup, selectors.get("author", []))
        if author_el:
            author = author_el.get_text().strip()

        # 3. Cover Image
        cover = ""
        cover_el = self._select_first(soup, selectors.get("cover", []))
        if cover_el:
            if cover_el.name == "meta":
                cover = cover_el.get("content", "").strip()
            elif cover_el.name == "img":
                cover = cover_el.get("src", "") or cover_el.get("data-src", "")
            if cover:
                cover = urljoin(clean_url, cover)

        # 4. Description
        description = ""
        desc_el = self._select_first(soup, selectors.get("description", []))
        if desc_el:
            if desc_el.name == "meta":
                description = desc_el.get("content", "").strip()
            else:
                description = desc_el.get_text("\n").strip()

        # 5. Status
        status = "Đang ra"
        status_regex = selectors.get("status_regex")
        if status_regex:
            match = re.search(status_regex, html, re.IGNORECASE)
            if match:
                for g in match.groups():
                    if g:
                        status = g.strip()
                        break

        # 6. Total chapters from novel homepage
        total_chapters = 0

        # Check Next.js __NEXT_DATA__ script
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
        if next_data_match:
            try:
                nd = json.loads(next_data_match.group(1))
                props = nd.get("props", {}).get("pageProps", {})
                novel_data = props.get("novel") or props.get("truyen") or props.get("story") or props
                for key in ["total_chapters", "chap_count", "total_chap", "total_chapter", "num_chapters", "count_chap", "count_chapter"]:
                    if key in novel_data and isinstance(novel_data[key], int) and novel_data[key] > 0:
                        total_chapters = novel_data[key]
                        break
            except Exception:
                pass

        if total_chapters == 0:
            count_patterns = [
                r'(\d{1,6})(?:<[^>]+>|\s|<!--.*?-->)*?Chương',
                r'Truyện có\s*(?:<!--\s*-->)?\s*(\d+)\s*chương',
                r'Số chương[^\d<]*?(\d+)',
                r'class="text-base">\s*(\d+)'
            ]
            for pat in count_patterns:
                matches = re.findall(pat, html, re.IGNORECASE)
                if matches:
                    valid_nums = []
                    for m in matches:
                        if isinstance(m, tuple):
                            m = [x for x in m if x]
                            m = m[0] if m else ""
                        if m and m.isdigit() and int(m) > 0:
                            valid_nums.append(int(m))
                    if valid_nums:
                        total_chapters = max(valid_nums)
                        break

        # Check XTruyen specific latest chapter & total chapters
        if "xtruyen.vn" in clean_url:
            last_chap_btn = soup.find(lambda tag: tag.name == "a" and "Chương cuối" in tag.get_text())
            if last_chap_btn and last_chap_btn.get("href"):
                m_lc = re.search(r'chuong-(\d+)', last_chap_btn.get("href"), re.IGNORECASE)
                if m_lc:
                    total_chapters = int(m_lc.group(1))
            if total_chapters == 0:
                sum_chap = soup.select_one(".summary-content-chapter a")
                if sum_chap and sum_chap.get("href"):
                    m_sc = re.search(r'chuong-(\d+)', sum_chap.get("href"), re.IGNORECASE)
                    if m_sc:
                        total_chapters = int(m_sc.group(1))

        # 7. Fetch initial chapter list (default 1 page is enough for novel metadata & total chapter count)
        chapters, discovered_total = await self.fetch_chapter_list(
            session=session,
            novel_url=clean_url,
            site_cfg=site_cfg,
            expected_total=total_chapters,
            start_page=1,
            end_page=max_pages_to_fetch
        )
        if discovered_total > 0:
            total_chapters = discovered_total
        elif chapters and total_chapters == 0:
            total_chapters = len(chapters)

        return {
            "title": title or "Không có tiêu đề",
            "author": author or "Không rõ",
            "cover": cover,
            "description": description,
            "status": status,
            "total_chapters": total_chapters or len(chapters),
            "chapters": chapters,
            "site_name": site_cfg.get("name", "TruyenYY"),
            "novel_url": clean_url
        }

    async def fetch_chapter_list(
        self,
        session: BaseScraperSession,
        novel_url: str,
        site_cfg: Dict[str, Any],
        expected_total: int = 0,
        start_page: int = 1,
        end_page: Optional[int] = None,
        target_start_chap: int = 1,
        target_end_chap: int = 99999,
        cookie: str = "",
        user_agent: str = ""
    ) -> tuple[List[Dict[str, Any]], int]:
        """
        Fetch chapter list according to pagination and selectors.
        Supports fetching only a subset of pages [start_page, end_page].
        """
        clean_novel_url = normalize_novel_url(novel_url).rstrip("/")
        if "xtruyen.vn" in clean_novel_url:
            return await self._fetch_xtruyen_chapter_list(
                session=session,
                novel_url=clean_novel_url,
                expected_total=expected_total,
                start_page=start_page,
                end_page=end_page,
                target_start_chap=target_start_chap,
                target_end_chap=target_end_chap,
                cookie=cookie,
                user_agent=user_agent
            )

        headers = dict(site_cfg.get("headers", {})) if site_cfg else {}
        if not cookie and site_cfg and "headers" in site_cfg:
            cookie = site_cfg["headers"].get("Cookie", "")
        if not user_agent and site_cfg and "headers" in site_cfg:
            user_agent = site_cfg["headers"].get("User-Agent", "")

        if cookie:
            clean_c = cookie.strip()
            if not clean_c.startswith("cf_clearance=") and "=" not in clean_c:
                clean_c = f"cf_clearance={clean_c}"
            headers["Cookie"] = clean_c
        if user_agent:
            headers["User-Agent"] = user_agent.strip()

        selectors = site_cfg.get("selectors", {})
        pagination = site_cfg.get("pagination", {})

        list_url_pattern = selectors.get("chapter_list_page_url") or selectors.get("chapter_list_url")
        if not list_url_pattern:
            return [], expected_total

        chapters = []
        seen_urls = set()
        page_size = pagination.get("page_size", 100)
        curr_page = max(1, start_page)
        max_pages = math.ceil(expected_total / page_size) if expected_total > 0 else 1
        known_max = expected_total > 0

        while True:
            # Stop if reached target end_page
            if end_page is not None and curr_page > end_page:
                break
            # If max pages is known and exceeded, stop
            if known_max and curr_page > max_pages:
                break
            # Upper bound safeguard
            if curr_page > 500:
                break

            page_url = list_url_pattern.format(novel_url=clean_novel_url, page=curr_page)
            try:
                page_html = await session.get_html(page_url, headers=headers)
                soup = make_soup(page_html, "lxml")

                # On first page, inspect page for total chapters & dropdown options
                if curr_page == start_page:
                    tc_match = re.search(r'Truyện có\s*(?:<!--\s*-->)?\s*(\d+)\s*chương', page_html, re.IGNORECASE)
                    if tc_match:
                        try:
                            tc_val = int(tc_match.group(1))
                            if tc_val > 0:
                                expected_total = tc_val
                                max_pages = math.ceil(expected_total / page_size)
                                known_max = True
                        except ValueError:
                            pass

                    options = soup.select("select option")
                    if options:
                        highest_page = 0
                        for opt in options:
                            val = opt.get("value", "")
                            val_m = re.search(r'(\d+)', val)
                            if val_m:
                                highest_page = max(highest_page, int(val_m.group(1)))

                        if highest_page > 0:
                            max_pages = max(max_pages, highest_page)
                            known_max = True
                        if len(options) > max_pages:
                            max_pages = len(options)
                            known_max = True

                item_selector = selectors.get("chapter_items", "ul.divide-y li a")
                items = soup.select(item_selector)
                if not items:
                    for alt in ["ul.divide-y a", "ul li a[href*='chuong-']", "a[href*='/chuong-']", "div.divide-y a"]:
                        items = soup.select(alt)
                        if items:
                            break

                if not items:
                    # No chapters found on this page
                    break

                page_new_count = 0
                for a_tag in items:
                    href = a_tag.get("href", "")
                    if not href:
                        continue
                    full_url = urljoin(page_url, href)
                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)
                    page_new_count += 1

                    # Extract title
                    title_sel = selectors.get("chapter_title")
                    title_text = ""
                    if title_sel:
                        t_el = a_tag.select_one(title_sel)
                        if t_el:
                            title_text = t_el.get_text().strip()
                    if not title_text:
                        title_text = a_tag.get_text().strip()

                    # Extract chapter index
                    idx = None
                    idx_sel = selectors.get("chapter_index")
                    if idx_sel:
                        i_el = a_tag.select_one(idx_sel)
                        if i_el and i_el.get_text().strip().isdigit():
                            idx = int(i_el.get_text().strip())

                    # Regex fallback for index from href or title
                    if idx is None:
                        url_m = re.search(r'chuong-(\d+)', href, re.IGNORECASE)
                        if url_m:
                            idx = int(url_m.group(1))
                        else:
                            title_m = re.search(r'Chương\s+(\d+)', title_text, re.IGNORECASE)
                            if title_m:
                                idx = int(title_m.group(1))
                            else:
                                idx = len(chapters) + 1

                    # Check VIP badge
                    vip_badge = selectors.get("chapter_vip_badge")
                    is_vip = bool(a_tag.select_one(vip_badge)) if vip_badge else False

                    chapters.append({
                        "index": idx,
                        "title": clean_text_paragraph(title_text) or f"Chương {idx}",
                        "url": full_url,
                        "is_vip": is_vip
                    })

                if page_new_count == 0:
                    break

                curr_page += 1
            except Exception as e:
                logger.warning(f"Error fetching chapter list page {curr_page}: {e}")
                break

        # Sort chapters by index to guarantee sequential ordering
        chapters.sort(key=lambda x: x["index"])
        return chapters, expected_total

    async def parse_chapter(
        self,
        session: BaseScraperSession,
        chapter_url: str,
        chapter_index: int,
        chapter_title_hint: str = "",
        cookie: str = "",
        user_agent: str = ""
    ) -> Dict[str, Any]:
        """
        Download and parse a single chapter's content.
        """
        site_cfg = self.find_site_config(chapter_url)
        headers = dict(site_cfg.get("headers", {})) if site_cfg else {}
        if not cookie and site_cfg and "headers" in site_cfg:
            cookie = site_cfg["headers"].get("Cookie", "")
        if not user_agent and site_cfg and "headers" in site_cfg:
            user_agent = site_cfg["headers"].get("User-Agent", "")

        if cookie:
            clean_c = cookie.strip()
            if not clean_c.startswith("cf_clearance=") and "=" not in clean_c:
                clean_c = f"cf_clearance={clean_c}"
            headers["Cookie"] = clean_c
        if user_agent:
            headers["User-Agent"] = user_agent.strip()
        html = await session.get_html(chapter_url, headers=headers)
        soup = make_soup(html, "lxml")

        if not site_cfg:
            res = FallbackParser.parse_chapter_content(html)
            title = res["title"] or chapter_title_hint or f"Chương {chapter_index}"
            return {
                "index": chapter_index,
                "title": title,
                "paragraphs": res["paragraphs"]
            }

        selectors = site_cfg.get("selectors", {})

        # Remove noise elements
        for remove_sel in selectors.get("remove_selectors", []):
            for el in soup.select(remove_sel):
                el.decompose()

        # Extract title
        title = ""
        h1 = soup.select_one("h1")
        if h1:
            title = h1.get_text().strip()
        elif soup.title:
            title = soup.title.get_text().strip()
        if not title:
            title = chapter_title_hint or f"Chương {chapter_index}"

        # Check if xtruyen encrypted content
        if "xtruyen.vn" in chapter_url:
            decompressed_paras = self.decompress_xtruyen_content(html)
            if decompressed_paras:
                cleaned_paragraphs = clean_chapter_content(decompressed_paras)
                title = chapter_title_hint
                if not title:
                    if soup.title:
                        t_m = re.search(r'(Chương\s+\d+.*?)(\s*-\s*XTruyen|\s*-\s*Đọc truyện|$)', soup.title.get_text(), re.IGNORECASE)
                        if t_m:
                            title = t_m.group(1).strip()
                if not title:
                    title = f"Chương {chapter_index}"

                # Remove duplicate chapter title line at the beginning of paragraphs if present
                cleaned_paragraphs = strip_leading_chapter_titles(cleaned_paragraphs, title=title, chapter_index=chapter_index)

                if not cleaned_paragraphs:
                    raise ValueError("Nội dung chương từ XTruyen trống sau khi làm sạch")

                return {
                    "index": chapter_index,
                    "title": clean_text_paragraph(title),
                    "paragraphs": cleaned_paragraphs
                }
            else:
                raise ValueError("Không tìm thấy dữ liệu nội dung chương từ XTruyen (trang bị chặn hoặc trống)")

        # Extract paragraphs
        content_sel = selectors.get("chapter_content", "article")
        content_el = soup.select_one(content_sel)

        raw_paragraphs = []
        if content_el:
            p_tags = content_el.find_all("p")
            if p_tags:
                raw_paragraphs = [p.get_text().strip() for p in p_tags if p.get_text().strip()]
            else:
                lines = content_el.get_text("\n").split("\n")
                raw_paragraphs = [line.strip() for line in lines if line.strip()]

        cleaned_paragraphs = clean_chapter_content(raw_paragraphs)
        cleaned_paragraphs = strip_leading_chapter_titles(cleaned_paragraphs, title=title, chapter_index=chapter_index)
        if not cleaned_paragraphs:
            raise ValueError("Nội dung chương trống hoặc không thể trích xuất")

        return {
            "index": chapter_index,
            "title": clean_text_paragraph(title),
            "paragraphs": cleaned_paragraphs
        }
