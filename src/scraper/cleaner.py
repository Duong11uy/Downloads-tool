import re
import html
import unicodedata
from typing import List

# Patterns of ads, watermarks, betting and spam commonly found in novel sites
NOISE_PATTERNS = [
    r"truyện\s+(được\s+)?đăng\s+(độc\s+quyền\s+)?tại\s+[^\n.]+",
    r"đọc\s+truyện\s+(miễn\s+phí\s+)?tại\s+[^\n.]+",
    r"nguồn\s*:\s*[^\n.]+",
    r"tải\s+app\s+truyenyy[^\n.]*",
    r"chúc\s+bạn\s+đọc\s+truyện\s+vui\s+vẻ[^\n.]*",
    r"nhấn\s+vào\s+link\s+sau\s+để\s+tải\s+ngay[^\n.]*",
    r"tham\s+gia\s+group[^\n.]*",
    r"ủng\s+hộ\s+(dịch\s+giả|converter|nhóm\s+dịch)[^\n.]*",
    r"(nhà\s+cái|cá\s+cược|uy\s+tín\s+hàng\s+đầu|đặt\s+cược|khuyến\s+mãi\s+nạp|thưởng\s+thành\s+viên)[^\n.]*",
    r"\b(fb88|w88|188bet|kubet|jun88|shbet|new88|789bet|hi88|okvip)\b[^\n.]*",
    r"mọi\s+ý\s+kiến\s+đóng\s+góp[^\n.]*",
    r"vote\s+sao\s+cho\s+truyện[^\n.]*",
    r"hãy\s+tặng\s+(hoa|phiếu|kẹo|bánh)[^\n.]*"
]

COMPILED_NOISE = [re.compile(p, re.IGNORECASE) for p in NOISE_PATTERNS]


def sanitize_filename(name: str, max_length: int = 120) -> str:
    """
    Sanitize text to be safe for filenames across Windows and Linux.
    """
    if not name:
        return "unnamed"
    # Remove invalid characters
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = re.sub(r'[\r\n\t]+', " ", cleaned)
    cleaned = re.sub(r'\s+', " ", cleaned).strip()
    return cleaned[:max_length].strip() or "novel"


def clean_text_paragraph(text: str) -> str:
    """
    Normalize and clean a single paragraph of text.
    """
    if not text:
        return ""
    
    # Unescape HTML entities
    text = html.unescape(text)
    
    # Normalize unicode to NFC (Vietnamese standard)
    text = unicodedata.normalize("NFC", text)
    
    # Replace weird spaces and tabs
    text = text.replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text).strip()
    
    # Check against noise patterns
    for pat in COMPILED_NOISE:
        if pat.search(text) and len(text) < 150:
            # If paragraph contains spam and is relatively short, drop it
            return ""
            
    return text


def clean_chapter_content(paragraphs: List[str]) -> List[str]:
    """
    Clean an entire list of chapter paragraphs.
    Filters empty or advertisement lines.
    """
    cleaned = []
    for p in paragraphs:
        cleaned_p = clean_text_paragraph(p)
        if cleaned_p:
            cleaned.append(cleaned_p)
    return cleaned


def format_paragraphs_to_text(paragraphs: List[str]) -> str:
    """
    Join paragraphs with proper indentation and blank lines for TXT/EPUB.
    """
    return "\n\n".join(paragraphs)


def strip_leading_chapter_titles(paragraphs: List[str], title: str = "", chapter_index: int = 0) -> List[str]:
    """
    Remove redundant chapter headers / title lines at the beginning of a chapter's body.
    For example:
    - Paragraph 0 is 'Chương 98: Vây giết' while title is 'Chương 99: Vây giết'
    - Paragraph 0 is 'Chương 99'
    - Paragraph 0 is 'Vây giết' (exact subtitle match)
    - Any leading lines matching standard chapter title patterns.
    """
    if not paragraphs:
        return paragraphs

    cleaned = list(paragraphs)
    # Extract subtitle from title if any: e.g. "Chương 99: Vây giết" -> "Vây giết"
    subtitle = ""
    if title:
        sub_m = re.sub(
            r"^(?:Chương|Hồi|Tiết|Quyển|C|Chap|Chapter)\s*\d+[\s:.-]*",
            "",
            title,
            flags=re.IGNORECASE
        ).strip()
        subtitle = sub_m.lower()

    title_lower = title.strip().lower() if title else ""

    while cleaned:
        p = cleaned[0].strip()
        p_lower = p.lower()

        # 1. Exact match with chapter title
        if title_lower and p_lower == title_lower:
            cleaned.pop(0)
            continue

        # 2. Matches "Chương <digits>[: -.] <optional_text>" (<= 150 chars)
        # Handles any number, e.g. "Chương 98: Vây giết", "Chương 99", "Chương 98 - ...", "Hồi 98: ..."
        if len(p) < 150 and re.match(
            r"^(?:Chương|Hồi|Tiết|Quyển|C|Chap|Chapter)\s*\d+[\s:.-]*.*$",
            p,
            re.IGNORECASE
        ):
            cleaned.pop(0)
            continue

        # 3. Matches exact subtitle
        if subtitle and len(p) < 80 and p_lower == subtitle:
            cleaned.pop(0)
            continue

        break

    return cleaned
