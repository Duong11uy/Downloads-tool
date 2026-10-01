# Thiết Kế Chi Tiết & Đặc Tả Kỹ Thuật (Design Spec): Web Novel Downloader Server

- **Dự án:** Web Novel Downloader (Công cụ tải truyện chữ tự động trên Linux Server)
- **Ngày tạo:** 30/09/2026
- **Trạng thái:** Bản thảo thiết kế hoàn chỉnh (Spec Draft)
- **Mục tiêu:** Cung cấp dịch vụ self-hosted chạy trên Linux server, có giao diện Web responsive để tải truyện chữ từ các trang web tiếng Việt về định dạng EPUB và TXT.

---

## 1. Tổng Quan & Mục Tiêu (Overview & Goals)

### 1.1. Mục đích
Hệ thống là một ứng dụng Web tự lưu trữ (Self-hosted Web Service) chạy 24/7 trên Linux Server cá nhân (VPS/Home Server). Người dùng chỉ cần mở trình duyệt trên điện thoại hoặc laptop, dán liên kết truyện, chọn định dạng và khoảng chương mong muốn. Server sẽ tự động cào dữ liệu ngầm với tốc độ cao, đóng gói thành file chuẩn và cho phép tải trực tiếp về thiết bị.

### 1.2. Đối tượng & Trải nghiệm người dùng
- **Thiết bị truy cập:** Bất kỳ thiết bị nào có trình duyệt (Smartphone iOS/Android, Máy tính bảng, PC, Laptop).
- **Quy trình sử dụng:**
  1. Người dùng mở `http://<IP-server>:<port>` hoặc tên miền riêng.
  2. Dán link truyện (ví dụ từ TruyenFull, TangThuVien, Metruyenchu, Wikidich,TruyenYY, ...).
  3. Bấm **"Phân tích truyện"**: Hệ thống hiển thị Tên truyện, Tác giả, Ảnh bìa, Trạng thái (Đang ra/Hoàn thành) và Tổng số chương.
  4. Chọn cấu hình tải:
     - Định dạng: `EPUB` (mặc định), `TXT`, hoặc cả hai.
     - Khoảng chương: `Tất cả` hoặc `Từ chương X đến chương Y`.
  5. Bấm **"Bắt đầu tải"**: Xem thanh tiến trình (%) và số chương đang tải theo thời gian thực (Realtime via SSE).
  6. Hoàn tất: Bấm nút **"Tải về máy"** hoặc đọc trực tiếp.

---

## 2. Yêu Cầu & Tính Năng Chi Tiết (Requirements & Features)

### 2.1. Yêu cầu chức năng (Functional Requirements)
1. **Bóc tách đa nguồn (Multi-site Scraping Engine):**
   - Hỗ trợ sẵn các trang truyện phổ biến: TruyenFull, TangThuVien, Metruyenchu, Wikidich, TruyenYY, v.v.
   - Cơ chế **Site Adapter** tách biệt bằng file cấu hình `sites_config.json` (dễ dàng bổ sung/sửa đổi khi website đổi class HTML mà không cần sửa mã nguồn Python).
   - Thuật toán **Smart Fallback Reader**: Tự động nhận diện khối nội dung chính và nút chuyển chương cho các trang web lạ chưa có trong cấu hình.
2. **Lọc sạch nội dung (Noise & Ad Cleaner):**
   - Loại bỏ triệt để các đoạn chèn quảng cáo cá cược, link nhóm mạng xã hội, watermark bản quyền của website cào lậu.
   - Chuẩn hóa thụt lề, ngắt đoạn văn bản tiếng Việt đúng quy chuẩn.
3. **Định dạng xuất (Format Builders):**
   - **EPUB3:**
     - Đầy đủ Cover Image (ảnh bìa), Metadata (Tiêu đề, Tác giả, Mô tả, Nguồn).
     - Mục lục điều hướng (Table of Contents / NCX) phân tầng rõ ràng từng chương.
     - Tương thích 100% với Kindle (qua Send-to-Kindle), Kobo, Apple Books, Moon+ Reader.
   - **TXT:**
     - Mã hóa UTF-8 chuẩn.
     - Header thông tin truyện + Mục lục tóm tắt + Các chương cách nhau bằng vạch phân cách rõ ràng.
4. **Quản lý tác vụ tải ngầm (Background Task & Concurrency):**
   - Tải bất đồng bộ đa luồng (Async Concurrency) với tốc độ cao nhưng có cơ chế điều tiết (Rate Limiting) tránh bị web nguồn phát hiện và khóa IP.
   - Tự động thử lại (Auto-retry với exponential backoff) khi gặp timeout hoặc lỗi mạng.
