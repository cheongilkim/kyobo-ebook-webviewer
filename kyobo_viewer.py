#!/usr/bin/env python3
"""
Kyobo eBook Linux WebViewer
교보문고 eBook / 전자도서관 공식 웹뷰어를 리눅스 네이티브 앱처럼 사용하기 위한 GTK3 + WebKit2 래퍼.
"""

import json
import os
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Soup", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, Gio, GLib, Gtk, Soup, WebKit2  # noqa: E402

APP_ID = "kr.local.kyobo-webviewer"
APP_TITLE = "교보 eBook 웹뷰어"

CONFIG_DIR = Path.home() / ".config" / "kyobo-webviewer"
DATA_DIR = Path.home() / ".local" / "share" / "kyobo-webviewer"
BOOKMARKS_FILE = CONFIG_DIR / "bookmarks.json"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
SESSION_COOKIES_FILE = DATA_DIR / "session_cookies.json"
CHROME_PROFILE_DIR = DATA_DIR / "chrome-profile"

CHROME_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
)

DEFAULT_BOOKMARKS = [
    {
        "name": "교보문고 eBook",
        "url": "https://ebook.kyobobook.co.kr",
        "desc": "교보문고 eBook 스토어 및 서재",
    },
    {
        "name": "교보문고 내 서재",
        "url": "https://my.kyobobook.co.kr",
        "desc": "마이페이지 · 구매 도서 확인",
    },
    {
        "name": "교보문고 전자도서관",
        "url": "https://elib.kyobobook.co.kr",
        "desc": "학교/공공기관 전자도서관 바로보기",
    },
    {
        "name": "교보문고 sam",
        "url": "https://sam.kyobobook.co.kr",
        "desc": "구독형 전자책 서비스",
    },
]

THEME_STYLES = {
    "normal": "",
    "sepia": (
        "html { filter: sepia(0.32) contrast(0.96) brightness(0.97) !important; }"
    ),
    "dim": (
        "html { filter: brightness(0.80) contrast(0.95) !important; }"
    ),
    "dark": (
        "html { filter: invert(0.90) hue-rotate(180deg) !important; background: #121212 !important; }"
        "img, video, canvas, svg { filter: invert(1) hue-rotate(180deg) !important; }"
    ),
}

THEME_LABELS = {
    "normal": "기본",
    "sepia": "세피아",
    "dim": "저조도",
    "dark": "다크",
}


