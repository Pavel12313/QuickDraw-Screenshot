@echo off
echo ===================================
echo QuickDraw-Screenshot セットアップ
echo ===================================
echo.

REM 設定ファイルのコピー
if not exist settings.json (
    copy settings.json.example settings.json
    echo ✓ 設定ファイルを作成しました
) else (
    echo ✓ 設定ファイルは既に存在します
)

REM 依存関係のインストール
echo.
echo 依存関係をインストールしています...
pip install -r requirements.txt

REM ログディレクトリの作成
if not exist logs mkdir logs
echo ✓ ログディレクトリを作成しました

echo.
echo ===================================
echo セットアップが完了しました！
echo ===================================
echo.
echo 実行方法: python main.py
echo.
pause