# Test report

A snapshot of `main` on **2026-10-12** (commit `a48a53c`): what is tested, how well, what gates a change, and what is
left to do. Fresh numbers come from every CI run (tests, coverage) and from mutant; see [Reproducing](#reproducing).

## Summary

| Measure | Result |
|---|---|
| Tests | **642**, all passing on Linux; Windows skips 112 (the Docker tests and a few platform cases) |
| Line coverage | **99.4%** (3,981 of 4,006 lines) of the workspace's own code |
| Mutation coverage | core **99.80%**, Claude **99.75%**, MCP **100%** (full runs, all methods) |
| Lint, types, gems | RuboCop: no offenses in 328 files; Steep: no type error; bundler-audit: no vulnerable gem |
| Required checks on every pull request | `ruby-ubuntu`, `ruby-windows`, `ruby-quality`, `ruby-mutation` ([decisions](decisions.md#required-checks)) |

## Test suites

From CI run [38203676507](https://github.com/sleepyshark85/officina/actions/runs/38203676507) on `a48a53c`, and a
local verbose run for the split by gem. All tests run in one process, one at a time, in random order, with warnings on.

| Part | Tests | What it tests |
|---|---|---|
| `officina` (core) | 325 | Run loop, tool pipeline, approval, audit, budgets, memory and its stores, telemetry, typed output, schema DSL and validator, conversations; property tests (`pbt`) |
| `officina-claude` | 51 | The Claude adapter against a fake API: request layout, streaming, retries, caching, context editing, failures |
| `officina-mcp` | 94 | The MCP client over stdio and streamable HTTP against the test kit's fake server; JSON-RPC and event-stream parsing with generated input |
| `officina-testing` | 12 | The test kit: scripted model, approver, recording sink, fake MCP server, prefix assertions |
| `apps/bookshop` | 144 | The application against PostgreSQL in Docker: tools, console, sessions, budgets, memory, exports, audit, summaries, telemetry, the command and its settings |
| Workspace (`test/`) | 14 | The dependency rules (TEST-05), the core's size budget, the warnings check, the Steep verdict |
| `examples/hello` | 1 | The GEN-06 sample with the scripted model |
| **Total** | **642** | Linux: 642 passed. Windows: 530 passed, 112 skipped |

- **Skipped on purpose:** on Windows and macOS, the tests that need PostgreSQL or the export server in Docker, and a few
  process and pipe cases Windows cannot reproduce ([running and testing](running-and-testing.md#tests-that-need-docker)).
- **No live test yet:** the Ruby suite makes no API call. The live smoke test (TEST-04) is planned for S13.
- **Fakes** replace only system boundaries: the model, the network and MCP servers, the clock, the human, and Docker's
  database where none runs (docs/conventions.md).
- **Speed:** the whole suite takes about 25 s locally. 557 tests take under 0.1 s, 75 under 0.5 s, 8 under 1 s (all
  `BookshopTest`, the tests of the `exe/bookshop` command), and 2 over 1 s, both against PostgreSQL (see [Open gaps](#open-gaps)).

## Coverage

Lines the tests run, measured with SimpleCov (`COVERAGE=1`); CI's `ruby-quality` job writes the total to its summary.

| Part | Lines | Covered |
|---|---|---|
| `officina` | 1,697 | **100%** |
| `officina-claude` | 267 | **100%** |
| `officina-mcp` | 594 | 99.5% |
| `officina-testing` | 273 | 97.1% |
| `apps/bookshop` | 1,128 | 99.2% |
| `examples` | 42 | 88.1% |
| **Total** | **4,006** | **99.4%** |

The 25 lines not run: the fake MCP server's error paths (8), the sample's interactive loop (5), and one or two lines in
each of `exports.rb`, `telemetry.rb`, `terminal.rb`, `child_process.rb`, `session_store.rb`, `summarizer.rb`,
`streamable_http.rb` and `bookshop.rb`. Coverage shows code ran, not that a test checked it, so it is reported, not
gated; mutation is the gate.

## Mutation testing

[mutant](https://github.com/mbj/mutant) changes the code on purpose (a removed statement, a swapped method, a changed
literal) and checks that a test fails. Full runs of every method, from each gem with a `mutant.yml`, on `a48a53c`, with
`PROPERTY_SEED=20261010` as in CI. Coverage is killed ÷ mutations; a timeout counts as killed.

| Gem | Mutations | Killed | Of them timeouts | Survived | Coverage | Local runtime |
|---|---|---|---|---|---|---|
| `officina` | 12,677 | 12,652 | 59 | 25 | **99.80%** | 12 min |
| `officina-claude` | 2,035 | 2,030 | 82 | 5 | **99.75%** | 2.5 min |
| `officina-mcp` | 3,321 | 3,321 | 200 | 0 | **100%** | 5 min |

- **A pull request** mutates only the methods it changes (`--since` the base), and any survivor fails it.
- **A full run** (push to `main`, weekly, on demand) fails a gem below 99%: all three are above it.
- **29 methods are excluded** with a `# mutant:disable -- <why>` comment, each judged in its PR's review: 23 in the MCP
  gem (process, pipe and socket timing), 4 in the core, 2 in the Claude gem.
- `officina-testing` and the application have no `mutant.yml`: their code is test support and the app, checked by
  their tests and coverage.

## Gates

| Where | Gate |
|---|---|
| Required checks (branch protection) | `ruby-ubuntu` (all tests, Docker included), `ruby-windows` (all tests, Docker ones skipped), `ruby-quality` (RuboCop, Steep, bundler-audit, coverage in the summary), `ruby-mutation` (no survivor in a changed method); with the other implementations' checks and `review`, the branch up to date |
| Other checks | CodeQL for the workflows |
| Claude Code hooks, blocking (`.claude/`) | No push to `main` or commit on `main`; branch prefixes; staging in its own command; before a commit that stages Ruby code, RuboCop and Steep; before a push, the tests |
| Claude Code hooks, reporting | After a `.rb` edit: `# frozen_string_literal: true` first, no requirement IDs in comments |

## Open gaps

Most important first:

| Gap | Why it matters |
|---|---|
| **CI's full mutation run never finishes.** `ruby-mutation` has a 30-minute limit and runs the three gems one after the other; on a CI runner the Claude gem alone took 13.5 min, and the run is cancelled during the MCP gem, so the core is never mutated in full. Every Ruby run on `main` since 2026-10-10 (41) ends *cancelled* | The 99% floor is not checked by CI; the numbers above come from a local run. Fix: one job per gem, or a longer limit |
| 25 survivors in 19 core methods | In 5 of them a survivor removes a `Mutex` (`Cancellation`, `HashMemoryStore`), which a deterministic test cannot observe; the rest are in `Conversation` (JSON reading and writing, `append`), the schema and input DSL, `MemoryRules.valid_path?`, `FileMemoryStore#directory` and `Block.canonical`, each to kill or show equivalent |
| 5 survivors in 3 Claude methods | `Model#check`, `Failure#transient?`, `Call#initialize` |
| Two tests over 1 s | `ConsoleInterruptsTest#test_app03_ctrl_c_at_the_first_of_two_approvals_asks_no_more` (2.2 s) and `ConsoleExportsTest#test_app12_an_order_history_is_exported_as_csv_after_approval` (1.2 s), both against PostgreSQL in Docker; measured once, locally |
| No live smoke test | TEST-04 waits for S13 |

## Reproducing

All from `ruby/` ([running and testing](running-and-testing.md#testing) has the details).

| What | How |
|---|---|
| Tests | `bundle exec rake test`; `TESTOPTS=-v` prints each test's time |
| Coverage | `COVERAGE=1 bundle exec rake test`, report in `coverage/` |
| Mutation | `cd <gem> && PROPERTY_SEED=20261010 bundle exec mutant run` (every method) or `… mutant run --since origin/main` (as on a PR) |
| Lint and types | `bundle exec rubocop`, `bundle exec rake steep` |
| Requirements to tests | [traceability.md](traceability.md) |
