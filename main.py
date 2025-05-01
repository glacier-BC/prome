import sys
import os
import json
import string
import subprocess  # 保留用于其他功能
import shutil  # 用于复制文件
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                           QLineEdit, QPushButton, QScrollArea, QLabel, QFileDialog,
                           QColorDialog, QFormLayout, QProgressBar, QComboBox,
                           QStackedWidget, QListWidget, QTreeWidget, QTreeWidgetItem,
                           QDateTimeEdit, QMessageBox, QFileIconProvider, QGridLayout)
from PyQt6.QtGui import QPixmap, QColor, QCursor, QIcon
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QUrl, QFileInfo, QSize
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtMultimedia import QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtPdf import QPdfDocument
from PyQt6.QtPdfWidgets import QPdfView
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import urllib.request

# 获取应用程序的基础路径
def get_base_path():
    """获取应用程序的基础路径，兼容开发环境和打包后的环境"""
    if getattr(sys, 'frozen', False):
        # 如果应用被打包
        return os.path.dirname(sys.executable)
    else:
        # 开发环境
        return os.path.dirname(os.path.abspath(__file__))

# 获取设置文件路径
def get_settings_path():
    """获取设置文件的完整路径"""
    base_dir = get_base_path()
    settings_dir = os.path.join(base_dir, 'settings')

    # 确保设置目录存在
    if not os.path.exists(settings_dir):
        try:
            os.makedirs(settings_dir)
        except Exception:
            # 如果无法创建目录，则使用基础目录
            settings_dir = base_dir

    return os.path.join(settings_dir, 'settings.json')

# 获取设置图片目录
def get_settings_images_path():
    """获取设置图片的目录路径"""
    base_dir = get_base_path()
    images_dir = os.path.join(base_dir, 'settings', 'images')

    # 确保图片目录存在
    if not os.path.exists(images_dir):
        try:
            os.makedirs(images_dir)
        except Exception:
            # 如果无法创建目录，则使用设置目录
            images_dir = os.path.join(base_dir, 'settings')
            if not os.path.exists(images_dir):
                try:
                    os.makedirs(images_dir)
                except Exception:
                    # 如果仍然无法创建，则使用基础目录
                    images_dir = base_dir

    return images_dir

# 浏览器检测函数 - 保留但不再用于爬虫
def detect_browsers():
    """Detect installed browsers and their paths on the system."""
    browsers = {}

    if os.name == 'nt':  # Windows
        # Common browser locations on Windows
        possible_paths = {
            'Chrome': [
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'Google\\Chrome\\Application\\chrome.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Google\\Chrome\\Application\\chrome.exe'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google\\Chrome\\Application\\chrome.exe')
            ],
            'Edge': [
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'Microsoft\\Edge\\Application\\msedge.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Microsoft\\Edge\\Application\\msedge.exe'),
                os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft\\Edge\\Application\\msedge.exe')
            ],
            'Firefox': [
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'Mozilla Firefox\\firefox.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Mozilla Firefox\\firefox.exe')
            ],
            '360浏览器': [
                os.path.join(os.environ.get('PROGRAMFILES', ''), '360\\360se6\\Application\\360se.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), '360\\360se6\\Application\\360se.exe'),
                os.path.join(os.environ.get('PROGRAMFILES', ''), '360\\360Chrome\\Chrome\\Application\\360chrome.exe'),
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), '360\\360Chrome\\Chrome\\Application\\360chrome.exe')
            ]
        }

        # Check registry for browser paths
        try:
            import winreg
            for browser, reg_path in [
                ('Chrome', r'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\chrome.exe'),
                ('Edge', r'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\msedge.exe'),
                ('Firefox', r'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\firefox.exe')
            ]:
                try:
                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                        browsers[browser] = winreg.QueryValue(key, None)
                except:
                    pass
        except ImportError:
            pass

        # Check file existence for each possible path
        for browser, paths in possible_paths.items():
            if browser not in browsers:
                for path in paths:
                    if os.path.exists(path):
                        browsers[browser] = path
                        break

    else:  # macOS and Linux
        # Use 'which' command to find browser executables
        for browser, cmd in [
            ('Chrome', 'google-chrome'),
            ('Chrome', 'chrome'),
            ('Chrome', 'chromium'),
            ('Firefox', 'firefox'),
            ('Edge', 'microsoft-edge')
        ]:
            try:
                path = subprocess.check_output(['which', cmd], stderr=subprocess.STDOUT).decode().strip()
                if path and os.path.exists(path):
                    browsers[browser] = path
            except:
                pass

    return browsers

# 媒体扫描线程
class MediaScanner(QThread):
    file_found = pyqtSignal(str, str, str)  # filename, filepath, type
    scan_complete = pyqtSignal()
    progress_signal = pyqtSignal(int)

    def __init__(self, media_type='all'):
        super().__init__()
        self.image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
        self.video_extensions = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp')
        self.max_files = 1000
        self.scanned_files = 0
        self.is_scanning = False
        self.media_type = media_type

    def run(self):
        self.is_scanning = True
        self.scanned_files = 0
        for drive in self.get_available_drives():
            self.scan_directory(drive)
            if self.scanned_files >= self.max_files:
                break
            self.progress_signal.emit(int(self.scanned_files / self.max_files * 100))
        self.is_scanning = False
        self.scan_complete.emit()

    def get_available_drives(self):
        if os.name == 'nt':  # Windows
            import string
            return [f'{d}:\\' for d in string.ascii_uppercase if os.path.exists(f'{d}:')]
        else:  # Unix-based systems
            return ['/']

    def scan_directory(self, directory):
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if self.scanned_files >= self.max_files:
                        return
                    lower_file = file.lower()
                    if self.media_type in ['all', 'image'] and lower_file.endswith(self.image_extensions):
                        self.file_found.emit(file, os.path.join(root, file), 'image')
                        self.scanned_files += 1
                    elif self.media_type in ['all', 'video'] and lower_file.endswith(self.video_extensions):
                        self.file_found.emit(file, os.path.join(root, file), 'video')
                        self.scanned_files += 1
            if self.scanned_files >= self.max_files:
                return
        except PermissionError:
            pass  # Skip directories we don't have permission to access
        except Exception as e:
            print(f"扫描目录时出错: {str(e)}")

