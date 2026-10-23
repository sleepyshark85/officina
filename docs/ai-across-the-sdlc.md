# AI across the SDLC

A discussion page, written on 2026-10-23. It walks the phases of
[Quality monitoring](sdlc-improvements.md#quality-monitoring) and, for each, sets out the industry's current practice
for building software with AI: what good looks like, how AI helps, what it makes harder, and how teams measure and
improve their AI use. It then compares Officina with that practice and lists what we can improve. Nothing here is a
rule; a point that becomes one goes through [`sdlc-improvements.md`](sdlc-improvements.md)'s route into the
conventions.

Industry practice moves fast and its sources vary in quality: published frameworks (DORA, NIST, OWASP, OpenSSF,
OpenTelemetry) are cited by name; vendor practice is described without endorsing a product. The repository facts are
from 2026-10-22 and 2026-10-23.

## The thesis

The owner's view: AI speeds the whole SDLC up a lot, but doesn't change the fundamentals of how an SDLC should work in
the CI/CD era.

The industry's evidence agrees on both halves. DORA's 2025 report on AI-assisted development describes AI as an
**amplifier**: it makes teams with strong practices (small batches, version control, a good internal platform, clear
policy on AI use) faster, and teams without them faster at producing instability. DORA's 2024 report had found more AI
adoption going with lower delivery stability, and METR's 2025 trial found experienced developers slower with AI while
believing they were faster. Speed without the fundamentals isn't a gain.

Officina is a case of the amplifier working: from the first commit (2026-10-05) to 142 merged PRs, two finished
implementations and a third in progress in 17 days, and every guard that made that safe is a CI/CD fundamental.

What AI does change is the **cost ratios between activities**, and practice is built on those ratios:

| Activity | Before | With agents | Consequence |
|---|---|---|---|
| Writing code | Expensive, the bottleneck | Nearly free | The bottleneck moves to specifying and verifying |
| Verifying code (review, tests) | A share of the writing cost | The largest cost (here: up to 3 Opus rounds per PR) | Verification capacity sets throughput; spend it on judgement, not on what a tool can check |
| Tests, mutation runs, property tests | Often skipped as too costly | Cheap to write and run | A higher bar is affordable: the owner raised it on 2026-10-10 |
| Knowledge transfer | Tacit, in people's heads | Every agent starts cold | What isn't written down (conventions, contracts, briefs) doesn't exist |
| A second implementation | Rarely worth it | Affordable | N-version builds find spec ambiguity (the parity findings, proposal 7) |

So the fundamentals hold, and three of them become load-bearing:

1. **Verification is the product of the process.** An agent optimizes against whatever check it can see. A check it
   can pass without the behaviour being right (a test that passes for the wrong reason: 37% of Ruby's must-fixes) is
   worse than no check.
2. **Independent review.** A model reviewing a model's code shares its blind spots. Independence has to be built in:
   fresh reviewers, different context, another model family, a human sample.
3. **The written process is code.** Agent definitions, skills, hooks and context files run on every task. They need
   versioning, review and measurement like the code they shape.

## How to read each phase

Each phase has the same four parts:

- **Industry practice:** what good teams do now, AI included.
- **AI helps, AI hurts:** where AI changes the phase.
- **Measuring AI use:** the metrics the industry uses for the AI's part in the phase.
- **Officina compared:** a table of each practice, what we have, and the gap. Gaps that an existing proposal covers
  name it (P1 to P16 in [`sdlc-improvements.md`](sdlc-improvements.md#proposals)); new ones are numbered N1 onward
  and collected in [Improvements](#improvements).

## 1. Requirements and plan

**Industry practice.**

- **Spec-driven development.** Agentic tools have converged on a written spec before code: requirements, then a
  design, then a task list, each reviewed by a person before the agent builds (GitHub's Spec Kit, Amazon's Kiro).
  Requirements are written in a structured form such as EARS ("When X, the system shall Y") or Given/When/Then so
  they map one to one onto tests.
- **Traceability.** Every requirement has an ID; every test names the ID it checks.
- **The spec is versioned with the code** and changed through the same review, because it is now the input the agents
  regenerate code from.
- **Ambiguity is surfaced, not filled.** Agents are told to ask, or to list their assumptions, rather than guess.

**AI helps:** drafting ACs and edge states; checking a spec for contradictions, missing error cases and untestable
words; checking that each AC can be met where its slice sits in the order. **AI hurts:** an agent fills a gap
silently and plausibly, so ambiguity surfaces late as a bug or a parity difference; a model-written spec reads well
and can still be unmeetable.

**Measuring AI use.** Requirement volatility (changes after build started); defects traced back to a spec gap; the
number of clarifying questions and recorded assumptions per task; the share of ACs with an executable test.

**Officina compared.**

| Practice | Here | Gap |
|---|---|---|
| Spec before code, reviewed | REQUIREMENTS.md, ARCHITECTURE.md and the phase 1 plan, all through PRs | None |
| Structured, testable requirements | IDs and testable ACs; prose rather than EARS | Edge states unspecified (#90, #108), shared ACs unowned in split slices (#117): P8 |
| Traceability | Test names carry IDs; a traceability page per implementation | None |
| Ambiguity surfaced | Agents fill gaps; findings arrive in review | N1: an *Assumptions* section in every PR description |
| Volatility measured | The scorecard lists plan and requirement commits | Not per slice yet: P13 |

## 2. Design

**Industry practice.**

- **Architecture decision records** (one short page per decision: context, decision, consequences) and C4-style views,
  kept next to the code.
- **Contract first.** Interfaces, schemas and events agreed before the code on either side, with contract tests that
  both sides run (consumer-driven contracts where there are services).
- **Fitness functions.** Architecture rules checked by tests in CI (allowed dependencies, layering), so a design rule
  can't erode silently.
- **Threat modelling as part of design**, updated per feature: STRIDE for the classic threats, and for agentic systems
  the OWASP Top 10 for LLM Applications (2025: prompt injection, excessive agency, improper output handling…), OWASP's
  agentic AI threat guidance and the Cloud Security Alliance's MAESTRO framework.

**AI helps:** exploring alternatives, drafting ADRs and contracts and their tests, drafting a threat model and keeping
it current, checking a change against stated rules. **AI hurts:** agents don't push back on a design and build
whatever shape the first file suggests; parallel agents each invent their side of a seam; a design can look complete
and answer no threat at all.

**Measuring AI use.** Contract or interface defects found after a seam is built; decisions made in code without a
record; threat model coverage (each untrusted input listed, each with a mitigation and a test).

**Officina compared.**

| Practice | Here | Gap |
|---|---|---|
| Decision records | REQUIREMENTS §7 and each `decisions.md`, as tables | None; the table form fits |
| Architecture views | ARCHITECTURE.md (language-neutral); .NET diagrams drawn from code | None |
| Contract first | Contracts in ARCHITECTURE §4; not at slice seams | Seam findings (#100, #114, #117): P9 |
| Fitness functions | The dependency check test (TEST-05), prefix stability (TEST-02), hooks for file layout | Fine for now |
| Threat model, LLM threats | Structural defences (approval, audit before write, no SQL tools, redaction), unstated | P15, mapped to the OWASP LLM Top 10's categories |

## 3. Coding

**Industry practice.**

- **Agents work from context files** in the repository (AGENTS.md, CLAUDE.md, rules files), kept short and current,
  plus skills or templates for repeated tasks.
- **Small batches.** Small PRs, one change each, trunk-based. With agents this matters more, as an agent produces
  large diffs cheaply and review cost grows faster than size.
- **Mechanical rules are tools, not reviews**: formatters, linters, type checkers, pre-commit hooks.
- **A human is accountable** for every merged change, whoever wrote it; AI authorship is visible (commit trailers,
  PR labels).
- **Agents run with least privilege**: sandboxed shell, scoped tokens, an allowlist of commands, no direct access to
  production or to the protected branch.

**AI helps:** speed; consistent application of written conventions; idiomatic code in a language the owner doesn't
write daily; refactors a person would postpone. **AI hurts:** volume beyond what anyone reads; plausible, subtly wrong
code (#88); code that meets a rule's letter; more duplication and churn (GitClear's analyses of 2024 and 2025 code
found both rising with AI assistance); **comprehension debt**, code that no person has understood end to end.

**Measuring AI use.** The common frameworks (DX's AI measurement framework, the SPACE dimensions, vendors' usage
APIs) measure three things together: **utilization** (share of PRs or lines AI-authored), **impact** (PR throughput,
lead time, review rounds, change failure rate, developer experience) and **cost** (spend per developer or per PR).
Code-level signals: PR size, churn (lines rewritten within weeks), duplication, suppressions added. Acceptance rate
of suggestions, once the headline metric, is falling out of use for agentic work, as it says nothing about quality.

**Officina compared.**

| Practice | Here | Gap |
|---|---|---|
| Context files and templates | CLAUDE.md per implementation, conventions, agent definitions, the dispatch skill | None |
| Small PRs | One slice or fix per PR, slices split into parts | PR size isn't measured: N2 |
| Mechanical rules as tools | Hooks before commit and push; analyzers with warnings as errors; RuboCop, Steep, golangci-lint | Recurring findings not yet tools: P3 |
| Self-check before review | Tests in hooks; no mutation or diff re-read before the PR | P2 |
| Accountable human, visible AI authorship | `Co-Authored-By` trailers; the owner delegated merge on approval | See *Merge* |
| Least privilege for agents | Hooks block pushes to `main` and bad branches; `.claude/settings.json` has no permission allowlist or sandbox, so agents get the session's permissions | N3 |
| Churn, duplication, suppressions | Suppressions in the .NET scorecard | Churn and duplication not measured: N2 |

## 4. Security in code

**Industry practice.**

- **A secure development framework**: NIST's SSDF (SP 800-218) and its profile for generative AI (SP 800-218A), which
  adds the model and its data to the supply chain.
- **Scanning on every change and on a schedule**: SAST, dependency vulnerabilities, secrets with push protection.
- **Supply chain hygiene** (OpenSSF and SLSA): actions and dependencies pinned by hash, workflows with least-privilege
  tokens, an OpenSSF Scorecard run, and for released artifacts an SBOM and build provenance.
- **AI-specific risks**: package hallucination ("slopsquatting", agents suggesting packages that don't exist and that
  attackers then register), insecure patterns reproduced from training data, and the coding agent itself as an attack
  surface (prompt injection through a file, issue or web page it reads, acting with the developer's credentials).

**AI helps:** fixing alerts fast; reviewing against a security checklist without fatigue; writing the injection tests.
**AI hurts:** dependencies added freely; insecure but plausible code; an agent with shell and push rights reading
untrusted text.

**Measuring AI use.** Alerts introduced versus fixed by AI-authored PRs; time to fix an alert; dependencies added per
period and whether each was justified; OpenSSF Scorecard score over time.

**Officina compared.**

| Practice | Here | Gap |
|---|---|---|
| SAST | CodeQL for C#, Go and the workflows, weekly and per PR | Not Ruby: P14 |
| Dependency vulnerabilities | `dotnet list package --vulnerable`, `govulncheck`, `bundler-audit`; Dependabot security updates on | .NET's scan not scheduled weekly (named in the improvements page) |
| Secrets | Secret scanning and push protection on | Non-provider patterns off: N4 |
| New dependencies justified | The bar's *Dependencies* row: a decisions line, licence, maintenance | None; it also answers slopsquatting |
| Least-privilege workflows | Each workflow declares `permissions` | None |
| Actions pinned by hash | Most actions pinned by tag (`@v4`, `@v7`); golangci-lint by hash | N4 |
| OpenSSF Scorecard | Not run | N4 |
| SBOM and provenance | No releases yet: the library is used from source | At the first release: N9 |
| Agent as attack surface | Hooks protect `main`; the review gate counts only trusted authors' verdicts | No sandbox or allowlist: N3 |
| Threat model for the product | Unstated | P15 |

## 5. Testing

**Industry practice.**

- **Fast, deterministic tests** with only the boundaries faked; flaky tests quarantined and fixed, tracked as a rate.
- **Mutation testing in code review.** Google reports running mutation on the changed lines of each code review
  rather than on whole codebases; that is now the established way to make it affordable.
- **Property-based and fuzz testing** for parsers, validators and state machines.
- **AI-generated tests checked by an oracle.** Meta's published work (TestGen-LLM in 2024, and mutation-guided test
  generation in 2025) keeps a generated test only if it builds, passes reliably and kills a mutant or adds coverage.
  A generated test that can't fail is discarded.
- **Contract tests** between components built separately.

**AI helps:** this is where AI changes most. Tests, fuzzers, property tests and fakes cost little, so a mutation gate,
once gold-plating, becomes normal. **AI hurts:** an agent asked to make tests pass will make them pass: assertions
that hold with the behaviour broken, mocks inside the system, tests shaped to the implementation. Goodhart's law at
machine speed, which is why the oracle must check the tests, not the code.

**Measuring AI use.** Mutation score and survivors per PR; the share of generated tests that kill a mutant; flaky
rate; suite duration; test-related review findings.

**Officina compared.**

| Practice | Here | Gap |
|---|---|---|
| Boundaries only, deterministic | A convention; real PostgreSQL in Docker; scripted model, approver and MCP server | None |
| Diff-scoped mutation in review | Per PR for all three implementations; full runs weekly | Not on the Ruby app or test kit: P1. Agents see survivors only in review: P2 |
| Property and fuzz tests | Required for every parser and validator (TEST-07, TEST-08) | None |
| Generated tests checked by an oracle | Mutation catches weak tests, but in CI, after the PR opens | P2: the developer runs mutation and keeps only tests that kill something |
| Contract tests across implementations | Shared `testdata/` fixtures for some points | Parity points without a fixture: P7 |
| Flaky and slow tests tracked | "A flaky test is a bug" rule; no measurement | Slow tests in P13; flaky reruns not counted: N2 |

## 6. Merge and release

**Industry practice.**

- **Trunk-based development** with required checks, an up-to-date branch or a **merge queue**, and code owners.
- **AI review as a first pass, a person approves.** Most organizations using AI review tools keep a human approval as
  the merge condition, at least for risky paths. Review by a second model family is used where errors must be caught
  independently.
- **DORA's metrics**, which since 2024 are five: deployment frequency, lead time, failed deployment recovery time,
  change failure rate and **rework rate** (unplanned changes to fix what shipped). Throughput and stability are read
  together.
- **For libraries**: semantic versioning, an API compatibility check in CI, release notes, and provenance on releases.
- **Progressive delivery** (feature flags, canaries) where there is a service.

**AI helps:** agents rebase, retarget and fix CI without friction; review is immediate. **AI hurts:** throughput
numbers inflate and stop meaning what they used to (a 23-minute median lead time says the agents are fast, not that
the change is good); model review is fast and can be wrong in ways a second model of the same family repeats.

**Measuring AI use.** DORA's five metrics split by AI-authored versus not; review rounds; escaped defects by cause; the
share of PRs a person read.

**Officina compared.**

| Practice | Here | Gap |
|---|---|---|
| Protected trunk, required checks, up to date | 15 required checks, strict up-to-date | Merge queue waits for the gate to support `merge_group` (dispatch `later.md`) |
| Approval as the merge condition | The review gate: a verdict naming the commit, from a trusted author | — |
| A person approves | The owner delegated approval to a fresh Opus reviewer | The main departure from industry practice. N5: the owner reads a random sample per wave |
| Independent review | A fresh reviewer per PR; strict re-review | Same model family throughout: "review by another model family" (considered for later) on risky PRs |
| Change failure and rework rate | Escaped defects known by example (#88, #144); not counted | P13's `Escaped from:` line; N6 adds rework rate |
| Library releases | Used from source, no versions | N9 at the first release |

## 7. The AI process itself

This phase has no counterpart before AI: the agents are a production system with their own cost, capacity and
failure modes. The industry calls the practice **AI governance** at the organization level and **agent operations**
at the team level.

**Industry practice.**

- **A clear AI policy**: which tools, which models, which data, which tasks are allowed. DORA 2025 lists this as the
  first of the capabilities that make AI pay off.
- **Instructions are versioned and evaluated.** Prompts, agent definitions and skills live in version control; a
  change to them is tested against a fixed set of tasks before it spreads (evals for the process, not only for the
  product).
- **Cost management**: budgets per agent, task and person; cost per delivered change tracked.
- **Agent observability**: every agent's calls, tools and tokens traced, the OpenTelemetry generative-AI conventions
  now covering agent and tool spans.
- **Human-in-the-loop by risk**: autonomy levels decided per task type, escalation paths defined.
- **Management systems** for organizations that need them: NIST's AI Risk Management Framework, ISO/IEC 42001.

**AI helps:** the process can measure itself: transcripts are complete logs, so reports are scripts, not surveys.
**AI hurts:** context is a hidden cost. Of about 2.46 billion input tokens processed in the recorded sessions, the five
lead sessions account for 28%, more than three times all reviewers (9%); developers are 48%.

**Measuring AI use.** Cost per merged change by role; escalations to a person per unit of work; autonomy rate (tasks
finished without human intervention); instruction changes and the metric each moved.

**Officina compared.**

| Practice | Here | Gap |
|---|---|---|
| Clear AI policy | Roles, models and review rules in the conventions; owner rules in memory | None at this size |
| Instructions versioned | Agent definitions, dispatch skill, hooks in the repository, changed through PRs | — |
| Instructions evaluated | A change is judged by the next PRs' rounds, by impression | N7: each process change names the scorecard metric it should move, and is kept or reverted on it |
| Cost tracked | `agent-usage.py` per session and agent | Not per PR or role: P13 |
| Budgets and context limits | Live-check spend caps; the context-size hook at 150k and 300k | Live spend not read from the provider: P13 |
| Autonomy by risk | Owner delegated merge; escalation after 3 rounds | Escalations not counted: N2 |
| Scripted orchestration | The lead runs the pipeline by hand | P11 |

## 8. Product at runtime

Officina is itself a library for AI agents, so the product has the same problem the process has: a non-deterministic
component in the middle. The industry practice here is **LLMOps**.

**Industry practice.**

- **Evaluation-driven development.** An eval set of realistic tasks, scored by code assertions where possible and by a
  calibrated model judge only where not, run on every prompt, tool or model change and tracked over time.
- **Observability with the OpenTelemetry generative-AI semantic conventions**: spans per model and tool call with
  tokens, cost, latency, errors; content capture off by default.
- **Guardrails by design**: least agency (tools scoped to the task), human approval for consequential actions, audit
  of every write, validated structured output; input and output filters as a second layer.
- **Red teaming** against the OWASP LLM Top 10, prompt injection above all, before release and on model change.
- **Model change management**: model versions pinned, an upgrade treated as a release (evals first), cost and latency
  regressions alerted on.

**AI helps:** evals and red-team inputs can be generated at scale. **AI hurts:** a model or prompt change shifts
behaviour without a code diff; offline tests can't see it; cost and caching regress silently; untrusted text reaches
the model.

**Measuring AI use.** Eval pass rate per model and version; cost, cache hit ratio and latency per run; refusals and
stopped runs by reason; approvals asked and denied; injection test pass rate.

**Officina compared.**

| Practice | Here | Gap |
|---|---|---|
| OpenTelemetry generative-AI conventions | EVT-02: spans and metrics by those conventions; content off by default (EVT-04) | None |
| Guardrails by design | Approval for writes, audit before a write, tools without SQL, validated output, structured signals decide | None; stated by P15 |
| Evals | Scripted end-to-end tests; one live smoke test on demand | P16 (phase 2, NS-12) |
| Red teaming | None | P15's scripted injection tests, then a live pass |
| Model change management | The default model set in code; spikes per SDK | N8: a model change runs the smoke test (and later the eval set) before it becomes the default |
| Cost and caching regressions | The smoke test asserts cache reads; not trended | P13's weekly smoke test |

## Measuring AI use: the layers

Every phase measures the same four layers. Watching only the first two is how teams conclude AI made them faster while
it made them worse.

| Layer | Question | Industry measures | Officina's |
|---|---|---|---|
| Cost | What did it spend? | Spend per developer, per change | Tokens by role; live spend caps |
| Flow | How fast does work move? | Lead time, throughput, deployment frequency | Lead time, rounds per PR |
| Quality | Is what moved good? | Change failure rate, rework rate, defects, security alerts | Mutation, alerts, must-fixes by cause; failure rate pending |
| People | What did it take from, or give to, the humans? | Developer experience surveys, time saved, cognitive load | Not measured: N2's escalation count |

For a one-owner project the fourth layer is the owner's attention: escalations, decisions, time reading the
scorecard. If it rises, the process leaks routine work back to the owner, however good the other numbers look.

## Improvements

The new items, ranked by value for cost. The existing proposals keep their order in
[`sdlc-improvements.md`](sdlc-improvements.md#proposals); this comparison mostly confirms them, P2, P13 and P15
above all.

| # | Improvement | Phase | Cost |
|---|---|---|---|
| N4 | Pin every action by hash, enable secret scanning's non-provider patterns, run the OpenSSF Scorecard workflow | Security | One small PR |
| N1 | An *Assumptions* section in every PR description: what the spec left open and what the agent chose | Requirements | A line in the developer brief |
| N3 | An agent permission policy in `.claude/settings.json`: allowlisted commands, denied destructive ones (force push, branch deletion, `gh pr merge` outside the pipeline), the sandbox where available | Coding, security | One small PR, then tuning |
| N2 | More scorecard columns: PR size, churn within the wave, flaky reruns, escalations to the owner | Coding, process | Lines in `sdlc-metrics.py` |
| N5 | The owner reads one randomly chosen merged PR per wave in full and records what review missed | Merge | Owner time per wave |
| N6 | Rework rate beside change failure rate: fix PRs to a wave's code within the next wave | Merge | Lines in `sdlc-metrics.py`, with P13's `Escaped from:` |
| N7 | Each process change states the metric it should move; the next scorecard keeps or reverts it | Process | A line in the PR template for process changes |
| N8 | A model change is a release: smoke test (later the eval set) before a new default model | Runtime | A line in the conventions |
| N9 | At the first release: semantic versions, an API compatibility check, SBOM and provenance | Merge, security | When releases start |

Left out on purpose, as in [the improvements page](sdlc-improvements.md#left-out-of-the-guide): SonarQube, LangSmith
and similar platforms, coverage targets, and a model judging code or answers. Acceptance rate of suggestions is left
out too: it measures autocomplete, not agents.

## To discuss

1. **Comprehension debt.** Nobody has read all the code. Is that acceptable for a library others will build on? N5 is
   the cheapest answer; reading the spec closely (point 2) is the other.
2. **The spec as source.** If code is regenerable, `REQUIREMENTS.md`, `ARCHITECTURE.md` and the shared fixtures are
   the real source. Should they get the strictest review, ahead of the code?
3. **Human approval.** Industry keeps a person as the merge condition; we replaced that with a fresh model reviewer
   and a gate. Is the change failure rate, once measured, enough evidence to keep that, and what rate would make us
   go back?
4. **Goodhart on the scorecard.** Agents optimize what they can see. Keep the scorecard out of their briefs: the briefs
   carry the rules, the scorecard judges the rules.
5. **The owner's skills.** The process works because the owner can judge code and design. Keeping that judgement sharp
   (reading code, writing an occasional slice by hand) is part of the process, not outside it.
