#!/bin/bash
# ============================================================
# 案件自動収集システム 日次実行スクリプト
# CrowdWorks / Lancers から業務委託案件を収集し、AIスコアリング後にSlack通知
# ============================================================

# スクリプトのディレクトリに移動
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ログファイル
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
LOGFILE="$LOG_DIR/cron_$(date +%Y%m%d_%H%M%S).log"

echo "========================================" >> "$LOGFILE"
echo "実行開始: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOGFILE"
echo "========================================" >> "$LOGFILE"

# .envファイルの読み込み
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# Python実行
python3.11 "$SCRIPT_DIR/main.py" >> "$LOGFILE" 2>&1
EXIT_CODE=$?

echo "========================================" >> "$LOGFILE"
echo "実行終了: $(date '+%Y-%m-%d %H:%M:%S') (終了コード: $EXIT_CODE)" >> "$LOGFILE"
echo "========================================" >> "$LOGFILE"

# 古いログを30日以上経過したものは削除
find "$LOG_DIR" -name "*.log" -mtime +30 -delete

exit $EXIT_CODE
