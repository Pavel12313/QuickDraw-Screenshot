from PIL import Image, ImageTk
import os
import math
import tkinter as tk
from tkinter import ttk
import win32clipboard
import io

def load_icon(filename, size=(20, 20)):
    """アイコンファイルを読み込み"""
    try:
        image = Image.open(os.path.join("assets", "icons", filename))
        image = image.resize(size, Image.LANCZOS)
        return ImageTk.PhotoImage(image)
    except FileNotFoundError:
        print(f"警告: アイコンファイル {filename} が見つかりません。")
        return None

def draw_pil_arrow(draw, x1, y1, x2, y2, fill, width):
    """PIL用の矢印を描画"""
    angle = math.atan2(y2 - y1, x2 - x1)
    angle_deg = math.degrees(angle)

    # 矢印の頭のサイズを調整
    arrow_length = max(width * 3, 8)
    arrow_width = max(width * 2, 6)

    sin_angle = math.sin(angle)
    cos_angle = math.cos(angle)

    x_diff = arrow_length * cos_angle
    y_diff = arrow_length * sin_angle

    # 矢印の頭の点を計算
    arrow_point1 = (x2 - x_diff + arrow_width * sin_angle, y2 - y_diff - arrow_width * cos_angle)
    arrow_point2 = (x2 - x_diff - arrow_width * sin_angle, y2 - y_diff + arrow_width * cos_angle)

    # 矢印の軸を描画
    draw.line([(x1, y1), (x2 - x_diff, y2 - y_diff)], fill=fill, width=width)
    # 矢印の頭を描画
    draw.polygon([(x2, y2), arrow_point1, arrow_point2], fill=fill)


def setup_styles(theme_color, accent_color, text_color):
    """スタイルを設定"""
    style = ttk.Style()
    style.theme_use('clam')
    
    # 標準ボタンスタイル
    style.configure(
        'Toolbar.TButton', 
        background=theme_color, 
        foreground=text_color, 
        padding=(5, 5), 
        font=('Segoe UI', 10), 
        borderwidth=1
    )
    style.map(
        'Toolbar.TButton', 
        background=[('active', accent_color)],
        foreground=[('active', 'white')]
    )
    
    # 白いボタンスタイル
    style.configure(
        'White.Toolbar.TButton', 
        background='white', 
        foreground='black', 
        padding=(5, 5), 
        font=('Segoe UI', 10), 
        borderwidth=1
    )
    style.map(
        'White.Toolbar.TButton', 
        background=[('active', '#e6e6e6'), ('pressed', '#d9d9d9')],
        foreground=[('active', 'black'), ('pressed', 'black')]
    )
    
    # フレームスタイル
    style.configure('Toolbar.TFrame', background=theme_color)
    
    # ラベルスタイル
    style.configure(
        'Toolbar.TLabel', 
        background=theme_color, 
        foreground=text_color, 
        font=('Segoe UI', 10)
    )

def copy_image_to_clipboard(image):
    """画像をクリップボードにコピー"""
    output = io.BytesIO()
    image.convert('RGB').save(output, 'BMP')
    data = output.getvalue()[14:]
    output.close()
    
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    win32clipboard.CloseClipboard()

def show_error(root, error_message, theme_color):
    """エラーダイアログを表示"""
    top = tk.Toplevel(root)
    top.geometry('300x100')
    top.title('エラー')
    top.configure(bg=theme_color)
    
    ttk.Label(
        top, 
        text=f'エラーが発生しました:\n{error_message}', 
        style='Toolbar.TLabel'
    ).pack(pady=20)
    
    ttk.Button(
        top, 
        text="OK", 
        command=top.destroy, 
        style='Toolbar.TButton'
    ).pack()