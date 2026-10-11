# Go plan

Go's part of the [phase 1 plan](../../docs/plan/phase-1.md): the shared slices and their acceptance criteria are
there, and its decisions in [`decisions.md`](decisions.md).

## Per slice

How Go realizes a slice, where it differs from the shared criteria.

| Slice | Go |
|---|---|
| [S01](../../docs/plan/phase-1.md#slices) | `go.mod` (G1, G2), `doc.go` per package, `.golangci.yml`, `go.yml` with its own required checks (G15); hooks run the Go checks for files under `go/` and the .NET ones for the rest; a `go-rules.py` edit hook that flags a package without `doc.go` and requirement IDs in comments; the dependency test checks direct imports (G4, G6); checks `gremlins` runs on Go 1.27 (G12) |
| [S02](../../docs/plan/phase-1.md#slices) | [`go/docs/spikes/claude-features.md`](spikes/claude-features.md): all seven features typed in the SDK; blocks stored in the canonical form and replayed through `param.Override` |
| [S03](../../docs/plan/phase-1.md#slices) | The run as `iter.Seq[RunEvent]` plus result (G10); `jsontext.Value` blocks in the canonical form (G9), pinned by a test that marshals, unmarshals and marshals again a conversation holding `<`, `&`, non-ASCII and `\u` escapes; `goleak` clean; a consumer that `break`s mid-run leaves no goroutine; 100 concurrent runs under `-race`; sets the core line budget (G13) |
| [S04](../../docs/plan/phase-1.md#slices) | Blocks stored canonical as they arrive; the model settings string the fingerprint uses agreed with .NET's (for Go S08); a reply's `tool_use` blocks never left in the conversation without results, as the real API rejects the next request; retries tested on `httptest.Server`; `examples/hello`. Conversation JSON compares across implementations as parsed JSON; only each block's raw JSON, and the request messages built from it, compare byte for byte |
| [S05](../../docs/plan/phase-1.md#slices) | Every `tool_use` block gets its result (until now a tool-use stop is Failed and its reply has none); Schema derived with `reflect` (the one place `go/CLAUDE.md` allows it); reads under a `sync.WaitGroup`; the event channel sized from the call count; a panicking tool becomes an error result; fuzz test of the validator; `rapid` properties; the first `gremlins` run sets the mutation threshold |
| [S06](../../docs/plan/phase-1.md#slices) | `cmd/bookshop` on `pgx` (G7); Ctrl+C through `signal.NotifyContext`; end-to-end tests with `testcontainers-go` |
| [S07](../../docs/plan/phase-1.md#slices) | The OpenTelemetry API with host-passed providers (G6); the SDK's in-memory exporter in tests only |
| [S08](../../docs/plan/phase-1.md#slices) | The fingerprint matches .NET's byte for byte (its JSON escaping, the tool schemas as given rather than re-encoded, and the model settings string agreed in Go S04). Cross-implementation resume is proven at the core level: shared fixtures in `testdata/session/`, a session each implementation saved mid-reply resuming in the other. The Bookshop sessions do not resume across implementations yet, as .NET's chat agent has more in its prefix: they wait for memory (Go S09), context management (Go S10, which brings the fingerprint's `contextManagement` part), the MCP export tools (Go S11) and typed output (Go S12, the `output` part) |
| [S09](../../docs/plan/phase-1.md#slices) | Fuzz test of path scoping, besides the `rapid` property |
| [S10](../../docs/plan/phase-1.md#slices) | Checks on-demand compaction and `clear_at` live before relying on them (Go S02 left them unproven) |
| [S11](../../docs/plan/phase-1.md#slices) | Stdio through `os/exec`, Streamable HTTP through `net/http`; fuzz test of message parsing; the child process is stopped and waited for when the context ends |
| [S12](../../docs/plan/phase-1.md#slices) | The output schema through S05's schema derivation |
| [S13](../../docs/plan/phase-1.md#slices) | `examples/` as runnable `Example` tests and programs; the live smoke test behind a build tag; `go/docs/traceability.md` complete; a Bookshop session the .NET application saved resumes in the Go one with the same prefix and cache reads (live, once; a live test builds and runs the .NET application). It found that the schemas Go derives must be .NET's bytes, description first and strings escaped as .NET's encoder does, as the fingerprint takes each schema as given |

## Progress

| Slice | Go |
|---|---|
| [S01](../../docs/plan/phase-1.md#slices) | Merged (#56) |
| [S02](../../docs/plan/phase-1.md#slices) | Merged (#55) |
| [S03](../../docs/plan/phase-1.md#slices) | Merged (#58) |
| [S04](../../docs/plan/phase-1.md#slices) | Merged (#59) |
| [S05](../../docs/plan/phase-1.md#slices) | Merged (#61) |
| [S06](../../docs/plan/phase-1.md#slices) | Merged (#63) |
| [S07](../../docs/plan/phase-1.md#slices) | Merged (#64) |
| [S08](../../docs/plan/phase-1.md#slices) | Merged (#68) |
| [S09](../../docs/plan/phase-1.md#slices) | Merged (#71) |
| [S10](../../docs/plan/phase-1.md#slices) | Merged (#70) |
| [S11](../../docs/plan/phase-1.md#slices) | Merged (#69) |
| [S12](../../docs/plan/phase-1.md#slices) | Merged (#72) |
| [S13](../../docs/plan/phase-1.md#slices) | Merged (#73) |
