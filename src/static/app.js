document.addEventListener('DOMContentLoaded', () => {
    // Theme Management
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    const isDark = localStorage.getItem('theme') === 'dark' || 
                   (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
    
    if (isDark) {
        document.documentElement.classList.add('dark');
    }

    themeToggleBtn.addEventListener('click', () => {
        document.documentElement.classList.toggle('dark');
        const currentDark = document.documentElement.classList.contains('dark');
        localStorage.setItem('theme', currentDark ? 'dark' : 'light');
    });

    // Elements
    const novelUrlInput = document.getElementById('novelUrlInput');
    const analyzeBtn = document.getElementById('analyzeBtn');
    const sampleUrlBtn = document.getElementById('sampleUrlBtn');
    const analyzeLoader = document.getElementById('analyzeLoader');

    const novelCard = document.getElementById('novelCard');
    const novelCover = document.getElementById('novelCover');
    const novelTitle = document.getElementById('novelTitle');
    const novelAuthor = document.getElementById('novelAuthor');
    const novelDesc = document.getElementById('novelDesc');
    const toggleDescBtn = document.getElementById('toggleDescBtn');
    const siteBadge = document.getElementById('siteBadge');
    const statusBadge = document.getElementById('statusBadge');
    const chapterCountBadge = document.getElementById('chapterCountBadge');

    const startChapterInput = document.getElementById('startChapterInput');
    const endChapterInput = document.getElementById('endChapterInput');
    const btnSelectAll = document.getElementById('btnSelectAll');
    const btnFirst50 = document.getElementById('btnFirst50');
    const btnFirst100 = document.getElementById('btnFirst100');
    const startDownloadBtn = document.getElementById('startDownloadBtn');

    const progressCard = document.getElementById('progressCard');
    const progressStatusLabel = document.getElementById('progressStatusLabel');
    const progressPercent = document.getElementById('progressPercent');
    const progressBarFill = document.getElementById('progressBarFill');
    const currentChapterLabel = document.getElementById('currentChapterLabel');
    const downloadCounter = document.getElementById('downloadCounter');
    const completedFilesArea = document.getElementById('completedFilesArea');
    const downloadButtonsList = document.getElementById('downloadButtonsList');

    const filesList = document.getElementById('filesList');
    const refreshFilesBtn = document.getElementById('refreshFilesBtn');

    // Cloudflare Cookie Modal Elements
    const cookieSettingsBtn = document.getElementById('cookieSettingsBtn');
    const cookieModal = document.getElementById('cookieModal');
    const closeCookieModalBtn = document.getElementById('closeCookieModalBtn');
    const cancelCookieModalBtn = document.getElementById('cancelCookieModalBtn');
    const saveCookieBtn = document.getElementById('saveCookieBtn');
    const clearCookieBtn = document.getElementById('clearCookieBtn');
    const cookieInput = document.getElementById('cookieInput');
    const cookieActiveDot = document.getElementById('cookieActiveDot');
    const cookieStatusText = document.getElementById('cookieStatusText');
    const sampleXtruyenBtn = document.getElementById('sampleXtruyenBtn');

    // Check saved cookie state
    async function checkSavedCookie() {
        const localCookie = localStorage.getItem('cf_cookie') || '';
        try {
            const res = await fetch('/api/get_cookie?site=xtruyen.vn');
            const data = await res.json();
            if (data.has_cookie || localCookie) {
                cookieActiveDot?.classList.remove('hidden');
                if (cookieInput && (localCookie || data.cookie)) {
                    cookieInput.value = localCookie || data.cookie;
                }
            } else {
                cookieActiveDot?.classList.add('hidden');
            }
        } catch {
            if (localCookie) {
                cookieActiveDot?.classList.remove('hidden');
                if (cookieInput) cookieInput.value = localCookie;
            }
        }
    }
    checkSavedCookie();

    cookieSettingsBtn?.addEventListener('click', () => {
        cookieModal?.classList.remove('hidden');
        cookieInput?.focus();
    });

    const closeCookieModal = () => cookieModal?.classList.add('hidden');
    closeCookieModalBtn?.addEventListener('click', closeCookieModal);
    cancelCookieModalBtn?.addEventListener('click', closeCookieModal);
    cookieModal?.addEventListener('click', (e) => {
        if (e.target === cookieModal) closeCookieModal();
    });

    saveCookieBtn?.addEventListener('click', async () => {
        const val = cookieInput?.value.trim() || '';
        if (!val) {
            alert('Vui lòng dán chuỗi cookie hoặc mã cf_clearance từ trình duyệt.');
            return;
        }
        localStorage.setItem('cf_cookie', val);
        try {
            const res = await fetch('/api/save_cookie', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    site: 'xtruyen.vn',
                    cookie: val,
                    user_agent: navigator.userAgent
                })
            });
            const data = await res.json();
            if (data.success) {
                cookieActiveDot?.classList.remove('hidden');
                alert('Đã lưu Cookie thành công! Bây giờ bạn có thể phân tích và tải truyện bình thường.');
                closeCookieModal();
            } else {
                throw new Error(data.detail || 'Lỗi lưu cookie');
            }
        } catch (e) {
            alert('Lỗi lưu cookie: ' + e.message);
        }
    });

    clearCookieBtn?.addEventListener('click', async () => {
        localStorage.removeItem('cf_cookie');
        if (cookieInput) cookieInput.value = '';
        cookieActiveDot?.classList.add('hidden');
        try {
            await fetch('/api/save_cookie', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ site: 'xtruyen.vn', cookie: '', user_agent: '' })
            });
        } catch {}
        alert('Đã xóa Cookie đã lưu.');
    });

    sampleXtruyenBtn?.addEventListener('click', () => {
        novelUrlInput.value = 'https://xtruyen.vn/truyen/huyen-giam-tien-toc/';
        analyzeBtn.click();
    });

    let currentNovelData = null;
    let activeEventSource = null;

    // Sample URL button
    sampleUrlBtn.addEventListener('click', () => {
        novelUrlInput.value = 'https://www.truyenyy.co/truyen/doc-quyen-dich-vo-han-quay-nguoc-thoi-gian-cac-ha-ung-doi-ra-sao';
        analyzeBtn.click();
    });

    // Description toggle
    let descExpanded = false;
    toggleDescBtn.addEventListener('click', () => {
        descExpanded = !descExpanded;
        if (descExpanded) {
            novelDesc.classList.remove('line-clamp-3');
            toggleDescBtn.textContent = 'Thu gọn';
        } else {
            novelDesc.classList.add('line-clamp-3');
            toggleDescBtn.textContent = 'Xem thêm nội dung giới thiệu';
        }
    });

    // Range quick selection buttons
    btnSelectAll.addEventListener('click', () => {
        if (!currentNovelData) return;
        startChapterInput.value = 1;
        endChapterInput.value = currentNovelData.total_chapters || currentNovelData.chapters.length || 100;
    });

    btnFirst50.addEventListener('click', () => {
        if (!currentNovelData) return;
        startChapterInput.value = 1;
        endChapterInput.value = Math.min(50, currentNovelData.total_chapters || 50);
    });

    btnFirst100.addEventListener('click', () => {
        if (!currentNovelData) return;
        startChapterInput.value = 1;
        endChapterInput.value = Math.min(100, currentNovelData.total_chapters || 100);
    });

    // Analyze Action
    analyzeBtn.addEventListener('click', async () => {
        const url = novelUrlInput.value.trim();
        if (!url) {
            alert('Vui lòng nhập đường dẫn URL truyện.');
            return;
        }

        analyzeBtn.disabled = true;
        analyzeLoader.classList.remove('hidden');
        novelCard.classList.add('hidden');
        progressCard.classList.add('hidden');

        try {
            const savedCookie = localStorage.getItem('cf_cookie') || '';
            const resp = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url,
                    cookie: savedCookie,
                    user_agent: navigator.userAgent
                })
            });

            const data = await resp.json();
            if (!resp.ok || !data.success) {
                throw new Error(data.detail || 'Không thể phân tích liên kết truyện');
            }

            const info = data.data;
            currentNovelData = info;

            // Auto-update input with normalized novel URL if available
            if (info.novel_url) {
                novelUrlInput.value = info.novel_url;
            }

            const total = info.total_chapters || (info.chapters ? info.chapters.length : 0);

            // Populate UI
            novelTitle.textContent = info.title || 'Không có tiêu đề';
            novelAuthor.textContent = info.author || 'Không rõ';
            novelCover.src = info.cover || 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="150" height="200"><rect width="100%" height="100%" fill="%23ddd"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23666">No Cover</text></svg>';
            novelDesc.textContent = info.description || 'Chưa có thông tin giới thiệu.';
            
            siteBadge.textContent = info.site_name || 'TruyenYY';
            statusBadge.textContent = info.status || 'Đang ra';
            chapterCountBadge.textContent = `${total} chương`;

            startChapterInput.value = 1;
            // Default select first 100 or all if less
            endChapterInput.value = total > 0 ? Math.min(100, total) : 100;

            novelCard.classList.remove('hidden');
            novelCard.scrollIntoView({ behavior: 'smooth' });

        } catch (err) {
            const msg = err.message || '';
            if (msg.includes('403') || msg.includes('Forbidden') || msg.includes('Cloudflare')) {
                const openModal = confirm(
                    'Trang web đang kích hoạt tường lửa Cloudflare (Lỗi 403 Forbidden).\n\n' +
                    'Bạn có muốn mở bảng "Vượt Cloudflare" để dán mã Cookie từ trình duyệt vào không? (Chỉ mất 15 giây)'
                );
                if (openModal) {
                    cookieModal?.classList.remove('hidden');
                    cookieInput?.focus();
                }
            } else {
                alert('Lỗi: ' + msg);
            }
        } finally {
            analyzeBtn.disabled = false;
            analyzeLoader.classList.add('hidden');
        }
    });

    // Start Download Action
    startDownloadBtn.addEventListener('click', async () => {
        if (!currentNovelData) return;

        const totalChapters = currentNovelData.total_chapters || (currentNovelData.chapters ? currentNovelData.chapters.length : 0);
        if (totalChapters === 0) {
            alert('Không tìm thấy chương nào trong truyện này. Vui lòng kiểm tra lại liên kết truyện!');
            return;
        }

        const url = novelUrlInput.value.trim();
        const startChap = parseInt(startChapterInput.value) || 1;
        const endChap = parseInt(endChapterInput.value) || 100;
        const formatOption = document.querySelector('input[name="formatOption"]:checked').value;

        if (startChap > endChap) {
            alert('Chương bắt đầu không được lớn hơn chương kết thúc.');
            return;
        }

        startDownloadBtn.disabled = true;
        progressCard.classList.remove('hidden');
        completedFilesArea.classList.add('hidden');
        downloadButtonsList.innerHTML = '';
        progressBarFill.style.width = '0%';
        progressPercent.textContent = '0%';
        progressStatusLabel.textContent = 'Đang khởi tạo tác vụ...';
        currentChapterLabel.textContent = 'Chờ lượt xử lý...';

        progressCard.scrollIntoView({ behavior: 'smooth' });

        try {
            const savedCookie = localStorage.getItem('cf_cookie') || '';
            const resp = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: url,
                    start_chapter: startChap,
                    end_chapter: endChap,
                    format: formatOption,
                    cookie: savedCookie,
                    user_agent: navigator.userAgent
                })
            });

            const data = await resp.json();
            if (!resp.ok || !data.success) {
                throw new Error(data.detail || 'Không thể tạo tác vụ tải');
            }

            const taskId = data.task_id;
            listenProgress(taskId);

        } catch (err) {
            alert('Lỗi: ' + err.message);
            startDownloadBtn.disabled = false;
        }
    });

    // Realtime Progress Listener (Dual Mode: SSE + Periodic Polling fallback)
    function listenProgress(taskId) {
        if (activeEventSource) {
            activeEventSource.close();
            activeEventSource = null;
        }

        let pollInterval = null;

        function updateUI(data) {
            if (!data) return;
            const progress = data.progress || 0;
            
            progressBarFill.style.width = `${progress}%`;
            progressPercent.textContent = `${Math.round(progress)}%`;

            if (data.status === 'analyzing' || data.status === 'pending') {
                progressStatusLabel.textContent = 'Đang chuẩn bị tải...';
                currentChapterLabel.textContent = data.current_chapter || 'Đang kết nối danh sách chương...';
                downloadCounter.textContent = `${data.downloaded_count || 0} / ${data.total_to_download || 0}`;
            } else if (data.status === 'downloading') {
                progressStatusLabel.textContent = 'Đang tải nội dung các chương...';
                currentChapterLabel.textContent = `Chương đang tải: ${data.current_chapter || ''}`;
                downloadCounter.textContent = `${data.downloaded_count} / ${data.total_to_download}`;
            } else if (data.status === 'building') {
                progressStatusLabel.textContent = 'Đang đóng gói file sách...';
                currentChapterLabel.textContent = data.current_chapter || 'Đang tạo EPUB/TXT...';
            } else if (data.status === 'completed') {
                progressBarFill.style.width = '100%';
                progressPercent.textContent = '100%';
                progressStatusLabel.textContent = 'Hoàn tất tải về!';
                currentChapterLabel.textContent = 'Sách đã được đóng gói thành công.';
                
                showCompletedFiles(data.files || []);
                stopListening();
                startDownloadBtn.disabled = false;
                loadRecentFiles();
            } else if (data.status === 'failed') {
                progressStatusLabel.textContent = 'Quá trình tải thất bại!';
                currentChapterLabel.textContent = data.error || 'Đã xảy ra sự cố trong quá trình cào dữ liệu.';
                stopListening();
                startDownloadBtn.disabled = false;
            }
        }

        function stopListening() {
            if (activeEventSource) {
                activeEventSource.close();
                activeEventSource = null;
            }
            if (pollInterval) {
                clearInterval(pollInterval);
                pollInterval = null;
            }
        }

        // 1. SSE Connection
        try {
            activeEventSource = new EventSource(`/api/progress/${taskId}`);
            activeEventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    updateUI(data);
                } catch (e) {
                    console.error('Error parsing SSE event:', e);
                }
            };
            activeEventSource.onerror = (err) => {
                console.warn('SSE disconnected, falling back to polling:', err);
            };
        } catch (e) {
            console.warn('SSE failed to init:', e);
        }

        // 2. Polling Fallback (runs every 1s to guarantee UI never freezes)
        pollInterval = setInterval(async () => {
            try {
                const resp = await fetch(`/api/progress_poll/${taskId}`);
                if (resp.ok) {
                    const data = await resp.json();
                    updateUI(data);
                }
            } catch (e) {
                // Ignore poll network errors
            }
        }, 1000);
    }

    function showCompletedFiles(files) {
        completedFilesArea.classList.remove('hidden');
        downloadButtonsList.innerHTML = '';

        files.forEach(f => {
            const isFolder = f.format === 'folder';
            const isEpub = f.format === 'epub';
            const isZip = f.format === 'zip';
            const sizeStr = formatFileSize(f.size);

            if (isFolder) {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'px-5 py-3 rounded-xl bg-gradient-to-r from-amber-600 to-orange-600 text-white font-medium text-sm flex items-center gap-2 shadow-sm hover:opacity-95 active:scale-95 transition cursor-pointer';
                const countStr = f.count ? ` (${f.count} chương)` : '';
                btn.innerHTML = `<i class="fa-solid fa-folder-open"></i> Mở Thư Mục Truyện${countStr}`;
                btn.onclick = async () => {
                    try {
                        const r = await fetch(`/api/open_folder?name=${encodeURIComponent(f.name)}`);
                        const res = await r.json();
                        if (!res.success) alert(res.detail || 'Không thể mở thư mục');
                    } catch (e) {
                        alert('Không thể mở thư mục: ' + e.message);
                    }
                };
                downloadButtonsList.appendChild(btn);
            } else {
                const btn = document.createElement('a');
                btn.href = `/api/files/${encodeURIComponent(f.name)}`;
                btn.download = f.name;
                const icon = isEpub ? 'fa-book' : (isZip ? 'fa-file-zipper' : 'fa-file-lines');
                const colorClass = isEpub 
                    ? 'from-purple-600 to-indigo-600' 
                    : (isZip ? 'from-amber-600 to-orange-600' : 'from-emerald-600 to-teal-600');
                const labelText = isZip ? 'Tải ZIP Từng Chương' : `Tải ${f.format.toUpperCase()}`;

                btn.className = `px-5 py-3 rounded-xl bg-gradient-to-r ${colorClass} text-white font-medium text-sm flex items-center gap-2 shadow-sm hover:opacity-95 active:scale-95 transition`;
                btn.innerHTML = `<i class="fa-solid ${icon}"></i> ${labelText} (${sizeStr})`;
                downloadButtonsList.appendChild(btn);
            }
        });
    }

    // Format file size
    function formatFileSize(bytes) {
        if (!bytes) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }

    // Load Recent Files
    async function loadRecentFiles() {
        try {
            const resp = await fetch('/api/files');
            const data = await resp.json();
            const files = data.files || [];

            if (files.length === 0) {
                filesList.innerHTML = '<p class="text-xs text-gray-400 py-4 text-center">Chưa có file nào được tải.</p>';
                return;
            }

            filesList.innerHTML = '';
            files.forEach(f => {
                const item = document.createElement('div');
                item.className = 'py-3 flex items-center justify-between gap-3';
                const isFolder = f.format === 'folder';
                const isEpub = f.format === 'epub';
                const isZip = f.format === 'zip';
                const icon = isFolder
                    ? 'fa-folder text-amber-500'
                    : (isEpub ? 'fa-book text-purple-500' : (isZip ? 'fa-file-zipper text-amber-500' : 'fa-file-lines text-emerald-500'));
                const subText = isFolder 
                    ? `${f.count || 0} file chương • ${formatFileSize(f.size)}`
                    : formatFileSize(f.size);

                const actionBtn = isFolder
                    ? `<button data-foldername="${f.name}" class="open-folder-btn p-2 text-amber-600 hover:bg-amber-50 dark:hover:bg-amber-900/30 rounded-lg transition" title="Mở thư mục trên máy">
                         <i class="fa-solid fa-folder-open text-base"></i>
                       </button>`
                    : `<a href="/api/files/${encodeURIComponent(f.name)}" download="${f.name}" class="p-2 text-brand-500 hover:bg-brand-50 dark:hover:bg-brand-900/30 rounded-lg transition" title="Tải về">
                         <i class="fa-solid fa-download"></i>
                       </a>`;

                item.innerHTML = `
                    <div class="flex items-center gap-3 overflow-hidden">
                        <i class="fa-solid ${icon} text-lg flex-shrink-0"></i>
                        <div class="truncate">
                            <p class="font-medium text-gray-900 dark:text-white truncate text-sm">${f.name}</p>
                            <p class="text-xs text-gray-400">${subText}</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                        ${actionBtn}
                        <button data-filename="${f.name}" class="delete-file-btn p-2 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/30 rounded-lg transition" title="Xóa">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                `;
                filesList.appendChild(item);
            });

            // Bind open folder buttons
            document.querySelectorAll('.open-folder-btn').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const foldername = btn.getAttribute('data-foldername');
                    try {
                        const r = await fetch(`/api/open_folder?name=${encodeURIComponent(foldername)}`);
                        const res = await r.json();
                        if (!res.success) alert(res.detail || 'Không thể mở thư mục');
                    } catch (e) {
                        alert('Không thể mở thư mục: ' + e.message);
                    }
                });
            });

            // Bind delete buttons
            document.querySelectorAll('.delete-file-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const filename = btn.getAttribute('data-filename');
                    if (!confirm(`Bạn có chắc chắn muốn xóa file "${filename}"?`)) return;
                    try {
                        const delResp = await fetch(`/api/files/${encodeURIComponent(filename)}`, { method: 'DELETE' });
                        if (delResp.ok) {
                            loadRecentFiles();
                        }
                    } catch (err) {
                        alert('Lỗi xóa file: ' + err.message);
                    }
                });
            });

        } catch (e) {
            console.error('Failed to load recent files:', e);
        }
    }

    refreshFilesBtn.addEventListener('click', loadRecentFiles);
    loadRecentFiles();
});
