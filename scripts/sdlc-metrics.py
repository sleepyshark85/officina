#!/usr/bin/env python3
"""Writes docs/quality/<implementation>-<since>-<until>.md: the quality scorecard of the pull requests merged in a date
range that change an implementation (docs/sdlc-improvements.md, proposal 13), read from GitHub through `gh` and from
this repository with git. Only .NET has an entry so far.

Usage: python3 -B scripts/sdlc-metrics.py --since YYYY-MM-DD --until YYYY-MM-DD
Both dates are UTC and included. Run it from a checkout whose git has every merge of the range (fetch first). The page
is written only once it is complete, so a run that fails leaves it as it was.

Which pull requests belong to an implementation is what .github/changes.py decides for their merge commit's change.
The open alerts are read when the script runs, not as they were at the end of the range."""
import argparse
import importlib.util
import json
import re
import statistics
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, NamedTuple

ROOT = Path(__file__).resolve().parent.parent
QUALITY_DIR = ROOT / "docs" / "quality"

_spec = importlib.util.spec_from_file_location("changes", ROOT / ".github" / "changes.py")
changes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(changes)

# What .github/review_gate.py counts as a verdict. A verdict that is not an approval asks for changes, as it fails the
# gate.
VERDICT_AUTHORS = {"OWNER", "MEMBER", "COLLABORATOR"}
VERDICT_PREFIX = "**Verdict:"
APPROVAL_PREFIX = "**Verdict: APPROVE**"

# GitHub's search returns at most 1000 results; a range with more is refused rather than cut short.
SEARCH_LIMIT = 1000
COMMENTS_PER_PR = 100
RUN_LIMIT = 1000
# The newest runs searched for the latest full run of a workflow on main.
LATEST_RUN_WINDOW = 20
MAIN = "main"
RUN_FIELDS = "databaseId,displayTitle,createdAt,url,event"
RUN_FAILED = "failure"
RUN_SUCCEEDED = "success"
PULL_REQUEST_EVENT = "pull_request"

PULL_REQUESTS_QUERY = """
query($q: String!, $endCursor: String) {
  search(query: $q, type: ISSUE, first: 50, after: $endCursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number title url createdAt mergedAt
        mergeCommit { oid }
        comments(first: %d) { totalCount nodes { authorAssociation body } }
      }
    }
  }
}""" % COMMENTS_PER_PR

# Stryker's mutant statuses: its mutation score is detected over detected and undetected; the rest are not counted.
SURVIVED = "Survived"
NO_COVERAGE = "NoCoverage"
STRYKER_DETECTED = {"Killed", "Timeout"}
STRYKER_UNDETECTED = {SURVIVED, NO_COVERAGE}


class Workflow(NamedTuple):
    """A GitHub Actions workflow, by the name it shows and its file."""
    name: str
    file: str


class Suppression(NamedTuple):
    """A way to turn a check off in code: the text that marks it, and the pattern the rest of its line matches when it
    gives a reason."""
    marker: str
    reason: re.Pattern


class Implementation(NamedTuple):
    """Where one implementation's scorecard reads its data."""
    name: str
    title: str
    checks: tuple[Workflow, ...]
    dependabot_ecosystem: str
    suppressions: tuple[Suppression, ...]
    suppression_paths: tuple[str, ...]
    plan_docs: tuple[str, ...]
    mutation: Workflow
    mutation_artifact: str
    mutation_scores: Callable[[Path], list]
    coverage: Workflow
    coverage_artifact: str
    coverage_table: Callable[[Path], str]


class PullRequest(NamedTuple):
    """A merged pull request and the verdicts on it, oldest first."""
    number: int
    title: str
    url: str
    created: datetime
    merged: datetime
    merge_commit: str
    verdicts: list[str]

    @property
    def changes_requested(self):
        return sum(not verdict.startswith(APPROVAL_PREFIX) for verdict in self.verdicts)

    @property
    def merged_on_first_verdict(self):
        return self.verdicts[0].startswith(APPROVAL_PREFIX)

    @property
    def lead_time(self):
        return self.merged - self.created


class Run(NamedTuple):
    """A workflow run on main."""
    workflow: str
    id: int
    title: str
    created: datetime
    url: str
    event: str


class Alert(NamedTuple):
    """An open security alert: what it found, how severe, and where."""
    kind: str
    severity: str
    where: str
    url: str


