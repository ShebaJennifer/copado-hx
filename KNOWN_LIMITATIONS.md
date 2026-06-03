# Known Limitations — copado-hx

| # | Limitation | Workaround | Severity |
|---|-----------|------------|----------|
| 1 | CRT test execution uses mock mode in demo | Trial org has no CRT test cases with results. Mock data is realistic and demonstrates the feature correctly. Toggle `mock_mode` in `.copado-hx.json` | Low |
| 2 | OAuth token expires every ~2 hours | `copado-hx auth login` re-authenticates in 15 seconds via browser | Low |
| 3 | Single-org only — no multi-org switching | Reconfigure `.copado-hx.json` to point to a different org | Low |
| 4 | AI agent responses are non-deterministic | Streaming output shows real-time generation; responses may vary | Low |
| 5 | No automated test suite | Manual testing against live Copado org confirms all commands work | Medium |
| 6 | `result.c` field in commit payload rejected by our org | Omitted from payload. Module (`m`) and category (`c`) fields in changes array work correctly | None — resolved |
| 7 | Tooling API metadata query limited to 200 results per type | Covers most orgs. Enterprise orgs with 200+ classes of a single type would need pagination | Low |
| 8 | CRT confidence score uses a simplified formula | Production version would incorporate historical trends, component-level risk, and org-specific weights | Low |
