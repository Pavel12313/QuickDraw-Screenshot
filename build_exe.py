import PyInstaller.__main__
import os
import shutil
import sys

# 現在のディレクトリを取得
current_dir = os.path.dirname(os.path.abspath(__file__))

# アセットフォルダのパス
assets_dir = os.path.join(current_dir, 'assets')
icons_dir = os.path.join(assets_dir, 'icons')

# 隠しインポート
hidden_imports = [
    '--hidden-import=PIL._tkinter_finder',
    '--hidden-import=keyboard',
    '--hidden-import=screeninfo',
    '--hidden-import=pystray',
    '--hidden-import=mss',
    '--hidden-import=ttkbootstrap',
    '--hidden-import=win32ts',
    '--hidden-import=win32gui',
    '--hidden-import=win32con',
]

# PyInstallerの引数
main_pyinstaller_args = [
    'main.py',
    '--name=QuickDraw-Screenshot',
    '--onefile',
    '--windowed',
    f'--add-data=assets;assets',
    f'--icon={os.path.join(assets_dir, "sc.ico")}',
] + hidden_imports

# メインアプリケーションのみビルド
PyInstaller.__main__.run(main_pyinstaller_args)

print("ビルド完了。実行ファイルは'dist'フォルダにあります。")