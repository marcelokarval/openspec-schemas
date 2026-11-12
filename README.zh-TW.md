# openspec-schemas

[English](./README.md) · [繁體中文](./README.zh-TW.md)

社群貢獻的 [OpenSpec](https://github.com/Fission-AI/OpenSpec) schema 集合。每個 schema 都是一個自包式 bundle —— 把它複製到你專案的 `openspec/schemas/` 目錄,然後用 `--schema <name>` 在每次 change 個別選擇。

## 本 repo 提供的 bridges

| Bridge | 用途 | 狀態 |
|--------|------|------|
| [`superpowers-bridge`](./superpowers-bridge/) | 結合 OpenSpec 文件與 [Superpowers](https://github.com/obra/superpowers) 規劃、TDD、審查及證據導向的 retrospective。 | v2 本地候選，相容性未驗證 |

## 為什麼另外開一個 repo?

[OpenSpec PR #970](https://github.com/Fission-AI/OpenSpec/pull/970) 原本提議把 `sdd-plus-superpowers` 收進 OpenSpec 內建 schema。維護者 review 後建議改成社群 repo —— 這跟 [github/spec-kit 的 community extension catalog](https://speckit-community.github.io/extensions/) 處理第三方工具整合的模式相同:讓它們待在社群層,不進 core。

好處:

- OpenSpec core 不需要跟 Superpowers 的發布節奏綁在一起
- bridge 可以獨立疊代、發版
- 其他社群 schema 之後可以以 sibling 的方式加入本 repo

## 安裝

v2 合約與遷移限制見 [`superpowers-bridge/README.zh-TW.md`](./superpowers-bridge/README.zh-TW.md)。安裝須另行授權。

## Roadmap

未來規劃見 [`docs/roadmap.md`](./docs/roadmap.md)。

## License

MIT — 詳見 [LICENSE](./LICENSE)。
