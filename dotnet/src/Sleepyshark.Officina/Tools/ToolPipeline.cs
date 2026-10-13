using System.Collections.Immutable;
using System.Diagnostics;
using System.Diagnostics.CodeAnalysis;
using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Channels;

namespace Sleepyshark.Officina;

/// <summary>
/// Runs one reply's tool calls: find the tool, validate the input, ask approval if needed, record the attempt, invoke,
/// truncate. Reads run concurrently; a write waits for the calls before it and runs alone; approvals are asked one at a
/// time, in call order. Every call gets exactly one result, in call order, and every failure is an error result, never
/// an exception. Events go to <paramref name="events"/> as they happen; each started call gets a span under the run's,
/// and each handler gets the run's <see cref="ToolContext"/>.
/// </summary>
internal sealed class ToolPipeline(RunScope run, ChannelWriter<RunEvent> events)
{
    /// <summary>The longest result the model gets, in characters: about 16k tokens.</summary>
    internal const int MaxResultLength = 64_000;

    private readonly Agent agent = run.Agent;
    private readonly AuditRecorder audit = run.Audit;

    public async Task<ImmutableArray<ToolResult>> RunAsync(IReadOnlyList<ToolCall> calls, CancellationToken cancellationToken)
    {
        var results = new ToolResult?[calls.Count];
        var steps = new Step?[calls.Count];

        // Reads all start at once: the reply's calls bound how many.
        var reads = new List<Task>();
        for (var index = 0; index < calls.Count && !cancellationToken.IsCancellationRequested; index++)
        {
            // A copy for the closures below, as the loop variable moves on before they run.
            var (call, at) = (calls[index], index);
            var tool = agent.Tools.FirstOrDefault(tool => tool.Name == call.Name);
            if (tool?.Kind == ToolKind.Write)
            {
                await Task.WhenAll(reads).ConfigureAwait(false);
                reads.Clear();
            }

            var step = new Step(Telemetry.StartToolCall(agent, run.Span, tool, call), agent.Time.GetTimestamp());
            steps[at] = step;
            events.TryWrite(new ToolCallStarted(Shown(call)));

            if (!TryReadInput(tool, call, out var input, out var refusal)
                || (refusal = await DenialAsync(tool, call, input, step, cancellationToken).ConfigureAwait(false)) is not null)
            {
                results[at] = await EndAsync(call, step, refusal, ToolOutcome.Error, null).ConfigureAwait(false);
                continue;
            }

            // The host may have cancelled while the approver decided, or while this write waited for the reads before it.
            if (cancellationToken.IsCancellationRequested)
            {
                break;
            }

            var running = Task.Run(async () => results[at] = await InvokeAsync(tool, call, step, input, cancellationToken).ConfigureAwait(false), CancellationToken.None);
            if (tool.Kind == ToolKind.Write)
            {
                await running.ConfigureAwait(false);
            }
            else
            {
                reads.Add(running);
            }
        }

        await Task.WhenAll(reads).ConfigureAwait(false);

        // Calls that never started, because the run was cancelled.
        for (var index = 0; index < calls.Count; index++)
        {
            results[index] ??= await EndAsync(calls[index], steps[index], "The call was cancelled before it started.", ToolOutcome.Error, null).ConfigureAwait(false);
        }

        return [.. results.Select(result => result!)];
    }

    /// <summary>Finds the call's tool and reads its input against the tool's schema, or says why it cannot.</summary>
    private static bool TryReadInput(
        [NotNullWhen(true)] Tool? tool, ToolCall call, out JsonElement input, [NotNullWhen(false)] out string? problem)
    {
        (input, problem) = (default, null);
        if (tool is null)
        {
            problem = $"There is no tool named '{call.Name}'.";
            return false;
        }

        try
        {
            using var document = JsonDocument.Parse(call.Input);
            input = document.RootElement.Clone();
        }
        catch (JsonException exception)
        {
            problem = $"The input is not valid JSON: {exception.Message}";
            return false;
        }

        List<string> problems;
        try
        {
            problems = SchemaValidator.Validate(tool.Schema, input);
        }
        catch (RegexMatchTimeoutException exception)
        {
            problem = $"The input could not be validated: {exception.Message}";
            return false;
        }

        if (problems.Count > 0)
        {
            problem = $"The input does not match the tool's schema:\n{string.Join("\n", problems)}";
            return false;
        }

        return true;
    }

