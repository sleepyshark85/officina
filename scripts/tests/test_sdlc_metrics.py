"""Tests for sdlc-metrics.py: gh is replaced by a fake that answers as GitHub does, and git runs on a scratch repository
built per test. Run: python3 -B -m unittest discover -s scripts/tests"""
import contextlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent.parent
spec = importlib.util.spec_from_file_location("sdlc_metrics", ROOT / "scripts" / "sdlc-metrics.py")
sdlc_metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdlc_metrics)

SINCE, UNTIL = date(2026, 10, 1), date(2026, 10, 22)


def comment(body, by="OWNER"):
    return {"authorAssociation": by, "body": body}


def approve(sha="a" * 40, by="OWNER"):
    return comment(f"**Verdict: APPROVE** at {sha}\n\nChecked.", by)


def request_changes(by="OWNER"):
    return comment(f"**Verdict: CHANGES REQUESTED** at {'b' * 40}\n\n1. Fix it.", by)


def pull_request_node(number, merge_commit, comments=(), created="2026-10-05T10:00:00Z",
                      merged="2026-10-05T11:30:00Z"):
    return {"number": number, "title": f"PR {number}", "url": f"https://github.com/owner/repo/pull/{number}",
            "createdAt": created, "mergedAt": merged, "mergeCommit": {"oid": merge_commit},
            "comments": {"totalCount": len(comments), "nodes": list(comments)}}


def run(run_id, event="push", created="2026-10-06T08:00:00Z"):
    return {"databaseId": run_id, "displayTitle": f"Run {run_id}", "createdAt": created,
            "url": f"https://github.com/owner/repo/actions/runs/{run_id}", "event": event}


def code_scanning_alert(path, rule="cs/log-forging", severity="medium"):
    return {"rule": {"id": rule, "security_severity_level": severity, "severity": "warning"},
            "most_recent_instance": {"location": {"path": path}},
            "html_url": f"https://github.com/owner/repo/security/code-scanning/{rule}"}


def stryker_report(*statuses):
    mutants = [{"id": str(index), "status": status} for index, status in enumerate(statuses)]
    return json.dumps({"schemaVersion": "2", "files": {"/src/Pkg/A.cs": {"mutants": mutants}}})


COBERTURA = """<?xml version="1.0"?>
<coverage line-rate="0.9" branch-rate="0.75"><packages>
<package name="Pkg" line-rate="0.9" branch-rate="0.75"/></packages></coverage>
"""


class FakeGitHub:
    """Answers the gh commands the script runs, from what a test sets, and records each call."""

    def __init__(self):
        self.pull_requests = []
        self.issue_count = None
        self.runs = {}
        self.code_scanning = []
        self.dependabot = []
        self.artifacts = {}
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        command, options = args[:2], dict(zip(args[2::2], args[3::2]))
        if command == ("repo", "view"):
            return "owner/repo\n"
        if command == ("api", "graphql"):
            search = {"issueCount": self.issue_count or len(self.pull_requests),
                      "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": self.pull_requests}
            return json.dumps([{"data": {"search": search}}])
        if command == ("run", "list"):
            return json.dumps(self.runs.get((options["--workflow"], options["--status"]), []))
        if command == ("run", "download"):
            options = dict(zip(args[3::2], args[4::2]))
            artifact = (int(args[2]), options["--name"])
            if artifact not in self.artifacts:
                raise subprocess.CalledProcessError(1, ["gh", *args], stderr="no valid artifacts found to download")
            for path, content in self.artifacts[artifact].items():
                target = Path(options["--dir"]) / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            return ""
        if args[0] == "api" and "/code-scanning/alerts?" in args[-1]:
            return json.dumps([self.code_scanning])
        if args[0] == "api" and "/dependabot/alerts?" in args[-1]:
            return json.dumps([self.dependabot])
        raise AssertionError(f"Unexpected gh call: {args}")


class SdlcMetricsTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory(prefix="sdlc-metrics-test-")
        self.addCleanup(scratch.cleanup)
        self.repo = Path(scratch.name) / "repo"
        self.pages = Path(scratch.name) / "quality"
        self.repo.mkdir()
        self.git("init", "--quiet", "--initial-branch=main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.com")
        self.base = self.commit({"README.md": "Officina\n"}, "Start")
        self.github = FakeGitHub()
        patcher = mock.patch.object(sdlc_metrics, "gh", self.github)
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True,
                              check=True).stdout.strip()

    def commit(self, files, message="change"):
        for path, content in files.items():
            target = self.repo / path
            if content is None:
                target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        self.git("add", "--all")
        self.git("commit", "--quiet", "--message", message)
        return self.git("rev-parse", "HEAD")

    def merge(self, files, message="change"):
        """Merges a branch with one commit of the files into main, as a pull request merges, and returns the merge."""
        self.git("switch", "--quiet", "--create", "pr")
        self.commit(files, message)
        self.git("switch", "--quiet", "main")
        self.git("merge", "--quiet", "--no-ff", "--message", "Merge pull request", "pr")
        self.git("branch", "--quiet", "--delete", "pr")
        return self.git("rev-parse", "HEAD")

    def merged(self, *nodes):
        self.github.pull_requests = list(nodes)

    def collect(self):
        return sdlc_metrics.collect(self.repo, sdlc_metrics.DOTNET, SINCE, UNTIL)

    def run_main(self):
        sdlc_metrics.main(["--since", str(SINCE), "--until", str(UNTIL)], repo=self.repo, directory=self.pages)
        return (self.pages / f"dotnet-{SINCE}-{UNTIL}.md").read_text(encoding="utf-8")

    def test_changes_py_loads_without_running_its_main(self):
        loader = importlib.util.spec_from_file_location("changes_import", ROOT / ".github" / "changes.py")
        module = importlib.util.module_from_spec(loader)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), mock.patch("sys.argv", ["changes.py", "dotnet"]):
            loader.loader.exec_module(module)
        self.assertEqual((output.getvalue(), module.owners("go/x.go")), ("", {"go"}))

    def test_dotnet_pull_requests_are_those_whose_merge_changes_a_path_changes_py_gives_dotnet(self):
        dotnet = self.merge({"dotnet/src/A.cs": "class A {}\n"})
        go = self.merge({"go/a.go": "package a\n"})
        shared = self.merge({"testdata/case.json": "{}\n"})
        root = self.merge({"docs/notes.md": "Notes\n"})
        self.merged(*(pull_request_node(number, sha) for number, sha in enumerate((dotnet, go, shared, root), 1)))
        self.assertEqual([each.number for each in self.collect().pull_requests], [1, 3, 4])

    def test_a_file_moved_out_of_dotnet_still_changes_dotnet(self):
        self.commit({"dotnet/Moved.cs": "class Moved { int value; }\n"})
        moved = self.merge({"dotnet/Moved.cs": None, "go/moved.cs": "class Moved { int value; }\n"})
        self.merged(pull_request_node(1, moved))
        self.assertEqual([each.number for each in self.collect().pull_requests], [1])

    def test_pull_requests_merged_in_the_range_are_searched_for_in_this_repository(self):
        self.merged(pull_request_node(1, self.merge({"dotnet/A.cs": "a\n"})))
        self.collect()
        query = next(call for call in self.github.calls if call[:2] == ("api", "graphql"))
        self.assertIn(f"q=repo:owner/repo is:pr is:merged merged:{SINCE}..{UNTIL}", query)

    def test_a_verdict_is_a_comment_starting_the_verdict_line_by_the_owner_a_member_or_a_collaborator(self):
        comments = [request_changes(by="CONTRIBUTOR"), comment("Looks fine. **Verdict: APPROVE**"),
                    request_changes(by="MEMBER"), approve(by="COLLABORATOR"),
                    comment("**Verdict: APPROVE** late", by="NONE")]
        pull_request = sdlc_metrics.pull_request(pull_request_node(1, "c" * 40, comments))
        self.assertEqual(pull_request.verdicts, [comments[2]["body"], comments[3]["body"]])

    def test_every_verdict_but_an_approval_is_a_changes_requested_round(self):
        comments = [request_changes(), comment("**Verdict: COMMENT** at x"), approve()]
        pull_request = sdlc_metrics.pull_request(pull_request_node(1, "c" * 40, comments))
        self.assertEqual((pull_request.changes_requested, pull_request.merged_on_first_verdict), (2, False))

    def test_an_approval_as_the_first_verdict_merges_on_it(self):
        pull_request = sdlc_metrics.pull_request(pull_request_node(1, "c" * 40, [approve()]))
        self.assertEqual((pull_request.changes_requested, pull_request.merged_on_first_verdict), (0, True))

    def test_lead_time_runs_from_open_to_merge(self):
        pull_request = sdlc_metrics.pull_request(pull_request_node(1, "c" * 40, created="2026-10-05T22:00:00Z",
                                                                   merged="2026-10-06T00:30:00Z"))
        self.assertEqual(pull_request.lead_time, timedelta(hours=2, minutes=30))

    def test_a_pull_request_with_more_comments_than_read_is_refused_rather_than_cut(self):
        node = pull_request_node(7, "c" * 40, [approve()])
        node["comments"]["totalCount"] = 101
        with self.assertRaisesRegex(ValueError, "#7 has more than 100 comments"):
            sdlc_metrics.pull_request(node)

    def test_a_range_beyond_what_search_returns_is_refused_rather_than_cut(self):
        self.merged(pull_request_node(1, self.merge({"dotnet/A.cs": "a\n"})))
        self.github.issue_count = 1001
        with self.assertRaisesRegex(ValueError, "More than 1000 pull requests"):
            self.collect()

    def test_pull_requests_without_a_verdict_show_as_such_and_count_in_neither_total(self):
        self.merged(pull_request_node(1, self.merge({"dotnet/A.cs": "a\n"})),
                    pull_request_node(2, self.merge({"dotnet/B.cs": "b\n"}), [request_changes(), approve()]),
                    pull_request_node(3, self.merge({"dotnet/C.cs": "c\n"}), [approve()]))
        page = self.run_main()
        self.assertIn("| [#1](https://github.com/owner/repo/pull/1) | PR 1 | no verdict | - | - | 90 |", page)
        self.assertIn("- **Merged:** 3, of which 2 with a verdict; the others count in neither total below.", page)
        self.assertIn("- **Merged on their first verdict:** 1 of 2.", page)
        self.assertIn("- **\"Changes requested\" rounds:** 1, 0.5 per PR with a verdict.", page)
        self.assertIn("| [#2](https://github.com/owner/repo/pull/2) | PR 2 | 2 | 1 | no | 90 |", page)
        self.assertIn("| [#3](https://github.com/owner/repo/pull/3) | PR 3 | 1 | 0 | yes | 90 |", page)
        self.assertIn("Runs of CI, Mutation, CodeQL that failed (cancelled ones are left out).\n\nNone.\n", page)

    def test_failed_runs_are_read_per_check_workflow_on_main_in_the_range(self):
        self.merged(pull_request_node(1, self.merge({"dotnet/A.cs": "a\n"})))
        self.github.runs[("codeql.yml", "failure")] = [run(41)]
        card = self.collect()
        listed = [call for call in self.github.calls if call[:2] == ("run", "list") and "failure" in call]
        self.assertEqual([dict(zip(call[2::2], call[3::2]))["--workflow"] for call in listed],
                         ["ci.yml", "mutation.yml", "codeql.yml"])
        self.assertTrue(all(("--branch", "main") == call[4:6] and f"{SINCE}..{UNTIL}" in call for call in listed))
        self.assertEqual([(failed.workflow, failed.id) for failed in card.failed_runs], [("CodeQL", 41)])

    def test_failed_runs_that_may_be_cut_at_the_limit_are_refused(self):
        self.github.runs[("ci.yml", "failure")] = [run(number) for number in range(1000)]
        with self.assertRaisesRegex(ValueError, "1000 or more failed CI runs"):
            sdlc_metrics.read_failed_runs(sdlc_metrics.DOTNET, SINCE, UNTIL)

    def test_the_latest_full_run_is_the_newest_successful_one_not_of_a_pull_request(self):
        self.github.runs[("mutation.yml", "success")] = [run(3, event="pull_request"), run(2, event="schedule"),
                                                         run(1, event="workflow_dispatch")]
        self.assertEqual(sdlc_metrics.latest_full_run(sdlc_metrics.DOTNET_MUTATION, UNTIL).id, 2)
        call = next(call for call in self.github.calls if call[:2] == ("run", "list"))
        self.assertIn(f"<={UNTIL}", call)

    def test_code_scanning_alerts_count_on_the_implementations_paths_and_dependabot_reads_its_ecosystem(self):
        self.github.code_scanning = [code_scanning_alert("spikes/go-claude-features/main.go"),
                                     code_scanning_alert("dotnet/src/A.cs", "cs/sql-injection", "high")]
        self.github.dependabot = [{"security_advisory": {"ghsa_id": "GHSA-1", "severity": "low"},
                                   "dependency": {"package": {"name": "Npgsql"}}, "html_url": "https://x/1"}]
        alerts = sdlc_metrics.read_alerts(sdlc_metrics.DOTNET)
        self.assertEqual([(alert.kind, alert.severity, alert.where) for alert in alerts],
                         [("cs/sql-injection", "high", "dotnet/src/A.cs"), ("GHSA-1", "low", "Npgsql")])
        dependabot = next(call for call in self.github.calls if "/dependabot/alerts?" in call[-1])
        self.assertIn("ecosystem=nuget", dependabot[-1])

    def test_suppressions_added_and_removed_over_the_range_and_those_added_without_a_reason(self):
        self.commit({"dotnet/Old.cs": "#pragma warning disable CA1031 // Old reason.\n"})
        first = self.merge({"dotnet/Old.cs": None,
                            "dotnet/A.cs": "#pragma warning disable CA1031 // Any failure fails the run.\n"
                                           "#pragma warning disable CA2000 //\n"})
        last = self.merge({"dotnet/B.cs": '[SuppressMessage("x", "CA1", Justification = "Owned by the caller.")]\n'
                                          '[SuppressMessage("x", "CA2", Justification = "")]\n'
                                          "// Stryker disable once all : equivalent\n"
                                          "// Stryker disable all\n",
                           "dotnet/docs/notes.md": "#pragma warning disable CA9\n",
                           "go/a.cs": "#pragma warning disable CA9\n"})
        self.merged(pull_request_node(1, first), pull_request_node(2, last))
        found = self.collect().suppressions
        self.assertEqual(found.removed, [("dotnet/Old.cs", "#pragma warning disable CA1031 // Old reason.")])
        self.assertEqual(len(found.added), 6)
        self.assertEqual(found.without_reason, [("dotnet/A.cs", "#pragma warning disable CA2000 //"),
                                                ("dotnet/B.cs", "// Stryker disable all"),
                                                ("dotnet/B.cs", '[SuppressMessage("x", "CA2", Justification = "")]')])

    def test_plan_changes_are_the_ranges_commits_to_each_plan_and_requirement_doc(self):
        self.commit({"REQUIREMENTS.md": "Before the range\n\n\n\nEnd\n"}, "Requirements before")
        first = self.merge({"REQUIREMENTS.md": "In the range\n\n\n\nEnd\n"}, "Requirements in range")
        # Both sides of this merge change the doc, so the merge differs from each parent.
        self.git("switch", "--quiet", "--create", "both")
        self.commit({"REQUIREMENTS.md": "In the range\n\n\n\nEnd, changed\n"}, "Requirements end")
        self.git("switch", "--quiet", "main")
        self.commit({"REQUIREMENTS.md": "Changed in the range\n\n\n\nEnd\n", "dotnet/docs/plan.md": "Plan\n"},
                    ".NET plan")
        self.git("merge", "--quiet", "--no-ff", "--message", "Merge both", "both")
        last = self.merge({"go/docs/plan.md": "Go plan\n"}, "Go plan")
        self.merged(pull_request_node(1, first), pull_request_node(2, last))
        changed = {doc: sorted(line.split(" ", 2)[2] for line in commits)
                   for doc, commits in self.collect().plan_changes}
        self.assertEqual(changed, {"docs/plan/phase-1.md": [], "dotnet/docs/plan.md": [".NET plan"],
                                   "REQUIREMENTS.md": [".NET plan", "Requirements end", "Requirements in range"],
                                   "ARCHITECTURE.md": []})

    def test_the_mutation_score_is_strykers_detected_over_detected_and_undetected(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "Pkg" / "StrykerOutput" / "2026-10-19.08-29-02" / "reports"
            report.mkdir(parents=True)
            (report / "mutation-report.json").write_text(stryker_report(
                *["Killed"] * 6, *["Timeout"] * 2, "Survived", "NoCoverage", *["CompileError"] * 5,
                *["Ignored"] * 3), encoding="utf-8")
            [score] = sdlc_metrics.stryker_scores(Path(folder))
        self.assertEqual(score, sdlc_metrics.MutationScore("Pkg", 80.0, 1, 1))

    def test_a_package_without_a_scored_mutant_has_no_score(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "Pkg" / "StrykerOutput" / "t" / "reports"
            report.mkdir(parents=True)
            (report / "mutation-report.json").write_text(stryker_report("Ignored"), encoding="utf-8")
            [score] = sdlc_metrics.stryker_scores(Path(folder))
        self.assertIsNone(score.score)

    def test_the_page_shows_the_mutation_and_coverage_of_the_latest_full_runs(self):
        self.merged(pull_request_node(1, self.merge({"dotnet/A.cs": "a\n"})))
        self.github.runs[("mutation.yml", "success")] = [run(5, event="schedule")]
        self.github.runs[("ci.yml", "success")] = [run(6)]
        self.github.artifacts[(5, "mutation-reports")] = {
            "Pkg/StrykerOutput/t/reports/mutation-report.json": stryker_report("Killed", "Killed", "Killed",
                                                                               "Survived")}
        self.github.artifacts[(6, "coverage-report")] = {"Pkg.Tests/coverage.cobertura.xml": COBERTURA}
        page = self.run_main()
        self.assertIn("| `Pkg` | 75.00% | 1 | 0 |", page)
        self.assertIn("| **Total** | **90.0%** | **75.0%** |", page)
        self.assertIn("From the run [6](https://github.com/owner/repo/actions/runs/6) of 2026-10-06.", page)

    def test_without_a_merged_pull_request_nothing_is_written(self):
        with self.assertRaises(SystemExit):
            self.run_main()
        self.assertFalse(self.pages.exists())

    def test_a_run_that_fails_leaves_the_page_as_it_was(self):
        self.merged(pull_request_node(1, self.merge({"dotnet/A.cs": "a\n"})))
        self.github.runs[("ci.yml", "success")] = [run(6)]
        page = self.pages / f"dotnet-{SINCE}-{UNTIL}.md"
        self.pages.mkdir()
        page.write_text("Earlier page\n", encoding="utf-8")
        with self.assertRaises(subprocess.CalledProcessError) as raised:
            self.run_main()
        self.assertEqual(raised.exception.cmd[:3], ["gh", "run", "download"])
        self.assertEqual(page.read_text(encoding="utf-8"), "Earlier page\n")


if __name__ == "__main__":
    unittest.main()
