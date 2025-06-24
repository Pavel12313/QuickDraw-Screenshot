import os
import sys
import platform
import math
import time
import json
import io
import queue
import threading
import logging
import tkinter as tk
import tkinter.colorchooser
import tkinter.font
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from PIL import Image, ImageTk, ImageDraw, ImageFont
from mss import mss
from screeninfo import get_monitors

# プラットフォームチェック
if platform.system() != "Windows":
    print(f"\n警告: このアプリケーションはWindows専用です。現在のOS: {platform.system()}\n")
    sys.exit(1)

# Windows専用モジュール
import ctypes
from ctypes import wintypes
import keyboard
import pystray
import win32gui, win32con, win32ts
import win32clipboard

from src.commands import Command, DrawCommand, TextCommand
from src.color_picker import ColorPicker
from src.text import CanvasTextEditor
from src.utils import load_icon, draw_pil_arrow, setup_styles, copy_image_to_clipboard, show_error
from src.logger import setup_logger
from src.__version__ import __version__, __author__, __description__

# ロガーの設定
logger = setup_logger()

# アプリケーション情報
APP_NAME = "QuickDraw-Screenshot"
APP_VERSION = __version__

# Windows APIメッセージ定数
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
WM_INPUTLANGCHANGE = 0x0051

class QuickDrawScreenshot:
    """超軽量・高速スクリーンショットツールのメインクラス"""
    
    SCREENSHOT_KEY_MAP = {
        'print screen': 'print_screen',
        'prtscn': 'print_screen',
        'prt sc': 'print_screen',
        'prnt scrn': 'print_screen',
        'print_screen': 'print_screen',
        'ctrl+shift+s': 'ctrl+shift+s',
    }

    def __init__(self):
        # UI要素
        self.root = None
        self.rect_canvas = None
        self.toolbar = None
        self.text_toolbar = None
        self.text_entry = None
        
        # 座標と画像
        self.start_x = self.start_y = self.end_x = self.end_y = None
        self.screenshot = None
        self.full_screenshot = None
        self.screen_width = self.screen_height = None
        self.tk_image = None
        
        # 描画設定
        self.current_tool = "move"
        self.current_color = "red"
        self.line_width = 2
        self.line_thickness = 2
        self.max_line_thickness = 10
        self.font_size = 12
        
        # テーマ設定
        self.theme_color = "#f0f0f0"
        self.accent_color = "#007bff"
        self.text_color = "#333333"
        
        # UI状態
        self.selection_rect = None
        self.overlay_rectangles = []
        self.dimension_text = None
        self.is_drawing_mode = False
        self.is_screenshot_in_progress = False
        self.state = "idle"
        
        # ツールバー要素
        self.toolbar_buttons = {}
        self.font_size_var = None
        self.thickness_label = None
        
        # アンドゥ/リドゥスタック
        self.undo_stack = []
        self.redo_stack = []
        
        # リサイズハンドル
        self.resize_handles = []
        self.resizing = None
        self.resize_start_x = None
        self.resize_start_y = None
        
        # ドラッグ状態
        self.dragging = False
        self.drag_start_x = None
        self.drag_start_y = None
        
        # パフォーマンス設定
        self.last_update_time = 0
        self.refresh_rate = 60.0
        self.update_interval = 1 / self.refresh_rate
        
        # その他
        self.drawing_area = None
        self.icon = None
        self.queue = queue.Queue()
        self.color_picker = None
        
        # 設定読み込み
        self.settings = self.load_settings()
        self.screenshot_key = self.settings.get("screenshot_key", "print screen").lower()
        if self.screenshot_key not in self.SCREENSHOT_KEY_MAP:
            self.screenshot_key = "print screen"
        self.current_color = self.settings.get("color", self.current_color)
        self.font_size = self.settings.get("font_size", self.font_size)
        self.line_thickness = self.settings.get("line_thickness", 2)
        self.refresh_rate = float(self.settings.get("refresh_rate", 60.0))
        self.update_interval = 1 / self.refresh_rate

    def start(self):
        """アプリケーションを起動"""
        self.state = "idle"
        self.root = ttk.Window(themename="cyborg")
        self.root.withdraw()
        self.create_toolbar()
        
        # キーポーリング開始
        self.poll_hotkey_state()
        self.poll_escape_key()
        
        # Caps Lockモニター（フォールバック用）
        try:
            keyboard.add_hotkey('caps lock', self.handle_input_change, suppress=False)
        except Exception as e:
            logger.warning(f"Caps Lockモニターの追加に失敗しました: {e}")
        
        self.create_system_tray_icon()
        self.root.after(100, self.process_queue)
        self.root.mainloop()

    def poll_escape_key(self):
        """Escapeキーを直接ポーリング"""
        if not hasattr(self, '_last_escape_state'):
            self._last_escape_state = False
        
        try:
            # Escapeキーが押されているかチェック
            escape_pressed = ctypes.windll.user32.GetAsyncKeyState(win32con.VK_ESCAPE) & 0x8000 != 0
            
            # キーダウン時のみトリガー
            if escape_pressed and not self._last_escape_state:
                self.root.after(0, self.handle_escape)
            
            self._last_escape_state = escape_pressed
        except Exception as e:
            logger.error(f"Escapeポーリングでエラー: {e}")
        
        if self.root:
            self.root.after(50, self.poll_escape_key)

    def handle_escape(self):
        """Escapeキーの処理"""
        if hasattr(self, 'color_picker') and self.color_picker and self.color_picker.is_open:
            self.color_picker.close()
        elif self.state in ["selecting", "drawing"]:
            self.safe_cancel_screenshot()

    def safe_cancel_screenshot(self):
        """スクリーンショットを安全にキャンセル"""
        self.state = "idle"
        self.is_screenshot_in_progress = False
        self.is_drawing_mode = False

        if self.rect_canvas:
            self.rect_canvas.destroy()
            self.rect_canvas = None

        if self.toolbar:
            self.toolbar.place_forget()

        if self.text_toolbar:
            self.text_toolbar.place_forget()

        self.root.withdraw()
        self.start_x = self.start_y = self.end_x = self.end_y = None
        self.screenshot = None
        self.full_screenshot = None
        self.unbind_keys()
        self.root.unbind('<Escape>')

    def poll_hotkey_state(self):
        """ホットキーの状態を直接ポーリング"""
        if not hasattr(self, '_last_hotkey_state'):
            self._last_hotkey_state = False
        
        try:
            # Ctrl+Shift+Sが押されているかチェック
            ctrl_pressed = ctypes.windll.user32.GetAsyncKeyState(win32con.VK_CONTROL) & 0x8000 != 0
            shift_pressed = ctypes.windll.user32.GetAsyncKeyState(win32con.VK_SHIFT) & 0x8000 != 0
            s_pressed = ctypes.windll.user32.GetAsyncKeyState(ord('S')) & 0x8000 != 0
            
            # Print Screenが押されているかチェック
            printscreen_pressed = ctypes.windll.user32.GetAsyncKeyState(win32con.VK_SNAPSHOT) & 0x8000 != 0
            
            # 設定されたキーに基づいてホットキーの状態を判定
            hotkey_pressed = False
            if self.screenshot_key == "ctrl+shift+s" and ctrl_pressed and shift_pressed and s_pressed:
                hotkey_pressed = True
            elif self.screenshot_key in ["print screen", "print_screen"] and printscreen_pressed:
                hotkey_pressed = True
            
            # キーダウン時のみトリガー
            if hotkey_pressed and not self._last_hotkey_state and self.state == "idle":
                self.root.after(0, self.initiate_screenshot)
            
            self._last_hotkey_state = hotkey_pressed
        except Exception as e:
            logger.error(f"ホットキーポーリングでエラー: {e}")
        
        if self.root:
            self.root.after(50, self.poll_hotkey_state)

    def process_queue(self):
        """キューの処理"""
        try:
            task = self.queue.get(block=False)
            if task == "open_settings":
                self.show_settings_dialog()
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def handle_input_change(self):
        """入力メソッドの変更を処理（Caps Lock経由）"""
        logger.info("入力メソッドの変更を検出しました（Caps Lock経由）")

    def create_toolbar(self):
        """ツールバーを作成"""
        self.reload_settings()
        self.toolbar = ttk.Frame(self.root, style='Toolbar.TFrame')
        self.toolbar.pack_forget()
        self.toolbar_buttons = {}
        
        # ツールバーボタンの定義
        buttons = [
            ("move.png", lambda: self.set_tool("move")),
            ("rectangle.png", lambda: self.set_tool("rectangle")),
            ("arrow.png", lambda: self.set_tool("arrow")),
            ("text.png", lambda: self.set_tool("text")),
            ("color.png", self.open_color_picker),
            ("smallline.png", lambda: self.adjust_line_thickness(-1)),
            ("bigline.png", lambda: self.adjust_line_thickness(1)),
            (None, None),  # 線の太さ表示用スペース
            ("undo.png", self.undo),
            ("copy.png", self.copy_to_clipboard),
        ]
        
        # ボタンを作成
        for item, command in buttons:
            if item is None:
                # 線の太さパーセンテージ表示
                percentage = int((self.line_thickness / self.max_line_thickness) * 100)
                self.thickness_label = ttk.Label(self.toolbar, text=f"{percentage}%", style='Toolbar.TLabel')
                self.thickness_label.pack(side=tk.LEFT, padx=5)
            elif item.endswith('.png'):
                icon = load_icon(item)
                btn = ttk.Button(self.toolbar, image=icon, command=command, style='Toolbar.TButton', width=3)
                btn.image = icon
                btn.pack(side=tk.LEFT, padx=5)
                self.toolbar_buttons[item] = btn
        
        # フォントサイズ選択
        font_sizes = [8, 9, 10, 11, 12, 14, 16, 18, 20, 22, 24, 26, 28, 36, 48, 72]
        self.font_size_var = tk.StringVar(value=str(self.font_size))
        font_size_menu = ttk.OptionMenu(
            self.toolbar, self.font_size_var, str(self.font_size),
            *[str(size) for size in font_sizes], 
            command=lambda x: self.change_font_size(x)
        )
        font_size_menu.pack(side=tk.LEFT, padx=5)
        
        # 閉じるボタン
        close_icon = load_icon("close.png")
        close_btn = ttk.Button(self.toolbar, image=close_icon, command=self.reset_tool_state, style='Toolbar.TButton', width=3)
        close_btn.image = close_icon
        close_btn.pack(side=tk.LEFT, padx=5)
        self.toolbar_buttons["close.png"] = close_btn

    def reload_settings(self):
        """設定を再読み込み"""
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                self.screenshot_key = settings.get("screenshot_key", self.screenshot_key)
                self.current_color = settings.get("color", self.current_color)
                self.font_size = settings.get("font_size", self.font_size)
                self.line_thickness = settings.get("line_thickness", self.line_thickness)
        except FileNotFoundError:
            pass

    def open_color_picker(self):
        """カラーピッカーを開く"""
        if self.toolbar and self.toolbar.winfo_ismapped():
            toolbar_x = self.toolbar.winfo_rootx()
            toolbar_y = self.toolbar.winfo_rooty()
            toolbar_width = self.toolbar.winfo_width()
            
            def color_callback(color):
                if color:
                    self.current_color = color
                self.root.after(10, self.refocus_screenshot)
            
            initial_color = self.current_color if self.current_color.startswith('#') else '#FF0000'
            
            if not hasattr(self, 'color_picker') or not self.color_picker:
                self.color_picker = ColorPicker(self.root, initial_color, color_callback)
            else:
                self.color_picker.initial_color = initial_color
            
            if self.color_picker.is_open:
                return
            
            # カラーピッカーの位置を計算
            x = toolbar_x + toolbar_width + 5
            y = toolbar_y
            screen_width = self.root.winfo_screenwidth()
            if x + 400 > screen_width:
                x = toolbar_x - 400 - 5
            
            self.color_picker.open(x, y)

    def refocus_screenshot(self):
        """スクリーンショットウィンドウにフォーカスを戻す"""
        self.root.attributes('-topmost', True)
        self.root.update()
        self.root.attributes('-topmost', False)
        self.root.focus_force()
        if self.rect_canvas:
            self.rect_canvas.focus_set()

    def set_tool(self, tool):
        """ツールを設定"""
        self.current_tool = tool
        if tool == "text":
            self.rect_canvas.config(cursor="xterm")
        elif tool == "move":
            self.rect_canvas.config(cursor="fleur")
        else:
            self.rect_canvas.config(cursor="cross")

    def adjust_line_thickness(self, delta):
        """線の太さを調整"""
        self.line_thickness = max(1, min(self.max_line_thickness, self.line_thickness + delta))
        percentage = int((self.line_thickness / self.max_line_thickness) * 100)
        self.thickness_label.config(text=f"{percentage}%")
        self.line_width = self.line_thickness
        self.save_settings()

    def change_font_size(self, size):
        """フォントサイズを変更"""
        self.font_size = int(size)
        if self.text_entry:
            self.text_entry.configure(font=("TkDefaultFont", self.font_size))
        self.save_settings()

    def reset_tool_state(self):
        """ツール状態をリセット"""
        self.reset_for_new_screenshot()
        self.is_drawing_mode = False
        self.undo_stack.clear()
        self.redo_stack.clear()
        
        if self.rect_canvas:
            for handle in self.resize_handles:
                self.rect_canvas.delete(handle)
            self.rect_canvas.destroy()
            self.rect_canvas = None
        
        if self.toolbar:
            self.toolbar.place_forget()
        
        if self.text_toolbar:
            self.text_toolbar.place_forget()
        
        for widget in self.root.winfo_children():
            if isinstance(widget, ColorPicker):
                widget.destroy()
        
        self.root.withdraw()
        self.is_drawing_mode = False
        self.is_screenshot_in_progress = False
        self.unbind_keys()
        self.resize_handles = []
        self.resizing = None
        self.resize_start_x = None
        self.resize_start_y = None

    def initiate_screenshot(self):
        """スクリーンショット撮影を開始"""
        if self.state == "idle":
            self.state = "selecting"
            self.root.after(0, self._initiate_screenshot_gui)

    def _initiate_screenshot_gui(self):
        """GUI上でスクリーンショットを開始"""
        self.state = "selecting"
        self.is_screenshot_in_progress = True
        self.reset_screenshot_state()
        self.setup_screenshot_canvas()
        self.bind_screenshot_events()
        self.root.deiconify()
        self.root.attributes('-topmost', True)
        self.bind_keys()
        self.root.after(500, lambda: None)

    def reset_screenshot_state(self):
        """スクリーンショット状態をリセット"""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.start_x = self.start_y = self.end_x = self.end_y = None
        self.screenshot = None
        
        if self.rect_canvas:
            self.rect_canvas.destroy()
        if self.toolbar:
            self.toolbar.place_forget()
        if self.text_toolbar:
            self.text_toolbar.place_forget()

    def setup_screenshot_canvas(self):
        """スクリーンショット用キャンバスをセットアップ"""
        # モニター情報を取得
        monitors = get_monitors()
        min_x = min(m.x for m in monitors)
        min_y = min(m.y for m in monitors)
        max_x = max(m.x + m.width for m in monitors)
        max_y = max(m.y + m.height for m in monitors)
        self.screen_width = max_x - min_x
        self.screen_height = max_y - min_y
        
        # スクリーンショットを撮影
        with mss() as sct:
            monitor = {"top": min_y, "left": min_x, "width": self.screen_width, "height": self.screen_height}
            screenshot = sct.grab(monitor)
            self.full_screenshot = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        
        # ウィンドウを設定
        self.root.deiconify()
        self.root.geometry(f"{self.screen_width}x{self.screen_height}+{min_x}+{min_y}")
        self.root.overrideredirect(True)
        
        # キャンバスを作成
        self.rect_canvas = tk.Canvas(self.root, cursor="cross", highlightthickness=0)
        self.rect_canvas.pack(fill=tk.BOTH, expand=True)
        
        # スクリーンショット画像を表示
        self.tk_image = ImageTk.PhotoImage(self.full_screenshot)
        self.rect_canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        
        # 選択矩形を作成
        self.selection_rect = self.rect_canvas.create_rectangle(
            0, 0, 0, 0, outline=self.accent_color, width=2
        )
        
        # オーバーレイ矩形を作成
        self.overlay_rectangles = [
            self.rect_canvas.create_rectangle(
                0, 0, self.screen_width, self.screen_height,
                fill='black', stipple='gray50', tags=('overlay',)
            ) for _ in range(4)
        ]
        
        # 寸法テキストを作成
        self.dimension_text = self.rect_canvas.create_text(
            0, 0, text="", fill="white", font=('Segoe UI', 10, 'bold'), tags="dimensions"
        )
        self.rect_canvas.itemconfig(self.dimension_text, state='normal')

    def bind_screenshot_events(self):
        """スクリーンショットイベントをバインド"""
        self.rect_canvas.bind('<ButtonPress-1>', self.on_button_press)
        self.rect_canvas.bind('<B1-Motion>', self.on_move_press)
        self.rect_canvas.bind('<ButtonRelease-1>', self.on_button_release)
        self.root.bind('<Escape>', self.on_escape)

    def on_button_press(self, event):
        """マウスボタン押下時の処理"""
        self.start_x = self.end_x = event.x
        self.start_y = self.end_y = event.y
        self.update_selection()

    def on_move_press(self, event):
        """マウスドラッグ時の処理"""
        self.end_x, self.end_y = event.x, event.y
        self.update_selection()

    def update_selection(self):
        """選択範囲を更新"""
        if self.start_x is None or self.start_y is None or self.end_x is None or self.end_y is None:
            return
        
        # パフォーマンスのためのスロットリング
        current_time = time.monotonic()
        if current_time - self.last_update_time < self.update_interval:
            return
        self.last_update_time = current_time
        
        # 座標を正規化
        x1, y1 = min(self.start_x, self.end_x), min(self.start_y, self.end_y)
        x2, y2 = max(self.start_x, self.end_x), max(self.start_y, self.end_y)
        
        # 選択矩形を更新
        self.rect_canvas.coords(self.selection_rect, x1, y1, x2, y2)
        self.update_overlay(x1, y1, x2, y2)

    def update_overlay(self, x1, y1, x2, y2):
        """オーバーレイを更新"""
        # 上部
        self.rect_canvas.coords(self.overlay_rectangles[0], 0, 0, self.screen_width, y1)
        # 左側
        self.rect_canvas.coords(self.overlay_rectangles[1], 0, y1, x1, y2)
        # 右側
        self.rect_canvas.coords(self.overlay_rectangles[2], x2, y1, self.screen_width, y2)
        # 下部
        self.rect_canvas.coords(self.overlay_rectangles[3], 0, y2, self.screen_width, self.screen_height)
        
        # オーバーレイの色を設定
        for rect in self.overlay_rectangles:
            self.rect_canvas.itemconfig(rect, fill='black', stipple='gray50')
        
        # 寸法を表示
        width, height = x2 - x1, y2 - y1
        self.rect_canvas.coords(self.dimension_text, (x1 + x2) / 2, (y1 + y2) / 2)
        self.rect_canvas.itemconfig(self.dimension_text, text=f"{width}x{height}", state='normal')

    def on_button_release(self, event):
        """マウスボタンリリース時の処理"""
        if self.start_x is None or self.start_y is None:
            return
        
        self.end_x, self.end_y = event.x, event.y
        
        # 1ピクセルの選択を防ぐ
        if self.end_x == self.start_x and self.end_y == self.start_y:
            self.end_x += 1
            self.end_y += 1
        
        self.update_selection()
        
        # 座標を正規化
        x1, y1 = min(self.start_x, self.end_x), min(self.start_y, self.end_y)
        x2, y2 = max(self.start_x, self.end_x), max(self.start_y, self.end_y)
        
        try:
            self.screenshot = self.full_screenshot.crop((x1, y1, x2, y2))
            self.setup_drawing_mode(x1, y1, x2, y2)
            self.state = "drawing"
            self.is_screenshot_in_progress = False
            self.root.attributes('-topmost', False)
            self.root.bind('<Escape>', self.on_escape)
        except Exception as e:
            logger.error(f"ボタンリリースでエラー: {e}")

    def setup_drawing_mode(self, x1, y1, x2, y2):
        """描画モードをセットアップ"""
        # スクリーンショットイベントをアンバインド
        self.rect_canvas.unbind('<ButtonPress-1>')
        self.rect_canvas.unbind('<B1-Motion>')
        self.rect_canvas.unbind('<ButtonRelease-1>')
        
        # 寸法テキストを非表示
        self.rect_canvas.itemconfig(self.dimension_text, state='hidden')
        
        # キャンバスサイズを調整
        self.rect_canvas.config(width=x2 - x1, height=y2 - y1)
        self.rect_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 描画イベントをバインド
        self.rect_canvas.bind("<ButtonPress-1>", self.on_press)
        self.rect_canvas.bind("<B1-Motion>", self.on_drag)
        self.rect_canvas.bind("<Motion>", self.on_drag)
        self.rect_canvas.bind("<ButtonRelease-1>", self.on_release)
        self.rect_canvas.config(cursor="fleur")
        
        # キーバインド
        self.root.bind('<Control-z>', self.undo)
        self.root.bind('<Control-y>', self.redo)
        self.root.bind('<Control-c>', self.copy_to_clipboard)
        
        # 描画エリアを保存
        self.drawing_area = (x1, y1, x2, y2)
        self.is_drawing_mode = True
        
        # リサイズハンドルを作成
        self.create_resize_handles(x1, y1, x2, y2)
        
        # ツールバーを表示
        self.show_toolbar(x1, y1, x2, y2)

    def create_resize_handles(self, x1, y1, x2, y2):
        """リサイズハンドルを作成"""
        self.resize_handles = []
        handle_size = 10
        corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        
        for i, (x, y) in enumerate(corners):
            handle = self.rect_canvas.create_rectangle(
                x - handle_size/2, y - handle_size/2,
                x + handle_size/2, y + handle_size/2,
                fill="white", outline="black", tags=f"handle{i}"
            )
            self.resize_handles.append(handle)

    def show_toolbar(self, x1, y1, x2, y2):
        """ツールバーを表示"""
        toolbar_width = min(500, x2 - x1)
        toolbar_height = self.toolbar.winfo_reqheight()
        
        # ツールバーの位置を計算
        if self.screen_height - y2 > toolbar_height + 10:
            toolbar_x = x1 + (x2 - x1) // 2 - toolbar_width // 2
            toolbar_y = y2 + 10
        else:
            toolbar_x = x1 + (x2 - x1) // 2 - toolbar_width // 2
            toolbar_y = y1 - toolbar_height - 10
        
        # 画面内に収める
        toolbar_x = max(0, min(toolbar_x, self.screen_width - toolbar_width))
        
        self.toolbar.configure(width=toolbar_width)
        self.toolbar.place(x=toolbar_x, y=toolbar_y)
        self.toolbar.lift()

    def on_press(self, event):
        """マウスプレス時の処理"""
        x, y = event.x, event.y
        
        # リサイズハンドルのチェック
        for i, handle in enumerate(self.resize_handles):
            coords = self.rect_canvas.coords(handle)
            if coords[0] <= x <= coords[2] and coords[1] <= y <= coords[3]:
                self.resizing = i
                self.resize_start_x = x
                self.resize_start_y = y
                self.toolbar.place_forget()
                self.rect_canvas.itemconfig(self.dimension_text, state='normal')
                return
        
        # 移動ツールの処理
        if self.current_tool == "move":
            x1, y1, x2, y2 = self.drawing_area
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.dragging = True
                self.drag_start_x = x
                self.drag_start_y = y
                return
        # テキストツールの処理
        elif self.current_tool == "text":
            self.start_text_entry(event)
        # その他の描画ツール
        else:
            self.start_draw(event)

    def on_drag(self, event):
        """ドラッグ時の処理"""
        if event.state & 0x0100:  # マウスボタンが押されている
            if self.resizing is not None:
                self.resize_selection(event.x, event.y)
            elif self.dragging and self.current_tool == "move":
                self.drag_selection(event.x, event.y)
            elif self.current_tool not in ["text", "move"]:
                self.draw_shape(event)
        self.rect_canvas.update_idletasks()

    def on_release(self, event):
        """マウスリリース時の処理"""
        if self.resizing is not None:
            self.resize_selection(event.x, event.y)
            self.show_toolbar(*self.drawing_area)
            self.resizing = None
            self.resize_start_x = None
            self.resize_start_y = None
            self.rect_canvas.itemconfig(self.dimension_text, state='hidden')
        elif self.dragging and self.current_tool == "move":
            self.drag_selection(event.x, event.y)
            self.dragging = False
            self.drag_start_x = None
            self.drag_start_y = None
            self.show_toolbar(*self.drawing_area)
        elif self.current_tool not in ["text", "move"]:
            self.end_draw(event)

    def drag_selection(self, x, y):
        """選択範囲をドラッグ"""
        if not self.dragging:
            return
        
        dx = x - self.drag_start_x
        dy = y - self.drag_start_y
        x1, y1, x2, y2 = self.drawing_area
        
        # 新しい座標を計算
        new_x1, new_y1, new_x2, new_y2 = x1 + dx, y1 + dy, x2 + dx, y2 + dy
        
        # 画面境界内に制限
        if new_x1 < 0:
            dx = -x1
        elif new_x2 > self.screen_width:
            dx = self.screen_width - x2
        if new_y1 < 0:
            dy = -y1
        elif new_y2 > self.screen_height:
            dy = self.screen_height - y2
        
        new_x1, new_y1, new_x2, new_y2 = x1 + dx, y1 + dy, x2 + dx, y2 + dy
        
        # 選択矩形を移動
        self.rect_canvas.coords(self.selection_rect, new_x1, new_y1, new_x2, new_y2)
        
        # 描画要素を移動
        for item in self.rect_canvas.find_withtag("drawing"):
            self.rect_canvas.move(item, dx, dy)
        
        # リサイズハンドルを更新
        self.update_resize_handles(new_x1, new_y1, new_x2, new_y2)
        
        # 描画エリアを更新
        self.drawing_area = (new_x1, new_y1, new_x2, new_y2)
        self.update_overlay(new_x1, new_y1, new_x2, new_y2)
        self.rect_canvas.itemconfig(self.dimension_text, state='hidden')
        
        # ドラッグ開始位置を更新
        self.drag_start_x = x
        self.drag_start_y = y

    def update_resize_handles(self, x1, y1, x2, y2):
        """リサイズハンドルを更新"""
        handle_size = 10
        corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        
        for handle, (x, y) in zip(self.resize_handles, corners):
            self.rect_canvas.coords(
                handle, 
                x - handle_size/2, y - handle_size/2, 
                x + handle_size/2, y + handle_size/2
            )

    def resize_selection(self, x, y):
        """選択範囲をリサイズ"""
        x1, y1, x2, y2 = self.rect_canvas.coords(self.selection_rect)
        
        # リサイズハンドルに応じて座標を更新
        if self.resizing == 0:  # 左上
            x1, y1 = x, y
        elif self.resizing == 1:  # 右上
            x2, y1 = x, y
        elif self.resizing == 2:  # 右下
            x2, y2 = x, y
        elif self.resizing == 3:  # 左下
            x1, y2 = x, y
        
        # 座標を正規化
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        
        # 選択矩形を更新
        self.rect_canvas.coords(self.selection_rect, x1, y1, x2, y2)
        self.update_resize_handles(x1, y1, x2, y2)
        self.update_overlay(x1, y1, x2, y2)
        self.drawing_area = (x1, y1, x2, y2)
        
        # 寸法を更新
        width, height = abs(x2 - x1), abs(y2 - y1)
        self.rect_canvas.itemconfig(self.dimension_text, text=f"{width}x{height}", state='normal')
        self.rect_canvas.coords(self.dimension_text, (x1 + x2) / 2, (y1 + y2) / 2)

    def start_draw(self, event):
        """描画を開始"""
        x1, y1, _, _ = self.drawing_area
        self.start_x, self.start_y = event.x - x1, event.y - y1

    def draw_shape(self, event):
        """図形を描画"""
        if self.start_x is None or not self.point_in_drawing_area(event.x, event.y):
            return
        
        self.rect_canvas.delete("temp_shape")
        x1, y1, _, _ = self.drawing_area
        current_x, current_y = event.x - x1, event.y - y1
        
        if self.current_tool == "rectangle":
            # 矩形を描画
            draw_x1, draw_y1 = min(self.start_x, current_x), min(self.start_y, current_y)
            draw_x2, draw_y2 = max(self.start_x, current_x), max(self.start_y, current_y)
            self.rect_canvas.create_rectangle(
                draw_x1 + x1, draw_y1 + y1, draw_x2 + x1, draw_y2 + y1,
                outline=self.current_color, width=self.line_thickness,
                tags=("temp_shape", "drawing")
            )
        elif self.current_tool == "arrow":
            # 矢印を描画
            self.draw_arrow(
                self.start_x + x1, self.start_y + y1, 
                current_x + x1, current_y + y1, 
                ("temp_shape", "drawing")
            )

    def draw_arrow(self, x1, y1, x2, y2, tags):
        """矢印を描画"""
        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_length = max(self.line_thickness * 3, 8)
        x_diff = arrow_length * math.cos(angle)
        y_diff = arrow_length * math.sin(angle)
        
        # 矢印の軸を描画
        self.rect_canvas.create_line(
            x1, y1, x2 - x_diff, y2 - y_diff, 
            fill=self.current_color, width=self.line_thickness, tags=tags
        )
        
        # 矢印の頭を描画
        self.rect_canvas.create_polygon(
            x2, y2,
            x2 - x_diff + self.line_thickness * 2 * math.sin(angle),
            y2 - y_diff - self.line_thickness * 2 * math.cos(angle),
            x2 - x_diff - self.line_thickness * 2 * math.sin(angle),
            y2 - y_diff + self.line_thickness * 2 * math.cos(angle),
            fill=self.current_color, tags=tags
        )

    def end_draw(self, event):
        """描画を終了"""
        if self.start_x is None or not self.point_in_drawing_area(event.x, event.y):
            return
        
        self.rect_canvas.delete("temp_shape")
        x1, y1, _, _ = self.drawing_area
        current_x, current_y = event.x - x1, event.y - y1
        
        # 描画コマンドを作成
        command = DrawCommand(
            self.current_tool, self.rect_canvas, None,
            self.start_x + x1, self.start_y + y1,
            current_x + x1, current_y + y1,
            self.current_color, self.line_thickness
        )
        shape_id = command.execute()
        
        # 描画タグを追加
        if isinstance(shape_id, list):
            for sid in shape_id:
                self.rect_canvas.addtag_withtag("drawing", sid)
        else:
            self.rect_canvas.addtag_withtag("drawing", shape_id)
        
        # アンドゥスタックに追加
        self.undo_stack.append(command)
        self.redo_stack.clear()
        self.start_x = self.start_y = None

    def point_in_drawing_area(self, x, y):
        """点が描画エリア内にあるか確認"""
        x1, y1, x2, y2 = self.drawing_area
        return x1 <= x <= x2 and y1 <= y <= y2

    def start_text_entry(self, event):
        """テキスト入力を開始"""
        if self.point_in_drawing_area(event.x, event.y):
            if self.text_entry:
                self.end_text_entry()
            
            # イベントをアンバインド
            self.rect_canvas.unbind("<ButtonPress-1>")
            self.rect_canvas.unbind("<B1-Motion>")
            self.rect_canvas.unbind("<ButtonRelease-1>")
            
            self.start_x = event.x
            self.start_y = event.y
            
            # テキストボックスのリサイズイベントをバインド
            self.rect_canvas.bind("<B1-Motion>", self.resize_text_box)
            self.rect_canvas.bind("<ButtonRelease-1>", self.finalize_text_box)
            
            # テキストボックスを作成
            self.text_box = self.rect_canvas.create_rectangle(
                self.start_x, self.start_y, event.x, event.y,
                outline=self.current_color, dash=(2,2), tags="text_box"
            )

    def resize_text_box(self, event):
        """テキストボックスをリサイズ"""
        self.rect_canvas.coords(self.text_box, self.start_x, self.start_y, event.x, event.y)

    def finalize_text_box(self, event):
        """テキストボックスを確定"""
        self.rect_canvas.unbind("<B1-Motion>")
        self.rect_canvas.unbind("<ButtonRelease-1>")
        
        x1, y1, x2, y2 = self.rect_canvas.coords(self.text_box)
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        
        # テキスト入力フィールドを作成
        self.text_entry = ttk.Text(
            self.rect_canvas, font=("TkDefaultFont", self.font_size), 
            width=1, height=1, wrap=tk.WORD
        )
        self.text_entry.place(x=min(x1, x2), y=min(y1, y2), width=width, height=height)
        self.text_entry.focus_set()
        self.text_entry.bind("<FocusOut>", self.end_text_entry)
        self.text_entry.bind("<KeyRelease>", self.on_text_change)
        self.text_entry.configure(borderwidth=1, relief="solid")
        
        self.reset_drawing_bindings()

    def on_text_change(self, event):
        """テキスト変更時の処理"""
        pass

    def end_text_entry(self, event=None):
        """テキスト入力を終了"""
        if self.text_entry:
            text = self.text_entry.get("1.0", "end-1c")
            if text:
                x = self.text_entry.winfo_x()
                y = self.text_entry.winfo_y()
                width = self.text_entry.winfo_width()
                height = self.text_entry.winfo_height()
                
                # テキストコマンドを作成
                command = TextCommand(
                    self.rect_canvas, text, x, y, self.current_color, 
                    ("TkDefaultFont", self.font_size), width, height
                )
                text_id = command.execute()
                self.undo_stack.append(command)
                self.redo_stack.clear()
            
            self.text_entry.destroy()
            self.text_entry = None
            self.rect_canvas.delete("text_box")
            self.reset_drawing_bindings()

    def reset_drawing_bindings(self):
        """描画バインディングをリセット"""
        self.rect_canvas.bind("<ButtonPress-1>", self.on_press)
        self.rect_canvas.bind("<B1-Motion>", self.on_drag)
        self.rect_canvas.bind("<Motion>", self.on_drag)
        self.rect_canvas.bind("<ButtonRelease-1>", self.on_release)

    def undo(self, event=None):
        """アンドゥ"""
        if self.undo_stack:
            command = self.undo_stack.pop()
            command.undo()
            self.redo_stack.append(command)
            self.rect_canvas.delete("temp_shape")
            self.start_x = self.start_y = None

    def redo(self, event=None):
        """リドゥ"""
        if self.redo_stack:
            command = self.redo_stack.pop()
            command.execute()
            self.undo_stack.append(command)
            self.rect_canvas.delete("temp_shape")
            self.start_x = self.start_y = None

    def copy_to_clipboard(self, event=None):
        """クリップボードにコピー"""
        if not self.is_drawing_mode:
            return
        
        x1, y1, x2, y2 = self.drawing_area
        bbox = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        temp_image = self.full_screenshot.crop(bbox)
        
        # ストローク幅を追加
        stroke_width = 1
        new_size = (temp_image.width + 2 * stroke_width, temp_image.height + 2 * stroke_width)
        stroke_image = Image.new('RGBA', new_size, (0, 0, 0, 0))
        stroke_image.paste(temp_image, (stroke_width, stroke_width))
        
        draw = ImageDraw.Draw(stroke_image)
        draw.rectangle([0, 0, new_size[0] - 1, new_size[1] - 1], outline=self.current_color, width=stroke_width)
        
        # 描画コマンドを適用
        for command in self.undo_stack:
            if isinstance(command, DrawCommand):
                adjusted_x1 = command.x1 - bbox[0] + stroke_width
                adjusted_y1 = command.y1 - bbox[1] + stroke_width
                adjusted_x2 = command.x2 - bbox[0] + stroke_width
                adjusted_y2 = command.y2 - bbox[1] + stroke_width
                
                x0, y0 = min(adjusted_x1, adjusted_x2), min(adjusted_y1, adjusted_y2)
                x1_, y1_ = max(adjusted_x1, adjusted_x2), max(adjusted_y1, adjusted_y2)
                
                if command.tool == "rectangle":
                    draw.rectangle([x0, y0, x1_, y1_], outline=command.color, width=command.thickness)
                elif command.tool == "arrow":
                    draw_pil_arrow(draw, adjusted_x1, adjusted_y1, adjusted_x2, adjusted_y2, command.color, command.thickness)
            elif isinstance(command, TextCommand):
                adjusted_x = command.x - bbox[0] + stroke_width
                adjusted_y = command.y - bbox[1] + stroke_width
                
                try:
                    font_obj = ImageFont.truetype("meiryo.ttc", command.font[1])
                except Exception:
                    font_obj = ImageFont.load_default()
                
                draw.text((adjusted_x, adjusted_y), command.text, fill=command.color, font=font_obj)
        
        copy_image_to_clipboard(stroke_image)
        self.reset_for_new_screenshot()
        self.set_screenshot_key(self.screenshot_key)

    def reset_for_new_screenshot(self):
        """新しいスクリーンショットのためにリセット"""
        try:
            self.state = "idle"
            self.is_drawing_mode = False
            self.is_screenshot_in_progress = False
            self.undo_stack.clear()
            self.redo_stack.clear()
            
            # 画像をクリーンアップ
            if self.full_screenshot:
                try:
                    self.full_screenshot.close()
                except Exception:
                    pass
                self.full_screenshot = None
            
            if self.screenshot:
                try:
                    self.screenshot.close()
                except Exception:
                    pass
                self.screenshot = None
            
            if hasattr(self, 'tk_image'):
                try:
                    del self.tk_image
                except Exception:
                    pass
            
            # UIをクリーンアップ
            if self.rect_canvas:
                try:
                    for handle in self.resize_handles:
                        self.rect_canvas.delete(handle)
                    self.rect_canvas.destroy()
                except Exception:
                    pass
                self.rect_canvas = None
            
            if self.toolbar:
                try:
                    self.toolbar.place_forget()
                except Exception:
                    pass
            
            if self.text_toolbar:
                try:
                    self.text_toolbar.place_forget()
                except Exception:
                    pass
            
            self.root.withdraw()
            self.start_x = self.start_y = self.end_x = self.end_y = None
            self.drawing_area = None
            
            if self.text_entry:
                try:
                    self.text_entry.destroy()
                except Exception:
                    pass
                self.text_entry = None
            
            self.resize_handles = []
            self.resizing = None
            self.resize_start_x = None
            self.resize_start_y = None
            self.unbind_keys()
            
            # ガベージコレクション
            import gc
            gc.collect()
            
            self.set_screenshot_key(self.screenshot_key)
        except Exception:
            try:
                self.set_screenshot_key(self.screenshot_key)
            except Exception:
                pass

    def on_escape(self, event=None):
        """Escapeキー処理（GUIイベント用）"""
        self.handle_escape()

    def unbind_keys(self):
        """キーバインドを解除"""
        self.root.unbind('<Control-z>')
        self.root.unbind('<Control-y>')
        self.root.unbind('<Control-c>')
        self.root.unbind('<Escape>')

    def bind_keys(self):
        """キーバインドを設定"""
        self.root.bind('<Control-z>', self.undo)
        self.root.bind('<Control-y>', self.redo)
        self.root.bind('<Control-c>', self.copy_to_clipboard)
        self.root.bind('<Escape>', self.on_escape)

    def create_system_tray_icon(self):
        """システムトレイアイコンを作成"""
        icon_path = os.path.join(os.getcwd(), "assets", "sc.png")
        if os.path.exists(icon_path):
            image = Image.open(icon_path)
        else:
            # デフォルトアイコンを作成
            image = Image.new('RGB', (64, 64), color=(73, 109, 137))
            d = ImageDraw.Draw(image)
            d.text((10, 10), "SC", fill=(255, 255, 0))
        
        menu = pystray.Menu(
            pystray.MenuItem("設定", self.open_settings),
            pystray.MenuItem("終了", lambda: self.safe_quit_app(from_tray=True))
        )
        
        self.icon = pystray.Icon("QuickDraw-Screenshot", image, "QuickDraw-Screenshot", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def open_settings(self):
        """設定を開く"""
        self.root.after(0, self.show_settings_dialog)

    def show_settings_dialog(self):
        """設定ダイアログを表示"""
        dialog = tk.Toplevel(self.root)
        dialog.title("設定")
        
        # スクリーンショットキー
        screenshot_key_label = ttk.Label(dialog, text="スクリーンショットキー:")
        screenshot_key_label.pack()
        screenshot_key_entry = ttk.Entry(dialog)
        screenshot_key_entry.insert(0, self.screenshot_key)
        screenshot_key_entry.pack()
        
        # 色
        color_label = ttk.Label(dialog, text="色:")
        color_label.pack()
        color_entry = ttk.Entry(dialog)
        color_entry.insert(0, self.current_color)
        color_entry.pack()
        
        # フォントサイズ
        font_size_label = ttk.Label(dialog, text="フォントサイズ:")
        font_size_label.pack()
        font_size_entry = ttk.Entry(dialog)
        font_size_entry.insert(0, str(self.font_size))
        font_size_entry.pack()
        
        # 線の太さ
        thickness_label = ttk.Label(dialog, text="線の太さ:")
        thickness_label.pack()
        thickness_entry = ttk.Entry(dialog)
        thickness_entry.insert(0, str(self.line_thickness))
        thickness_entry.pack()
        
        # リフレッシュレート
        refresh_rate_label = ttk.Label(dialog, text="リフレッシュレート (Hz):")
        refresh_rate_label.pack()
        refresh_rate_entry = ttk.Entry(dialog)
        refresh_rate_entry.insert(0, str(self.refresh_rate))
        refresh_rate_entry.pack()
        
        def save_settings():
            new_screenshot_key = screenshot_key_entry.get().lower()
            if self.set_screenshot_key(new_screenshot_key):
                self.current_color = color_entry.get()
                self.font_size = int(font_size_entry.get())
                self.line_thickness = int(thickness_entry.get())
                try:
                    self.refresh_rate = float(refresh_rate_entry.get())
                except ValueError:
                    show_error(dialog, "無効なリフレッシュレート。数値を入力してください。", self.theme_color)
                    return
                self.save_settings()
                self.update_interval = 1 / self.refresh_rate
                dialog.destroy()
            else:
                show_error(dialog, f"無効なスクリーンショットキー: {new_screenshot_key}", self.theme_color)
        
        save_button = ttk.Button(dialog, text="保存", command=save_settings)
        save_button.pack()
        dialog.wait_window()

    def load_settings(self):
        """設定を読み込み"""
        try:
            with open('settings.json', 'r') as f:
                settings = json.load(f)
                return settings
        except FileNotFoundError:
            return {
                "screenshot_key": "print screen", 
                "color": "red", 
                "font_size": 12, 
                "line_thickness": 2, 
                "refresh_rate": 60.0
            }

    def save_settings(self):
        """設定を保存"""
        settings = {
            "screenshot_key": self.screenshot_key, 
            "color": self.current_color,
            "font_size": self.font_size, 
            "line_thickness": self.line_thickness,
            "refresh_rate": self.refresh_rate
        }
        with open('settings.json', 'w') as f:
            json.dump(settings, f)

    def set_screenshot_key(self, key):
        """スクリーンショットキーを設定"""
        self.screenshot_key = key.lower()
        
        try:
            keyboard.unhook_all()
        except Exception:
            pass
            
        return True

    def safe_quit_app(self, from_tray=False):
        """アプリケーションを安全に終了"""
        self.save_settings()
        
        if self.icon:
            self.icon.stop()
        
        self.root.quit()


if __name__ == "__main__":
    app = QuickDrawScreenshot()
    app.start()