# 文档扫描线程
class DocumentScanner(QThread):
    file_found = pyqtSignal(str, str, str)  # filename, filepath, type
    scan_complete = pyqtSignal()
    progress_signal = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.document_extensions = {
            'word': ('.doc', '.docx'),
            'excel': ('.xls', '.xlsx'),
            'powerpoint': ('.ppt', '.pptx'),
            'pdf': ('.pdf',)
        }
        self.max_files = 1000
        self.scanned_files = 0
        self.is_scanning = False

    def run(self):
        self.is_scanning = True
        self.scanned_files = 0
        for drive in self.get_available_drives():
            self.scan_directory(drive)
            if self.scanned_files >= self.max_files:
                break
            self.progress_signal.emit(int(self.scanned_files / self.max_files * 100))
        self.is_scanning = False
        self.scan_complete.emit()

    def get_available_drives(self):
        if os.name == 'nt':  # Windows
            import string
            return [f'{d}:\\' for d in string.ascii_uppercase if os.path.exists(f'{d}:')]
        else:  # Unix-based systems
            return ['/']

    def scan_directory(self, directory):
        try:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    if self.scanned_files >= self.max_files:
                        return
                    lower_file = file.lower()
                    for doc_type, extensions in self.document_extensions.items():
                        if lower_file.endswith(extensions):
                            self.file_found.emit(file, os.path.join(root, file), doc_type)
                            self.scanned_files += 1
                            break
            if self.scanned_files >= self.max_files:
                return
        except PermissionError:
            pass  # Skip directories we don't have permission to access
        except Exception as e:
            print(f"扫描文档时出错: {str(e)}")

# 文件搜索线程
class FileSearchThread(QThread):
    update_signal = pyqtSignal(str, str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()

    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.is_cancelled = False

    def run(self):
        available_drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:")]
        total_drives = len(available_drives)

        for i, drive in enumerate(available_drives):
            if self.is_cancelled:
                break
            self.search_directory(drive, max_depth=5)  # Limit search depth to 5 levels
            self.progress_signal.emit(int((i + 1) / total_drives * 100))

        self.finished_signal.emit()

    def search_directory(self, directory, current_depth=0, max_depth=5):
        if self.is_cancelled or current_depth > max_depth:
            return

        try:
            for entry in os.scandir(directory):
                if self.is_cancelled:
                    return
                if entry.is_file() and self.filename.lower() in entry.name.lower():
                    self.update_signal.emit(entry.name, entry.path)
                elif entry.is_dir():
                    self.search_directory(entry.path, current_depth + 1, max_depth)
        except PermissionError:
            pass  # Skip directories we don't have permission to access
        except Exception as e:
            print(f"搜索文件时出错: {str(e)}")

    def cancel(self):
        self.is_cancelled = True

# 爬虫线程 - 无浏览器依赖版本
# 增强版爬虫线程
class CrawlerThread(QThread):
    update_signal = pyqtSignal(str, str)
    status_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    debug_signal = pyqtSignal(str)  # 新增调试信号

    def __init__(self, url, browser=None, browser_path=None):
        QThread.__init__(self)
        self.url = url
        # 保留browser和browser_path参数以保持接口兼容性，但不再使用它们
        self.browser = browser
        self.browser_path = browser_path
        self.found_items = 0  # 跟踪找到的项目数量

    def run(self):
        try:
            self.status_signal.emit("开始访问页面...")
            self.debug_signal.emit(f"正在请求URL: {self.url}")

            # 使用更健壮的请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
                'DNT': '1',
            }

            self.status_signal.emit("正在发送HTTP请求...")

            # 增加超时和重试机制
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(max_retries=3)
            session.mount('http://', adapter)
            session.mount('https://', adapter)

            response = session.get(self.url, headers=headers, timeout=30)

            if response.status_code != 200:
                self.status_signal.emit(f"HTTP请求失败，状态码: {response.status_code}")
                self.debug_signal.emit(f"请求失败，响应内容: {response.text[:500]}...")
                return

            # 尝试检测编码
            if response.encoding == 'ISO-8859-1':
                # 尝试更准确地检测编码
                encodings = requests.utils.get_encodings_from_content(response.text)
                if encodings:
                    response.encoding = encodings[0]
                else:
                    response.encoding = response.apparent_encoding

            self.status_signal.emit("网页加载完成，开始解析...")
            self.debug_signal.emit(f"使用编码: {response.encoding}, 内容长度: {len(response.text)}")

            # 使用BeautifulSoup解析HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # 提取元信息
            title = soup.title.string if soup.title else "无标题"
            self.status_signal.emit(f"正在爬取: {title}")

            # 提取图片
            self.status_signal.emit("正在提取图片...")
            images = soup.find_all('img')
            total_images = len(images)
            self.debug_signal.emit(f"找到 {total_images} 个图片标签")

            for i, img in enumerate(images):
                if self.isInterruptionRequested():
                    break

                src = img.get('src') or img.get('data-src') or img.get('data-original')
                if src:
                    # 处理相对URL
                    full_url = urljoin(self.url, src)
                    self.debug_signal.emit(f"处理图片: {full_url}")
                    self.update_signal.emit(full_url, 'image')
                    self.found_items += 1

                # 更新进度
                self.progress_signal.emit(int((i+1) / max(total_images, 1) * 100))

            # 提取视频
            self.status_signal.emit("正在提取视频...")
            videos = soup.find_all(['video', 'iframe'])
            self.debug_signal.emit(f"找到 {len(videos)} 个视频标签")

            for video in videos:
                if self.isInterruptionRequested():
                    break

                # 处理video标签
                if video.name == 'video':
                    src = video.get('src')
                    if src:
                        full_url = urljoin(self.url, src)
                        self.debug_signal.emit(f"处理视频: {full_url}")
                        self.update_signal.emit(full_url, 'video')
                        self.found_items += 1

                # 处理iframe嵌入视频(YouTube, Vimeo等)
                elif video.name == 'iframe':
                    src = video.get('src')
                    if src and ('youtube.com' in src or 'vimeo.com' in src or 'youku.com' in src or 'bilibili.com' in src):
                        self.debug_signal.emit(f"处理嵌入视频: {src}")
                        self.update_signal.emit(src, 'video')
                        self.found_items += 1

            # 提取视频源
            video_sources = soup.find_all('source')
            self.debug_signal.emit(f"找到 {len(video_sources)} 个视频源标签")

            for source in video_sources:
                if self.isInterruptionRequested():
                    break

                src = source.get('src')
                if src:
                    full_url = urljoin(self.url, src)
                    self.debug_signal.emit(f"处理视频源: {full_url}")
                    self.update_signal.emit(full_url, 'video')
                    self.found_items += 1

            # 提取链接
            if not self.isInterruptionRequested():
                self.status_signal.emit("正在提取链接...")
                links = soup.find_all('a')
                total_links = len(links)
                self.debug_signal.emit(f"找到 {total_links} 个链接标签")

                for i, link in enumerate(links):
                    if self.isInterruptionRequested():
                        break

                    href = link.get('href')
                    if href and not href.startswith(('javascript:', '#', 'mailto:')):
                        full_url = urljoin(self.url, href)
                        self.debug_signal.emit(f"处理链接: {full_url}")
                        self.update_signal.emit(full_url, 'link')
                        self.found_items += 1

                    # 更新进度
                    self.progress_signal.emit(int((i+1) / max(total_links, 1) * 100))

            # 尝试提取CSS背景图片
            self.status_signal.emit("正在提取CSS背景图片...")
            style_tags = soup.find_all('style')
            inline_styles = []

            # 提取内联样式标签内容
            for style in style_tags:
                if style.string:
                    inline_styles.append(style.string)

            # 提取元素内联样式
            elements_with_style = soup.find_all(lambda tag: tag.has_attr('style'))
            for element in elements_with_style:
                inline_styles.append(element['style'])

            # 简单解析内联样式中的URL
            import re
            url_pattern = re.compile(r'url$$[\'"]?(.*?)[\'"]?$$')
            for style in inline_styles:
                urls = url_pattern.findall(style)
                for url in urls:
                    if url and not url.startswith('data:'):
                        full_url = urljoin(self.url, url)
                        self.debug_signal.emit(f"处理CSS背景图片: {full_url}")
                        self.update_signal.emit(full_url, 'image')
                        self.found_items += 1

            # 检查是否找到任何内容
            if self.found_items == 0:
                self.debug_signal.emit("未找到任何可爬取内容，尝试使用备用方法...")

                # 备用方法：直接提取所有URL
                all_urls = re.findall(r'https?://[^\s<>"\']+', response.text)
                for url in all_urls:
                    # 简单判断URL类型
                    if any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
                        self.update_signal.emit(url, 'image')
                        self.found_items += 1
                    elif any(url.lower().endswith(ext) for ext in ['.mp4', '.webm', '.avi', '.mov']):
                        self.update_signal.emit(url, 'video')
                        self.found_items += 1
                    else:
                        self.update_signal.emit(url, 'link')
                        self.found_items += 1

            if self.isInterruptionRequested():
                self.status_signal.emit("爬取已停止")
            else:
                self.status_signal.emit(f"爬取完成，共找到 {self.found_items} 个项目")

        except requests.exceptions.RequestException as e:
            self.status_signal.emit(f"请求错误: {str(e)}")
            self.debug_signal.emit(f"请求异常详情: {str(e)}")
        except Exception as e:
            self.status_signal.emit(f"爬取失败: {str(e)}")
            self.debug_signal.emit(f"异常详情: {str(e)}")
            import traceback
            self.debug_signal.emit(f"异常堆栈: {traceback.format_exc()}")

