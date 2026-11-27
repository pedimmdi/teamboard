# Contributing to TeamBoard

Fork the repository and start from the current `main`. Open a pull request that describes the problem, the change and how you verified it. A maintainer reviews changes before they are merged.

Follow the [local development guide](README.md), [architecture notes](docs/architecture.md) and [MCP guide](docs/mcp-local.md) for work on AI integrations. Use dedicated development data. Keep credentials, private records and commercially licensed assets out of pull requests. The bundled Vazirmatn font supports Persian development without a separate font license.

Run Django tests for backend changes and lint, type checking and unit tests for frontend changes. Run relevant Playwright tests for authentication, UI or end-to-end behavior. Include coverage for permissions and tenant boundaries when editing access to shared records. See [Tests](.github/workflows/tests.yml) for the full CI checks.

The project's [Code of Conduct](CODE_OF_CONDUCT.md) applies to contributions. Report security concerns through the [security reporting instructions](SECURITY.md).
