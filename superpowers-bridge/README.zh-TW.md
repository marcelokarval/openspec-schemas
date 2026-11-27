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
python3 -B '<bundle>/scripts/bridge_guard.py' preflight --repo '<repo>' --base '<base>' --change '<change>'
python3 -B '<bundle>/scripts/bridge_guard.py' candidate --repo '<repo>' --base '<base>' --change '<change>'
python3 -B '<bundle>/scripts/bridge_guard.py' verify --repo '<repo>' --base '<base>' --change '<change>'
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
這些仍是自述，須獨立核對。單檔上限 4 MiB。舊版 guard 允許程式碼圍欄前有 0–3 個
空格；有標記的文件要求起始圍欄從行首開始，不得縮排。

明確對應實際可用 skill 名稱，例如 `brainstorming` 或
`superpowers:brainstorming`，並記錄實際呼叫。subagent 模式需授權；inline 模式
仍須 TDD 與審查。發現 skill 不代表已載入或執行。commit、建立工作區、安裝、
archive、release、PR、push、merge 均須獨立授權；archive 不等於人工驗收或發布。
未經 owner 批准，選用檢查不能替代必要驗收。

## 以任務微契約規劃

在規劃階段拆解、審視及細化任務。每個任務只交付一項可獨立驗證的成果，支援步驟
留在同一任務。`tasks.md` 仍是正式清單。保留穩定 ID 及已有證據的進度；拆出的新工作
使用新 ID，更新兩份文件中受影響的引用，再重新驗證。不另建逐任務檔案或追蹤表。

新計畫須保留一行 `Bridge task contract: 1`。依模板填寫每個 `## Task X.Y` 或
`## Task X.Y: 標題` 下的頂層欄位：

- `Outcome`、`Owner/resolver`、`Acceptance`、`Stop`、`Resume` 須填具體內容：成果、
  負責交付或解決尚未定案事項的人、驗收整項成果的檢查、停止及恢復條件。
- `Inputs` 列出任務圖以外的必要輸入，沒有則寫 `none`。
- `Depends on` 列出前置任務 ID，沒有則寫 `none`。每個前置任務須有一行
  `Needs: ID => output-id`，識別碼須和該任務的 `Produces` 完全一致。沒有前置任務
  時只寫一行 `Needs: none`。`Produces` 定義一個交付物識別碼，實際內容由 `Outcome` 說明。
- `Write paths`、`Exclusions`、`Shared resources` 以逗號分隔，沒有則寫 `none`。
  路徑須為精確的 repository 相對路徑，各段只用英文字母、數字及 `. _ @ + -`；不接受
  絕對路徑、跳脫目錄或萬用字元。`Exclusions` 限制該任務的寫入範圍。資源及交付物
  識別碼以 ASCII 字母或數字開頭，其餘也可用 `_ . : -`。每個路徑或識別碼最多 1,024 字元。

程式碼圍欄中的範例與 HTML 註解不算欄位內容。有標記的文件不接受原始 HTML 區塊；
HTML 註解與行內程式碼的起訖符號必須在同一行。多行範例或 HTML 註解起訖符號的示例
請使用程式碼圍欄，且起始圍欄必須從行首開始，不得縮排。在註解與圍欄外，有標記的文件不接受
以反斜線跳脫這些符號，也不接受把它們放在行內程式碼中或同一行未配對的反引號後。
有標記的計畫中，每個任務微契約欄位須使用不縮排的 `-`；欄位名稱周圍的空格或 tab 不會
改變欄位的識別。
`tasks.md` 只接受頂層的 `- [ ] X.Y 說明` 格式及支援的勾選狀態，不接受其他清單符號
或巢狀任務核取方塊。空白欄位、`TBD` 等占位符及互相矛盾的宣告也會被拒絕。
交付新計畫前及每次細化後執行：

```sh
python3 -B '<bundle>/scripts/bridge_guard.py' planning --change '<change-dir>'
```

未啟用規則契約時，`planning` 讀取 `plan.md` 與 `tasks.md` 的任務契約。啟用後也會讀取差異規格；不需 candidate manifest。若引用變更目錄外的正式規則，必須指定所屬 Git 根目錄：

```sh
python3 -B '<bundle>/scripts/bridge_guard.py' planning --repo '<repo>' --change '<change-dir>'
```

CLI 參數以實際套件的 `scripts/bridge_guard.py --help` 為準。
缺少標記會失敗；未知或重複標記在任何讀取此契約的指令中均會失敗。`preflight`、
`candidate`、`verify` 也會依 `tasks.md` 檢查有標記的計畫；candidate 摘要仍綁定原始
位元組。對有標記的計畫，`verify` 要求報告區段必須可見，且不接受一般 Markdown
清單項目（含巢狀項目）上的未完成核取方塊。未標記的舊計畫保有既有檢查及投影行為，
不自動遷移。通過結構檢查不代表
輸入已存在、資源宣告完整或計畫已獲批准。

