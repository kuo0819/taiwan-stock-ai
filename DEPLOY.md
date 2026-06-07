# 雲端部署說明

此專案已設定 GitHub Pages 與 GitHub Actions。部署完成後，即使個人電腦關機，網站仍可透過公開網址使用。

## 第一次部署

1. 在 GitHub 建立一個新的 repository，例如 `taiwan-stock-ai`。
2. 將本專案全部檔案上傳至 repository，預設分支使用 `main`。
3. 進入 repository 的 `Settings` → `Pages`。
4. 在 `Build and deployment` 的 `Source` 選擇 `GitHub Actions`。
5. 進入 `Actions`，開啟「更新台股資料並部署網站」，按下 `Run workflow`。
6. 等待流程完成，網站網址會顯示在部署結果中，通常格式為：

   `https://你的GitHub帳號.github.io/taiwan-stock-ai/`

## 自動更新

`.github/workflows/deploy-pages.yml` 會：

- 每次推送至 `main` 分支時更新並部署。
- 每個台股交易日台灣時間 18:30 自動更新並部署。
- 支援從 GitHub Actions 頁面手動執行。

GitHub 排程可能延遲數分鐘。資料日期仍應以網站頂部顯示日期為準。

## 公開性與免責

GitHub Pages 網站通常是公開的，請勿在專案中加入密碼、API 金鑰或私人資料。此網站的量化判斷不代表投資保證。