# 文件详情窗口
class FileDetailsWindow(QMainWindow):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.setWindowTitle("文件详情")
        self.setGeometry(200, 200, 400, 500)
        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)

        # Set dark theme
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e1e;
                color: white;
            }
            QLineEdit, QDateTimeEdit {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 5px;
                color: white;
            }
            QPushButton {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px;
                color: white;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
            QLabel {
                color: white;
            }
        """)

        file_info = QFileInfo(self.file_path)
        icon_provider = QFileIconProvider()

        # 文件图标
        self.icon_label = QLabel()
        icon = icon_provider.icon(file_info)
        self.icon_label.setPixmap(icon.pixmap(64, 64))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon_label)

        # 更改图标按钮
        change_icon_button = QPushButton("更改图标")
        change_icon_button.clicked.connect(self.change_icon)
        layout.addWidget(change_icon_button)

        # 文件名称（可编辑）
        layout.addWidget(QLabel("文件名称:"))
        self.file_name_edit = QLineEdit(file_info.fileName())
        layout.addWidget(self.file_name_edit)

        # 文件类型
        layout.addWidget(QLabel("文件类型:"))
        file_type_label = QLineEdit(file_info.suffix())
        file_type_label.setReadOnly(True)
        layout.addWidget(file_type_label)

        # 文件路径
        layout.addWidget(QLabel("文件路径:"))
        file_path_label = QLineEdit(file_info.absolutePath())
        file_path_label.setReadOnly(True)
        layout.addWidget(file_path_label)

        # 文件大小
        layout.addWidget(QLabel("文件大小:"))
        size_label = QLineEdit(self.format_size(file_info.size()))
        size_label.setReadOnly(True)
        layout.addWidget(size_label)

        # 创建时间（可编辑）
        layout.addWidget(QLabel("创建时间:"))
        self.creation_time_edit = QDateTimeEdit(file_info.birthTime())
        self.creation_time_edit.setCalendarPopup(True)
        layout.addWidget(self.creation_time_edit)

        # 修改时间（可编辑）
        layout.addWidget(QLabel("修改时间:"))
        self.modified_time_edit = QDateTimeEdit(file_info.lastModified())
        self.modified_time_edit.setCalendarPopup(True)
        layout.addWidget(self.modified_time_edit)

        # 功能按钮
        button_layout = QVBoxLayout()
        button_layout.setSpacing(8)

        # PDF预览按钮（仅对PDF文件显示）
        if file_info.suffix().lower() == 'pdf':
            preview_button = QPushButton("预览 PDF")
            preview_button.clicked.connect(self.preview_pdf)
            button_layout.addWidget(preview_button)
        # 视频预览按钮（仅对视频文件显示）
        elif file_info.suffix().lower() in ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'):
            preview_button = QPushButton("预览视频")
            preview_button.clicked.connect(self.preview_video)
            button_layout.addWidget(preview_button)
        else:
            open_button = QPushButton("打开文件")
            open_button.clicked.connect(self.open_file)
            button_layout.addWidget(open_button)

        # 打开文件所在位置按钮
        open_location_button = QPushButton("打开文件所在位置")
        open_location_button.clicked.connect(self.open_file_location)
        button_layout.addWidget(open_location_button)

        # 保存更改按钮
        save_button = QPushButton("保存更改")
        save_button.clicked.connect(self.save_changes)
        button_layout.addWidget(save_button)

        layout.addLayout(button_layout)

    def change_icon(self):
        icon_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图标",
            "",
            "图标文件 (*.ico *.png *.jpg *.jpeg)"
        )
        if icon_path:
            icon = QIcon(icon_path)
            self.icon_label.setPixmap(icon.pixmap(64, 64))

    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0

    def open_file(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.file_path))

    def open_file_location(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(QFileInfo(self.file_path).absolutePath()))

    def preview_pdf(self):
        pdf_view = QPdfView()
        document = QPdfDocument()
        document.load(self.file_path)
        pdf_view.setDocument(document)

        preview_window = QMainWindow()
        preview_window.setCentralWidget(pdf_view)
        preview_window.setWindowTitle(f"PDF 预览 - {QFileInfo(self.file_path).fileName()}")
        preview_window.setGeometry(300, 300, 800, 600)
        preview_window.show()

    def preview_video(self):
        preview_window = QMainWindow(self)
        preview_window.setWindowTitle(f"视频预览 - {os.path.basename(self.file_path)}")
        preview_window.setGeometry(100, 100, 800, 600)

        video_widget = QVideoWidget()
        preview_window.setCentralWidget(video_widget)

        media_player = QMediaPlayer()
        media_player.setVideoOutput(video_widget)
        media_player.setSource(QUrl.fromLocalFile(self.file_path))

        preview_window.show()
        media_player.play()

    def save_changes(self):
        try:
            # 保存文件名更改
            new_name = self.file_name_edit.text()
            new_path = os.path.join(os.path.dirname(self.file_path), new_name)

            if new_name != os.path.basename(self.file_path):
                os.rename(self.file_path, new_path)
                self.file_path = new_path

            # 保存时间更改
            new_ctime = self.creation_time_edit.dateTime().toSecsSinceEpoch()
            new_mtime = self.modified_time_edit.dateTime().toSecsSinceEpoch()
            os.utime(self.file_path, (new_ctime, new_mtime))

            QMessageBox.information(self, "成功", "文件信息已更新")
        except OSError as e:
            QMessageBox.warning(self, "错误", f"无法更新文件信息: {str(e)}")

# 预览窗口
class PreviewWindow(QMainWindow):
    def __init__(self, url, media_type):
        super().__init__()
        self.setWindowTitle("预览")
        self.setGeometry(200, 200, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        if media_type == 'image':
            self.web_view = QWebEngineView()
            self.web_view.setUrl(QUrl(url))
            layout.addWidget(self.web_view)
        elif media_type == 'video':
            self.video_widget = QVideoWidget()
            self.media_player = QMediaPlayer()
            self.media_player.setVideoOutput(self.video_widget)
            self.media_player.setSource(QUrl(url))
            layout.addWidget(self.video_widget)
            self.media_player.play()
        else:  # For links or any other type
            self.web_view = QWebEngineView()
            self.web_view.setUrl(QUrl(url))
            layout.addWidget(self.web_view)

# 媒体子页面
class MediaSubPage(QWidget):
    def __init__(self, media_type, parent=None):
        super().__init__(parent)
        self.media_type = media_type
        self.setup_ui()
        self.scanner = MediaScanner(media_type)
        self.scanner.file_found.connect(self.add_media_to_grid)
        self.scanner.scan_complete.connect(self.on_scan_complete)
        self.scanner.progress_signal.connect(self.update_progress)
        self.media_items = []

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: white;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 5px 15px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QLabel {
                color: white;
            }
        """)

        # Header
        header_layout = QHBoxLayout()
        self.status_label = QLabel(f"准备扫描{self.media_type}文件...")
        header_layout.addWidget(self.status_label)

        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.start_scan)
        header_layout.addWidget(self.refresh_button)
        layout.addLayout(header_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Scroll Area for Media Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setSpacing(10)

        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

        # Counter label
        self.counter_label = QLabel(f"{self.media_type.capitalize()}: 0")
        layout.addWidget(self.counter_label)

        self.loading_label = QLabel(f"正在加载{self.media_type}文件...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("font-size: 18px; color: #2196F3;")
        self.loading_label.hide()
        layout.addWidget(self.loading_label)

        self.media_count = 0
        self.current_row = 0
        self.current_col = 0
        self.max_columns = 4

    def start_scan(self):
        if self.scanner.isRunning():
            self.scanner.terminate()
            self.scanner.wait()
        self.media_count = 0
        self.counter_label.setText(f"{self.media_type.capitalize()}: 0")
        self.clear_grid()
        self.current_row = 0
        self.current_col = 0
        self.status_label.setText(f"正在扫描{self.media_type}文件...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.loading_label.show()
        self.scanner = MediaScanner(self.media_type)
        self.scanner.file_found.connect(self.add_media_to_grid)
        self.scanner.scan_complete.connect(self.on_scan_complete)
        self.scanner.progress_signal.connect(self.update_progress)
        self.scanner.start()

    def clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.media_items.clear()
        self.media_count = 0
        self.counter_label.setText(f"{self.media_type.capitalize()}: 0")
        self.progress_bar.setValue(0)

    def create_media_widget(self, file_path):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(5)

        # Thumbnail
        thumbnail = QLabel()
        thumbnail.setFixedSize(QSize(150, 150))
        thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if self.media_type == 'image':
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
                thumbnail.setPixmap(pixmap)
            else:
                thumbnail.setText("无法加载图片")
        elif self.media_type == 'video':
            thumbnail.setText("🎥")
            thumbnail.setStyleSheet("QLabel { font-size: 48px; }")

        layout.addWidget(thumbnail)

        # File name label
        name_label = QLabel(os.path.basename(file_path))
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        # Make the widget clickable
        widget.mouseDoubleClickEvent = lambda e: self.show_media_details(file_path)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        widget.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border-radius: 8px;
                padding: 8px;
            }
            QWidget:hover {
                background-color: #3d3d3d;
            }
        """)

        return widget

    def add_media_to_grid(self, filename, filepath, media_type):
        if media_type != self.media_type:
            return
        widget = self.create_media_widget(filepath)
        self.grid_layout.addWidget(widget, self.current_row, self.current_col)

        self.media_count += 1
        self.counter_label.setText(f"{self.media_type.capitalize()}: {self.media_count}")

        self.current_col += 1
        if self.current_col >= self.max_columns:
            self.current_col = 0
            self.current_row += 1

        self.media_items.append(widget)
        self.loading_label.hide()

    def show_media_details(self, file_path):
        self.details_window = FileDetailsWindow(file_path)
        self.details_window.show()

    def on_scan_complete(self):
        self.loading_label.hide()
        if self.scanner.scanned_files == 0:
            self.status_label.setText(f"未找到{self.media_type}文件")
        else:
            self.status_label.setText("扫描完成")
        self.progress_bar.setVisible(False)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

# 媒体页面
class MediaPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: white;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 5px 15px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QLabel {
                color: white;
            }
        """)

        # Toggle buttons
        toggle_layout = QHBoxLayout()
        self.image_button = QPushButton("图片")
        self.image_button.clicked.connect(lambda: self.switch_page(0))
        toggle_layout.addWidget(self.image_button)

        self.video_button = QPushButton("视频")
        self.video_button.clicked.connect(lambda: self.switch_page(1))
        toggle_layout.addWidget(self.video_button)

        layout.addLayout(toggle_layout)

        # Stacked widget for image and video pages
        self.stacked_widget = QStackedWidget()
        self.image_page = MediaSubPage('image')
        self.video_page = MediaSubPage('video')
        self.stacked_widget.addWidget(self.image_page)
        self.stacked_widget.addWidget(self.video_page)
        layout.addWidget(self.stacked_widget)

    def switch_page(self, index):
        self.stacked_widget.setCurrentIndex(index)
        if index == 0:
            self.image_button.setStyleSheet("background-color: #1976D2;")
            self.video_button.setStyleSheet("")
        else:
            self.video_button.setStyleSheet("background-color: #1976D2;")
            self.image_button.setStyleSheet("")

    def start_scan(self):
        current_page = self.stacked_widget.currentWidget()
        if current_page:
            current_page.start_scan()

# 文档页面
class DocumentPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.scanner = DocumentScanner()
        self.scanner.file_found.connect(self.add_document_to_grid)
        self.scanner.scan_complete.connect(self.on_scan_complete)
        self.scanner.progress_signal.connect(self.update_progress)
        self.document_items = []
        self.document_counts = {
            'word': 0,
            'excel': 0,
            'powerpoint': 0,
            'pdf': 0
        }

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                color: white;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 5px 15px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QLabel {
                color: white;
            }
        """)

        # Header
        header_layout = QHBoxLayout()
        self.status_label = QLabel("准备扫描文档...")
        header_layout.addWidget(self.status_label)

        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.start_scan)
        header_layout.addWidget(self.refresh_button)
        layout.addLayout(header_layout)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Document type counters
        counter_layout = QHBoxLayout()
        self.counter_labels = {}
        for doc_type in ['word', 'excel', 'powerpoint', 'pdf']:
            label = QLabel(f"{doc_type.capitalize()}: 0")
            self.counter_labels[doc_type] = label
            counter_layout.addWidget(label)
        layout.addLayout(counter_layout)

        # Scroll Area for Document Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.scroll_content = QWidget()
        self.grid_layout = QGridLayout(self.scroll_content)
        self.grid_layout.setSpacing(10)

        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

        self.loading_label = QLabel("正在加载文档...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setStyleSheet("font-size: 18px; color: #2196F3;")
        self.loading_label.hide()
        layout.addWidget(self.loading_label)

        self.current_row = 0
        self.current_col = 0
        self.max_columns = 4

    def start_scan(self):
        if self.scanner.isRunning():
            self.scanner.terminate()
            self.scanner.wait()
        self.clear_grid()
        self.current_row = 0
        self.current_col = 0
        self.status_label.setText("正在扫描文档...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.loading_label.show()
        self.scanner = DocumentScanner()
        self.scanner.file_found.connect(self.add_document_to_grid)
        self.scanner.scan_complete.connect(self.on_scan_complete)
        self.scanner.progress_signal.connect(self.update_progress)
        self.scanner.start()

    def clear_grid(self):
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.document_items.clear()
        for doc_type in self.document_counts:
            self.document_counts[doc_type] = 0
            self.counter_labels[doc_type].setText(f"{doc_type.capitalize()}: 0")
        self.progress_bar.setValue(0)

    def create_document_widget(self, file_path, doc_type):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(5)

        # Icon/Thumbnail
        icon_label = QLabel()
        icon_label.setFixedSize(QSize(64, 64))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setText(self.get_document_icon(doc_type))
        icon_label.setStyleSheet("QLabel { font-size: 32px; }")
        layout.addWidget(icon_label)

        # File name label
        name_label = QLabel(os.path.basename(file_path))
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        # Make the widget clickable
        widget.mouseDoubleClickEvent = lambda e: self.show_document_details(file_path)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        widget.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border-radius: 8px;
                padding: 8px;
            }
            QWidget:hover {
                background-color: #3d3d3d;
            }
        """)

        return widget

    def get_document_icon(self, doc_type):
        icons = {
            'word': '📄',
            'excel': '📊',
            'powerpoint': '📑',
            'pdf': '📰'
        }
        return icons.get(doc_type, '📄')

    def add_document_to_grid(self, filename, filepath, doc_type):
        widget = self.create_document_widget(filepath, doc_type)
        self.grid_layout.addWidget(widget, self.current_row, self.current_col)

        self.document_counts[doc_type] += 1
        self.counter_labels[doc_type].setText(f"{doc_type.capitalize()}: {self.document_counts[doc_type]}")

        self.current_col += 1
        if self.current_col >= self.max_columns:
            self.current_col = 0
            self.current_row += 1

        self.document_items.append(widget)
        self.loading_label.hide()

    def show_document_details(self, file_path):
        self.details_window = FileDetailsWindow(file_path)
        self.details_window.show()

    def on_scan_complete(self):
        self.loading_label.hide()
        if sum(self.document_counts.values()) == 0:
            self.status_label.setText("未找到文档")
        else:
            self.status_label.setText("扫描完成")
        self.progress_bar.setVisible(False)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

