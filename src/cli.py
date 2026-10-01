import argparse
import asyncio
import sys
from src.scraper.base import BaseScraperSession
from src.scraper.site_parser import SiteParserManager
from src.builders.txt_builder import TxtBuilder
from src.builders.epub_builder import EpubBuilder
from src.core.config import DOWNLOAD_DIR, DEFAULT_CONCURRENCY


async def main_cli():
    parser = argparse.ArgumentParser(description="Web Novel Downloader CLI")
    parser.add_argument("--url", "-u", required=True, help="URL truyện (ví dụ: https://www.truyenyy.co/truyen/...)")
    parser.add_argument("--start", "-s", type=int, default=1, help="Chương bắt đầu (mặc định: 1)")
    parser.add_argument("--end", "-e", type=int, default=99999, help="Chương kết thúc")
    parser.add_argument("--format", "-f", choices=["epub", "txt", "both"], default="epub", help="Định dạng xuất (epub, txt, both)")
    parser.add_argument("--concurrency", "-c", type=int, default=DEFAULT_CONCURRENCY, help="Số luồng tải đồng thời")

    args = parser.parse_args()
    parser_manager = SiteParserManager()

    print(f"[*] Đang phân tích thông tin truyện từ: {args.url}")

    async with BaseScraperSession() as session:
        info = await parser_manager.analyze_novel(session, args.url)
        title = info.get("title", "Không rõ")
        author = info.get("author", "Không rõ")
        all_chapters = info.get("chapters", [])

        print(f"[+] Tên truyện: {title}")
        print(f"[+] Tác giả:    {author}")
        print(f"[+] Trạng thái: {info.get('status', 'Đang ra')}")
        print(f"[+] Tổng số chương tìm thấy: {len(all_chapters)}")

        target_chapters = [
            ch for ch in all_chapters
            if args.start <= ch.get("index", 0) <= args.end
        ]

        if not target_chapters:
            print("[-] Không có chương nào phù hợp trong khoảng lựa chọn.")
            return

        total_to_download = len(target_chapters)
        print(f"[*] Bắt đầu tải {total_to_download} chương (từ {args.start} đến {args.end})...")

        sem = asyncio.Semaphore(args.concurrency)
        completed_chapters = {}
        downloaded = 0

        async def worker(ch):
            nonlocal downloaded
            idx = ch.get("index", 1)
            async with sem:
                await asyncio.sleep(0.15)
                res = await parser_manager.parse_chapter(
                    session=session,
                    chapter_url=ch.get("url"),
                    chapter_index=idx,
                    chapter_title_hint=ch.get("title")
                )
                completed_chapters[idx] = res
                downloaded += 1
                percent = (downloaded / total_to_download) * 100
                sys.stdout.write(f"\r[+] Đang tải: {downloaded}/{total_to_download} ({percent:.1f}%) - {res.get('title')[:35]}...")
                sys.stdout.flush()

        jobs = [worker(ch) for ch in target_chapters]
        await asyncio.gather(*jobs)
        print("\n[*] Đang đóng gói file...")

        ordered_chapters = [completed_chapters[idx] for idx in sorted(completed_chapters.keys())]

        # Download cover if needed
        cover_bytes = None
        if args.format in ["epub", "both"] and info.get("cover"):
            try:
                cover_bytes = await session.get_binary(info.get("cover"))
            except Exception:
                pass

        if args.format in ["txt", "both"]:
            txt_path = TxtBuilder.build(info, ordered_chapters, DOWNLOAD_DIR)
            print(f"[✔] Đã tạo file TXT:  {txt_path}")

        if args.format in ["epub", "both"]:
            epub_path = EpubBuilder.build(info, ordered_chapters, cover_bytes, DOWNLOAD_DIR)
            print(f"[✔] Đã tạo file EPUB: {epub_path}")

        print("[✔] Hoàn thành xuất sắc!")


if __name__ == "__main__":
    asyncio.run(main_cli())
