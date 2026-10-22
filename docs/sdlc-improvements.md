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

- Ruby slices averaged about 2 "changes requested" rounds per PR, and none was approved first time. Go slices averaged
  1, before the [quality bar](conventions.md#code-quality-bar) was set on 2026-10-10.
- After the bar, test findings dominate. The Bookshop app (`ruby/apps/`) has no `mutant.yml`, unlike the three gems,
  so the reviewer finds its surviving mutants by hand, a round after the developer could have.
- Of the 12 AC and contract findings, about 4 would clearly have been prevented by sharper ACs or contracts written
  before coding, and about 6 partly. All of them fall into the three gaps in [the plan template](#4-plan-template-additions).

## Proposals

Cheapest and most effective first.

| # | Proposal | Targets | Cost |
|---|---|---|---|
| 1 | Mutation config for the Ruby app | Tests (37%) | One small PR |
| 2 | Developer self-check before opening a PR | Quality, process, tests | A few lines in the developer brief |
| 3 | Parity fixtures in the shared `testdata/` | Parity contract findings | A fixture PR per parity point |
| 4 | Plan template additions | AC and contract findings | Plan template lines |
| 5 | Contract first at slice seams | Contract findings | One extra small PR per seam |
| 6 | Scripted pipeline, lead for exceptions only | Lead token cost | A workflow script |
| 7 | Designer only for new architecture | Phase 2 features | One session per feature |

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

### 3. Parity fixtures

Most contract findings were behaviour that differs from .NET and Go where no test compares them:

- path limits counted in another unit (#95);
- one-hour cache writes priced at the five-minute rate (#107);
- tool-result times dropping their microseconds (#108);
- the usage event without its cost (#114).

A shared fixture per parity point makes a difference fail a test instead of reaching review. Each fixture is added once,
by its own documented step (conventions, *Tests*).

### 4. Plan template additions

The phase 1 ACs are testable and cite requirement IDs. The findings came from three gaps:

| Gap | Example | Template line |
|---|---|---|
| Parity with the other implementations unstated | #107, #114 | "Matches .NET and Go in: …", each point backed by a fixture (proposal 3) |
| A slice split into parts leaves shared ACs unowned | The traversal-path property test sat in part A, and part B assumed it was done (#117) | Each AC names the part that owns it |
| Edge states unspecified | S06 says "Ctrl+C" but not what it does at the prompt (#108); S03 tests a cancel mid-stream, not a host leaving after a reply with tool calls (#90) | One "edge states" line per AC |

Whoever splits a wave applies the template: the owner, the lead or a short `Plan` session. A standing planner agent
would cost more than the roughly 5% of findings it could prevent. An up-front AC review by the developer and a tester
was considered and rejected for the same reason: the ACs are not where the rework is.

### 5. Contract first at slice seams

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

### 6. Scripted pipeline, lead for exceptions only

The slice flow is fixed: developer, fresh reviewer, fixer for at most 3 rounds, then auto-merge. Today an Opus lead
steps through it in a context that grows with every brief and report, so routine steps cost the most.

- **Proposal:** a script runs the normal case and escalates only exceptions: a third round fails, a contract
  conflicts, or a spend cap is reached.
- **The lead's remaining jobs:** planning a wave and judging unclear review outcomes. These are a few decisions per wave, which
  the owner or a short planning session can make.
- **Arbitration stays independent of planning:** the owner, or a fresh strict re-reviewer as the conventions already
  say.
- The reviewer and fixer rounds without the lead, trialled in #122, are part of this.

### 7. Designer only for new architecture

A designer agent pays off where ARCHITECTURE.md has no section yet, as for phase 2 features. A short session writes
that section and it is reviewed before any implementation starts, as "a change to a shared rule changes
ARCHITECTURE.md first" requires. Slices that port an existing design don't need one.

### Considered for later

- **Model by risk.** Sonnet develops well-specified slices, Opus those that touch the core's design rules. The reviewer
  stays Opus. Compare the rounds per PR of the two before adopting it.
- **A tester agent.** If tests still dominate after proposals 1 and 2, a tester tries edge states after implementation
  and writes tests that break the code. This is adversarial testing, not AC review.
- **Review by another model family** on risky PRs (the `gemini-subagent` skill). Its errors overlap less with Opus's
  than a second Opus review's do.

## Measuring

Before and after each adopted proposal, record per merged slice PR:

- the rounds of "changes requested";
- the must-fixes by cause, as in the evidence table;
- the tokens by role (lead, developer, reviewer, fixer), from [`agent-usage.md`](agent-usage.md).

A proposal that doesn't move its target is dropped.
