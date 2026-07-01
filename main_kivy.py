# -*- coding: utf-8 -*-
"""
AI线号识别系统 — Kivy 跨平台版
支持 Windows / Linux / Android
核心功能：Excel 加载、线号搜索、核线标记、UDP 通信
"""
import sys
import os
import io
import socket
import threading
import queue
import hashlib
import tempfile
from datetime import datetime
from copy import copy

# 解决 GBK 编码问题
if sys.stdout and hasattr(sys.stdout, 'encoding') and sys.stdout.encoding and sys.stdout.encoding.upper() != "UTF-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

import pandas as pd
import kivy
kivy.require("2.0.0")

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.progressbar import ProgressBar
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleboxlayout import RecycleBoxLayout
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ObjectProperty
from kivy.metrics import dp, sp
from kivy.utils import platform
from kivy.lang import Builder

# ── 平台适配 ────────────────────────────────────────────
IS_ANDROID = platform == "android"
IS_WINDOWS = platform == "win"
IS_LINUX = platform == "linux"

if IS_ANDROID:
    try:
        from android.permissions import request_permissions, Permission  # type: ignore
        request_permissions([Permission.READ_EXTERNAL_STORAGE, Permission.WRITE_EXTERNAL_STORAGE])
    except ImportError:
        pass

# ── 常量 ────────────────────────────────────────────────
ACTIVATION_SECRET = "AI_LINE_RECOGNITION_2026_PRIVATE_KEY"
UDP_PORT = 8888
REQUIRED_FIELDS = ("线号", "起始位置", "起始设备", "连接点", "线径", "线型", "颜色", "电缆号")
CARD_FIELDS = (
    ("线号", "_line_no"),
    ("起始位置", "_start_pos"),
    ("起始设备", "_start_dev"),
    ("终止设备", "_end_dev"),
    ("连接点", "_conn_point"),
    ("线型", "_wire_type"),
    ("线径", "_wire_diam"),
    ("颜色", "_color"),
    ("电缆号", "_cable_no"),
)

# ── KV 界面定义 ──────────────────────────────────────────

