import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from src.scraper.cleaner import clean_chapter_content


def make_soup(html_text: str) -> BeautifulSoup:
    try:
        return BeautifulSoup(html_text, "lxml")
    except Exception:
        return BeautifulSoup(html_text, "html.parser")


class FallbackParser:
    """
    Heuristic Smart Reader Fallback for arbitrary or unconfigured novel sites.
    """

    @staticmethod
    def parse_novel_info(html: str, url: str) -> Dict[str, Any]:
        soup = make_soup(html)

        # 1. Title
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text().strip()
        if not title and soup.title:
            title = soup.title.get_text().strip()

        # 2. Author
        author = "Không rõ"
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta and author_meta.get("content"):
            author = author_meta["content"].strip()
        else:
            # Search in page text for "Tác giả:"
            match = re.search(r"Tác\s*giả\s*[:\-]\s*([^\n<]+)", html, re.IGNORECASE)
            if match:
                author = match.group(1).strip()

        # 3. Cover Image
        cover = ""
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            cover = urljoin(url, og_image["content"].strip())

        # 4. Description
        description = ""
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            description = og_desc["content"].strip()
        if not description:
            desc_tag = soup.find("meta", attrs={"name": "description"})
            if desc_tag and desc_tag.get("content"):
                description = desc_tag["content"].strip()

        return {
            "title": title,
            "author": author,
            "cover": cover,
            "description": description,
            "status": "Đang ra",
            "total_chapters": 0,
            "chapters": []
        }

    @staticmethod
    def parse_chapter_content(html: str) -> Dict[str, Any]:
        soup = make_soup(html)

        # Extract title
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text().strip()
        elif soup.title:
            title = soup.title.get_text().strip()

        # Clean noise tags
        for tag in soup(["script", "style", "noscript", "iframe", "svg"]):
            tag.decompose()

        # Candidates for chapter content container
        content_el = None
        selectors = [
            "article",
            "#chapter-c",
            ".chapter-c",
            "#chapter-content",
            ".chapter-content",
            ".reading-content",
            "#content",
            ".content",
            ".box-chap"
        ]

        for sel in selectors:
            candidate = soup.select_one(sel)
            if candidate:
                content_el = candidate
                break

        # Fallback: Find container with most <p> elements
        if not content_el:
            paragraphs = soup.find_all("p")
            if len(paragraphs) > 5:
                # Group by parent
                parents = [p.parent for p in paragraphs]
                content_el = max(set(parents), key=parents.count)

        raw_paragraphs = []
        if content_el:
            p_tags = content_el.find_all("p")
            if p_tags:
                raw_paragraphs = [p.get_text().strip() for p in p_tags if p.get_text().strip()]
            else:
                # Split by <br> or double newlines
                text = content_el.get_text("\n")
                raw_paragraphs = [line.strip() for line in text.split("\n") if line.strip()]

        cleaned_paragraphs = clean_chapter_content(raw_paragraphs)

        return {
            "title": title,
            "paragraphs": cleaned_paragraphs
        }
