# SDLC improvements

Proposals for how the agent team builds Officina, from a review of phase 1 on 2026-10-22. Nothing here is a rule
yet: each accepted item lands in [`conventions.md`](conventions.md), the [dispatch skill](../.claude/skills/dispatch/)
or an implementation's `decisions.md` through its own PR, and is then struck from this page.

## Evidence

Every must-fix in the "changes requested" verdicts of the 22 Ruby slice PRs (#83 to #124) and 8 Go slice PRs (#55 to
#72), sorted by cause. The sorting is one agent's reading of the verdicts, so the split is approximate.

| Cause | Ruby must-fixes | Share | Go must-fixes |
|---|---|---|---|
| Tests: surviving mutants, tests that pass for the wrong reason | 44 | 37% | 3 |
| Code quality bar | 29 | 25% | 1 |
| Real bugs | 19 | 16% | 3 |
| Process: PR description, merging main, CI | 14 | 12% | 6 |
| Contract between slices or with the design rules | 8 | 7% | 1 |
| Acceptance criterion missed or unclear | 4 | 3% | 2 |
| **Total** | **118** | | **16** |

- Ruby slices averaged about 2 "changes requested" rounds per PR, and none merged on its first verdict. Go slices averaged
  1. Three things differ between them, so the gap is not one cause:
  - Go was reviewed before the [quality bar](conventions.md#code-quality-bar) was set on 2026-10-10; some Ruby PRs
    straddled it.
  - Ruby brought new tools with their own learning curve (mutant, Steep).
  - Ruby split several slices into parts.
- After the bar, test findings dominate. The Bookshop app (`ruby/apps/`) has no `mutant.yml`, unlike the three gems,
  so the reviewer finds its surviving mutants by hand, a round after the developer could have.
- Of the 12 AC and contract findings, about 4 would clearly have been prevented by sharper ACs or contracts written
  before coding, and about 6 partly. All of them fall into the gaps in
  [the plan template](#8-plan-template-additions).
- Rounds measure friction, not quality. Some bugs got past review and were fixed after merge, for example #88, #122
  (a race in the stdio MCP client) and #144 (the audit of a cancelled approval). Escaped defects are not counted yet.

### Where the cost goes

| Cost | Why |
|---|---|
| The lead's context | Every brief, report and reply adds to it. Each later turn re-reads that context, so routine steps cost more as the session goes on |
| Agent cold starts | Each new agent re-reads CLAUDE.md, the conventions and the code. Fresh reviewers are worth it; extra handoffs are not |
| Review rounds | Up to 3 rounds of Opus review plus fixes: the largest cost, and the source of the quality |
| Parallel work | Saves wall-clock time, not money. It adds stacked PRs, retargeting and collisions in the shared scratchpad |

## Proposals

Cheapest and most effective first.

| # | Proposal | Targets | Cost |
|---|---|---|---|
| 1 | Mutation config for the Ruby app | Tests (37%) | One small PR |
| 2 | Developer self-check before opening a PR | Quality, process, tests | Lines in the developer brief |
| 3 | Recurring findings into linters and hooks | Quality (25%) | A cop or hook per finding |
| 4 | A cause on every must-fix | Measuring | A line in the reviewer brief |
| 5 | The developer fixes the first round | Cold starts, fix-induced findings | A dispatch change |
| 6 | A complete first review round | Rounds | A line in the reviewer brief, once 4 shows the need |
| 7 | Parity fixtures in the shared `testdata/` | Parity contract findings | A fixture PR per parity point |
| 8 | Plan template additions | AC and contract findings | Plan template lines |
| 9 | Contract first at slice seams | Contract findings | One extra small PR per seam |
| 10 | Conventions settled before a port or phase | Retrofit rework | Owner time before the first slice |
| 11 | Scripted pipeline, lead for exceptions only | Lead token cost | A workflow script |
| 12 | Designer only for new architecture | Phase 2 features | One session per feature |
| 13 | A quality scorecard per wave | Seeing the whole SDLC | A script like `agent-usage.py` |
| 14 | CodeQL for Ruby | Security flaws in Ruby code | A matrix row |
| 15 | A threat model and injection tests | Prompt injection through tool results | An ARCHITECTURE section and scripted tests |
| 16 | A live eval set for Bookshop | The real model's behaviour | Phase 2, with NS-12 |

Whether 9 to 11 are worth it depends on the work left. With few Ruby slices remaining, 1 to 6, 13 and 14 may be
enough, and the rest wait for phase 2.

### 1. Mutation config for the Ruby app

Give `ruby/apps/` a `mutant.yml` like the gems', so CI's diff-scoped mutation run covers it and the developer sees
survivors before review.

### 2. Developer self-check before opening a PR

Before opening or updating a PR, the developer:

- runs mutation on the code it changed;
- re-reads its own diff against the quality bar, as the next maintainer would;
- checks that the PR description matches the code;
- merges `main`.

It goes in the dispatch skill's developer and fixer briefs.

### 3. Recurring findings into linters and hooks

A quality finding the reviewer raises again and again, and that a tool can detect, becomes a check: a RuboCop cop, an
analyzer rule or a hook. Candidates are a literal the bar says to name, an item public by default, or a public item
without a doc comment. The reviewer's rounds then go to design and judgement.

### 4. A cause on every must-fix

The reviewer labels each must-fix in its verdict with one cause from the evidence table. Rebuilding that table from
free-text verdicts took an agent about 180k tokens. With labels it is a script, run at the end of every wave.

### 5. The developer fixes the first round

Today a fresh fixer re-reads the conventions and the code to fix the findings. The developer already holds that
context, so continuing it costs less and is less likely to break what it built. The reviewer stays new, which is the
independence that matters. A fresh fixer takes over when the developer nears its context limit, and for later rounds.

### 6. A complete first review round

#91 and #95 took 4 rounds each. If later rounds mostly raise new findings on code the fixes didn't touch, rather than
problems in the fixes, the reviewer brief asks for every finding in the first round. Decide once proposal 4's labels
show which it is; the conventions' "a later round may raise a missed must-fix, once" stays.

### 7. Parity fixtures

Most contract findings were behaviour that differs from .NET and Go where no test compares them:

- path limits counted in another unit (#95);
- one-hour cache writes priced at the five-minute rate (#107);
- tool-result times dropping their microseconds (#108);
- the usage event without its cost (#114);
- in Go, a fingerprint whose bytes differed from .NET's (#58).

A shared fixture per parity point makes a difference fail a test instead of reaching review. Each fixture is added once,
by its own documented step (conventions, *Tests*).

### 8. Plan template additions

The phase 1 ACs are testable and cite requirement IDs. The findings came from these gaps:

| Gap | Example | Template line |
|---|---|---|
| Parity with the other implementations unstated | #107, #114, Go #58 | "Matches .NET and Go in: …", each point backed by a fixture (proposal 7) |
| A slice split into parts leaves shared ACs unowned | The traversal-path property test sat in part A, and part B assumed it was done (#117) | Each AC names the part that owns it |
| Edge states unspecified | S06 says "Ctrl+C" but not what it does at the prompt (#108); S03 tests a cancel mid-stream, not a host leaving after a reply with tool calls (#90) | One "edge states" line per AC |
| An AC that cannot be met where the slice sits in the order | Go S08's resume across implementations needed the prefix parts of S09 to S12 (#68) | Each AC is checked against the slice order |

An implementation's `docs/plan.md` cells say how a slice is built; they also say what is checked, in these lines.

Whoever splits a wave applies the template: the owner, the lead or a short `Plan` session. A standing planner agent
would cost more than the roughly 5% of findings it could prevent. An up-front AC review by the developer and a tester
was considered and rejected for the same reason: the ACs are not where the rework is.

### 9. Contract first at slice seams

When a slice is split or a later slice depends on it, its first PR lands only the contract, and it is reviewed before
anything is built against it. The contract is:

- the interface or duck type, event fields and handler signatures, with doc comments;
- a contract test that a fake and the real implementation both pass;
- in Ruby, the RBS signatures, which Steep checks, so the contract cannot drift from the code.

Examples it would have prevented: the memory handler's scope (#117), the usage event's cost field (#114), and the
events the run relays (#100).

No class diagrams before coding. ARCHITECTURE.md already fixes components, contracts and flows. The class level beneath
it is each language's own ("port the behaviour, never the shape"), and a diagram drawn first drifts once the code
teaches something. Diagrams are drawn from the code afterwards, for readers, as `dotnet/docs/design/` is.

### 10. Conventions settled before a port or phase

The quality bar arrived in the middle of the Ruby port. That produced the audit and retrofit PRs (#140, #142, #143)
and the extra rounds on the PRs that straddled it. Before phase 2 or another implementation, the owner settles the
conventions and the bar, and the first slice starts after that.

### 11. Scripted pipeline, lead for exceptions only

The slice flow is fixed: developer, fresh reviewer, fixes for at most 3 rounds, then auto-merge. Today an Opus lead
steps through it in a context that grows with every brief and report (see [the costs](#where-the-cost-goes)).

- **Proposal:** a script runs the normal case and escalates only exceptions: a third round fails, a contract
  conflicts, or a spend cap is reached.
- **The lead's remaining jobs:** planning a wave and judging unclear review outcomes. These are a few decisions per
  wave, which the owner or a short planning session can make.
- **Arbitration stays independent of planning:** the owner, or a fresh strict re-reviewer as the conventions already
  say.
- **Parallel only where slices are independent.** Slices that share a contract run one after another, after their
  contract PR (proposal 9).
- **The owner checks in at wave boundaries:** approving the wave plan before work starts, and reading the
  [scorecard](#scorecard) at the end. Interruptions mid-wave are escalations only.
- The reviewer and fixer rounds without the lead, trialled in #122, are part of this.

### 12. Designer only for new architecture

A designer agent pays off where ARCHITECTURE.md has no section yet, as for phase 2 features. A short session writes
that section and it is reviewed before any implementation starts, as "a change to a shared rule changes
ARCHITECTURE.md first" requires. Slices that port an existing design don't need one.

### 13. A quality scorecard per wave

A script reads GitHub (PRs, verdicts, CI runs), the repository and the session transcripts, and writes the
[scorecard](#scorecard) for a wave, as `scripts/agent-usage.py` writes [`agent-usage.md`](agent-usage.md). It needs
proposal 4's cause labels for the must-fix split. The owner reads it at the end of each wave (proposal 11).

### 14. CodeQL for Ruby

`.github/workflows/codeql.yml` scans C#, Go and the workflows, but not Ruby, which CodeQL supports. Ruby's only
security check today is `bundler-audit`, which covers dependencies, not the code.

### 15. A threat model and injection tests

Officina runs a model that reads untrusted text: tool results, MCP servers' output, memory files, database rows. The
defences are structural: approval for writes, audit before a write runs, tools that take no SQL, and redaction. No page
states the threats they answer, and no test feeds the run an injection.

- A short threat-model section in ARCHITECTURE.md: each untrusted input, what it could make the model try, and which
  structural rule stops it.
- Scripted tests per implementation: a tool result or memory file carrying instructions makes the scripted model
  request a write, and the write still waits for approval and is audited. These test the structure, which doesn't
  depend on the model behaving.
- A live red-team pass over Bookshop's tools waits for proposal 16, under a spend cap.

### 16. A live eval set for Bookshop

The offline end-to-end tests (TEST-09) script the model, and the live smoke test (TEST-04) checks one flow. Nothing
measures how the real model does across many requests: the right tool chosen, out-of-scope requests declined,
approvals asked for. A small dataset of requests with expected tool calls, scored by assertions on the structured
signals rather than by a judging model, run on demand with a cap. It is the first user of the north star's evaluation
(NS-12), so it waits for phase 2.

### Considered for later

- **Model by risk.** Sonnet develops well-specified slices, Opus those that touch the core's design rules. The reviewer
  stays Opus. Compare the rounds per PR of the two before adopting it.
- **A tester agent.** If tests still dominate after proposals 1 and 2, a tester tries edge states after implementation
  and writes tests that break the code. This is adversarial testing, not AC review.
- **Review by another model family** on risky PRs (the `gemini-subagent` skill). Its errors overlap less with Opus's
  than a second Opus review's do.

## Quality monitoring

Two things are watched:

- the process that builds Officina, where agents write and review the code;
- the product, a library for AI agents and its reference application.

The phases follow a general SDLC quality guide the owner supplied, adapted to this repository.

### By phase

| Phase | What can go wrong | Metric | Source | Today |
|---|---|---|---|---|
| Requirements and plan | ACs ambiguous, unowned or unmeetable | AC and contract must-fixes per slice; AC or requirement changes after a slice started | Verdict labels (proposal 4); `git log` of the plan docs and REQUIREMENTS.md | Manual, from this review |
| Design | Contracts between slices break; threats not answered | Contract must-fixes; ARCHITECTURE.md changes per wave | Verdict labels; `git log` | No threat model (proposal 15) |
| Coding | Below the quality bar; debt added | First-verdict approvals; rounds per PR; must-fixes by cause; suppressions added | Verdicts; a count of `rubocop:disable`, `mutant:disable`, `nolint`, warning pragmas and Stryker disables | Rounds counted by hand |
| Security in code | Flaws, vulnerable dependencies, secrets | Open CodeQL and vulnerability alerts | CodeQL; `dotnet list package --vulnerable`, `govulncheck`, `bundler-audit` | No CodeQL for Ruby (proposal 14) |
| Testing | Tests that don't pin behaviour; flaky or slow tests | Mutation score of the full runs; survivors in PR runs; tests over a second | Mutation workflows; test timings | Gated per PR; trend not tracked |
| Merge | Bugs past review; `main` broken | Change failure rate (fix PRs to a wave's code, per slice PR); lead time from PR open to merge; failed CI runs on `main` | GitHub | Not measured |
| AI process | Spend; context bloat; live checks over their cap | Tokens per merged PR by role; live API spend against its cap | [`agent-usage.md`](agent-usage.md); the agents' reports | Tokens recorded; not per PR |
| Product at runtime | Cost or caching regressions; the real model misbehaving | Live smoke test result, cost and cache reads; eval pass rate | TEST-04; the app's telemetry; proposal 16 | Smoke test on demand; no trend |

### Scorecard

Written per wave by proposal 13's script. Baselines are from this review where one exists.

| Metric | Target | Baseline |
|---|---|---|
| Slice PRs merged on their first verdict | Rising | Ruby 0 of 22 |
| "Changes requested" rounds per slice PR | 1 or less | Ruby about 2, Go about 1 |
| Must-fixes by cause | Tests and quality shrinking | Ruby: tests 37%, quality 25% |
| Change failure rate | Falling | Not measured |
| Suppressions added, each with an agreed reason | No unexplained rise | Not measured |
| Mutation score of the full runs | At or above each implementation's floor | In each `decisions.md` |
| Failed CI runs on `main` | None | Not measured |
| Open CodeQL and vulnerability alerts | None | Not measured |
| Tokens per merged slice PR, by role | The lead's falling | Not split per PR |
| Live API spend against cap | Never over | S10 overshot once ($0.58 against $0.40) |
| Live smoke test | Passes, at about $0.40, with cache reads from the second call | On demand |

A proposal that doesn't move its target is dropped, and one that cuts rounds while the change failure rate rises is
reverted.

### Left out of the guide

| From the guide | Why it is left out |
|---|---|
| Uptime, APM, MTTR in production, NPS, customer-reported bugs, canary and blue-green releases | No deployed service: the library is used from source and Bookshop runs locally. Revisit if Bookshop is deployed |
| Data curation, drift and poisoning | No training or retrieval data; the seed is fixed. Redaction before data leaves is already a rule (EVT-03, D13) |
| Coverage over 80% as a target | Mutation testing is the gate and says more; coverage stays reported |
| Defect density per thousand lines, cyclomatic complexity as targets | Too noisy at this size. The linters' size rules and the core's line budget already bound complexity; the change failure rate measures defects |
| An LLM judging the code or the answers | The reviewer is already a model; the change failure rate checks it. Evals score structured signals, as the design rules require |
| Toxicity scores, runtime guardrail products | The provider's refusal ends a run as `Stopped(Refusal)`; Bookshop's risk is unapproved writes, which approval and audit answer (proposal 15) |
| Jira, SonarQube, TestRail, LangSmith and similar tools | GitHub, CI and the app's own OpenTelemetry already hold the data. A tool is added when a metric needs it |
