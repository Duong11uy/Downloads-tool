import asyncio
import json
import logging
import mimetypes
import os
import queue
import re
import shutil
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, unquote, quote

# 1. Ensure project root is always in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import (
    APP_NAME,
    APP_VERSION,
    HOST,
    PORT,
    DOWNLOAD_DIR,
    STATIC_DIR,
    DEFAULT_CONCURRENCY,
    SITES_CONFIG_PATH
)
from src.core.task_manager import TaskManager
from src.scraper.base import BaseScraperSession

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("novel_downloader")

task_manager = TaskManager()

# Check if FastAPI and Uvicorn are available
FASTAPI_AVAILABLE = False
try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError as e:
    logger.warning(f"FastAPI or Uvicorn not installed: {e}. Falling back to Python built-in HTTP server.")


# =====================================================================
# FASTAPI IMPLEMENTATION (When FastAPI + Uvicorn are installed)
# =====================================================================
if FASTAPI_AVAILABLE:
    app = FastAPI(title=APP_NAME, version=APP_VERSION)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class AnalyzeRequest(BaseModel):
        url: str

    class DownloadRequest(BaseModel):
        url: str
        start_chapter: int = 1
        end_chapter: int = 99999
        format: str = "epub"
        concurrency: Optional[int] = DEFAULT_CONCURRENCY

    @app.post("/api/analyze")
    async def analyze_novel(req: AnalyzeRequest):
        url = str(req.url).strip()
        if not url:
            raise HTTPException(status_code=400, detail="Vui lòng cung cấp URL truyện.")
        try:
            async with BaseScraperSession() as session:
                info = await task_manager.parser_manager.analyze_novel(session, url)
                return {"success": True, "data": info}
        except Exception as e:
            logger.exception(f"Analyze failed: {e}")
            raise HTTPException(status_code=500, detail=f"Lỗi phân tích truyện: {str(e)}")

    @app.post("/api/download")
    async def start_download(req: DownloadRequest):
        url = str(req.url).strip()
        if not url:
            raise HTTPException(status_code=400, detail="Vui lòng cung cấp URL truyện.")
        task = task_manager.create_task(
            url=url,
            start_chapter=req.start_chapter,
            end_chapter=req.end_chapter,
            format_type=req.format,
            concurrency=req.concurrency or DEFAULT_CONCURRENCY
        )
        return {"success": True, "task_id": task.task_id}

    @app.get("/api/progress/{task_id}")
    async def stream_progress(task_id: str):
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Không tìm thấy task")

        async def event_generator():
            q = task.add_subscriber()
            initial_data = {
                "task_id": task.task_id,
                "status": task.status,
                "progress": round(task.progress, 1),
                "current_chapter": task.current_chapter,
                "downloaded_count": task.downloaded_count,
                "total_to_download": task.total_to_download,
                "files": task.files,
                "error": task.error
            }
            yield f"data: {json.dumps(initial_data, ensure_ascii=False)}\n\n"
            try:
                while True:
                    try:
                        payload = await asyncio.to_thread(q.get, timeout=15.0)
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        if payload.get("status") in ["completed", "failed", "cancelled"]:
                            break
                    except Exception:
                        yield ": heartbeat\n\n"
            finally:
                task.remove_subscriber(q)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
        )

    @app.get("/api/progress_poll/{task_id}")
    async def poll_progress(task_id: str):
        task = task_manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Không tìm thấy task")
        return {
            "task_id": task.task_id,
            "status": task.status,
            "progress": round(task.progress, 1),
            "current_chapter": task.current_chapter,
            "downloaded_count": task.downloaded_count,
            "total_to_download": task.total_to_download,
            "files": task.files,
            "error": task.error
        }

    @app.get("/api/open_folder")
    async def open_folder(name: str):
        folder_name = unquote(name).strip()
        target = DOWNLOAD_DIR / folder_name
        if target.exists() and target.is_dir():
            try:
                if hasattr(os, "startfile"):
                    os.startfile(str(target.resolve()))
                return {"success": True, "message": "Đã mở thư mục"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        raise HTTPException(status_code=404, detail="Thư mục không tồn tại")

    @app.get("/api/files")
    async def list_files():
        results = []
        if DOWNLOAD_DIR.exists():
            for file in sorted(DOWNLOAD_DIR.iterdir(), key=os.path.getmtime, reverse=True):
                if file.is_file() and file.suffix.lower() in [".epub", ".txt", ".zip"]:
                    stat = file.stat()
                    results.append({
                        "name": file.name,
                        "format": file.suffix.lstrip(".").lower(),
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                        "url": f"/api/files/{file.name}"
                    })
                elif file.is_dir() and not file.name.startswith("."):
                    txt_files = [tf for tf in file.glob("*.txt") if tf.is_file()]
                    if txt_files:
                        total_size = sum(tf.stat().st_size for tf in txt_files)
                        results.append({
                            "name": file.name,
                            "format": "folder",
                            "size": total_size,
                            "count": len(txt_files),
                            "mtime": file.stat().st_mtime,
                            "url": f"/api/open_folder?name={quote(file.name)}"
                        })
        return {"files": results}

    @app.get("/api/files/{filename}")
    async def download_file(filename: str):
        file_path = DOWNLOAD_DIR / filename
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="File không tồn tại")
        if filename.endswith(".epub"):
            media_type = "application/epub+zip"
        elif filename.endswith(".zip"):
            media_type = "application/zip"
        else:
            media_type = "text/plain; charset=utf-8"
        ascii_name = re.sub(r'[^\x20-\x7E]', '_', filename)
        encoded_name = quote(filename)
        headers = {
            "Content-Disposition": f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded_name}'
        }
        return FileResponse(path=file_path, media_type=media_type, headers=headers)

    @app.delete("/api/files/{filename}")
    async def delete_file(filename: str):
        file_path = DOWNLOAD_DIR / filename
        if file_path.exists():
            try:
                if file_path.is_dir():
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()
                return {"success": True, "message": f"Đã xóa {filename}"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Không thể xóa: {e}")
        raise HTTPException(status_code=404, detail="Không tìm thấy file hoặc thư mục")

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            with open(index_file, "r", encoding="utf-8") as f:
                return f.read()
        return "<h1>Web Novel Downloader is running!</h1>"


# =====================================================================
# BUILT-IN HTTP SERVER FALLBACK (Zero external dependencies)
# =====================================================================
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import time

class BuiltinHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Clean logging
        sys.stderr.write(f"[{time.strftime('%H:%M:%S')}] {args[0]} - {args[1]}\n")

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            index_file = STATIC_DIR / "index.html"
            if index_file.exists():
                content = index_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return


        if path.startswith("/static/"):
            rel_path = path[8:]
            target = STATIC_DIR / rel_path
            if target.exists() and target.is_file():
                content = target.read_bytes()
                mime, _ = mimetypes.guess_type(str(target))
                self.send_response(200)
                self.send_header("Content-Type", (mime or "application/octet-stream") + "; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return


        if path == "/api/get_cookie":
            query = parsed.query
            import urllib.parse
            params = urllib.parse.parse_qs(query)
            site = params.get("site", ["xtruyen.vn"])[0]
            cfg = task_manager.parser_manager.find_site_config(site)
            cookie = ""
            if cfg:
                cookie = cfg.get("headers", {}).get("Cookie", "")
            data = json.dumps({"site": site, "cookie": cookie, "has_cookie": bool(cookie)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/api/open_folder":
            query = parsed.query
            import urllib.parse
            params = urllib.parse.parse_qs(query)
            folder_name = params.get("name", [""])[0]
            target = DOWNLOAD_DIR / unquote(folder_name).strip()
            if target.exists() and target.is_dir():
                try:
                    if hasattr(os, "startfile"):
                        os.startfile(str(target.resolve()))
                    data = json.dumps({"success": True, "message": "Đã mở thư mục"}).encode("utf-8")
                except Exception as e:
                    data = json.dumps({"success": False, "detail": str(e)}).encode("utf-8")
            else:
                data = json.dumps({"success": False, "detail": "Thư mục không tồn tại"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path == "/api/files":
            results = []
            if DOWNLOAD_DIR.exists():
                for f in sorted(DOWNLOAD_DIR.iterdir(), key=os.path.getmtime, reverse=True):
                    if f.is_file() and f.suffix.lower() in [".epub", ".txt", ".zip"]:
                        results.append({
                            "name": f.name,
                            "format": f.suffix.lstrip(".").lower(),
                            "size": f.stat().st_size,
                            "url": f"/api/files/{f.name}"
                        })
                    elif f.is_dir() and not f.name.startswith("."):
                        txt_files = [tf for tf in f.glob("*.txt") if tf.is_file()]
                        if txt_files:
                            results.append({
                                "name": f.name,
                                "format": "folder",
                                "size": sum(tf.stat().st_size for tf in txt_files),
                                "count": len(txt_files),
                                "url": f"/api/open_folder?name={quote(f.name)}"
                            })
            data = json.dumps({"files": results}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        if path.startswith("/api/files/"):
            fname = unquote(path[11:])
            target = DOWNLOAD_DIR / fname
            if target.exists() and target.is_file():
                content = target.read_bytes()
                if fname.endswith(".epub"):
                    mime = "application/epub+zip"
                elif fname.endswith(".zip"):
                    mime = "application/zip"
                else:
                    mime = "text/plain; charset=utf-8"
                ascii_name = re.sub(r'[^\x20-\x7E]', '_', fname)
                encoded_name = quote(fname)
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Disposition", f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{encoded_name}')
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        if path.startswith("/api/progress/"):
            task_id = path[14:]
            task = task_manager.get_task(task_id)
            if not task:
                self.send_error(404, "Task not found")
                return

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            q = task.add_subscriber()
            initial_data = {
                "task_id": task.task_id,
                "status": task.status,
                "progress": round(task.progress, 1),
                "current_chapter": task.current_chapter,
                "downloaded_count": task.downloaded_count,
                "total_to_download": task.total_to_download,
                "files": task.files,
                "error": task.error
            }
            self.wfile.write(f"data: {json.dumps(initial_data, ensure_ascii=False)}\n\n".encode("utf-8"))
            self.wfile.flush()

            try:
                while True:
                    try:
                        payload = q.get(timeout=15.0)
                        msg = f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
                        self.wfile.write(msg)
                        self.wfile.flush()
                        if payload.get("status") in ["completed", "failed", "cancelled"]:
                            break
                    except queue.Empty:
                        self.wfile.write(b": heartbeat\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                task.remove_subscriber(q)
            return

        if path.startswith("/api/progress_poll/"):
            task_id = path[19:]
            task = task_manager.get_task(task_id)
            if not task:
                self.send_error(404, "Task not found")
                return
            res_data = {
                "task_id": task.task_id,
                "status": task.status,
                "progress": round(task.progress, 1),
                "current_chapter": task.current_chapter,
                "downloaded_count": task.downloaded_count,
                "total_to_download": task.total_to_download,
                "files": task.files,
                "error": task.error
            }
            body = json.dumps(res_data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            payload = json.loads(body)
        except Exception:
            payload = {}



        if path == "/api/analyze":
            url = payload.get("url", "").strip()
            cookie = payload.get("cookie", "").strip()
            user_agent = payload.get("user_agent", "").strip() or self.headers.get("User-Agent", "")
            if not url:
                self.send_error(400, "URL required")
                return

            try:
                async def _analyze():
                    async with BaseScraperSession(cookie=cookie) as session:
                        return await task_manager.parser_manager.analyze_novel(
                            session, url, cookie=cookie, user_agent=user_agent
                        )

                info = asyncio.run(_analyze())
                res = json.dumps({"success": True, "data": info}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(res)))
                self.end_headers()
                self.wfile.write(res)
            except Exception as e:
                logger.exception(f"Analyze failed: {e}")
                err = json.dumps({"success": False, "detail": str(e)}, ensure_ascii=False).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
            return

        if path == "/api/download":
            try:
                url = payload.get("url", "").strip()
                start_chap = int(payload.get("start_chapter", 1))
                end_chap = int(payload.get("end_chapter", 99999))
                fmt = payload.get("format", "epub")
                cookie = payload.get("cookie", "").strip()
                user_agent = payload.get("user_agent", "").strip() or self.headers.get("User-Agent", "")
                task = task_manager.create_task(
                    url, start_chap, end_chap, fmt,
                    cookie=cookie, user_agent=user_agent
                )

                res = json.dumps({"success": True, "task_id": task.task_id}, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(res)))
                self.end_headers()
                self.wfile.write(res)
            except Exception as e:
                logger.exception(f"Download start failed: {e}")
                err = json.dumps({"success": False, "detail": str(e)}, ensure_ascii=False).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
            return

        if path == "/api/save_cookie":
            try:
                site = payload.get("site", "xtruyen.vn")
                cookie = payload.get("cookie", "").strip()
                user_agent = payload.get("user_agent", "").strip() or self.headers.get("User-Agent", "")
                task_manager.parser_manager.set_site_cookie(site, cookie, user_agent)
                res = json.dumps({"success": True, "message": "Cookie saved successfully"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(res)))
                self.end_headers()
                self.wfile.write(res)
            except Exception as e:
                err = json.dumps({"success": False, "detail": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(err)))
                self.end_headers()
                self.wfile.write(err)
            return

        self.send_error(404, "Not Found")

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/files/"):
            fname = unquote(path[11:])
            target = DOWNLOAD_DIR / fname
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
                res = json.dumps({"success": True}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res)))
                self.end_headers()
                self.wfile.write(res)
                return
        self.send_error(404, "Not Found")


def start_hot_reload_watcher():
    """
    Background daemon thread that monitors all .py, .json, .html, .js, .css files
    under PROJECT_ROOT / src and PROJECT_ROOT / config.
    When a change is detected, it exits with status code 42 so run.bat
    instantly restarts the process.
    """
    import threading
    import time
    from pathlib import Path

    watched_dirs = [PROJECT_ROOT / "src", PROJECT_ROOT / "config"]

    def snapshot():
        times = {}
        for d in watched_dirs:
            if not d.exists():
                continue
            for p in d.rglob("*"):
                if p.is_file() and p.suffix.lower() in [".py", ".json", ".html", ".js", ".css"]:
                    try:
                        times[str(p)] = p.stat().st_mtime
                    except Exception:
                        pass
        return times

    def _watch_loop():
        time.sleep(2.0)
        initial_times = snapshot()
        while True:
            time.sleep(1.0)
            current_times = snapshot()
            changed_file = None
            for p, mtime in current_times.items():
                if p in initial_times and initial_times[p] != mtime:
                    changed_file = Path(p).name
                    break
                elif p not in initial_times:
                    changed_file = Path(p).name
                    break
            if changed_file:
                print(f"\n🔄 [HOT-RELOAD] Phat hien file '{changed_file}' duoc cap nhat. Dang tu dong nap lai may chu...")
                os._exit(42)

    watcher_thread = threading.Thread(target=_watch_loop, daemon=True)
    watcher_thread.start()


def run_builtin_server():
    server = ThreadingHTTPServer((HOST, PORT), BuiltinHandler)
    print("=" * 60)
    print(f"🚀 MÁY CHỦ NOVEL DOWNLOADER ĐANG CHẠY TẠI: http://localhost:{PORT}")
    print(f"👉 Mở trình duyệt web của bạn và truy cập: http://localhost:{PORT}")
    print("🔄 Chế độ Hot-Reload ĐÃ BẬT: Code sửa đổi sẽ tự nạp lại!")
    print("=" * 60)
    print("Nhấn Ctrl+C để dừng máy chủ.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã nhận lệnh dừng. Đang tắt máy chủ...")
    finally:
        server.server_close()


if __name__ == "__main__":
    try:
        # Start file watcher for automatic hot-reload
        start_hot_reload_watcher()

        if FASTAPI_AVAILABLE:
            print("=" * 60)
            print(f"🚀 MÁY CHỦ NOVEL DOWNLOADER (FASTAPI) ĐANG CHẠY: http://localhost:{PORT}")
            print(f"👉 Mở trình duyệt web của bạn và truy cập: http://localhost:{PORT}")
            print("🔄 Chế độ Hot-Reload ĐÃ BẬT: Code sửa đổi sẽ tự nạp lại!")
            print("=" * 60)
            print("Nhấn Ctrl+C để dừng máy chủ.\n")
            uvicorn.run(app, host=HOST, port=PORT, log_level="info")
        else:
            run_builtin_server()
    except Exception as e:
        print(f"\n[LỖI HỆ THỐNG] {e}\n")
        import traceback
        traceback.print_exc()
    finally:
        print("\n[Hoàn tất]")
        try:
            input("Nhấn Enter để đóng cửa sổ...")
        except Exception:
            pass