# 文件搜索页面
class FileSearchPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.search_thread = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.setStyleSheet("background-color: #1e1e1e;")
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入文件名进行搜索")
        search_layout.addWidget(self.search_input)

        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self.start_search)
        search_layout.addWidget(self.search_button)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.cancel_search)
        self.cancel_button.setEnabled(False)
        search_layout.addWidget(self.cancel_button)

        layout.addLayout(search_layout)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["文件名", "路径"])
        self.results_tree.itemDoubleClicked.connect(self.show_file_details)
        self.results_tree.setStyleSheet("""
            QTreeWidget {
                background-color: #1e1e1e;
                color: white;
                border: 1px solid #333;
            }
            QTreeWidget::item:hover {
                background-color: #2d2d2d;
            }
            QTreeWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
        """)
        layout.addWidget(self.results_tree)

        self.status_label = QLabel("准备就绪")
        self.status_label.setStyleSheet("color: #2196F3; background-color: transparent;")
        layout.addWidget(self.status_label)

    def start_search(self):
        filename = self.search_input.text()
        if not filename:
            return

        self.results_tree.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("搜索中...")
        self.search_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        self.search_thread = FileSearchThread(filename)
        self.search_thread.update_signal.connect(self.update_results)
        self.search_thread.progress_signal.connect(self.update_progress)
        self.search_thread.finished_signal.connect(self.search_finished)
        self.search_thread.start()

    def cancel_search(self):
        if self.search_thread and self.search_thread.isRunning():
            self.search_thread.cancel()
            self.status_label.setText("搜索已取消")
            self.search_button.setEnabled(True)
            self.cancel_button.setEnabled(False)

    def update_results(self, filename, filepath):
        item = QTreeWidgetItem([filename, filepath])
        self.results_tree.addTopLevelItem(item)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def search_finished(self):
        self.status_label.setText("搜索完成")
        self.search_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_bar.setValue(100)

    def show_file_details(self, item, column):
        file_path = item.text(1)  # 获取文件路径（第二列）
        self.file_details_window = FileDetailsWindow(file_path)
        self.file_details_window.show()