class MutationScore(NamedTuple):
    """One package's result in a mutation run."""
    package: str
    score: float | None
    survived: int
    no_coverage: int


class SuppressionChanges(NamedTuple):
    """The suppressions added and removed between two commits, each as (path, line)."""
    added: list[tuple[str, str]]
    removed: list[tuple[str, str]]
    without_reason: list[tuple[str, str]]


def gh(*args):
    return subprocess.run(["gh", *args], cwd=ROOT, stdout=subprocess.PIPE, text=True, check=True).stdout


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, stdout=subprocess.PIPE, text=True, check=True).stdout


def read_pull_requests(since, until):
    """Every pull request merged in the range, in the order they merged."""
    repo = gh("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner").strip()
    query = f"repo:{repo} is:pr is:merged merged:{since}..{until}"
    pages = json.loads(gh("api", "graphql", "--paginate", "--slurp", "-f", f"query={PULL_REQUESTS_QUERY}",
                          "-f", f"q={query}"))
    if pages and pages[0]["data"]["search"]["issueCount"] > SEARCH_LIMIT:
        raise ValueError(f"More than {SEARCH_LIMIT} pull requests merged in {since}..{until}; split the range.")
    nodes = [node for page in pages for node in page["data"]["search"]["nodes"]]
    return sorted((pull_request(node) for node in nodes), key=lambda each: each.merged)


def pull_request(node):
    comments = node["comments"]
    if comments["totalCount"] > len(comments["nodes"]):
        raise ValueError(f"#{node['number']} has more than {COMMENTS_PER_PR} comments; its verdicts would be cut.")
    verdicts = [comment["body"] for comment in comments["nodes"]
                if comment["authorAssociation"] in VERDICT_AUTHORS and comment["body"].startswith(VERDICT_PREFIX)]
    return PullRequest(node["number"], node["title"], node["url"], datetime.fromisoformat(node["createdAt"]),
                       datetime.fromisoformat(node["mergedAt"]), node["mergeCommit"]["oid"], verdicts)


def changes_implementation(repo, merge_commit, implementation):
    # Without --no-renames a file moved between implementations lists only its new path, as in changes.py.
    paths = git(repo, "diff", "--no-renames", "--name-only", f"{merge_commit}^1", merge_commit).splitlines()
    return any(implementation.name in changes.owners(path) for path in paths)


def read_failed_runs(implementation, since, until):
    """The failed runs on main in the range of the workflows that check the implementation; cancelled ones are not
    failures."""
    runs = []
    for workflow in implementation.checks:
        listed = list_runs(workflow, f"{since}..{until}", RUN_FAILED, RUN_LIMIT)
        if len(listed) == RUN_LIMIT:
            raise ValueError(f"{RUN_LIMIT} or more failed {workflow.name} runs; split the range.")
        runs += listed
    return runs


def latest_full_run(workflow, until):
    """The newest successful run of the workflow on main created up to the date, not one of a pull request, or None."""
    listed = list_runs(workflow, f"<={until}", RUN_SUCCEEDED, LATEST_RUN_WINDOW)
    return next((run for run in listed if run.event != PULL_REQUEST_EVENT), None)


def list_runs(workflow, created, status, limit):
    """The workflow's runs on main created in the range (gh's date syntax) that ended in the status, newest first."""
    listed = json.loads(gh("run", "list", "--workflow", workflow.file, "--branch", MAIN, "--created", created,
                           "--status", status, "--limit", str(limit), "--json", RUN_FIELDS))
    return [Run(workflow.name, run["databaseId"], run["displayTitle"], datetime.fromisoformat(run["createdAt"]),
                run["url"], run["event"]) for run in listed]


def download_artifact(run, artifact, directory):
    gh("run", "download", str(run.id), "--name", artifact, "--dir", str(directory))


def read_alerts(implementation):
    """The open code-scanning alerts on the implementation's paths, then its open Dependabot alerts."""
    scanning = json.loads(gh("api", "--paginate", "--slurp", "repos/{owner}/{repo}/code-scanning/alerts?state=open"
                             "&per_page=100"))
    dependabot = json.loads(gh("api", "--paginate", "--slurp", "repos/{owner}/{repo}/dependabot/alerts?state=open"
                               f"&ecosystem={implementation.dependabot_ecosystem}&per_page=100"))
    alerts = [Alert(alert["rule"]["id"], alert["rule"]["security_severity_level"] or alert["rule"]["severity"],
                    alert["most_recent_instance"]["location"]["path"], alert["html_url"])
              for page in scanning for alert in page
              if implementation.name in changes.owners(alert["most_recent_instance"]["location"]["path"])]
    alerts += [Alert(alert["security_advisory"]["ghsa_id"], alert["security_advisory"]["severity"],
                     alert["dependency"]["package"]["name"], alert["html_url"])
               for page in dependabot for alert in page]
    return alerts


