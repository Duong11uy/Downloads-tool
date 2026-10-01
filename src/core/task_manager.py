import asyncio
import json
import logging
import math
import queue
import random
import threading
import uuid
from typing import Dict, Any, List, Optional
from urllib.parse import quote
from src.core.config import DEFAULT_CONCURRENCY, DOWNLOAD_DIR
from src.scraper.base import BaseScraperSession
from src.scraper.site_parser import SiteParserManager, normalize_novel_url
from src.builders.txt_builder import TxtBuilder
from src.builders.epub_builder import EpubBuilder

logger = logging.getLogger("core.task_manager")


class DownloadTask:
    def __init__(self, task_id: str, url: str, start_chapter: int, end_chapter: int, format_type: str, concurrency: int = DEFAULT_CONCURRENCY, cookie: str = "", user_agent: str = ""):
        self.task_id = task_id
        self.url = url
        self.start_chapter = start_chapter
        self.end_chapter = end_chapter
        self.format_type = format_type.lower()  # epub, txt, both
        self.concurrency = concurrency
        self.cookie = cookie
        self.user_agent = user_agent
        
        self.status = "pending"  # pending, analyzing, downloading, building, completed, failed, cancelled
        self.progress = 0.0
        self.current_chapter = ""
        self.downloaded_count = 0
        self.total_to_download = 0
        self.novel_info: Dict[str, Any] = {}
        self.files: List[Dict[str, str]] = []
        self.error: Optional[str] = None
        
        self.event_subscribers: List[queue.Queue] = []
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True
        self.status = "cancelled"
        self.emit_event()

    def add_subscriber(self) -> queue.Queue:
        q = queue.Queue()
        self.event_subscribers.append(q)
        return q

    def remove_subscriber(self, q: queue.Queue):
        if q in self.event_subscribers:
            self.event_subscribers.remove(q)

    def emit_event(self):
        payload = {
            "task_id": self.task_id,
            "status": self.status,
            "progress": round(self.progress, 1),
            "current_chapter": self.current_chapter,
            "downloaded_count": self.downloaded_count,
            "total_to_download": self.total_to_download,
            "files": self.files,
            "error": self.error
        }
        for q in list(self.event_subscribers):
            try:
                q.put_nowait(payload)
            except Exception:
                pass


