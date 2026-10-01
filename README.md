# Web Novel Downloader (Công Cụ Tải Truyện Chữ Tự Động)

Ứng dụng web self-hosted chuyên nghiệp, gọn nhẹ dùng để phân tích và tải truyện chữ từ các trang web (trước mắt tối ưu hóa hoàn chỉnh cho **TruyenYY - truyenyy.co / truyenyy.vip** và cơ chế **Smart Fallback** cho các trang khác), tự động đóng gói thành định dạng sách điện tử chuẩn **EPUB (tương thích 100% Kindle, Kobo, Apple Books)** và **TXT UTF-8**.

---

## 🌟 Tính Năng Nổi Bật

1. **Giao diện Web Hiện Đại & Responsive:**
   - Hỗ trợ đầy đủ màn hình điện thoại di động và máy tính.
   - Chế độ Sáng / Tối (Dark / Light Mode) lưu cấu hình tự động.
   - Hiển thị thanh tiến trình (%) và số chương tải thời gian thực bằng công nghệ **Server-Sent Events (SSE)**.
2. **Site Adapter Tách Biệt (`config/sites_config.json`):**
   - Đã cấu hình hoàn chỉnh các bộ chọn CSS/Regex bóc tách cho **TruyenYY** (`https://www.truyenyy.co/`, `truyenyy.vip`, v.v.).
   - Dễ dàng cập nhật class HTML của trang mà không cần sửa code Python.
3. **Đóng Gói Đa Định Dạng:**
   - **EPUB3 chuẩn OCF:** Tự động nhúng ảnh bìa gốc (Cover Image), mục lục NCX cho Kindle cũ và Nav HTML5 cho e-reader hiện đại, phân chia từng chương với định dạng CSS chuẩn máy đọc sách.
   - **TXT UTF-8:** Đầy đủ phần đầu tóm tắt, mục lục tổng quan và nội dung sạch sẽ.
4. **Bộ Lọc Sạch Rác & Quảng Cáo (`cleaner.py`):**
   - Tự động quét và loại bỏ triệt để quảng cáo cá cược, link nhóm Zalo/Telegram, lời nhắc ủng hộ hoa/kẹo, watermark...
   - Chuẩn hóa Unicode Tiếng Việt chuẩn NFC.
5. **Cơ chế tải ngầm đa luồng (Async Concurrency):**
   - Tải song song với điều tiết tốc độ (Rate Limiting + Jitter) để tránh bị chặn IP.
   - Hỗ trợ cả **Web UI** và **CLI (Dòng lệnh)**.

---

## 🚀 Hướng Dẫn Chạy Trên Local (Windows)

### Cách 1: Chạy nhanh bằng 1 click (Khuyên dùng)
Nhấp đúp chuột vào file:
```
run.bat
```
File `run.bat` sẽ tự động:
- Kiểm tra Python trên máy của bạn.
- Tự tạo môi trường ảo `venv`.
- Tự động cài đặt các thư viện từ `requirements.txt`.
- Khởi chạy Web Server tại địa chỉ: **`http://localhost:8000`**

---

### Cách 2: Chạy thủ công từ Terminal (PowerShell / CMD)

1. Mở PowerShell hoặc CMD trong thư mục dự án:
```powershell
cd "d:\HuySpace\Downloads tool"
```

2. Tạo môi trường ảo và kích hoạt:
```powershell
python -m venv venv
venv\Scripts\activate
```

3. Cài đặt các thư viện phụ thuộc:
```powershell
pip install -r requirements.txt
```

4. Khởi chạy máy chủ Web:
```powershell
python src\app.py
```

5. Mở trình duyệt web và truy cập:
👉 **`http://localhost:8000`**

---

## 💻 Hướng Dẫn Sử Dụng Giao Diện Web

1. Mở `http://localhost:8000`.
2. Dán link truyện muốn tải (ví dụ: `https://www.truyenyy.co/truyen/doc-quyen-dich-vo-han-quay-nguoc-thoi-gian-cac-ha-ung-doi-ra-sao`).
   *(Bạn cũng có thể bấm nút **"Dán link mẫu TruyenYY"** để thử nghiệm ngay)*.
3. Bấm **"Phân tích truyện"**: Hệ thống sẽ hiển thị ảnh bìa, tên truyện, tác giả, trạng thái và tổng số chương.
4. Chọn định dạng tải: **EPUB**, **TXT** hoặc **Cả hai**.
5. Chọn khoảng chương muốn tải:
   - Tất cả các chương.
   - Hoặc gõ số chương (ví dụ từ chương 1 đến chương 50).
