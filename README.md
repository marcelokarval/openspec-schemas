# openspec-schemas

[English](./README.md) · [繁體中文](./README.zh-TW.md)

Community-contributed [OpenSpec](https://github.com/Fission-AI/OpenSpec) schemas. Each schema is a self-contained bundle that you copy into your project's `openspec/schemas/` directory and select per-change with `--schema <name>`.

## Bridges in this repository

| Bridge | Purpose | Status |
|--------|---------|--------|
| [`superpowers-bridge`](./superpowers-bridge/) | Bridges OpenSpec artifacts with [Superpowers](https://github.com/obra/superpowers) planning, TDD and review, including an evidence-first retrospective. | v2 local candidate; compatibility unverified |

## Why a separate repository?

[OpenSpec PR #970](https://github.com/Fission-AI/OpenSpec/pull/970) originally proposed `sdd-plus-superpowers` as a built-in schema. After maintainer review, the integration moved to a community repository — same pattern as [github/spec-kit's community extension catalog](https://speckit-community.github.io/extensions/), which keeps third-party tool integrations out of core.

Benefits:
- OpenSpec core does not take on Superpowers' release cadence
- Bridge can iterate independently
- Other community schemas can join this repository as siblings

## Install

See [`superpowers-bridge/README.md`](./superpowers-bridge/README.md) for the v2 contract and migration limits. Installation requires separate authorization.

## Roadmap

See [`docs/roadmap.md`](./docs/roadmap.md) for what's planned.

## License

MIT — see [LICENSE](./LICENSE).
