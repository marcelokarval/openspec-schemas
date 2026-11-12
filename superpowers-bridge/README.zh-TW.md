# superpowers-bridge v2

[English](README.md) · [繁體中文](README.zh-TW.md)

本套件結合 [OpenSpec](https://github.com/Fission-AI/OpenSpec) 文件與
[Superpowers](https://github.com/obra/superpowers) 規劃及執行紀律。schema
只是提示指引，不是執行期強制機制。OpenSpec 2.0.0 與 Superpowers 7.0.2
僅為原始碼審視目標，不宣稱端到端相容、agent 執行或 CLI 驗證。

## 前置檢查與驗證

使用已授權工作區，明確指定 Git repository 根目錄、祖先 base 與現有 change
目錄；不需要 remote。路徑應引用為參數，勿作為 shell 片段。替換 `<bundle>`：

```sh
python3 '<bundle>/scripts/bridge_guard.py' preflight --repo '<repo>' --base '<base>' --change '<change>'
python3 '<bundle>/scripts/bridge_guard.py' candidate --repo '<repo>' --base '<base>' --change '<change>'
python3 '<bundle>/scripts/bridge_guard.py' verify --repo '<repo>' --base '<base>' --change '<change>'
```

前置檢查要求非空 brainstorm、proposal、design、tasks、plan，以及至少一個
`specs/**/spec.md`。缺少即停止，不得由聊天內容重建。建立或轉移工作區須另行
授權並重新檢查。tasks 使用唯一的 `- [ ] 1.1 說明` 穩定 ID；plan 需引用該 ID，
記錄實際 RED/GREEN 與審查 candidate 身分。

實作後執行 candidate，將 candidate 摘要單獨放在 `verify.md` 的
`## Candidate`。實際取得證據後，在 `## Mandatory checks` 放置三行
`- [x] structural`、`- [x] tests`、`- [x] review`。必要工作與缺口都解決後，
`## Overall Decision` 僅使用 `- [x] PASS`；其他狀態不是 PASS。然後執行 verify。
先在 change 建立 `candidate-manifest.json`，例如
`{"paths":[{"path":"src/new.py","state":"present"},{"path":"src/old.py","state":"absent"}]}`，列出相關實作
檔（包括被忽略檔案）的 repository 相對路徑及最終狀態。preflight 容許預計新增
檔案尚未存在、預計刪除檔案仍存在；candidate 與 verify 要求 present 存在且
absent 不存在。現存父目錄不得為符號連結；preflight 摘要僅供準備。
不可列入 change 內檔案；owner 與
審查者須核對清單完整性：未列入檔案及新增檔不會自動偵測。摘要綁定 base、HEAD、
清單、列出的檔案與必要規劃/spec；符號連結及不支援的檔案類型會被拒絕。
事後報告排除在摘要外，因此寫 retrospective 不會使 candidate 失效。已涵蓋檔案
變更會使摘要失效。guard 只檢查格式與新鮮度，不證明測試執行、
審查獨立性、語意完整性或人工驗收。

另建 `evidence.json`，其格式見英文 README 範例：每個 task ID 都要有對應 plan ID、
RED/GREEN 指令、details 與精確 outcome `expected_failure` / `passed`，並記錄 structural 指令與 pass、獨立 reviewer 身分、pass、
相同 candidate，以及空的 unresolved 陣列。plan 每個任務使用 `## Task 1.1` 或 `## Task 1.1: 標題`，
不得有未完成項，GREEN details 不可與成功矛盾。報告中的 FAIL 或 NOT VERIFIED 會阻止通過；既往失敗另行保存。
這些仍是自述，須獨立核對。單檔上限 4 MiB；Markdown fence 僅接受前面 0–3 空格，
模糊的縮排 fence 會被拒絕。

明確對應實際可用 skill 名稱，例如 `brainstorming` 或
`superpowers:brainstorming`，並記錄實際呼叫。subagent 模式需授權；inline 模式
仍須 TDD 與審查。發現 skill 不代表已載入或執行。commit、建立工作區、安裝、
archive、release、PR、push、merge 均須獨立授權；archive 不等於人工驗收或發布。
未經 owner 批准，選用檢查不能替代必要驗收。

## 從 v1 遷移

v2 改變驗證格式並加入 guard。保留既有 consumer 文件與歷史，不自動覆寫或刪除。
取得 owner 授權後更新 bundle，將進行中 change 的 task ID、plan 證據與驗證遷移至
v2 格式，再重新執行 preflight。舊的空白或缺少 FAIL 勾選不能視為 PASS。安裝與
升級不由本指引授權。
舊版 v2 的字串清單與 result 格式須遷移為上述狀態物件與 outcome 欄位。
