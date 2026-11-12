<!-- Source: superpowers-bridge/templates/adopters/CLAUDE.md.fragment.zh-TW.md -->
## OpenSpec 與 Superpowers 工作流程

依 v2 合約明確對應本地 skill 名稱。執行前在已授權工作區以明確的
repository、base、change 執行 `bridge_guard.py preflight`；缺少檔案即停止。
記錄 RED/GREEN 與對應 candidate 的獨立審查，填寫必要結果後執行 `verify`。
guard 成功不證明結果真實。建立工作區、封存、PR、push、merge 與人工驗收
均為獨立授權的行動，不得自動執行。