KV = """
<ResultCard>:
    size_hint_y: None
    height: dp(120)
    padding: dp(8)
    canvas.before:
        Color:
            rgba: (0.86, 0.96, 0.91, 1) if root.checked else (1, 1, 1, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(8)]
    BoxLayout:
        orientation: 'vertical'
        spacing: dp(4)
        BoxLayout:
            size_hint_y: None
            height: dp(20)
            Label:
                text: f'#{root.index}'
                size_hint_x: 0.3
                halign: 'left'
                color: (0.58, 0.65, 0.72, 1)
                font_size: sp(11)
            Label:
                text: '✅ 已核线' if root.checked else ''
                size_hint_x: 0.7
                halign: 'right'
                color: (0.09, 0.40, 0.20, 1)
                font_size: sp(11)
        GridLayout:
            cols: 3
            spacing: dp(4)
            size_hint_y: None
            height: dp(80)
            Label:
                text: f'线号\\n[root.line_no]'
                markup: True
                halign: 'center'
                font_size: sp(13)
                bold: True
            Label:
                text: f'起始\\n[root.start_pos]'
                markup: True
                halign: 'center'
                font_size: sp(11)
            Label:
                text: f'设备\\n[root.start_dev]'
                markup: True
                halign: 'center'
                font_size: sp(11)

<MainScreen>:
    BoxLayout:
        orientation: 'vertical'
        # 标题栏
        BoxLayout:
            size_hint_y: None
            height: dp(56)
            padding: [dp(12), dp(8)]
            canvas.before:
                Color:
                    rgba: (0.12, 0.25, 0.69, 1)
                Rectangle:
                    pos: self.pos
                    size: self.size
            Label:
                text: '🔌 线号识别'
                font_size: sp(20)
                bold: True
                color: (1, 1, 1, 1)
                halign: 'left'
                size_hint_x: 0.6
            Label:
                id: status_label
                text: root.status_text
                font_size: sp(12)
                color: (0.8, 0.85, 1, 1)
                halign: 'right'
                size_hint_x: 0.4

        # 统计行
        BoxLayout:
            size_hint_y: None
            height: dp(80)
            padding: [dp(8), dp(4)]
            BoxLayout:
                orientation: 'vertical'
                Label:
                    text: str(root.total_count)
                    font_size: sp(28)
                    bold: True
                    color: (0.23, 0.51, 0.96, 1)
                Label:
                    text: '总条数'
                    font_size: sp(11)
                    color: (0.58, 0.65, 0.72, 1)
            BoxLayout:
                orientation: 'vertical'
                Label:
                    text: str(root.checked_count)
                    font_size: sp(28)
                    bold: True
                    color: (0.13, 0.77, 0.36, 1)
                Label:
                    text: '已核线'
                    font_size: sp(11)
                    color: (0.58, 0.65, 0.72, 1)
            BoxLayout:
                orientation: 'vertical'
                Label:
                    text: str(root.remain_count)
                    font_size: sp(28)
                    bold: True
                    color: (0.94, 0.27, 0.27, 1)
                Label:
                    text: '剩余'
                    font_size: sp(11)
                    color: (0.58, 0.65, 0.72, 1)

        # 进度条
        ProgressBar:
            id: progress_bar
            size_hint_y: None
            height: dp(8)
            max: 100
            value: root.progress_percent
            canvas.before:
                Color:
                    rgba: (0.87, 0.9, 0.94, 1)
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [dp(4)]
            canvas.after:
                Color:
                    rgba: (0.13, 0.77, 0.36, 1) if root.progress_percent < 100 else (0.23, 0.51, 0.96, 1)
                RoundedRectangle:
                    pos: self.pos
                    size: [self.width * self.value_normalized, self.height]
                    radius: [dp(4)]

        # Sheet 选择 + 文件信息
        BoxLayout:
            size_hint_y: None
            height: dp(44)
            padding: [dp(12), dp(4)]
            spacing: dp(8)
            Label:
                text: f'📄 {root.current_sheet}'
                size_hint_x: 0.5
                halign: 'left'
                font_size: sp(13)
                color: (0.3, 0.37, 0.45, 1)
            Button:
                text: '切换工作表'
                size_hint_x: 0.3
                font_size: sp(12)
                background_normal: ''
                background_color: (0.23, 0.51, 0.96, 1)
                color: (1, 1, 1, 1)
                on_release: root.show_sheet_selector()
            Button:
                text: '📁 换文件'
                size_hint_x: 0.2
                font_size: sp(12)
                background_normal: ''
                background_color: (0.5, 0.56, 0.64, 1)
                color: (1, 1, 1, 1)
                on_release: root.goto_file_screen()

        # 搜索栏
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            padding: [dp(8), dp(4)]
            spacing: dp(6)
            TextInput:
                id: search_input
                hint_text: '输入线号搜索...'
                font_size: sp(16)
                multiline: False
                size_hint_x: 0.75
                on_text_validate: root.do_search()
            Button:
                text: '🔍'
                size_hint_x: 0.15
                font_size: sp(18)
                background_normal: ''
                background_color: (0.23, 0.51, 0.96, 1)
                color: (1, 1, 1, 1)
                on_release: root.do_search()
            Button:
                text: '全部'
                size_hint_x: 0.1
                font_size: sp(11)
                background_normal: ''
                background_color: (0.5, 0.56, 0.64, 1)
                color: (1, 1, 1, 1)
                on_release: root.show_all()

        # 结果列表
        RecycleView:
            id: result_list
            viewclass: 'ResultCard'
            RecycleBoxLayout:
                default_size: None, dp(120)
                default_size_hint: 1, None
                size_hint_y: None
                height: self.minimum_height
                orientation: 'vertical'
                spacing: dp(4)
                padding: dp(8)

        # 底部 UDP 状态
        BoxLayout:
            size_hint_y: None
            height: dp(32)
            padding: [dp(12), dp(4)]
            Label:
                id: udp_label
                text: root.udp_text
                font_size: sp(11)
                color: (0.58, 0.65, 0.72, 1)
                halign: 'left'

<FileScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(24)
        spacing: dp(16)

        Label:
            text: '📂 加载 Excel 文件'
            font_size: sp(24)
            bold: True
            size_hint_y: None
            height: dp(60)

        Label:
            text: '输入文件路径或上传'
            font_size: sp(14)
            color: (0.58, 0.65, 0.72, 1)
            size_hint_y: None
            height: dp(30)

        TextInput:
            id: file_path_input
            hint_text: 'C:\\\\数据\\\\接线表.xlsx' if IS_WINDOWS else '/sdcard/数据/接线表.xlsx'
            font_size: sp(16)
            multiline: False
            size_hint_y: None
            height: dp(48)

        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(12)
            Button:
                text: '📁 浏览文件'
                font_size: sp(15)
                background_normal: ''
                background_color: (0.5, 0.56, 0.64, 1)
                color: (1, 1, 1, 1)
                on_release: root.browse_file()
            Button:
                text: '✅ 加载'
                font_size: sp(15)
                background_normal: ''
                background_color: (0.13, 0.77, 0.36, 1)
                color: (1, 1, 1, 1)
                on_release: root.load_file()

        Label:
            id: msg_label
            text: ''
            font_size: sp(13)
            color: (0.94, 0.27, 0.27, 1)
            size_hint_y: None
            height: dp(30)

        # 示例/最近文件
        Label:
            text: '最近文件'
            font_size: sp(14)
            bold: True
            color: (0.3, 0.37, 0.45, 1)
            size_hint_y: None
            height: dp(30)

        ScrollView:
            id: recent_scroll
            GridLayout:
                id: recent_grid
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(4)

<SheetScreen>:
    BoxLayout:
        orientation: 'vertical'
        padding: dp(24)
        spacing: dp(16)

        Label:
            text: '选择工作表'
            font_size: sp(24)
            bold: True
            size_hint_y: None
            height: dp(60)

        Label:
            id: info_label
            text: ''
            font_size: sp(14)
            color: (0.58, 0.65, 0.72, 1)
            size_hint_y: None
            height: dp(30)

        ScrollView:
            GridLayout:
                id: sheet_grid
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(8)
                padding: [dp(4)]
"""