def suppressions_at(repo, commit, implementation):
    """Each suppression line at the commit, as (path, line), counted."""
    markers = [arg for suppression in implementation.suppressions for arg in ("-e", suppression.marker)]
    grep = subprocess.run(["git", "grep", "-z", "-F", *markers, commit, "--", *implementation.suppression_paths],
                          cwd=repo, stdout=subprocess.PIPE, text=True)
    # git grep exits 1 when nothing matches.
    if grep.returncode == 1:
        return Counter()
    grep.check_returncode()
    found = Counter()
    for match in grep.stdout.splitlines():
        location, line = match.split("\0", 1)
        found[(location.removeprefix(f"{commit}:"), line.strip())] += 1
    return found


def compare_suppressions(repo, before, after, implementation):
    earlier = suppressions_at(repo, before, implementation)
    later = suppressions_at(repo, after, implementation)
    added = sorted((later - earlier).elements())
    return SuppressionChanges(added, sorted((earlier - later).elements()),
                              [(path, line) for path, line in added if not gives_reason(line, implementation)])


def gives_reason(line, implementation):
    suppression = next(each for each in implementation.suppressions if each.marker in line)
    return suppression.reason.search(line.split(suppression.marker, 1)[1]) is not None


def plan_changes(repo, before, after, implementation):
    """The commits between two commits that change each plan or requirement doc, as (doc, [log line])."""
    return [(doc, git(repo, "log", "--no-merges", "--format=%h %cs %s", f"{before}..{after}", "--", doc).splitlines())
            for doc in implementation.plan_docs]


def stryker_scores(directory):
    """Each package's mutation score from the Stryker JSON reports in an artifact, laid out as
    <package>/StrykerOutput/<time>/reports/mutation-report.json."""
    scores = []
    for report in sorted(directory.glob("*/StrykerOutput/*/reports/mutation-report.json")):
        statuses = Counter(mutant["status"] for file in json.loads(report.read_text(encoding="utf-8"))["files"].values()
                           for mutant in file["mutants"])
        detected = sum(statuses[status] for status in STRYKER_DETECTED)
        valid = detected + sum(statuses[status] for status in STRYKER_UNDETECTED)
        scores.append(MutationScore(report.relative_to(directory).parts[0], 100 * detected / valid if valid else None,
                                    statuses[SURVIVED], statuses[NO_COVERAGE]))
    return scores


def cobertura_table(directory):
    return subprocess.run([sys.executable, "-B", str(ROOT / ".github" / "coverage-summary.py"), str(directory)],
                          stdout=subprocess.PIPE, text=True, check=True).stdout


DOTNET_CI = Workflow("CI", "ci.yml")
DOTNET_MUTATION = Workflow("Mutation", "mutation.yml")
DOTNET = Implementation(
    name="dotnet",
    title=".NET",
    checks=(DOTNET_CI, DOTNET_MUTATION, Workflow("CodeQL", "codeql.yml")),
    dependabot_ecosystem="nuget",
    suppressions=(
        # A reason is a comment after the codes, a non-empty Justification, or the text after Stryker's colon.
        Suppression("#pragma warning disable", re.compile(r"//\s*\S")),
        Suppression("SuppressMessage", re.compile(r'Justification\s*=\s*"\s*[^"\s]')),
        Suppression("Stryker disable", re.compile(r":\s*\S")),
    ),
    suppression_paths=("dotnet/*.cs",),
    plan_docs=("docs/plan/phase-1.md", "dotnet/docs/plan.md", "REQUIREMENTS.md", "ARCHITECTURE.md"),
    mutation=DOTNET_MUTATION,
    mutation_artifact="mutation-reports",
    mutation_scores=stryker_scores,
    coverage=DOTNET_CI,
    coverage_artifact="coverage-report",
    coverage_table=cobertura_table,
)
IMPLEMENTATIONS = (DOTNET,)