    /// <summary>Asks for approval when the call needs it: why it may not run, said for the model, or null when it may.</summary>
    private async Task<string?> DenialAsync(Tool tool, ToolCall call, JsonElement input, Step step, CancellationToken cancellationToken)
    {
        if (!tool.NeedsApprovalFor(input))
        {
            return null;
        }

        if (agent.Approver is not { } approver)
        {
            return "The call needs approval, and this run is unattended, so it was denied.";
        }

        await audit.RecordAsync(AuditKind.ApprovalAsked, entry => entry with { Tool = tool.Name, CallId = call.Id, Input = call.Input }, step.Span)
            .ConfigureAwait(false);
        events.TryWrite(new ApprovalAsked(Shown(call)));
        var asked = agent.Time.GetTimestamp();
        Approval approval;
        try
        {
            approval = await approver.ApproveAsync(tool, call, cancellationToken).ConfigureAwait(false)
                ?? throw new InvalidOperationException("The approver gave no answer.");
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            Telemetry.WaitedForApproval(step.Span, agent.Time.GetElapsedTime(asked));
            return "The call was cancelled while waiting for approval.";
        }
#pragma warning disable CA1031 // A failing approver denies the call.
        catch (Exception exception)
#pragma warning restore CA1031
        {
            approval = Approval.Denied($"asking for approval failed: {exception.Message}");
        }

        Telemetry.Approved(step.Span, agent, call, approval, agent.Time.GetElapsedTime(asked));
        await audit.RecordAsync(
            AuditKind.ApprovalAnswered,
            entry => entry with { Tool = tool.Name, CallId = call.Id, Outcome = approval.Answer, Detail = approval.Reason },
            step.Span).ConfigureAwait(false);
        events.TryWrite(new ApprovalAnswered(Shown(call), approval.Approved));
        return approval.Approved ? null : $"The call was denied{(approval.Reason is null ? "." : $": {approval.Reason}")}";
    }

    private async Task<ToolResult> InvokeAsync(Tool tool, ToolCall call, Step step, JsonElement input, CancellationToken cancellationToken)
    {
        var started = agent.Time.GetTimestamp();
        var recorded = await audit.RecordAsync(AuditKind.ToolStarted, entry => entry with { Tool = tool.Name, CallId = call.Id, Input = call.Input }, step.Span)
            .ConfigureAwait(false);
        if (!recorded && tool.Kind == ToolKind.Write)
        {
            return await EndAsync(call, step, "The call was not run: its attempt could not be recorded in the audit trail.", ToolOutcome.Blocked, null)
                .ConfigureAwait(false);
        }

        ToolOutput output;
        try
        {
            output = await tool.Handler(input, run.Tools, cancellationToken).ConfigureAwait(false)
                ?? throw new InvalidOperationException("The tool returned no output.");
        }
        catch (OperationCanceledException) when (cancellationToken.IsCancellationRequested)
        {
            output = new ToolOutput("The call was cancelled while it ran.", true);
        }
#pragma warning disable CA1031 // Any tool failure goes back to the model as an error result.
        catch (Exception exception)
#pragma warning restore CA1031
        {
            output = new ToolOutput(exception.Message, true);
        }

        var outcome = output.IsError ? ToolOutcome.Error : ToolOutcome.Ok;
        return await EndAsync(call, step, output.Content, outcome, agent.Time.GetElapsedTime(started)).ConfigureAwait(false);
    }

    /// <summary>
    /// Redacts and truncates a call's result, records its outcome and makes the result. <paramref name="step"/> is null for
    /// a call that never started, and <paramref name="duration"/> for one whose tool never ran.
    /// </summary>
    private async Task<ToolResult> EndAsync(ToolCall call, Step? step, string output, ToolOutcome outcome, TimeSpan? duration)
    {
        var redacted = agent.Redact(output);
        var content = Truncated(redacted);
        var audited = outcome == ToolOutcome.Ok ? AuditOutcome.Ok : AuditOutcome.Error;
        await audit.RecordAsync(
            AuditKind.ToolEnded,
            entry => entry with { Tool = call.Name, CallId = call.Id, Input = call.Input, Outcome = audited, Detail = content, Duration = duration },
            step?.Span).ConfigureAwait(false);
        if (step is { } started)
        {
            Telemetry.EndToolCall(
                started.Span, agent, call, started.Started, outcome, duration, redacted.Length, redacted.Length > MaxResultLength, content);
        }

        var result = new ToolResult(call.Id, content, outcome != ToolOutcome.Ok);
        events.TryWrite(new ToolCallFinished(Shown(call), result));
        return result;
    }

    /// <summary>The result as the model gets it: cut to <see cref="MaxResultLength"/>, with a note saying so.</summary>
    private static string Truncated(string content) => content.Length <= MaxResultLength
        ? content
        : string.Create(
            CultureInfo.InvariantCulture,
            $"{Strings.Cut(content, MaxResultLength)}\n[Truncated: the result had {content.Length} characters; only the first {MaxResultLength} are shown.]");

    /// <summary>The call as events show it: its input without the agent's secrets.</summary>
    private ToolCall Shown(ToolCall call) => call with { Input = agent.Redact(call.Input) };

    /// <summary>A started call's span, if anything listens, and when it started.</summary>
    private readonly record struct Step(Activity? Span, long Started);
}