Builder.load_string(KV)


# ── 数据引擎 ────────────────────────────────────────────

class ExcelEngine:
    """Excel 数据加载和搜索（线程安全）"""

    def __init__(self):
        self.lock = threading.Lock()
        self.df = None
        self.file_path = ""
        self.file_name = ""
        self.sheet_names = []
        self.current_sheet = ""
        self.checked_rows = set()
        self.temp_file = None

    def load_sheets(self, file_path):
        """获取 Excel 文件的工作表列表"""
        ef = pd.ExcelFile(file_path)
        self.file_path = file_path
        self.file_name = os.path.basename(file_path)
        self.sheet_names = ef.sheet_names
        return self.sheet_names

    def load_sheet(self, sheet_name, engine=None):
        """加载指定工作表"""
        if engine is None:
            engine = self._detect_engine()
        df = pd.read_excel(self.file_path, sheet_name=sheet_name, engine=engine)
        df = df.fillna("")
        # 扫描已核线标记
        checked = set()
        for col in df.columns:
            found = False
            for idx in df.index:
                val = df.at[idx, col]
                if isinstance(val, str) and val.strip() == "已核线":
                    checked.add(idx)
                    found = True
            if found:
                df = df.drop(columns=[col])
                break
        unnamed = [c for c in df.columns if str(c).startswith("Unnamed")]
        if unnamed:
            df = df.drop(columns=unnamed, errors="ignore")
        with self.lock:
            self.df = df
            self.current_sheet = sheet_name
            self.checked_rows = checked
        return df, checked

    def find_column(self, field_name):
        """查找列名"""
        if self.df is None:
            return None
        for col in self.df.columns:
            if str(col).strip() == field_name:
                return col
        return None

    def search(self, query):
        """搜索线号"""
        if self.df is None:
            return []
        with self.lock:
            if query.startswith("-W"):
                sc = self.find_column("电缆号")
            else:
                sc = self.find_column("线号")
            if sc is None:
                return []
            mask = self.df[sc].astype(str).str.strip() == query
            results = []
            for r in self.df.index[mask]:
                d = {"_index": int(r), "_checked": r in self.checked_rows}
                d["_line_no"] = str(self.df.at[r, sc])
                for label, key in CARD_FIELDS[1:]:
                    col = self.find_column(label)
                    d[key] = str(self.df.at[r, col]) if col is not None else ""
                results.append(d)
            return results

    def get_valid_rows(self):
        """获取有效数据行索引"""
        if self.df is None:
            return set()
        spc = self.find_column("起始位置")
        if spc is None:
            return set(self.df.index)
        col = self.df[spc].astype(str).str.strip()
        mask = (col != "") & (~col.str.contains("操作者", na=False))
        return set(self.df.index[mask].tolist())

    def get_progress(self):
        """获取进度统计"""
        valid = self.get_valid_rows()
        total = len(valid)
        checked = len(valid & self.checked_rows)
        remain = max(total - checked, 0)
        percent = int(checked / total * 100) if total else 0
        return total, checked, remain, percent

    def mark_checked(self, row_idx):
        """标记某行为已核线"""
        self.checked_rows.add(row_idx)

    @staticmethod
    def _detect_engine():
        try:
            import python_calamine  # type: ignore
            return "calamine"
        except ImportError:
            return "openpyxl"


