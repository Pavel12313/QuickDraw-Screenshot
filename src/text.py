import tkinter as tk
from tkinter import font

class CanvasTextEditor:
    """キャンバス上のテキストエディタクラス"""
    
    def __init__(self, canvas, x, y, initial_text="", font_name="Arial", font_size=20, color="black"):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.text = initial_text
        self.color = color
        self.font_name = font_name
        self.font_size = font_size

        # フォントオブジェクトを作成
        self.font = font.Font(family=self.font_name, size=self.font_size)
        
        # テキストをキャンバスに描画
        self.text_id = self.canvas.create_text(
            self.x, self.y, text=self.text, font=self.font, 
            fill=self.color, anchor="nw"
        )

        # テキストの境界ボックスを作成
        bbox = self.canvas.bbox(self.text_id)
        self.rect_id = self.canvas.create_rectangle(bbox, outline=self.color, width=1)

        # キーイベントをバインド
        self.canvas.bind("<Key>", self.on_key_press)
        self.canvas.focus_set()

    def on_key_press(self, event):
        """キー押下時の処理"""
        if event.keysym == "BackSpace":
            # バックスペースで文字を削除
            self.text = self.text[:-1]
        elif event.keysym == "Return":
            # エンターキーでテキストを確定
            return self.finalize_text()
        else:
            # その他のキーは文字として追加
            self.text += event.char

        # テキストを更新
        self.canvas.itemconfig(self.text_id, text=self.text)
        self.update_rectangle()

    def update_rectangle(self):
        """境界ボックスを更新"""
        bbox = self.canvas.bbox(self.text_id)
        self.canvas.coords(self.rect_id, bbox)

    def finalize_text(self):
        """テキストを確定"""
        self.canvas.delete(self.rect_id)
        self.canvas.unbind("<Key>")
        return self.text_id

    def cancel(self):
        """テキスト入力をキャンセル"""
        self.canvas.delete(self.rect_id)
        self.canvas.delete(self.text_id)
        self.canvas.unbind("<Key>")