class TaskManager:
    def __init__(self):
        self.tasks: Dict[str, DownloadTask] = {}
        self.parser_manager = SiteParserManager()

    def create_task(self, url: str, start_chapter: int, end_chapter: int, format_type: str = "epub", concurrency: int = DEFAULT_CONCURRENCY, cookie: str = "", user_agent: str = "") -> DownloadTask:
        task_id = str(uuid.uuid4())
        task = DownloadTask(task_id, url, start_chapter, end_chapter, format_type, concurrency, cookie, user_agent)
        self.tasks[task_id] = task

        # Run background worker in a dedicated thread
        def _thread_worker():
            asyncio.run(self._run_task(task))

        thread = threading.Thread(target=_thread_worker, daemon=True)
        thread.start()
        return task

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        return self.tasks.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        return [
            {
                "task_id": t.task_id,
                "url": t.url,
                "novel_title": t.novel_info.get("title", "Đang phân tích..."),
                "status": t.status,
                "progress": t.progress,
                "files": t.files,
                "error": t.error
            }
            for t in reversed(list(self.tasks.values()))
        ]

    async def _run_task(self, task: DownloadTask):
        try:
            task.status = "analyzing"
            task.current_chapter = "Đang kết nối và phân tích truyện..."
            task.emit_event()

            async with BaseScraperSession(cookie=task.cookie) as session:
                clean_url = normalize_novel_url(task.url)
                site_cfg = self.parser_manager.find_site_config(clean_url)

                # 1. Fast metadata analysis (only 1 page to get title, author, cover, and total chapters)
                novel_info = await self.parser_manager.analyze_novel(session, clean_url, max_pages_to_fetch=1)
                task.novel_info = novel_info

                total_chapters = novel_info.get("total_chapters", 0)
                page_size = 100
                if site_cfg:
                    page_size = site_cfg.get("pagination", {}).get("page_size", 100)

                # Calculate which pages contain the requested chapters
                start_p = max(1, (task.start_chapter - 1) // page_size + 1)
                end_p = max(start_p, (task.end_chapter - 1) // page_size + 1)
                if total_chapters > 0:
                    max_possible_page = max(1, math.ceil(total_chapters / page_size))
                    end_p = min(end_p, max_possible_page)

                task.current_chapter = f"Đang lấy danh mục chương {task.start_chapter} đến {task.end_chapter}..."
                task.emit_event()

                if site_cfg:
                    target_page_chapters, _ = await self.parser_manager.fetch_chapter_list(
                        session=session,
                        novel_url=clean_url,
                        site_cfg=site_cfg,
                        expected_total=total_chapters,
                        start_page=start_p,
                        end_page=end_p,
                        target_start_chap=task.start_chapter,
                        target_end_chap=task.end_chapter
                    )
                else:
                    target_page_chapters = novel_info.get("chapters", [])

                # Filter target chapters and deduplicate by index
                seen_idx = {}
                for ch in target_page_chapters:
                    idx = ch.get("index", 0)
                    if task.start_chapter <= idx <= task.end_chapter:
                        if idx not in seen_idx:
                            seen_idx[idx] = ch
                        elif len(ch.get("title", "")) > len(seen_idx[idx].get("title", "")):
                            seen_idx[idx] = ch

                target_chapters = [seen_idx[idx] for idx in sorted(seen_idx.keys())]

                if not target_chapters:
                    raise Exception(
                        f"Không tìm thấy chương nào trong khoảng từ {task.start_chapter} đến {task.end_chapter}. "
                        f"(Tổng số chương phát hiện: {total_chapters})"
                    )

                task.total_to_download = len(target_chapters)
                task.status = "downloading"
                task.current_chapter = f"Bắt đầu tải {task.total_to_download} chương..."
                task.emit_event()

                # Semaphore for concurrency control - respect site rate limits
                site_rate = site_cfg.get("rate_limit", {}) if site_cfg else {}
                site_max_c = site_rate.get("max_concurrent", 5)
                effective_c = max(1, min(task.concurrency, site_max_c))
                sem = asyncio.Semaphore(effective_c)
                min_delay = site_rate.get("min_delay", 0.15)
                max_delay = site_rate.get("max_delay", 0.35)
                story_title = novel_info.get("title", "Truyen").strip()
                story_dir = TxtBuilder.get_story_dir(story_title, DOWNLOAD_DIR)
                completed_chapters_dict = {}

                # 1. Check existing chapters on local disk to skip downloading and avoid overwriting
                need_download_chapters = []
                for ch in target_chapters:
                    idx = ch.get("index", 1)
                    existing_file = TxtBuilder.find_existing_chapter_file(story_dir, idx)
                    if existing_file:
                        cached_ch = TxtBuilder.read_chapter_from_file(existing_file, idx)
                        if cached_ch and cached_ch.get("paragraphs"):
                            completed_chapters_dict[idx] = cached_ch
                            task.downloaded_count += 1
                            continue
                    need_download_chapters.append(ch)

                if completed_chapters_dict:
                    logger.info(f"Đã phát hiện và nạp sẵn {len(completed_chapters_dict)}/{task.total_to_download} chương từ thư mục '{story_dir.name}' (không cần cào lại).")
                    task.progress = (task.downloaded_count / task.total_to_download) * 90.0
                    task.current_chapter = f"Đã có sẵn {len(completed_chapters_dict)}/{task.total_to_download} chương trong thư mục"
                    task.emit_event()

                async def download_single_chapter(ch_item):
                    if task._cancel_requested:
                        return
                    async with sem:
                        # Jitter delay to respect rate limit
                        await asyncio.sleep(random.uniform(min_delay, max_delay))
                        idx = ch_item.get("index", 1)
                        ch_url = ch_item.get("url", "")
                        ch_title_hint = ch_item.get("title", "")

                        try:
                            parsed_ch = await self.parser_manager.parse_chapter(
                                session=session,
                                chapter_url=ch_url,
                                chapter_index=idx,
                                chapter_title_hint=ch_title_hint,
                                cookie=task.cookie,
                                user_agent=task.user_agent
                            )
                            # Save chapter directly to story folder (does not overwrite if present)
                            TxtBuilder.save_chapter_to_story_dir(story_dir, parsed_ch, overwrite=False)
                        except Exception as ce:
                            logger.warning(f"Error parsing chapter {idx} ({ch_url}): {ce}")
                            parsed_ch = {
                                "index": idx,
                                "title": ch_title_hint or f"Chương {idx}",
                                "paragraphs": [f"[Lỗi khi tải nội dung chương từ nguồn: {ce}]"]
                            }

                        completed_chapters_dict[idx] = parsed_ch
                        
                        task.downloaded_count += 1
                        task.progress = (task.downloaded_count / task.total_to_download) * 90.0  # 0 to 90%
                        task.current_chapter = parsed_ch.get("title", f"Chương {idx}")
                        task.emit_event()

                # Run downloads concurrently only for chapters that need fetching
                if need_download_chapters:
                    download_jobs = [download_single_chapter(ch) for ch in need_download_chapters]
                    await asyncio.gather(*download_jobs, return_exceptions=False)

                if task._cancel_requested:
                    return

                # Automatic Repair Pass for any chapters that failed due to transient network drops
                def is_failed_chapter(ch):
                    paras = ch.get("paragraphs", [])
                    return not paras or (len(paras) == 1 and paras[0].startswith("[Lỗi khi tải nội dung chương"))

                for repair_round in range(1, 3):
                    failed_items = [
                        ch for ch in target_chapters
                        if is_failed_chapter(completed_chapters_dict.get(ch.get("index", 0), {}))
                    ]
                    if not failed_items or task._cancel_requested:
                        break

                    logger.info(f"Phát hiện {len(failed_items)} chương bị gián đoạn mạng. Bắt đầu tải bù vòng {repair_round}...")
                    task.current_chapter = f"Đang tải bù {len(failed_items)} chương bị gián đoạn mạng..."
                    task.emit_event()

                    # Pause to allow Cloudflare/server rate limiting window to clear
                    await asyncio.sleep(2.5)

                    for f_item in failed_items:
                        if task._cancel_requested:
                            break
                        f_idx = f_item.get("index", 1)
                        f_url = f_item.get("url", "")
                        f_hint = f_item.get("title", "")
                        try:
                            re_parsed = await self.parser_manager.parse_chapter(
                                session=session,
                                chapter_url=f_url,
                                chapter_index=f_idx,
                                chapter_title_hint=f_hint,
                                cookie=task.cookie,
                                user_agent=task.user_agent
                            )
                            if not is_failed_chapter(re_parsed):
                                completed_chapters_dict[f_idx] = re_parsed
                                TxtBuilder.save_chapter_to_story_dir(story_dir, re_parsed, overwrite=True)
                                logger.info(f"Đã tải bù thành công chương {f_idx}: {f_hint}")
                        except Exception as re_err:
                            logger.warning(f"Tải bù thất bại chương {f_idx} (vòng {repair_round}): {re_err}")
                        await asyncio.sleep(0.5)

                # Sort downloaded chapters by index
                ordered_chapters = [
                    completed_chapters_dict[idx]
                    for idx in sorted(completed_chapters_dict.keys())
                ]

                # 2. Building formats
                task.status = "building"
                task.current_chapter = "Đang đóng gói file sách..."
                task.progress = 92.0
                task.emit_event()

                # Download cover image if available
                cover_bytes = None
                cover_url = novel_info.get("cover")
                if cover_url:
                    try:
                        cover_bytes = await session.get_binary(cover_url)
                    except Exception as e:
                        logger.warning(f"Could not download cover image: {e}")

                # Build formats
                generated_files = []
                fmt = task.format_type

                if fmt in ["txt", "both"]:
                    txt_path = TxtBuilder.build(novel_info, ordered_chapters, DOWNLOAD_DIR)
                    generated_files.append({
                        "name": txt_path.name,
                        "format": "txt",
                        "size": txt_path.stat().st_size,
                        "url": f"/api/files/{txt_path.name}"
                    })

                if fmt in ["txt_split", "split"]:
                    story_dir = TxtBuilder.build_split(novel_info, ordered_chapters, DOWNLOAD_DIR)
                    txt_files = [f for f in story_dir.glob("*.txt") if f.is_file()]
                    total_bytes = sum(f.stat().st_size for f in txt_files)
                    generated_files.append({
                        "name": story_dir.name,
                        "format": "folder",
                        "size": total_bytes,
                        "count": len(txt_files),
                        "url": f"/api/open_folder?name={quote(story_dir.name)}"
                    })

                if fmt in ["epub", "both"]:
                    epub_path = EpubBuilder.build(novel_info, ordered_chapters, cover_bytes, DOWNLOAD_DIR)
                    generated_files.append({
                        "name": epub_path.name,
                        "format": "epub",
                        "size": epub_path.stat().st_size,
                        "url": f"/api/files/{epub_path.name}"
                    })

                task.files = generated_files
                task.status = "completed"
                task.progress = 100.0
                task.current_chapter = "Hoàn tất tải về!"
                task.emit_event()

        except Exception as e:
            logger.exception(f"Task {task.task_id} failed: {e}")
            task.status = "failed"
            task.error = str(e)
            task.emit_event()
