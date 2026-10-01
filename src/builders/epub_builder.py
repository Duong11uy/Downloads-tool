import html
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.core.config import DOWNLOAD_DIR
from src.scraper.cleaner import sanitize_filename, strip_leading_chapter_titles

CSS_CONTENT = """
@charset "utf-8";
body {
    margin: 5% 8%;
    font-family: "Georgia", "Times New Roman", "Palatino", serif;
    line-height: 1.6;
    text-align: justify;
    text-indent: 1.5em;
}
h1, h2, h3 {
    text-align: center;
    font-weight: bold;
    text-indent: 0;
    margin-top: 1.2em;
    margin-bottom: 0.8em;
    line-height: 1.3;
}
h2 { font-size: 1.4em; }
p {
    margin-top: 0;
    margin-bottom: 0.8em;
}
.cover-img {
    max-width: 100%;
    max-height: 100%;
    display: block;
    margin: 0 auto;
}
nav#toc ol {
    list-style-type: none;
    padding-left: 0;
    text-indent: 0;
}
nav#toc li {
    margin: 0.5em 0;
    text-indent: 0;
}
nav#toc a {
    text-decoration: none;
    color: #2c3e50;
}
"""

CONTAINER_XML = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>
"""


class EpubBuilder:
    """
    Pure Python EPUB3 Generator complying with Open Container Format (OCF).
    Guarantees compatibility with Kindle, Kobo, Apple Books, and Android readers.
    """

    @staticmethod
    def build(
        novel_info: Dict[str, Any],
        chapters: List[Dict[str, Any]],
        cover_bytes: Optional[bytes] = None,
        output_dir: Path = DOWNLOAD_DIR
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        title = novel_info.get("title", "Truyen").strip()
        author = novel_info.get("author", "Khong ro").strip()

        # Determine chapter range for filename
        if chapters:
            first_idx = chapters[0].get("index", 1)
            last_idx = chapters[-1].get("index", first_idx)
            range_suffix = f"(chương {first_idx})" if first_idx == last_idx else f"(chương {first_idx}-{last_idx})"
        else:
            range_suffix = ""

        filename_base = f"{title} {range_suffix}".strip() if range_suffix else title
        safe_title = sanitize_filename(filename_base)
        epub_path = output_dir / f"{safe_title}.epub"

        book_id = f"urn:uuid:{uuid.uuid4()}"
        modified_date = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        with zipfile.ZipFile(epub_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # 1. mimetype (Must be uncompressed at the beginning)
            zip_file.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

            # 2. META-INF/container.xml
            zip_file.writestr("META-INF/container.xml", CONTAINER_XML)

            # 3. OEBPS/style.css
            zip_file.writestr("OEBPS/style.css", CSS_CONTENT)

            # 4. Cover Image
            has_cover = False
            cover_ext = "jpg"
            if cover_bytes:
                if cover_bytes.startswith(b"\x89PNG"):
                    cover_ext = "png"
                zip_file.writestr(f"OEBPS/cover.{cover_ext}", cover_bytes)
                has_cover = True

                cover_html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>Bìa sách</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body style="margin:0;padding:0;text-align:center;">
    <img class="cover-img" src="cover.{cover_ext}" alt="Cover"/>
</body>
</html>"""
                zip_file.writestr("OEBPS/cover.xhtml", cover_html)

            # 5. Chapters XHTML - Directly start with chapter 1
            for i, ch in enumerate(chapters, start=1):
                raw_title = ch.get("title", f"Chương {ch.get('index', i)}")
                ch_title = html.escape(raw_title)
                ch_paragraphs = ch.get("paragraphs", [])
                ch_paragraphs = strip_leading_chapter_titles(ch_paragraphs, title=raw_title, chapter_index=ch.get("index", i))
                p_html = "".join(f"<p>{html.escape(p)}</p>\n" for p in ch_paragraphs)

                ch_content = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>{ch_title}</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
    <h2>{ch_title}</h2>
    {p_html}
</body>
</html>"""
                zip_file.writestr(f"OEBPS/chapter_{i:04d}.xhtml", ch_content)

            # 6. Navigation document (nav.xhtml - EPUB3 requirement)
            nav_items = []
            for i, ch in enumerate(chapters, start=1):
                ch_title = html.escape(ch.get("title", f"Chương {ch.get('index', i)}"))
                nav_items.append(f'<li><a href="chapter_{i:04d}.xhtml">{ch_title}</a></li>')
            nav_list_html = "\n        ".join(nav_items)

            nav_html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>Mục lục</title>
    <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
    <nav epub:type="toc" id="toc">
        <h1>Mục Lục</h1>
        <ol>
        {nav_list_html}
        </ol>
    </nav>
</body>
</html>"""
            zip_file.writestr("OEBPS/nav.xhtml", nav_html)

            # 7. NCX Table of Contents (toc.ncx - EPUB2/Kindle fallback)
            ncx_navpoints = []
            ncx_playorder = 0
            for i, ch in enumerate(chapters, start=1):
                ncx_playorder += 1
                ch_title = html.escape(ch.get("title", f"Chương {ch.get('index', i)}"))
                ncx_navpoints.append(f"""
    <navPoint id="navpoint-{ncx_playorder}" playOrder="{ncx_playorder}">
        <navLabel><text>{ch_title}</text></navLabel>
        <content src="chapter_{i:04d}.xhtml"/>
    </navPoint>""")
            ncx_points_str = "".join(ncx_navpoints)

            ncx_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{book_id}"/>
        <meta name="dtb:depth" content="1"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle><text>{html.escape(title)}</text></docTitle>
    <docAuthor><text>{html.escape(author)}</text></docAuthor>
    <navMap>
        {ncx_points_str}
    </navMap>
</ncx>"""
            zip_file.writestr("OEBPS/toc.ncx", ncx_content)

            # 8. Package document (content.opf)
            manifest_items = [
                '<item id="style" href="style.css" media-type="text/css"/>',
                '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
                '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
            ]
            spine_items = []

            if has_cover:
                media_type = "image/png" if cover_ext == "png" else "image/jpeg"
                manifest_items.insert(0, f'<item id="cover-img" href="cover.{cover_ext}" media-type="{media_type}" properties="cover-image"/>')
                manifest_items.insert(1, '<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>')
                spine_items.append('<itemref idref="cover"/>')

            for i in range(1, len(chapters) + 1):
                manifest_items.append(f'<item id="chapter_{i:04d}" href="chapter_{i:04d}.xhtml" media-type="application/xhtml+xml"/>')
                spine_items.append(f'<itemref idref="chapter_{i:04d}"/>')

            manifest_str = "\n        ".join(manifest_items)
            spine_str = "\n        ".join(spine_items)

            cover_meta = f'<meta name="cover" content="cover-img"/>' if has_cover else ""

            opf_content = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="BookID">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
        <dc:identifier id="BookID">{book_id}</dc:identifier>
        <dc:title>{html.escape(title)}</dc:title>
        <dc:creator>{html.escape(author)}</dc:creator>
        <dc:language>vi</dc:language>
        <meta property="dcterms:modified">{modified_date}</meta>
        {cover_meta}
    </metadata>
    <manifest>
        {manifest_str}
    </manifest>
    <spine toc="ncx">
        {spine_str}
    </spine>
</package>"""
            zip_file.writestr("OEBPS/content.opf", opf_content)

        return epub_path