5. **Giao diện Web (Web UI):**
   - Giao diện tối giản, trực quan, hỗ trợ Dark Mode / Light Mode.
   - Thiết kế tối ưu Mobile-first (dễ thao tác một tay trên điện thoại).
   - Lịch sử các truyện vừa tải gần đây để tải lại hoặc xóa nhanh.

### 2.2. Yêu cầu phi chức năng (Non-Functional Requirements)
- **Tài nguyên thấp:** Tiêu thụ dưới 150MB RAM trên server, không bắt buộc cài đặt cơ sở dữ liệu nặng như PostgreSQL hay Redis.
- **Triển khai đơn giản:** Chạy được ngay thông qua Docker (`docker-compose up -d`) hoặc dịch vụ Linux `systemd`.
- **Bảo mật:** Tùy chọn cấu hình mật khẩu bảo vệ (Basic Auth hoặc Secret Token) để tránh người lạ truy cập vào server của bạn.

---

## 3. Kiến Trúc Kỹ Thuật (Architecture & Tech Stack)

```
[ Browser (Mobile/PC) ]
         │ (HTTP / Server-Sent Events)
         ▼
[ FastAPI Web Server ]
  ├── Static UI (HTML5 + TailwindCSS + Vanilla JS)
  ├── API Router (/api/analyze, /api/download, /api/progress, /api/files)
  └── Task Manager (Asyncio Background Tasks)
         │
         ├── [ Scraper Engine ]
         │     ├── Site Adapters (sites_config.json)
         │     ├── Smart Fallback Heuristic Parser
         │     └── Anti-bot Session (curl_cffi / httpx)
         │
         ├── [ Text Cleaner ] (Loại bỏ watermark, chuẩn hóa văn bản)
         │
         └── [ Format Builder ]
               ├── EPUB Builder (XHTML + OPF + TOC)
               └── TXT Builder
                     │
                     ▼
             [ /app/downloads/ ] (Lưu trữ file tạm thời / xuất tải)
```

### 3.1. Danh mục công nghệ (Tech Stack)
- **Ngôn ngữ:** Python 3.11+
- **Web Framework:** `FastAPI` + `Uvicorn` (Xử lý bất đồng bộ native, tốc độ phản hồi cực nhanh).
- **HTTP Client:** `curl_cffi` (giả lập TLS/JA3 fingerprint của Chrome để vượt Cloudflare) kết hợp `httpx`.
- **HTML Parsing:** `BeautifulSoup4` + `lxml`.
- **Ebook Generation:** `ebooklib` hoặc module nén EPub native chuẩn Open Container Format (OCF).
- **Frontend:** Single Page Application (HTML5, TailwindCSS qua CDN, JavaScript Fetch API + EventSource cho SSE). Không cần Node.js build tool.
- **Containerization:** `Docker` đa nền tảng (x86_64, ARM64 cho Raspberry Pi/Oracle Cloud).

---

## 4. Cấu Trúc Dự Án (Project Structure)

```
novel-downloader/
├── config/
│   └── sites_config.json       # Cấu hình bộ chọn CSS/XPath cho từng trang web
├── src/
│   ├── app.py                  # Điểm khởi chạy FastAPI server
│   ├── core/
│   │   ├── config.py           # Cấu hình chung (Port, Download Dir, Concurrency,...)
│   │   └── task_manager.py     # Quản lý hàng đợi tải & kết nối SSE realtime
│   ├── scraper/
│   │   ├── base.py             # Lớp Scraper cơ sở & session quản lý request
│   │   ├── site_parser.py      # Bóc tách dựa trên sites_config.json
│   │   ├── fallback_parser.py  # Bóc tách thông minh cho web lạ
│   │   └── cleaner.py          # Lọc rác, quảng cáo, watermark
│   ├── builders/
│   │   ├── epub_builder.py     # Sinh file EPUB chuẩn EPub3
│   │   └── txt_builder.py      # Sinh file TXT UTF-8
│   └── static/
│       ├── index.html          # Giao diện chính (Responsive Mobile/Desktop)
│       ├── app.js              # Xử lý tương tác, gọi API, nhận SSE progress
│       └── style.css           # Tùy biến giao diện nếu cần
├── downloads/                  # Thư mục lưu file truyện đã xuất
├── Dockerfile                  # Đóng gói image Docker
├── docker-compose.yml          # Triển khai 1 lệnh
├── install.sh                  # Script cài đặt tự động cho Linux (Ubuntu/Debian)
├── requirements.txt            # Thư viện Python phụ thuộc
└── README.md                   # Hướng dẫn sử dụng & cấu hình
```

