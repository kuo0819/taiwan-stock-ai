# 部署說明

1. 解壓縮本包。
2. 將所有檔案覆蓋到 `kuo0819/taiwan-stock-ai` repo 根目錄。
3. Commit 並 push 到 `main`。
4. 到 GitHub → Settings → Pages，確認 Source 是 **GitHub Actions**。
5. 到 Actions 手動執行「更新台股資料並部署網站」。

若資料更新失敗，Actions 會紅燈，不會再偷偷部署舊資料。