# ── UDP 服务 ────────────────────────────────────────────

class UDPServer:
    """UDP 查询接收和回复"""

    def __init__(self, engine: ExcelEngine, on_query=None):
        self.engine = engine
        self.socket = None
        self.active = False
        self.on_query = on_query

    def start(self):
        self.active = True
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(("0.0.0.0", UDP_PORT))
            t = threading.Thread(target=self._recv_loop, daemon=True)
            t.start()
            return True
        except Exception as e:
            print(f"[UDP] 启动失败: {e}")
            return False

    def stop(self):
        self.active = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass

    def _recv_loop(self):
        while self.active:
            try:
                data, addr = self.socket.recvfrom(1024)
            except Exception:
                break
            try:
                text = data.decode("utf-8").strip()
                query = text.split("_")[0]
                results = self.engine.search(query)
                if results and self.socket:
                    r = results[-1]
                    fields = [
                        r.get("_wire_type", ""),
                        r.get("_wire_diam", ""),
                        r.get("_color", ""),
                        r.get("_cable_no", ""),
                        "",  # 线束号
                        r.get("_conn_point", ""),
                        r.get("_start_dev", ""),
                    ]
                    response = "@@".join(fields)
                    self.socket.sendto(response.encode("utf-8"), addr)
                if self.on_query:
                    self.on_query(query, results)
            except Exception:
                continue


# ── Kivy 组件 ──────────────────────────────────────────

class ResultCard(BoxLayout):
    """搜索结果卡片"""
    index = NumericProperty(0)
    line_no = StringProperty("")
    start_pos = StringProperty("")
    start_dev = StringProperty("")
    checked = BooleanProperty(False)