class Scorecard(NamedTuple):
    """Everything one page shows."""
    implementation: Implementation
    since: date
    until: date
    read_at: datetime
    pull_requests: list[PullRequest]
    failed_runs: list[Run]
    alerts: list[Alert]
    suppressions: SuppressionChanges
    plan_changes: list
    mutation_run: Run | None
    mutation_scores: list[MutationScore] | None
    coverage_run: Run | None
    coverage_table: str | None


def from_artifact(run, artifact, read):
    """What `read` makes of a run's artifact, or None when there is no run."""
    if run is None:
        return None
    with tempfile.TemporaryDirectory(prefix="sdlc-metrics-") as directory:
        download_artifact(run, artifact, directory)
        return read(Path(directory))


def collect(repo, implementation, since, until):
    """The scorecard of the range, or None when no pull request merged in it."""
    merged = read_pull_requests(since, until)
    if not merged:
        return None
    # The range's code runs from main before its first merge to its last merge.
    before, after = f"{merged[0].merge_commit}^1", merged[-1].merge_commit
    mutation_run = latest_full_run(implementation.mutation, until)
    coverage_run = latest_full_run(implementation.coverage, until)
    return Scorecard(
        implementation, since, until, datetime.now(timezone.utc),
        [each for each in merged if changes_implementation(repo, each.merge_commit, implementation)],
        read_failed_runs(implementation, since, until),
        read_alerts(implementation),
        compare_suppressions(repo, before, after, implementation),
        plan_changes(repo, before, after, implementation),
        mutation_run,
        from_artifact(mutation_run, implementation.mutation_artifact, implementation.mutation_scores),
        coverage_run,
        from_artifact(coverage_run, implementation.coverage_artifact, implementation.coverage_table),
    )


def minutes(duration):
    return f"{duration / timedelta(minutes=1):.0f}"


def cell(text):
    return text.replace("|", "/")


def day(moment):
    return moment.strftime("%Y-%m-%d")


def render_pull_requests(pull_requests):
    reviewed = [each for each in pull_requests if each.verdicts]
    rounds = sum(each.changes_requested for each in reviewed)
    first = sum(each.merged_on_first_verdict for each in reviewed)
    lines = ["## Pull requests", ""]
    if not pull_requests:
        return lines + ["None merged.", ""]
    lead_times = [each.lead_time for each in pull_requests]
    lines += [f"- **Merged:** {len(pull_requests)}, of which {len(reviewed)} with a verdict; the others count in "
              "neither total below.",
              f"- **Merged on their first verdict:** {first} of {len(reviewed)}.",
              f"- **\"Changes requested\" rounds:** {rounds}"
              + (f", {rounds / len(reviewed):.1f} per PR with a verdict." if reviewed else "."),
              f"- **Lead time from open to merge:** median {minutes(statistics.median(lead_times))} min, longest "
              f"{minutes(max(lead_times))} min.",
              "", "| PR | Title | Verdicts | Changes requested | Merged on first verdict | Lead time (min) |",
              "|---|---|---|---|---|---|"]
    for each in pull_requests:
        outcome = ([str(len(each.verdicts)), str(each.changes_requested),
                    "yes" if each.merged_on_first_verdict else "no"] if each.verdicts else ["no verdict", "-", "-"])
        lines.append(f"| [#{each.number}]({each.url}) | {cell(each.title)} | {' | '.join(outcome)} "
                     f"| {minutes(each.lead_time)} |")
    return lines + [""]


def render_failed_runs(implementation, runs):
    names = ", ".join(workflow.name for workflow in implementation.checks)
    lines = ["## Failed runs on main", "", f"Runs of {names} that failed (cancelled ones are left out).", ""]
    if not runs:
        return lines + ["None.", ""]
    lines += ["| Workflow | Run | Created (UTC) | Title |", "|---|---|---|---|"]
    lines += [f"| {run.workflow} | [{run.id}]({run.url}) | {run.created:%Y-%m-%d %H:%M} | {cell(run.title)} |"
              for run in sorted(runs, key=lambda run: run.created)]
    return lines + [""]


def render_alerts(implementation, alerts, read_at):
    lines = ["## Open security alerts", "",
             f"Code-scanning alerts on {implementation.title}'s paths and Dependabot alerts for "
             f"{implementation.dependabot_ecosystem}, open at {read_at:%Y-%m-%d %H:%M} UTC, when this page was "
             "generated.", ""]
    if not alerts:
        return lines + ["None.", ""]
    lines += ["| Alert | Severity | Where |", "|---|---|---|"]
    lines += [f"| [{alert.kind}]({alert.url}) | {alert.severity} | `{alert.where}` |" for alert in alerts]
    return lines + [""]


