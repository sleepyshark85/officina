# .NET plan

.NET's part of the [phase 1 plan](../../docs/plan/phase-1.md): the shared slices and their acceptance criteria are
there, and its decisions in [`decisions.md`](decisions.md).

## Per slice

How .NET realizes a slice, where it differs from the shared criteria.

| Slice | .NET |
|---|---|
| [S01](../../docs/plan/phase-1.md#slices) | Solution and central package versions. From `~/sources/agentic-core` (ARCHITECTURE §13; spike notes in its `docs/spikes/`), ported, not copied wholesale: the dependency check and build props here, the scripted model and human in S03 and S05, the Claude provider in S04, the MCP client in S11 |
| [S02](../../docs/plan/phase-1.md#slices) | [`docs/spikes/claude-features.md`](../../docs/spikes/claude-features.md) |
| [S03](../../docs/plan/phase-1.md#slices) | Events as `IAsyncEnumerable`; tool events through an unbounded channel |
| [S04](../../docs/plan/phase-1.md#slices) | `dotnet/samples/hello` |
| [S05](../../docs/plan/phase-1.md#slices) | CsCheck properties; Stryker.NET |
| [S06](../../docs/plan/phase-1.md#slices) | Npgsql |
| [S07](../../docs/plan/phase-1.md#slices) | `ActivitySource` and `Meter` |
| [S13](../../docs/plan/phase-1.md#slices) | [`dotnet/docs/demo.md`](demo.md) |

S08, S09, S10, S11 and S12 add nothing to the shared criteria.

## Progress

| Slice | .NET |
|---|---|
| [S01](../../docs/plan/phase-1.md#slices) | Merged |
| [S02](../../docs/plan/phase-1.md#slices) | Merged |
| [S03](../../docs/plan/phase-1.md#slices) | Merged |
| [S04](../../docs/plan/phase-1.md#slices) | Merged |
| [S05](../../docs/plan/phase-1.md#slices) | Merged |
| [S06](../../docs/plan/phase-1.md#slices) | Merged |
| [S07](../../docs/plan/phase-1.md#slices) | Merged |
| [S08](../../docs/plan/phase-1.md#slices) | Merged |
| [S09](../../docs/plan/phase-1.md#slices) | Merged |
| [S10](../../docs/plan/phase-1.md#slices) | Merged |
| [S11](../../docs/plan/phase-1.md#slices) | Merged |
| [S12](../../docs/plan/phase-1.md#slices) | Merged |
| [S13](../../docs/plan/phase-1.md#slices) | Merged |
