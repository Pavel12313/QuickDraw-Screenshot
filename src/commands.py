import tkinter as tk
import math

class Command:
    """コマンドパターンの基底クラス"""
    
    def execute(self):
        """コマンドを実行"""
        pass

    def undo(self):
        """コマンドを元に戻す"""
        pass

    def redo(self):
        """コマンドを再実行"""
        self.execute()


class DrawCommand(Command):
    """描画コマンドクラス"""
    
    def __init__(self, tool, canvas, shape_id, x1, y1, x2, y2, color, thickness):
        self.tool = tool
        self.canvas = canvas
        self.shape_id = shape_id
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.color = color
        self.thickness = thickness

    def execute(self):
        """図形を描画"""
        if self.tool == "rectangle":
            self.shape_id = self.canvas.create_rectangle(
                self.x1, self.y1, self.x2, self.y2, 
                outline=self.color, width=self.thickness,
                tags="drawing"
            )
        elif self.tool == "arrow":
            # 矢印のヘッドサイズを計算
            arrow_head_size = max(self.thickness * 3, 8)
            angle = math.atan2(self.y2 - self.y1, self.x2 - self.x1)
            x_diff = arrow_head_size * 0.8 * math.cos(angle)
            y_diff = arrow_head_size * 0.8 * math.sin(angle)
            
            # 矢印の軸を描画
            shaft = self.canvas.create_line(
                self.x1, self.y1, 
                self.x2 - x_diff, self.y2 - y_diff, 
                fill=self.color, width=self.thickness,
                tags="drawing"
            )
            
            # 矢印の頭を描画
            head = self.canvas.create_polygon(
                self.x2, self.y2,
                self.x2 - arrow_head_size * math.cos(angle - math.pi/6),
                self.y2 - arrow_head_size * math.sin(angle - math.pi/6),
                self.x2 - arrow_head_size * math.cos(angle + math.pi/6),
                self.y2 - arrow_head_size * math.sin(angle + math.pi/6),
                fill=self.color, outline=self.color, tags="drawing"
            )
            
            # 軸と頭をグループ化
            self.shape_id = [shaft, head]

        return self.shape_id

    def undo(self):
        """描画を元に戻す"""
        if isinstance(self.shape_id, list):
            for shape in self.shape_id:
                self.canvas.delete(shape)
        else:
            self.canvas.delete(self.shape_id)


class TextCommand(Command):
    """テキストコマンドクラス"""
    
    def __init__(self, canvas, text, x, y, color, font, width, height):
        self.canvas = canvas
        self.text = text
        self.x = x
        self.y = y
        self.color = color
        self.font = font
        self.width = width
        self.height = height
        self.text_id = None

    def execute(self):
        """テキストを描画"""
        self.text_id = self.canvas.create_text(
            self.x, self.y, text=self.text, fill=self.color, font=self.font,
            anchor='nw', width=self.width, tags=("text", "drawing")
        )
        self.canvas.tag_raise(self.text_id)
        return self.text_id

    def undo(self):
        """テキストを削除"""
        if self.text_id:
            self.canvas.delete(self.text_id)
            self.text_id = None