def render_suppressions(implementation, found):
    markers = ", ".join(f"`{suppression.marker}`" for suppression in implementation.suppressions)
    lines = ["## Suppressions", "",
             f"Lines with {markers} in `{'`, `'.join(implementation.suppression_paths)}`, from main before the "
             "range's first merge to its last merge. A line that moved counts as removed and added.", "",
             f"- **Added:** {len(found.added)}, of which {len(found.without_reason)} without a reason on the line.",
             f"- **Removed:** {len(found.removed)}.", ""]
    if found.added:
        lines += ["| Added in | Line | Reason given |", "|---|---|---|"]
        lines += [f"| `{path}` | `{cell(line)}` | {'no' if (path, line) in found.without_reason else 'yes'} |"
                  for path, line in found.added] + [""]
    if found.removed:
        lines += ["| Removed from | Line |", "|---|---|"]
        lines += [f"| `{path}` | `{cell(line)}` |" for path, line in found.removed] + [""]
    return lines


def render_plan_changes(changed_docs):
    lines = ["## Plan and requirement changes", "", "Commits in the range, merges left out, that change each doc.", ""]
    for doc, commits in changed_docs:
        lines.append(f"- **`{doc}`:** {len(commits) or 'none'}")
        lines += [f"  - {commit}" for commit in commits]
    return lines + [""]


def render_mutation(run, scores):
    lines = ["## Mutation score", ""]
    if run is None:
        return lines + ["No successful full run on main up to the end of the range.", ""]
    lines += [f"From the full run [{run.id}]({run.url}) of {day(run.created)}. The score is Stryker's: killed and "
              "timed-out mutants over those plus the survivors and the uncovered ones.", "",
              "| Package | Score | Survived | No coverage |", "|---|---|---|---|"]
    lines += [f"| `{score.package}` | {'n/a' if score.score is None else f'{score.score:.2f}%'} | {score.survived} "
              f"| {score.no_coverage} |"
              for score in scores]
    return lines + [""]


def render_coverage(run, table):
    if run is None:
        return ["## Coverage", "", "No successful run on main up to the end of the range.", ""]
    # The table brings its own heading.
    return [table.rstrip(), "", f"From the run [{run.id}]({run.url}) of {day(run.created)}.", ""]


def render(card):
    implementation = card.implementation
    intro = f"""# {implementation.title} quality scorecard, {card.since} to {card.until}

The pull requests merged in this range that change {implementation.title}, as `.github/changes.py` decides, and
the state of its code over the range. Generated by [`scripts/sdlc-metrics.py`](../../scripts/sdlc-metrics.py);
regenerate it rather than editing it:

```sh
python3 -B scripts/sdlc-metrics.py --since {card.since} --until {card.until}
```

A verdict is a comment the review gate reads (`.github/review_gate.py`); any verdict but an approval requested
changes. Dates are UTC.
"""
    sections = (render_pull_requests(card.pull_requests), render_failed_runs(implementation, card.failed_runs),
                render_alerts(implementation, card.alerts, card.read_at),
                render_suppressions(implementation, card.suppressions), render_plan_changes(card.plan_changes),
                render_mutation(card.mutation_run, card.mutation_scores),
                render_coverage(card.coverage_run, card.coverage_table))
    return "\n".join([intro, *(line for section in sections for line in section)]).rstrip() + "\n"


def main(argv, repo=ROOT, directory=QUALITY_DIR):
    """Writes each implementation's page for the range, or exits with a message when no pull request merged in it."""
    parser = argparse.ArgumentParser(description="Writes the quality scorecard of a date range.")
    parser.add_argument("--since", type=date.fromisoformat, required=True, help="first day, YYYY-MM-DD (UTC)")
    parser.add_argument("--until", type=date.fromisoformat, required=True, help="last day, YYYY-MM-DD (UTC)")
    args = parser.parse_args(argv)
    if args.since > args.until:
        parser.error("--since is after --until")
    for implementation in IMPLEMENTATIONS:
        card = collect(repo, implementation, args.since, args.until)
        if card is None:
            sys.exit(f"No pull request merged from {args.since} to {args.until}; nothing is written.")
        directory.mkdir(parents=True, exist_ok=True)
        page = directory / f"{implementation.name}-{args.since}-{args.until}.md"
        page.write_text(render(card), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