6. Bấm **"Bắt đầu tải truyện về máy"**: Xem tiến độ tải và đóng gói theo thời gian thực.
7. Khi hoàn tất, bấm nút tải trực tiếp file về máy tính hoặc điện thoại của bạn.

---

## ⌨️ Sử Dụng Bằng Dòng Lệnh (CLI)

Nếu bạn muốn tải trực tiếp từ terminal mà không cần mở trình duyệt:

```powershell
# Kích hoạt venv trước
venv\Scripts\activate

# Tải 50 chương đầu dạng EPUB
python -m src.cli --url "https://www.truyenyy.co/truyen/doc-quyen-dich-vo-han-quay-nguoc-thoi-gian-cac-ha-ung-doi-ra-sao" --start 1 --end 50 --format epub

# Tải tất cả chương dạng cả TXT và EPUB
python -m src.cli --url "https://www.truyenyy.co/truyen/..." --format both
```

Các tham số hỗ trợ:
- `--url`, `-u`: Đường dẫn truyện (bắt buộc).
- `--start`, `-s`: Chương bắt đầu (mặc định: 1).
- `--end`, `-e`: Chương kết thúc (mặc định: tải đến hết).
- `--format`, `-f`: Định dạng xuất: `epub`, `txt`, hoặc `both` (mặc định: `epub`).
- `--concurrency`, `-c`: Số luồng tải song song (mặc định: 5).

---

## 🐳 Triển Khai Bằng Docker (Tuỳ chọn)

Nếu bạn muốn chạy trên máy chủ Linux / Docker:

```bash
docker-compose up -d
```
Truy cập qua: `http://<ip-cua-ban>:8000`. Thư mục truyện tải về được lưu đồng bộ tại `./downloads`.

---

## 📁 Cấu Trúc Dự Án

```
novel-downloader/
├── config/
│   └── sites_config.json       # Cấu hình bộ chọn CSS/Regex cho TruyenYY & các trang khác
├── src/
│   ├── app.py                  # Điểm khởi chạy FastAPI Web Server
│   ├── cli.py                  # Tool dòng lệnh tải truyện qua terminal
│   ├── core/
│   │   ├── config.py           # Cấu hình hệ thống (Port, Thư mục downloads, Concurrency...)
│   │   └── task_manager.py     # Quản lý tiến trình tải ngầm & kết nối SSE realtime
│   ├── scraper/
│   │   ├── base.py             # HTTP client hỗ trợ anti-bot (curl_cffi / httpx)
│   │   ├── site_parser.py      # Bóc tách HTML dựa trên sites_config.json
│   │   ├── fallback_parser.py  # Thuật toán thông minh nhận diện web lạ
│   │   └── cleaner.py          # Lọc quảng cáo, từ khóa cá cược, chuẩn hóa tiếng Việt
│   ├── builders/
│   │   ├── epub_builder.py     # Sinh file EPUB chuẩn EPub3/OCF kèm ảnh bìa & mục lục
│   │   └── txt_builder.py      # Sinh file TXT định dạng chuẩn UTF-8
│   └── static/
│       ├── index.html          # Giao diện Web SPA responsive (TailwindCSS)
│       ├── app.js              # JavaScript điều khiển, xử lý API & SSE stream
│       └── style.css           # Hiệu ứng động thanh tiến trình
├── downloads/                  # Thư mục chứa các file truyện đã tải xong
├── Dockerfile                  # Đóng gói Docker container
├── docker-compose.yml          # Chạy Docker 1 lệnh
├── run.bat                     # File chạy 1-click cho Windows
├── run.sh                      # File chạy cho Linux / macOS
├── requirements.txt            # Danh sách thư viện Python
└── README.md                   # Hướng dẫn chi tiết
```

---

## ⚙️ Tùy Biến Cấu Hình TruyenYY (`config/sites_config.json`)

Trong file `config/sites_config.json`, cấu hình cho TruyenYY được định nghĩa chi tiết:
- **`domains`**: Danh sách domain hợp lệ (`truyenyy.co`, `truyenyy.vip`, v.v.).
- **`selectors`**:
  - `title`: `h1.font-title`
  - `author`: `div.pt-2 p.font-title`
  - `cover`: `meta[property='og:image']`
  - `description`: `div.prose`
  - `chapter_list_page_url`: `{novel_url}/danh-sach-chuong?p={page}`
  - `chapter_items`: `ul.divide-y li a`
  - `chapter_content`: `article`
  - `chapter_paragraphs`: `article p`
