# 台股全市場策略研究室｜資料更新修正版

這是直接覆蓋部署版，重點修正：

1. GitHub Actions 不再靜默沿用舊 `market-data.json`。
2. `update_market.py` 以 TWSE / TPEx 官方盤後資料為主，即使 Yahoo 歷史資料失敗，也會用官方當日資料產生新日期資料。
3. 部署前會檢查 `market-data.json` 的資料日期、股票數量與新鮮度。
4. 網站會顯示資料來源、資料日期、大盤狀態與 Top 名單。

## 使用方式

把本 ZIP 解壓縮後，整包覆蓋到 GitHub repo 根目錄，commit/push 到 `main`。

GitHub Pages 請設定為：

Settings → Pages → Source: GitHub Actions

## 本機測試

```bash
python work/update_market.py
python -m http.server 8317 --directory outputs
```

打開：

```text
http://127.0.0.1:8317/
```

## 注意

本工具是台股日線波段研究與風控輔助，不是當沖，也不是保證獲利訊號。