def is_safe_http_url(url):
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def ensure_dirs():
    for d in (CONFIG_DIR, DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(d, 0o700)
        except OSError:
            pass


def load_bookmarks():
    ensure_dirs()
    if BOOKMARKS_FILE.exists():
        try:
            data = json.loads(BOOKMARKS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
    save_bookmarks(DEFAULT_BOOKMARKS)
    return list(DEFAULT_BOOKMARKS)


def save_bookmarks(bookmarks):
    ensure_dirs()
    BOOKMARKS_FILE.write_text(
        json.dumps(bookmarks, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_settings():
    ensure_dirs()
    defaults = {"theme": "normal", "zoom": 1.0, "width": 1220, "height": 840}
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                defaults.update(data)
        except Exception:
            pass
    return defaults


def save_settings(settings):
    ensure_dirs()
    SETTINGS_FILE.write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_home_html(bookmarks):
    cards = []
    for idx, bm in enumerate(bookmarks):
        raw_url = bm.get("url", "").strip()
        if not is_safe_http_url(raw_url):
            continue
        name = GLib.markup_escape_text(bm.get("name", ""))
        url = GLib.markup_escape_text(raw_url)
        desc = GLib.markup_escape_text(bm.get("desc", raw_url))
        cards.append(
            f"""
            <a class="card" href="{url}">
              <div class="card-badge">{idx + 1}</div>
              <div class="card-title">{name}</div>
              <div class="card-desc">{desc}</div>
              <div class="card-url">{url}</div>
            </a>
            """
        )
    cards_html = "\n".join(cards)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{APP_TITLE}</title>
<style>
  :root {{
    --bg: #f4f6f9;
    --card: #ffffff;
    --text: #1c2430;
    --muted: #5c687a;
    --accent: #2a6f97;
    --border: #dfe5ee;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: "Noto Sans CJK KR", "Malgun Gothic", system-ui, sans-serif;
    background: var(--bg);
    color: var(--text);
    display: flex;
    justify-content: center;
    padding: 48px 24px;
  }}
  .wrap {{
    width: 100%;
    max-width: 920px;
  }}
  header {{
    margin-bottom: 28px;
  }}
  h1 {{
    margin: 0 0 8px 0;
    font-size: 28px;
    font-weight: 700;
  }}
  .subtitle {{
    color: var(--muted);
    font-size: 14px;
    line-height: 1.6;
  }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 16px;
    margin-top: 24px;
  }}
  .card {{
    display: block;
    text-decoration: none;
    color: inherit;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 20px;
    transition: transform 0.14s ease, box-shadow 0.14s ease, border-color 0.14s ease;
  }}
  .card:hover {{
    transform: translateY(-2px);
    border-color: var(--accent);
    box-shadow: 0 8px 22px rgba(29, 53, 87, 0.08);
  }}
  .card-badge {{
    width: 26px;
    height: 26px;
    border-radius: 8px;
    background: #e6f2f8;
    color: var(--accent);
    font-weight: 700;
    font-size: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 12px;
  }}
  .card-title {{
    font-size: 17px;
    font-weight: 700;
    margin-bottom: 6px;
  }}
  .card-desc {{
    font-size: 13px;
    color: var(--muted);
    margin-bottom: 10px;
  }}
  .card-url {{
    font-size: 12px;
    color: var(--accent);
    word-break: break-all;
  }}
  .tips {{
    margin-top: 32px;
    background: #eef4f8;
    border-radius: 12px;
    padding: 16px 20px;
    font-size: 13px;
    color: #324457;
    line-height: 1.7;
  }}
  .tips code {{
    background: #dce8f0;
    padding: 2px 6px;
    border-radius: 5px;
    font-size: 12px;
  }}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>{APP_TITLE}</h1>
      <div class="subtitle">
        교보문고 eBook 및 소속 전자도서관 웹뷰어를 리눅스에서 쾌적하게 읽기 위한 전용 뷰어입니다.<br>
        상단 툴바의 <b>+ 도서관 추가</b> 버튼으로 학교/지자체 전자도서관 주소를 저장할 수 있습니다.
      </div>
    </header>
    <div class="grid">
      {cards_html}
    </div>
    <div class="tips">
      <b>단축키 안내:</b>
      <code>F11</code> 전체 화면 ·
      <code>Ctrl+B</code> 툴바 숨김/표시 (집중 독서) ·
      <code>Ctrl++</code> / <code>Ctrl+-</code> / <code>Ctrl+0</code> 화면 확대/축소 ·
      <code>Alt+←</code> / <code>Alt+→</code> 뒤로/앞으로<br>
      ※ 일부 전자도서관 웹뷰어가 Chrome 전용 스크립트를 요구할 경우, 상단 <b>Chrome 앱으로 열기</b> 버튼을 눌러 독립 앱 창으로 실행할 수 있습니다.
    </div>
  </div>
</body>
</html>
"""


def create_web_context():
    ensure_dirs()
    data_manager = WebKit2.WebsiteDataManager(
        base_data_directory=str(DATA_DIR / "webkit-data"),
        base_cache_directory=str(DATA_DIR / "webkit-cache"),
    )
    # 크로스 도메인 SSO(mmbr/sam/ebook/네이버/카카오) 쿠키 차단 방지
    data_manager.set_itp_enabled(False)
    data_manager.set_persistent_credential_storage_enabled(True)

    context = WebKit2.WebContext.new_with_website_data_manager(data_manager)
    cookie_manager = data_manager.get_cookie_manager()
    cookie_db = DATA_DIR / "cookies.sqlite"
    cookie_manager.set_persistent_storage(
        str(cookie_db),
        WebKit2.CookiePersistentStorage.SQLITE,
    )
    if cookie_db.exists():
        try:
            os.chmod(cookie_db, 0o600)
        except OSError:
            pass
    cookie_manager.set_accept_policy(WebKit2.CookieAcceptPolicy.ALWAYS)
    return context, cookie_manager


def serialize_cookie(cookie):
    expires = cookie.get_expires()
    return {
        "name": cookie.get_name(),
        "value": cookie.get_value(),
        "domain": cookie.get_domain(),
        "path": cookie.get_path() or "/",
        "expires": expires.to_unix() if expires is not None else None,
        "secure": cookie.get_secure(),
        "http_only": cookie.get_http_only(),
        "same_site": int(cookie.get_same_site_policy()),
    }


def save_session_cookies_async(cookie_manager, on_done=None):
    def _on_ready(cm, result):
        try:
            cookies = cm.get_all_cookies_finish(result)
            # 만료일이 없는 세션 쿠키를 별도 파일에 백업 (앱 재시작 시 복원용)
            session_only = []
            for c in cookies:
                if c.get_expires() is None:
                    session_only.append(serialize_cookie(c))
            ensure_dirs()
            tmp = SESSION_COOKIES_FILE.with_suffix(".tmp")
            payload = json.dumps(session_only, ensure_ascii=False).encode("utf-8")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                os.write(fd, payload)
            finally:
                os.close(fd)
            tmp.replace(SESSION_COOKIES_FILE)
        except Exception:
            pass
        finally:
            if on_done:
                on_done()

    cookie_manager.get_all_cookies(None, _on_ready)


def restore_session_cookies(cookie_manager):
    if not SESSION_COOKIES_FILE.exists():
        return
    try:
        items = json.loads(SESSION_COOKIES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(items, list):
        return

    for item in items:
        try:
            name = item.get("name")
            value = item.get("value")
            domain = item.get("domain")
            path = item.get("path") or "/"
            if not (name and domain is not None):
                continue
            cookie = Soup.Cookie.new(name, value or "", domain, path, -1)
            cookie.set_secure(bool(item.get("secure", False)))
            cookie.set_http_only(bool(item.get("http_only", False)))
            same_site = item.get("same_site")
            if isinstance(same_site, int):
                try:
                    cookie.set_same_site_policy(Soup.SameSitePolicy(same_site))
                except Exception:
                    pass
            cookie_manager.add_cookie(cookie, None, None, None)
        except Exception:
            continue


def run_js(webview, script):
    if hasattr(webview, "evaluate_javascript"):
        webview.evaluate_javascript(script, -1, None, None, None, None, None)
    else:
        webview.run_javascript(script, None, None, None)


def configure_webkit_settings(webview):
    settings = webview.get_settings()
    settings.set_user_agent(CHROME_USER_AGENT)
    settings.set_enable_javascript(True)
    settings.set_javascript_can_open_windows_automatically(True)
    settings.set_enable_html5_local_storage(True)
    settings.set_enable_html5_database(True)
    settings.set_enable_smooth_scrolling(True)
    settings.set_enable_developer_extras(True)


class ReaderPopupWindow(Gtk.Window):
    """웹뷰어 [바로보기] 클릭 시 열리는 독서 전용 팝업 창."""

    def __init__(self, parent_window, related_view):
        super().__init__(title=f"{APP_TITLE} — 독서 창")
        self.parent_window = parent_window
        self.is_fullscreen = False
        self.toolbar_visible = True

        self.set_default_size(1100, 820)
        self._apply_icon()

        self.webview = WebKit2.WebView.new_with_related_view(related_view)
        configure_webkit_settings(self.webview)
        self.webview.set_zoom_level(parent_window.settings.get("zoom", 1.0))

        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.set_title("독서 창")
        self.set_titlebar(self.header)

        # 테마 선택
        self.theme_combo = Gtk.ComboBoxText()
        for key, label in THEME_LABELS.items():
            self.theme_combo.append(key, label)
        self.theme_combo.set_active_id(parent_window.current_theme)
        self.theme_combo.connect("changed", self.on_theme_changed)
        self.header.pack_start(self.theme_combo)

        # Chrome 앱으로 열기 버튼
        chrome_btn = Gtk.Button(label="Chrome 앱")
        chrome_btn.set_tooltip_text("현재 웹뷰어를 독립 Chrome 앱 창으로 열기")
        chrome_btn.connect("clicked", self.on_open_chrome)
        self.header.pack_end(chrome_btn)

        # 전체화면 버튼
        fs_btn = Gtk.Button.new_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.BUTTON)
        fs_btn.set_tooltip_text("전체 화면 (F11)")
        fs_btn.connect("clicked", lambda *_: self.toggle_fullscreen())
        self.header.pack_end(fs_btn)

        self.add(self.webview)

        self.webview.connect("ready-to-show", self.on_ready_to_show)
        self.webview.connect("notify::title", self.on_title_changed)
        self.webview.connect("close", lambda *_: self.destroy())
        self.webview.connect("load-changed", self.on_load_changed)
        self.webview.connect("create", self.on_create_popup)
        self.connect("key-press-event", self.on_key_press)

    def on_create_popup(self, webview, _navigation_action):
        popup = ReaderPopupWindow(self.parent_window, webview)
        return popup.webview

    def _apply_icon(self):
        icon_path = Path(__file__).resolve().parent / "icon.svg"
        if icon_path.exists():
            try:
                self.set_icon_from_file(str(icon_path))
            except Exception:
                pass

    def on_ready_to_show(self, _webview):
        self.show_all()

    def on_title_changed(self, webview, _param):
        title = webview.get_title() or "독서 창"
        self.header.set_title(title)
        self.set_title(title)

    def on_load_changed(self, _webview, event):
        if event in (WebKit2.LoadEvent.COMMITTED, WebKit2.LoadEvent.FINISHED):
            self.apply_theme(self.theme_combo.get_active_id() or "normal")

    def on_theme_changed(self, combo):
        self.apply_theme(combo.get_active_id() or "normal")

    def apply_theme(self, theme_id):
        css = THEME_STYLES.get(theme_id, "")
        js = f"""
        (function() {{
            let el = document.getElementById('__kyobo_linux_theme');
            if (!el) {{
                el = document.createElement('style');
                el.id = '__kyobo_linux_theme';
                (document.head || document.documentElement).appendChild(el);
            }}
            el.textContent = {json.dumps(css)};
        }})();
        """
        run_js(self.webview, js)

    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.unfullscreen()
            self.is_fullscreen = False
        else:
            self.fullscreen()
            self.is_fullscreen = True

    def on_open_chrome(self, _btn):
        uri = self.webview.get_uri()
        if uri and uri.startswith(("http://", "https://")):
            self.parent_window.launch_chrome_app(uri)

    def on_key_press(self, _widget, event):
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        if event.keyval == Gdk.KEY_F11:
            self.toggle_fullscreen()
            return True
        if ctrl and event.keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
            self.webview.set_zoom_level(min(2.5, self.webview.get_zoom_level() + 0.1))
            return True
        if ctrl and event.keyval in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
            self.webview.set_zoom_level(max(0.5, self.webview.get_zoom_level() - 0.1))
            return True
        if ctrl and event.keyval == Gdk.KEY_0:
            self.webview.set_zoom_level(1.0)
            return True
        return False


class KyoboViewerWindow(Gtk.ApplicationWindow):
    def __init__(self, app, start_url=None):
        super().__init__(application=app, title=APP_TITLE)
        self.bookmarks = load_bookmarks()
        self.settings = load_settings()
        self.current_theme = self.settings.get("theme", "normal")
        self.is_fullscreen = False
        self.toolbar_visible = True

        self.set_default_size(
            int(self.settings.get("width", 1220)),
            int(self.settings.get("height", 840)),
        )
        self._apply_icon()

        self.web_context, self.cookie_manager = create_web_context()
        restore_session_cookies(self.cookie_manager)
        self._cookie_save_timer = None
        self.cookie_manager.connect("changed", self.on_cookies_changed)

        self.webview = WebKit2.WebView.new_with_context(self.web_context)
        configure_webkit_settings(self.webview)
        self.webview.set_zoom_level(float(self.settings.get("zoom", 1.0)))

        # 레이아웃
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(root)

        # 상단 툴바
        self.toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.toolbar.set_border_width(6)
        root.pack_start(self.toolbar, False, False, 0)

        self.back_btn = Gtk.Button.new_from_icon_name("go-previous-symbolic", Gtk.IconSize.BUTTON)
        self.back_btn.set_tooltip_text("뒤로 (Alt+←)")
        self.back_btn.connect("clicked", lambda *_: self.webview.go_back())
        self.toolbar.pack_start(self.back_btn, False, False, 0)

        self.fwd_btn = Gtk.Button.new_from_icon_name("go-next-symbolic", Gtk.IconSize.BUTTON)
        self.fwd_btn.set_tooltip_text("앞으로 (Alt+→)")
        self.fwd_btn.connect("clicked", lambda *_: self.webview.go_forward())
        self.toolbar.pack_start(self.fwd_btn, False, False, 0)

        reload_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic", Gtk.IconSize.BUTTON)
        reload_btn.set_tooltip_text("새로고침 (F5)")
        reload_btn.connect("clicked", lambda *_: self.webview.reload())
        self.toolbar.pack_start(reload_btn, False, False, 0)

        home_btn = Gtk.Button.new_from_icon_name("go-home-symbolic", Gtk.IconSize.BUTTON)
        home_btn.set_tooltip_text("홈 (내 서재 대시보드)")
        home_btn.connect("clicked", lambda *_: self.load_home())
        self.toolbar.pack_start(home_btn, False, False, 0)

        # URL 입력창
        self.url_entry = Gtk.Entry()
        self.url_entry.set_placeholder_text("전자도서관 또는 교보문고 URL 입력 후 Enter")
        self.url_entry.connect("activate", self.on_url_activate)
        self.toolbar.pack_start(self.url_entry, True, True, 0)

        # 도서관 북마크 추가
        add_bm_btn = Gtk.Button(label="+ 도서관 추가")
        add_bm_btn.set_tooltip_text("자주 쓰는 전자도서관/서재 URL을 홈 화면에 저장")
        add_bm_btn.connect("clicked", self.on_add_bookmark)
        self.toolbar.pack_start(add_bm_btn, False, False, 0)

        # 독서 테마 선택
        self.theme_combo = Gtk.ComboBoxText()
        for key, label in THEME_LABELS.items():
            self.theme_combo.append(key, label)
        self.theme_combo.set_active_id(self.current_theme)
        self.theme_combo.set_tooltip_text("독서 화면 색상 필터")
        self.theme_combo.connect("changed", self.on_theme_changed)
        self.toolbar.pack_start(self.theme_combo, False, False, 0)

        # Chrome 앱 모드로 열기
        chrome_btn = Gtk.Button(label="Chrome 앱")
        chrome_btn.set_tooltip_text("현재 페이지를 독립 Chrome 앱 창으로 열기 (호환성 폴백)")
        chrome_btn.connect("clicked", self.on_open_chrome_app)
        self.toolbar.pack_start(chrome_btn, False, False, 0)

        # 전체화면
        fs_btn = Gtk.Button.new_from_icon_name("view-fullscreen-symbolic", Gtk.IconSize.BUTTON)
        fs_btn.set_tooltip_text("전체 화면 (F11)")
        fs_btn.connect("clicked", lambda *_: self.toggle_fullscreen())
        self.toolbar.pack_start(fs_btn, False, False, 0)

        # 로딩 바
        self.progress = Gtk.ProgressBar()
        self.progress.set_no_show_all(True)
        root.pack_start(self.progress, False, False, 0)

        # 웹뷰 본문
        root.pack_start(self.webview, True, True, 0)

        # 시그널 연결
        self.webview.connect("load-changed", self.on_load_changed)
        self.webview.connect("notify::estimated-load-progress", self.on_progress_changed)
        self.webview.connect("notify::uri", self.on_uri_changed)
        self.webview.connect("notify::title", self.on_title_changed)
        self.webview.connect("create", self.on_create_popup)
        self.connect("key-press-event", self.on_key_press)
        self.connect("delete-event", self.on_close)

        if start_url:
            self.navigate(start_url)
        else:
            self.load_home()

    def _apply_icon(self):
        icon_path = Path(__file__).resolve().parent / "icon.svg"
        if icon_path.exists():
            try:
                self.set_icon_from_file(str(icon_path))
            except Exception:
                pass

    def load_home(self):
        self.bookmarks = load_bookmarks()
        html = build_home_html(self.bookmarks)
        self.webview.load_html(html, "kyobo://home")
        self.url_entry.set_text("")
        self.set_title(APP_TITLE)

    def navigate(self, raw_url):
        url = raw_url.strip()
        if not url:
            self.load_home()
            return
        if not urllib.parse.urlparse(url).scheme:
            url = "https://" + url
        if not is_safe_http_url(url):
            return
        self.webview.load_uri(url)

    def on_url_activate(self, entry):
        self.navigate(entry.get_text())

    def on_uri_changed(self, webview, _param):
        uri = webview.get_uri() or ""
        if uri.startswith("kyobo://"):
            self.url_entry.set_text("")
        else:
            self.url_entry.set_text(uri)
        self.back_btn.set_sensitive(webview.can_go_back())
        self.fwd_btn.set_sensitive(webview.can_go_forward())

    def on_title_changed(self, webview, _param):
        title = webview.get_title()
        self.set_title(f"{title} — {APP_TITLE}" if title else APP_TITLE)

    def on_progress_changed(self, webview, _param):
        frac = webview.get_estimated_load_progress()
        if 0.0 < frac < 1.0:
            self.progress.set_fraction(frac)
            self.progress.show()
        else:
            self.progress.hide()

    def on_load_changed(self, _webview, event):
        if event in (WebKit2.LoadEvent.COMMITTED, WebKit2.LoadEvent.FINISHED):
            self.apply_theme(self.current_theme)
            self.back_btn.set_sensitive(self.webview.can_go_back())
            self.fwd_btn.set_sensitive(self.webview.can_go_forward())

    def on_create_popup(self, webview, _navigation_action):
        popup = ReaderPopupWindow(self, webview)
        return popup.webview

    def on_theme_changed(self, combo):
        self.current_theme = combo.get_active_id() or "normal"
        self.settings["theme"] = self.current_theme
        save_settings(self.settings)
        self.apply_theme(self.current_theme)

    def apply_theme(self, theme_id):
        css = THEME_STYLES.get(theme_id, "")
        js = f"""
        (function() {{
            let el = document.getElementById('__kyobo_linux_theme');
            if (!el) {{
                el = document.createElement('style');
                el.id = '__kyobo_linux_theme';
                (document.head || document.documentElement).appendChild(el);
            }}
            el.textContent = {json.dumps(css)};
        }})();
        """
        run_js(self.webview, js)

    def on_add_bookmark(self, _btn):
        dialog = Gtk.Dialog(
            title="도서관 / 서재 추가",
            transient_for=self,
            flags=Gtk.DialogFlags.MODAL,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK,
            Gtk.ResponseType.OK,
        )
        box = dialog.get_content_area()
        box.set_spacing(8)
        box.set_border_width(12)

        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("이름 (예: OO대학교 전자도서관)")
        current_title = self.webview.get_title() or ""
        if current_title and current_title != APP_TITLE:
            name_entry.set_text(current_title)

        url_entry = Gtk.Entry()
        url_entry.set_placeholder_text("URL (예: https://...)")
        current_uri = self.webview.get_uri() or ""
        if current_uri.startswith(("http://", "https://")):
            url_entry.set_text(current_uri)

        desc_entry = Gtk.Entry()
        desc_entry.set_placeholder_text("간단한 설명 (선택)")

        box.add(Gtk.Label(label="도서관/서재 이름:", xalign=0))
        box.add(name_entry)
        box.add(Gtk.Label(label="웹 주소 (URL):", xalign=0))
        box.add(url_entry)
        box.add(Gtk.Label(label="설명:", xalign=0))
        box.add(desc_entry)
        dialog.show_all()

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            name = name_entry.get_text().strip()
            url = url_entry.get_text().strip()
            desc = desc_entry.get_text().strip()
            if name and url:
                if not urllib.parse.urlparse(url).scheme:
                    url = "https://" + url
                if is_safe_http_url(url):
                    self.bookmarks.append({"name": name, "url": url, "desc": desc or url})
                    save_bookmarks(self.bookmarks)
                    if (self.webview.get_uri() or "").startswith("kyobo://"):
                        self.load_home()
        dialog.destroy()

    def launch_chrome_app(self, url):
        if not is_safe_http_url(url):
            return
        chrome = (
            shutil.which("google-chrome")
            or shutil.which("chromium")
            or shutil.which("chromium-browser")
        )
        if not chrome:
            dlg = Gtk.MessageDialog(
                transient_for=self,
                flags=Gtk.DialogFlags.MODAL,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text="Chrome 또는 Chromium을 찾을 수 없습니다.",
            )
            dlg.run()
            dlg.destroy()
            return

        CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(
            [
                chrome,
                f"--user-data-dir={CHROME_PROFILE_DIR}",
                f"--app={url}",
                "--class=KyoboWebViewer",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def on_open_chrome_app(self, _btn):
        uri = self.webview.get_uri() or ""
        target = uri if uri.startswith(("http://", "https://")) else "https://elib.kyobobook.co.kr"
        self.launch_chrome_app(target)

    def toggle_fullscreen(self):
        if self.is_fullscreen:
            self.unfullscreen()
            self.is_fullscreen = False
        else:
            self.fullscreen()
            self.is_fullscreen = True

    def toggle_toolbar(self):
        self.toolbar_visible = not self.toolbar_visible
        self.toolbar.set_visible(self.toolbar_visible)

    def on_key_press(self, _widget, event):
        ctrl = bool(event.state & Gdk.ModifierType.CONTROL_MASK)
        alt = bool(event.state & Gdk.ModifierType.MOD1_MASK)

        if event.keyval == Gdk.KEY_F11:
            self.toggle_fullscreen()
            return True
        if event.keyval == Gdk.KEY_F5:
            self.webview.reload()
            return True
        if ctrl and event.keyval in (Gdk.KEY_b, Gdk.KEY_B):
            self.toggle_toolbar()
            return True
        if ctrl and event.keyval in (Gdk.KEY_l, Gdk.KEY_L):
            if not self.toolbar_visible:
                self.toggle_toolbar()
            self.url_entry.grab_focus()
            return True
        if ctrl and event.keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
            z = min(2.5, round(self.webview.get_zoom_level() + 0.1, 2))
            self.webview.set_zoom_level(z)
            self.settings["zoom"] = z
            return True
        if ctrl and event.keyval in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
            z = max(0.5, round(self.webview.get_zoom_level() - 0.1, 2))
            self.webview.set_zoom_level(z)
            self.settings["zoom"] = z
            return True
        if ctrl and event.keyval == Gdk.KEY_0:
            self.webview.set_zoom_level(1.0)
            self.settings["zoom"] = 1.0
            return True
        if alt and event.keyval == Gdk.KEY_Left:
            self.webview.go_back()
            return True
        if alt and event.keyval == Gdk.KEY_Right:
            self.webview.go_forward()
            return True
        return False

    def on_cookies_changed(self, _cookie_manager):
        if self._cookie_save_timer is not None:
            GLib.source_remove(self._cookie_save_timer)
        self._cookie_save_timer = GLib.timeout_add(
            1200, self._flush_session_cookies
        )

    def _flush_session_cookies(self):
        self._cookie_save_timer = None
        save_session_cookies_async(self.cookie_manager)
        return False

    def on_close(self, *_args):
        w, h = self.get_size()
        self.settings["width"] = w
        self.settings["height"] = h
        self.settings["zoom"] = round(self.webview.get_zoom_level(), 2)
        save_settings(self.settings)

        # 종료 직전 세션 쿠키를 동기적으로 저장 완료 대기 (최대 1초)
        done = {"ok": False}

        def _done():
            done["ok"] = True

        save_session_cookies_async(self.cookie_manager, on_done=_done)
        ctx = GLib.MainContext.default()
        deadline = GLib.get_monotonic_time() + 1_000_000
        while not done["ok"] and GLib.get_monotonic_time() < deadline:
            ctx.iteration(False)
        return False


class KyoboViewerApp(Gtk.Application):
    def __init__(self, start_url=None):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.start_url = start_url
        self.win = None

    def do_activate(self):
        if not self.win:
            self.win = KyoboViewerWindow(self, start_url=self.start_url)
        self.win.show_all()
        self.win.present()


def main():
    start_url = sys.argv[1] if len(sys.argv) > 1 else None
    app = KyoboViewerApp(start_url=start_url)
    sys.exit(app.run([]))


if __name__ == "__main__":
    main()
