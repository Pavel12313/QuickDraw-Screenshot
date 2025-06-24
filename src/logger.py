import logging
import os
from datetime import datetime

def setup_logger():
    """ロガーの設定"""
    # ログディレクトリを作成
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # ログファイル名（日付付き）
    log_file = os.path.join(log_dir, f"screenshot_tool_{datetime.now().strftime('%Y%m%d')}.log")
    
    # ロガーの設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            # 開発時はコンソールにも出力
            # logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)