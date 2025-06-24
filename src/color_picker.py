import tkinter as tk
from tkinter import colorchooser

class ColorPicker:
    """カラーピッカーダイアログクラス"""
    
    def __init__(self, parent, initial_color, callback):
        self.parent = parent
        self.callback = callback
        self.initial_color = initial_color if initial_color.startswith('#') else '#FF0000'
        self.is_open = False
        self.color_window = None

    def open(self, x, y):
        """カラーピッカーを開く"""
        if self.is_open:
            return

        self.is_open = True
        
        # 位置決め用の透明ウィンドウを作成
        self.color_window = tk.Toplevel(self.parent)
        self.color_window.withdraw()  # ウィンドウを非表示
        self.color_window.attributes('-alpha', 0.0)  # 完全に透明
        self.color_window.geometry(f"+{x}+{y}")
        self.color_window.update()

        # カラーダイアログを表示
        color = colorchooser.askcolor(
            initialcolor=self.initial_color, 
            title="色を選択", 
            parent=self.color_window
        )
        
        if color[1]:
            self.callback(color[1])
        self.close()

    def close(self):
        """カラーピッカーを閉じる"""
        if self.color_window:
            self.color_window.destroy()
            self.color_window = None
        self.is_open = False
        self.callback(None)