class MainScreen(Screen):
    """主界面（搜索和展示）"""
    status_text = StringProperty("就绪")
    total_count = NumericProperty(0)
    checked_count = NumericProperty(0)
    remain_count = NumericProperty(0)
    progress_percent = NumericProperty(0)
    current_sheet = StringProperty("")
    udp_text = StringProperty("UDP 服务未启动")
    engine: ExcelEngine = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_items = []

    def on_enter(self):
        self.refresh_stats()
        self.ids.search_input.focus = True

    def do_search(self):
        q = self.ids.search_input.text.strip()
        if not q or not self.engine:
            return
        results = self.engine.search(q)
        self.display_results(results, q)
        Clock.schedule_once(lambda dt: self.refresh_stats())

    def show_all(self):
        if not self.engine or self.engine.df is None:
            return
        results = []
        df = self.engine.df
        checked = self.engine.checked_rows
        for r in df.index[:200]:
            d = {"_index": int(r), "_checked": r in checked}
            sc = self.engine.find_column("线号")
            d["_line_no"] = str(df.at[r, sc]) if sc else ""
            for label, key in CARD_FIELDS[1:]:
                col = self.engine.find_column(label)
                d[key] = str(df.at[r, col]) if col is not None else ""
            results.append(d)
        self.display_results(results, "全部(前200)")

    def display_results(self, results, label=""):
        self.data_items = []
        for r in results:
            self.data_items.append({
                "index": r["_index"],
                "line_no": r.get("_line_no", ""),
                "start_pos": r.get("_start_pos", ""),
                "start_dev": r.get("_start_dev", ""),
                "checked": r["_checked"],
            })
        self.ids.result_list.data = self.data_items
        n = len(results)
        self.ids.search_input.text = label if "全部" not in str(label) else ""
        self.status_text = f"找到 {n} 条" if results else "未找到匹配"

    def refresh_stats(self):
        if self.engine and self.engine.df is not None:
            t, c, r, p = self.engine.get_progress()
            self.total_count = t
            self.checked_count = c
            self.remain_count = r
            self.progress_percent = p
            self.current_sheet = self.engine.current_sheet
            self.status_text = f"{self.engine.file_name} | {self.engine.current_sheet}"
        else:
            self.total_count = 0
            self.checked_count = 0
            self.remain_count = 0
            self.progress_percent = 0

    def show_sheet_selector(self):
        if not self.engine or not self.engine.sheet_names:
            return
        sm = self.manager
        sheet_screen = sm.get_screen("sheet")
        sheet_screen.engine = self.engine
        sheet_screen.return_screen = "main"
        sheet_screen.refresh_list()
        sm.current = "sheet"

    def goto_file_screen(self):
        self.manager.current = "file"

    def update_udp_status(self, text):
        self.udp_text = text


class FileScreen(Screen):
    """文件选择界面"""
    engine: ExcelEngine = ObjectProperty(None)

    def on_enter(self):
        self.ids.msg_label.text = ""
        self.ids.file_path_input.text = ""
        self._show_recent()

    def browse_file(self):
        if IS_ANDROID:
            try:
                from plyer import filechooser  # type: ignore
                filechooser.open_file(on_selection=self._file_selected, filters=[("*.xlsx", ".xlsx")])
            except ImportError:
                self.ids.msg_label.text = "请手动输入文件路径"
        else:
            self.ids.msg_label.text = "请输入完整文件路径"

    def _file_selected(self, selection):
        if selection:
            self.ids.file_path_input.text = selection[0]

    def load_file(self):
        path = self.ids.file_path_input.text.strip()
        if not path:
            self.ids.msg_label.text = "请输入文件路径"
            return
        if not os.path.exists(path):
            self.ids.msg_label.text = f"文件不存在: {path}"
            return
        self.ids.msg_label.text = "正在解析..."
        Clock.schedule_once(lambda dt: self._do_load(path))

    def _do_load(self, path):
        try:
            if self.engine is None:
                self.engine = ExcelEngine()
            sheets = self.engine.load_sheets(path)
            sm = self.manager
            sheet_screen = sm.get_screen("sheet")
            sheet_screen.engine = self.engine
            sheet_screen.return_screen = "main"
            sheet_screen.refresh_list()
            sm.current = "sheet"
        except Exception as e:
            self.ids.msg_label.text = f"加载失败: {e}"

    def _show_recent(self):
        grid = self.ids.recent_grid
        grid.clear_widgets()
        recent = self._get_recent_files()
        for path in recent:
            btn = Button(
                text=os.path.basename(path) + f"\n{path}",
                size_hint_y=None,
                height=dp(60),
                font_size=sp(12),
                halign='left',
                background_normal='',
                background_color=(0.95, 0.96, 0.98, 1),
                color=(0.3, 0.37, 0.45, 1),
            )
            btn.bind(on_release=lambda b, p=path: self._quick_load(p))
            grid.add_widget(btn)

    def _get_recent_files(self):
        # 读取最近使用的文件列表
        recent = []
        try:
            cfg_path = os.path.join(os.path.dirname(__file__), "recent_files.txt")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    recent = [l.strip() for l in f.readlines() if l.strip() and os.path.exists(l.strip())]
        except Exception:
            pass
        return recent[:5]

    def _quick_load(self, path):
        self.ids.file_path_input.text = path
        self.load_file()


