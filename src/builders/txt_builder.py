import logging
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.core.config import DOWNLOAD_DIR
from src.scraper.cleaner import sanitize_filename, strip_leading_chapter_titles

logger = logging.getLogger("builders.txt")


class TxtBuilder:
    """
    Builds clean, standard UTF-8 text files for novels.
    Directly starts with chapter title and content without extra fluff or headers.
    """

    @staticmethod
    def get_story_dir(novel_title: str, output_dir: Path = DOWNLOAD_DIR) -> Path:
        """Returns or creates the dedicated folder downloads/[Tên truyện]/"""
        safe_title = sanitize_filename(novel_title.strip())
        story_dir = output_dir / safe_title
        story_dir.mkdir(parents=True, exist_ok=True)
        return story_dir

    @staticmethod
    def find_existing_chapter_file(story_dir: Path, chapter_index: int) -> Optional[Path]:
        """
        Checks if chapter_index already exists in story_dir with non-empty content.
        Matches 'Chương {index}...' or 'Chương 00{index}...'.
        """
        if not story_dir.exists():
            return None
        pattern = re.compile(rf"^chương\s*0*{chapter_index}\b", re.IGNORECASE)
        try:
            for f in story_dir.iterdir():
                if f.is_file() and f.suffix.lower() == ".txt":
                    if pattern.match(f.stem) and f.stat().st_size > 50:
                        return f
        except Exception as e:
            logger.warning(f"Error checking existing chapter file {chapter_index}: {e}")
        return None

    @staticmethod
    def read_chapter_from_file(file_path: Path, chapter_index: int) -> Optional[Dict[str, Any]]:
        """Reads title and paragraphs from an existing txt chapter file."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = [line.strip() for line in content.splitlines()]
            non_empty = [l for l in lines if l]
            if not non_empty:
                return None
            title = non_empty[0]
            paragraphs = non_empty[1:]
            return {
                "index": chapter_index,
                "title": title,
                "paragraphs": paragraphs
            }
        except Exception as e:
            logger.warning(f"Error reading chapter file {file_path}: {e}")
            return None

    @staticmethod
    def save_chapter_to_story_dir(
        story_dir: Path,
        chapter: Dict[str, Any],
        overwrite: bool = False
    ) -> Path:
        """
        Saves a single chapter to story_dir. If file exists and not overwrite, leaves it untouched.
        """
        idx = chapter.get("index", 1)
        existing = TxtBuilder.find_existing_chapter_file(story_dir, idx)
        if existing and not overwrite:
            return existing

        ch_title = chapter.get("title") or f"Chương {idx}"
        ch_title = ch_title.strip()
        safe_ch_filename = sanitize_filename(ch_title, max_length=100)
        file_path = story_dir / f"{safe_ch_filename}.txt"

        lines = [ch_title, ""]
        paragraphs = chapter.get("paragraphs", [])
        paragraphs = strip_leading_chapter_titles(paragraphs, title=ch_title, chapter_index=idx)
        for p in paragraphs:
            p_clean = p.strip()
            if p_clean:
                lines.append(p_clean)
                lines.append("")

        chapter_content = "\n".join(lines).strip() + "\n"
        file_path.write_text(chapter_content, encoding="utf-8")
        return file_path

    @staticmethod
    def build(
        novel_info: Dict[str, Any],
        chapters: List[Dict[str, Any]],
        output_dir: Path = DOWNLOAD_DIR
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        title = novel_info.get("title", "Truyen").strip()

        # Determine chapter range for filename
        if chapters:
            first_idx = chapters[0].get("index", 1)
            last_idx = chapters[-1].get("index", first_idx)
            range_suffix = f"(chương {first_idx})" if first_idx == last_idx else f"(chương {first_idx}-{last_idx})"
        else:
            range_suffix = ""

        filename_base = f"{title} {range_suffix}".strip() if range_suffix else title
        safe_title = sanitize_filename(filename_base)
        txt_path = output_dir / f"{safe_title}.txt"

        with open(txt_path, "w", encoding="utf-8") as f:
            for i, ch in enumerate(chapters):
                ch_title = ch.get("title") or f"Chương {ch.get('index', i + 1)}"
                ch_title = ch_title.strip()

                # Separate chapters with blank lines
                if i > 0:
                    f.write("\n\n\n")

                # Chapter title on its own line
                f.write(f"{ch_title}\n\n")

                # Paragraphs of content
                paragraphs = ch.get("paragraphs", [])
                paragraphs = strip_leading_chapter_titles(paragraphs, title=ch_title, chapter_index=ch.get("index", i + 1))
                for p in paragraphs:
                    p_clean = p.strip()
                    if p_clean:
                        f.write(f"{p_clean}\n\n")

        return txt_path

    @staticmethod
    def build_split(
        novel_info: Dict[str, Any],
        chapters: List[Dict[str, Any]],
        output_dir: Path = DOWNLOAD_DIR
    ) -> Path:
        """
        Saves each chapter as an individual clean UTF-8 text file directly into
        downloads/[Tên truyện]/ without overwriting existing files.
        Returns the story directory Path.
        """
        title = novel_info.get("title", "Truyen").strip()
        story_dir = TxtBuilder.get_story_dir(title, output_dir)

        for ch in chapters:
            TxtBuilder.save_chapter_to_story_dir(story_dir, ch, overwrite=False)

        return story_dir