---

## 5. Quy Trình Xử Lý Chi Tiết (Data Flow & Execution)

### Bước 1: Phân tích truyện (`POST /api/analyze`)
1. Nhận URL từ người dùng.
2. Kiểm tra domain trong `sites_config.json`:
   - Nếu có: Dùng cấu hình định sẵn để lấy Tên truyện, Tác giả, Ảnh bìa, Danh sách chương.
   - Nếu chưa có: Kích hoạt `fallback_parser.py` để tìm kiếm thông tin theo cấu trúc trang tiêu chuẩn.
3. Trả về JSON cho Web UI: Tên truyện, Tác giả, Link ảnh bìa, Tổng số chương (danh sách chương từ 1 đến N).

### Bước 2: Khởi tạo tiến trình tải (`POST /api/download`)
1. Nhận các tham số: `url`, `start_chapter`, `end_chapter`, `format` (`epub`, `txt`, `both`).
2. Sinh một `task_id` định danh duy nhất (UUID).
3. Đưa tác vụ vào hàng đợi bất đồng bộ (async background worker).
4. Web UI mở kết nối SSE tới `/api/progress/{task_id}` để lắng nghe cập nhật tiến độ.

### Bước 3: Tải nội dung chương & làm sạch (Background Scraper)
1. Tải song song danh sách chương theo batch (mặc định 5-10 requests đồng thời, có delay ngẫu nhiên 0.2s - 0.5s để chống chặn IP).
2. Với mỗi chương:
   - Bóc tách nội dung thô (Raw HTML).
   - Đưa qua `cleaner.py`: Xóa các thẻ script, style, quảng cáo, câu chào watermark.
   - Lưu trữ văn bản sạch vào bộ nhớ tạm của tác vụ.
   - Cập nhật tiến độ (% hoàn thành, chương hiện tại) qua SSE.

### Bước 4: Đóng gói và Xuất file
1. Dựa trên định dạng đã chọn:
   - Tạo file `.txt`: Ghép tiêu đề và toàn bộ các chương theo thứ tự.
   - Tạo file `.epub`: Tạo manifest, tải ảnh bìa làm cover, định dạng từng chương thành file XHTML riêng biệt với CSS chuẩn e-reader, tạo mục lục TOC.
2. Lưu file vào thư mục `/downloads/`.
3. Gửi sự kiện SSE trạng thái `COMPLETED` kèm link tải trực tiếp (`/api/files/{filename}`).
4. Web UI hiển thị thông báo thành công và nút bấm để người dùng tải file về máy.

---

## 6. Kế Hoạch Triển Khai (Implementation Steps)

1. **Giai đoạn 1: Lập trình Bộ lõi Scraper & Bộ lọc (Core Scraper & Cleaner)**
   - Xây dựng lớp client `curl_cffi` chống chặn.
   - Viết file `sites_config.json` hỗ trợ TruyenFull, TangThuVien, Metruyenchu, Wikidich.
   - Xây dựng module làm sạch nội dung `cleaner.py`.
2. **Giai đoạn 2: Lập trình Bộ đóng gói EPUB & TXT (Format Builders)**
   - Tạo file `.txt` có định dạng rõ ràng.
   - Tạo file `.epub` chuẩn OCF/EPub3 có ảnh bìa và mục lục.
3. **Giai đoạn 3: Xây dựng Backend FastAPI & Quản lý Tác vụ**
   - Viết các API endpoint: `/api/analyze`, `/api/download`, `/api/progress/{task_id}`, `/api/files/{filename}`.
   - Quản lý trạng thái tiến trình và stream SSE realtime.
4. **Giai đoạn 4: Thiết kế Giao diện Web Responsive**
   - Xây dựng trang `index.html` với TailwindCSS: input link, card hiển thị thông tin truyện, thanh trượt/chọn khoảng chương, progress bar sinh động.
   - Kết nối JavaScript xử lý sự kiện mượt mà trên mobile.
5. **Giai đoạn 5: Đóng gói Docker & Script Cài đặt Linux**
   - Viết `Dockerfile` tối ưu kích thước image.
   - Viết `docker-compose.yml` cho phép cấu hình port và thư mục mount dễ dàng.
   - Viết `install.sh` tự động cài đặt cho Ubuntu/Debian (chạy qua systemd hoặc Docker).
6. **Giai đoạn 6: Kiểm thử & Nghiệm thu**
   - Thử nghiệm tải thực tế từ các trang truyện với truyện dài từ vài chục đến hàng nghìn chương.
   - Kiểm tra hiển thị file EPUB trên máy đọc sách (Kindle/Kobo) và app điện thoại.