若兩種解讀會改變結果、權限或驗收條件，由代理在既有需求啟用規則契約。只改措辭而不改效果時，無須宣告。區分來源所顯示的現況、誰有權決定，以及決定的預期結果；全新行為不必虛構現況。列出預期結果及一個條件相近、結果卻必須不同的案例。
保留 REMOVED 的 Reason/Migration 及 RENAMED 的 FROM/TO；只改名不新增規則。移除或跨能力變更若改變其他能力的結果，應在仍存續的對應需求描述新結果，並引用共用決策。

- 在 `### Requirement:` 下以獨立純文字行寫 `Rule: BR-LIMIT` 與 `Decision: approved`（或 `proposed`、`blocked`）；每個實質 `#### Scenario:` 下各寫一行唯一的 `Scenario ID: AC-OVER`。共用規則改用 `Rule reference: BR-LIMIT => policies/limits.md#limit`，不重複定義。目標必須是同一 repository 內、變更目錄外的一般 Markdown 檔；其中 `### Requirement: Limit {#limit}` 須直接定義同一規則及決策。guard 將引用檔的位元組納入 candidate 摘要；一般引文或網址只交代出處，不會自動解析，也不能證明實作結果。
- 在 `plan.md` 的任務標記旁加上 `Bridge rule contract: 1`。只在受規則影響的任務內，以純文字逐對寫 `Rule scenario: BR-LIMIT => AC-OVER`，並寫一行 `Rule readiness: ready` 或 `Rule readiness: blocked`；涵蓋所有本地宣告的規則情境。共用缺口只記一次，註明解決人、受影響 ID 與恢復條件。規則仍為 proposed 或 blocked 時，其任務必須標為 blocked 且不得勾選完成；任何狀態都不授予執行權。
- 審查時問：結果互斥的兩種實作能否同時通過這些情境？實作者是否必須自行制定政策？任一為是，就先細化受影響的決策或情境。每對規則及情境以 TDD 測試已決定的結果，在同一 candidate 記錄實際 RED/GREEN；於 `evidence.json` 的對應任務加上 `"rule_scenarios":[{"rule":"BR-LIMIT","scenario":"AC-OVER","proof":"policy_test"}]`，每對一筆。只描述既有行為的測試不足以證明政策。

派工前，即使 DAG 顯示相依性已滿足，也須排除 guard 的 `rule_blocked_tasks` 及所有直接或間接依賴它們的任務。從其餘就緒任務依保留中的資源、實際輸入、寫入與資源衝突及授權重算獨立批次；保持 DAG 不變，不可直接照 `Next front` 派工。局部阻擋可通過規劃檢查，但不能通過最終驗證。

執行階段只使用並複核已批准的計畫。若缺少必要輸入、關鍵決策或範圍，只將受影響的
工作批次退回規劃細化；獨立就緒、無衝突且已獲授權的工作仍可進行。不得略過失敗
的檢查。檢查與投影皆不取代 Superpowers 或原生協作機制。

## 任務相依性投影

多任務工作預設顯示 ASCII 相依圖、任務表及下一批工作；也可輸出 Mermaid：

```sh
python3 -B '<bundle>/scripts/task_dag.py' --change '<change-dir>'
python3 -B '<bundle>/scripts/task_dag.py' --change '<change-dir>' --format mermaid
```

恢復時依目前計畫及清單重算；相依性、勾選狀態或下一批有變動才再次顯示。舊計畫
缺少 `Depends on` 表示未知，不等於 `none`。舊版 `Next front` 顯示所有相依性已滿足的
待辦 ID，不判斷資源衝突。`[x]` 不代表驗收；`[~]` 不證明正在執行，也不會滿足後續相依性。

有標記的計畫以 `Dependency ready` 列出相依性已滿足的任務；`Declared conflicts`
另外列出重疊的寫入路徑（含已宣告的上層路徑與其下層路徑）及相同資源識別碼，
不把衝突轉成相依邊。`Next front` 先保留所有 `[~]` 任務宣告的路徑及資源，再按
ID 數字順序選入沒有碰到保留項或已選項的就緒任務。Mermaid 以註解呈現相同結果。
這批工作只對已宣告的衝突做投影，不能證明安全、授權或驗收；派工前仍須核對計畫、
實際輸入、資源及授權。工具不寫檔，只讀每檔最多 4 MiB 的一般 UTF-8 檔案，不接受
符號連結及特殊檔案。

## 從 v1 遷移

v2 改變驗證格式並加入 guard。保留既有 consumer 文件與歷史，不自動覆寫或刪除。
取得 owner 授權後更新 bundle，將進行中 change 的 task ID、plan 證據與驗證遷移至
v2 格式，再重新執行 preflight。舊的空白或缺少 FAIL 勾選不能視為 PASS。安裝與
升級不由本指引授權。
舊版 v2 的字串清單與 result 格式須遷移為上述狀態物件與 outcome 欄位。