class SheetScreen(Screen):
    """工作表选择界面"""
    engine: ExcelEngine = ObjectProperty(None)
    return_screen = StringProperty("main")

    def refresh_list(self):
        grid = self.ids.sheet_grid
        grid.clear_widgets()
        if not self.engine:
            return
        self.ids.info_label.text = f"文件: {self.engine.file_name} ({len(self.engine.sheet_names)} 个表)"
        for s in self.engine.sheet_names:
            btn = Button(
                text=s,
                size_hint_y=None,
                height=dp(52),
                font_size=sp(18),
                background_normal='',
                background_color=(0.95, 0.96, 0.98, 1) if self.engine.current_sheet != s else (0.23, 0.51, 0.96, 1),
                color=(0.3, 0.37, 0.45, 1) if self.engine.current_sheet != s else (1, 1, 1, 1),
            )
            btn.bind(on_release=lambda b, s=s: self._select(s))
            grid.add_widget(btn)

    def _select(self, sheet_name):
        try:
            self.engine.load_sheet(sheet_name)
            main_screen = self.manager.get_screen("main")
            main_screen.engine = self.engine
            main_screen.refresh_stats()
            self.manager.current = self.return_screen
        except Exception as e:
            self.ids.info_label.text = f"加载失败: {e}"


# ── 主应用 ──────────────────────────────────────────────

class WireRecognitionApp(App):
    """线号识别 Kivy 应用"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.engine = ExcelEngine()
        self.udp_server = UDPServer(self.engine, on_query=self._on_udp_query)
        self.title = "线号识别系统"

    def build(self):
        sm = ScreenManager(transition=SlideTransition(duration=0.2))

        file_screen = FileScreen(name="file")
        file_screen.engine = self.engine

        sheet_screen = SheetScreen(name="sheet")

        main_screen = MainScreen(name="main")
        main_screen.engine = self.engine

        sm.add_widget(file_screen)
        sm.add_widget(sheet_screen)
        sm.add_widget(main_screen)
        sm.current = "file"

        # 启动 UDP 服务
        if self.udp_server.start():
            main_screen.update_udp_status(f"UDP 服务已启动 · 端口 {UDP_PORT}")
        else:
            main_screen.update_udp_status("UDP 服务启动失败")

        # 定期刷新统计
        Clock.schedule_interval(lambda dt: main_screen.refresh_stats(), 2)

        return sm

    def _on_udp_query(self, query, results):
        """UDP 查询回调"""
        main_screen = self.root.get_screen("main") if self.root else None
        if main_screen:
            n = len(results)
            main_screen.status_text = f"UDP 查询: {query} ({n} 条)"
            if results:
                label = f"UDP_{query}"
                main_screen.display_results(results, label)

    def on_stop(self):
        self.udp_server.stop()


# ── 入口 ────────────────────────────────────────────────


def main():
    print("=" * 50)
    print("  AI线号识别系统 — Kivy 版")
    print(f"  平台: {platform}")
    print("=" * 50)
    WireRecognitionApp().run()


if __name__ == "__main__":
    main()