# 爬虫页面
class CrawlerPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
        self.crawler_thread = None

    def setup_ui(self):
        layout = QVBoxLayout(self)
        self.setStyleSheet("background-color: #1e1e1e;")

        # 添加说明标签
        info_label = QLabel("研究性课题，仅供学习参考;部分网页可能无法爬取;爬取过程时请耐心等待...")
        info_label.setStyleSheet("color: #4CAF50; padding: 10px; background-color: #1e1e1e; border-radius: 4px;")
        layout.addWidget(info_label)

        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("请输入网址")
        self.url_input.setStyleSheet("""
            QLineEdit {
                background-color: #1e1e1e;
                color: white;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        input_layout.addWidget(self.url_input)

        self.clear_button = QPushButton("清空")
        self.clear_button.setFixedWidth(60)
        self.clear_button.clicked.connect(self.clear_url)
        input_layout.addWidget(self.clear_button)

        self.crawl_button = QPushButton("开始爬取")
        self.crawl_button.setFixedWidth(100)
        self.crawl_button.clicked.connect(self.start_crawling)
        input_layout.addWidget(self.crawl_button)

        self.stop_button = QPushButton("停止")
        self.stop_button.setFixedWidth(60)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_crawling)
        input_layout.addWidget(self.stop_button)

        layout.addLayout(input_layout)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1e1e1e;
                border: 1px solid #333;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.scroll_area)

    def update_ui(self, url, file_type):
        # 调试信息
        print(f"收到爬取结果: {url} - {file_type}")

        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_widget.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border-radius: 4px;
                margin: 2px;
                padding: 4px;
            }
            QLabel {
                color: white;
            }
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)

        type_label = QLabel(f"[{file_type}]")
        type_label.setStyleSheet("color: #2196F3; min-width: 50px;")
        item_layout.addWidget(type_label)

        if file_type == 'image':
            try:
                label = QLabel()
                label.setText("加载中...")

                # 使用QTimer延迟加载图片，避免UI阻塞
                def load_image():
                    try:
                        response = requests.get(url, timeout=5)
                        if response.status_code == 200:
                            pixmap = QPixmap()
                            pixmap.loadFromData(response.content)
                            if not pixmap.isNull():
                                label.setPixmap(pixmap.scaled(100, 60, Qt.AspectRatioMode.KeepAspectRatio))
                            else:
                                label.setText("图片加载失败")
                        else:
                            label.setText("请求失败")
                    except Exception as e:
                        label.setText(f"错误: {str(e)[:20]}")

                QTimer.singleShot(100, load_image)

                label.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
                label.mousePressEvent = lambda e: self.preview_media(url, 'image')
                item_layout.addWidget(label)

                url_label = QLabel(url)
                url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                url_label.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
                url_label.setWordWrap(True)
                item_layout.addWidget(url_label)

                preview_button = QPushButton("预览")
                preview_button.clicked.connect(lambda: self.preview_media(url, 'image'))
                item_layout.addWidget(preview_button)

                download_button = QPushButton("下载")
                download_button.clicked.connect(lambda: self.download_file(url))
                item_layout.addWidget(download_button)
            except Exception as e:
                label = QLabel(f"{url} (加载错误: {str(e)[:30]})")
                label.setWordWrap(True)
                item_layout.addWidget(label)

        elif file_type == 'video':
            label = QLabel(url)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
            label.setWordWrap(True)
            item_layout.addWidget(label)

            preview_button = QPushButton("预览")
            preview_button.clicked.connect(lambda: self.preview_media(url, 'video'))
            item_layout.addWidget(preview_button)

            download_button = QPushButton("下载")
            download_button.clicked.connect(lambda: self.download_file(url))
            item_layout.addWidget(download_button)

        else:  # 链接
            label = QLabel(url)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setCursor(QCursor(Qt.CursorShape.IBeamCursor))
            label.setWordWrap(True)
            item_layout.addWidget(label)

            open_button = QPushButton("打开")
            open_button.clicked.connect(lambda: self.preview_media(url, 'link'))
            item_layout.addWidget(open_button)

            copy_button = QPushButton("复制")
            copy_button.clicked.connect(lambda: self.copy_to_clipboard(url, copy_button))
            item_layout.addWidget(copy_button)

        item_layout.addStretch()
        self.scroll_layout.addWidget(item_widget)

    def preview_media(self, url, media_type):
        self.preview_window = PreviewWindow(url, media_type)
        self.preview_window.show()

    def download_file(self, url):
        if hasattr(self.parent, 'download_file'):
            self.parent.download_file(url)
        else:
            self.show_status(f"下载功能未实现")

    def copy_to_clipboard(self, text, button):
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

        original_text = button.text()
        button.setText("已复制")
        button.setEnabled(False)

        QTimer.singleShot(1000, lambda: self.reset_button(button, original_text))

    def reset_button(self, button, text):
        button.setText(text)
        button.setEnabled(True)

    def clear_url(self):
        self.url_input.clear()

    def start_crawling(self):
        url = self.url_input.text()
        if not url:
            self.show_status("请输入有效的网址")
            return

        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            self.url_input.setText(url)

        self.clear_results()
        self.show_status(f"开始爬取: {url}")

        self.crawler_thread = CrawlerThread(url, self.parent.browser, self.parent.browser_path)
        # 确保正确连接信号
        self.crawler_thread.update_signal.connect(self.update_ui)
        self.crawler_thread.status_signal.connect(self.show_status)
        self.crawler_thread.progress_signal.connect(self.update_progress)
        self.crawler_thread.finished.connect(self.on_crawl_finished)
        self.crawler_thread.start()

        self.crawl_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def clear_results(self):
        while self.scroll_layout.count():
            child = self.scroll_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.progress_bar.setValue(0)

    def show_status(self, message):
        status_label = QLabel(message)
        status_label.setStyleSheet("color: #2196F3; background-color: #1e1e1e; padding: 5px; border-radius: 4px;")
        # 总是插入到顶部
        self.scroll_layout.insertWidget(0, status_label)

    def stop_crawling(self):
        if self.crawler_thread and self.crawler_thread.isRunning():
            self.crawler_thread.requestInterruption()
            self.crawler_thread.wait()
            self.show_status("爬取已停止")
            self.stop_button.setEnabled(False)
            self.crawl_button.setEnabled(True)

    def on_crawl_finished(self):
        self.crawl_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

# 设置页面
class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        layout = QFormLayout(self)
        self.setStyleSheet("""
            background-color: #1e1e1e;
            color: white;
        """)

        self.color_button = QPushButton("选择主题颜色")
        self.color_button.setStyleSheet("""
            background-color: #2196F3;
            color: white;
            padding: 5px 15px;
            border: none;
            border-radius: 4px;
        """)
        self.color_button.clicked.connect(self.choose_color)
        layout.addRow("主题颜色:", self.color_button)

        self.directory_button = QPushButton("选择下载目录")
        self.directory_button.setStyleSheet("""
            background-color: #2196F3;
            color: white;
            padding: 5px 15px;
            border: none;
            border-radius: 4px;
        """)
        self.directory_button.clicked.connect(self.choose_directory)
        layout.addRow("下载目录:", self.directory_button)

        # 添加说明标签
        browser_note = QLabel("注意: 爬虫功能已优化为不需要浏览器，以下设置仅供参考")
        browser_note.setStyleSheet("color: #FFA500;")  # 橙色警告
        layout.addRow(browser_note)

        self.browser_combo = QComboBox()
        self.browser_combo.addItems(["Chrome", "Edge", "Firefox", "360浏览器"])
        self.browser_combo.setStyleSheet("""
            background-color: #1e1e1e;
            color: white;
            padding: 5px;
            border: 1px solid #333;
            border-radius: 4px;
        """)
        if hasattr(self.parent, 'browser'):
            index = self.browser_combo.findText(self.parent.browser)
            if index >= 0:
                self.browser_combo.setCurrentIndex(index)
        layout.addRow("默认浏览器(不再使用):", self.browser_combo)

        self.browser_path_input = QLineEdit()
        self.browser_path_input.setPlaceholderText("浏览器可执行文件路径 (不再使用)")
        self.browser_path_input.setStyleSheet("""
            background-color: #1e1e1e;
            color: white;
            padding: 5px;
            border: 1px solid #333;
            border-radius: 4px;
        """)
        if hasattr(self.parent, 'browser_path') and self.parent.browser_path:
            self.browser_path_input.setText(self.parent.browser_path)
        layout.addRow("浏览器路径(不再使用):", self.browser_path_input)

        # 检测到的浏览器部分可以保留，但添加说明
        detected_browsers = detect_browsers()
        if detected_browsers:
            detected_label = QLabel("检测到的浏览器(仅供参考):")
            detected_label.setStyleSheet("color: #2196F3;")
            layout.addRow(detected_label)

            for browser, path in detected_browsers.items():
                browser_label = QLabel(f"{browser}: {path}")
                browser_label.setStyleSheet("color: white; font-size: 10px;")
                layout.addRow(browser_label)

        self.background_button = QPushButton("选择背景图片")
        self.background_button.setStyleSheet("""
            background-color: #2196F3;
            color: white;
            padding: 5px 15px;
            border: none;
            border-radius: 4px;
        """)
        self.background_button.clicked.connect(self.choose_background)
        layout.addRow("背景图片:", self.background_button)

        self.remove_background_button = QPushButton("移除背景图片")
        self.remove_background_button.setStyleSheet("""
            background-color: #F44336;
            color: white;
            padding: 5px 15px;
            border: none;
            border-radius: 4px;
        """)
        self.remove_background_button.clicked.connect(self.remove_background)
        layout.addRow("", self.remove_background_button)

        self.save_button = QPushButton("保存设置")
        self.save_button.setStyleSheet("""
            background-color: #2196F3;
            color: white;
            padding: 5px 15px;
            border: none;
            border-radius: 4px;
        """)
        self.save_button.clicked.connect(self.save_settings)
        layout.addRow(self.save_button)

        self.show_current_settings()

    def show_current_settings(self):
        if hasattr(self.parent, 'download_directory'):
            self.directory_button.setToolTip(f"当前下载目录: {self.parent.download_directory}")
        if hasattr(self.parent, 'theme_color'):
            self.color_button.setToolTip(f"当前主题颜色: {self.parent.theme_color.name()}")
        if hasattr(self.parent, 'background_image') and self.parent.background_image:
            self.background_button.setToolTip(f"当前背景图片: {self.parent.background_image}")

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.parent.theme_color = color
            self.parent.apply_theme()
            self.show_current_settings()

    def choose_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "选择下载目录")
        if directory:
            self.parent.download_directory = directory
            self.show_current_settings()

    def choose_background(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "选择背景图片",
            "",
            "图片文件 (*.jpg *.jpeg *.png *.bmp)"
        )
        if file_name:
            try:
                # 获取图片目录
                images_dir = get_settings_images_path()

                # 生成目标文件名（使用原始文件名，但确保唯一性）
                base_name = os.path.basename(file_name)
                target_file = os.path.join(images_dir, base_name)

                # 如果文件已存在，添加数字后缀
                counter = 1
                name, ext = os.path.splitext(base_name)
                while os.path.exists(target_file):
                    target_file = os.path.join(images_dir, f"{name}_{counter}{ext}")
                    counter += 1

                # 复制文件
                shutil.copy2(file_name, target_file)

                # 输出调试信息
                print(f"背景图片已复制到: {target_file}")

                # 更新背景图片路径为复制后的路径
                self.parent.background_image = target_file
                self.parent.apply_theme()
                self.parent.save_settings()
                self.show_current_settings()

                # 显示成功消息并包含完整路径
                QMessageBox.information(self, "成功", f"背景图片已设置并保存到:\n{target_file}")

                # 强制刷新主题以确保背景正确显示
                self.parent.force_refresh_theme()

            except Exception as e:
                QMessageBox.warning(self, "错误", f"设置背景图片时出错: {str(e)}")
                print(f"设置背景图片时出错: {str(e)}")

    def remove_background(self):
        if hasattr(self.parent, 'background_image') and self.parent.background_image:
            reply = QMessageBox.question(self, '确认', '确定要移除背景图片吗？',
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                # 不删除文件，只移除引用
                self.parent.background_image = None
                self.parent.apply_theme()
                self.parent.save_settings()
                self.show_current_settings()
                QMessageBox.information(self, "成功", "背景图片已移除")
        else:
            QMessageBox.information(self, "提示", "当前没有设置背景图片")

    def save_settings(self):
        self.parent.browser = self.browser_combo.currentText()
        self.parent.browser_path = self.browser_path_input.text() if self.browser_path_input.text() else None
        self.parent.save_settings()
        QMessageBox.information(self, "成功", "设置已保存")
        self.show_current_settings()

# 主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("文件管理工具")
        self.setGeometry(100, 100, 1000, 600)
        self.background_image = None
        self.load_settings()

        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        sidebar = QListWidget()
        sidebar.addItems(["爬虫", "文件搜索", "文档", "媒体", "设置"])
        sidebar.setFixedWidth(200)
        sidebar.currentRowChanged.connect(self.switch_page)
        main_layout.addWidget(sidebar)

        self.stacked_widget = QStackedWidget()
        self.crawler_page = CrawlerPage(self)
        self.file_search_page = FileSearchPage(self)
        self.document_page = DocumentPage(self)
        self.media_page = MediaPage(self)
        self.settings_page = SettingsPage(self)
        self.stacked_widget.addWidget(self.crawler_page)
        self.stacked_widget.addWidget(self.file_search_page)
        self.stacked_widget.addWidget(self.document_page)
        self.stacked_widget.addWidget(self.media_page)
        self.stacked_widget.addWidget(self.settings_page)
        main_layout.addWidget(self.stacked_widget)

        self.apply_theme()

    def force_refresh_theme(self):
        """强制刷新主题，确保背景图片正确显示"""
        # 保存当前背景图片路径
        current_bg = self.background_image

        # 临时移除背景图片
        self.background_image = None
        self.apply_theme()

        # 重新应用背景图片
        self.background_image = current_bg
        self.apply_theme()

        # 更新布局以确保变更生效
        self.centralWidget().layout().update()

    def switch_page(self, index):
        self.stacked_widget.setCurrentIndex(index)
        if index == 3:  # Media page
            self.media_page.start_scan()
        elif index == 2:  # Document page
            self.document_page.start_scan()
        elif index == 0:  # Crawler page
            self.crawler_page.clear_results()

    def download_file(self, url):
        file_name = os.path.join(self.download_directory, url.split('/')[-1])
        try:
            urllib.request.urlretrieve(url, file_name)
            self.show_status(f"文件已下载到: {file_name}")
        except Exception as e:
            self.show_status(f"下载失败: {str(e)}")

    def apply_theme(self):
        darker_color = QColor(
            int(self.theme_color.red() * 0.3),
            int(self.theme_color.green() * 0.3),
            int(self.theme_color.blue() * 0.3)
        )

        background_style = ""
        if self.background_image and os.path.exists(self.background_image):
            # 将反斜杠转换为正斜杠，确保Qt样式表正确解析路径
            qt_style_path = self.background_image.replace('\\', '/')
            background_style = f"""
                background-image: url("{qt_style_path}");
                background-position: center;
                background-repeat: no-repeat;
                background-attachment: fixed;
                background-size: cover;
            """

        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {self.theme_color.name()};
                {background_style}
            }}
            QWidget#centralWidget {{
                background-color: {darker_color.name()};
                background-color: rgba({darker_color.red()}, {darker_color.green()}, {darker_color.blue()}, 0.85);
            }}
            QLineEdit {{
                background-color: {darker_color.name()};
                color: white;
                padding: 5px;
                border: 1px solid #333;
                border-radius: 4px;
            }}
            QPushButton {{
                background-color: #2196F3;
                color: white;
                padding: 5px 15px;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: #1976D2;
            }}
            QTreeWidget {{
                background-color: {darker_color.name()};
                color: white;
                border: 1px solid #333;
                border-radius: 4px;
            }}
            QTreeWidget::item:hover {{
                background-color: {self.theme_color.name()};
            }}
            QTreeWidget::item:selected {{
                background-color: #2196F3;
                color: white;
            }}
        """)

    def show_status(self, message):
        self.crawler_page.show_status(message)

    def load_settings(self):
        try:
            settings_path = get_settings_path()
            if os.path.exists(settings_path):
                with open(settings_path, 'r') as f:
                    settings = json.load(f)
                    self.theme_color = QColor(settings.get('theme_color', '#F0F0F0'))
                    self.download_directory = settings.get('download_directory', os.path.expanduser("~/Downloads"))
                    self.browser = settings.get('browser', 'Chrome')
                    self.browser_path = settings.get('browser_path', None)
                    self.background_image = settings.get('background_image', None)
            else:
                self.theme_color = QColor(240, 240, 240)
                self.download_directory = os.path.expanduser("~/Downloads")
                self.browser = 'Chrome'
                self.browser_path = None
                self.background_image = None
        except Exception as e:
            print(f"加载设置时出错: {str(e)}")
            # 使用默认设置
            self.theme_color = QColor(240, 240, 240)
            self.download_directory = os.path.expanduser("~/Downloads")
            self.browser = 'Chrome'
            self.browser_path = None
            self.background_image = None

    def save_settings(self):
        try:
            settings = {
                'theme_color': self.theme_color.name(),
                'download_directory': self.download_directory,
                'browser': self.browser,
                'browser_path': self.browser_path,
                'background_image': self.background_image
            }

            settings_path = get_settings_path()
            with open(settings_path, 'w') as f:
                json.dump(settings, f)
        except Exception as e:
            print(f"保存设置时出错: {str(e)}")
            self.show_status(f"保存设置失败: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)

    # 设置应用程序图标
    try:
        app_icon_path = os.path.join(get_base_path(), "app_icon.ico")
        if os.path.exists(app_icon_path):
            app.setWindowIcon(QIcon(app_icon_path))
        else:
            # 如果图标文件不存在，使用默认图标
            pass
    except Exception as e:
        print(f"设置应用图标时出错: {str(e)}")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())