# 台股日線波段策略研究室｜Top 10 + 回測修正版

這版保留原本 GitHub Actions 自動更新資料的修正，同時恢復：

- Top 3 / Top 5 / Top 10 推薦名單
- 分類篩選
- 現股日線波段下單參數
- 單檔策略回測
- 全部股票表格與套用功能

## 重點修正

1. 更新資料失敗時，GitHub Actions 會失敗，不再偷偷沿用舊的 `market-data.json`。
2. `outputs/market-data.json` 必須由 `work/update_market.py` 正常產生才會部署。
3. 網站端保留 Top 10 與回測 UI。
4. 回測使用 FinMind API 於瀏覽器端抓取單檔日線資料；如果遇到額度限制，可在網站填入 FinMind Token。

## 使用

把本 ZIP 全部檔案上傳覆蓋到 GitHub repository 根目錄，Commit 後到 Actions 手動執行 workflow。

GitHub Pages Source 請使用 **GitHub Actions**。
