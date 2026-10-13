namespace Sleepyshark.Officina.Tests;

/// <summary>Waits for an answer that never comes, while the host cancels the run.</summary>
internal sealed class UnansweredApprover(CancellationTokenSource cancellation) : IApprover
{
    public async Task<Approval> ApproveAsync(Tool tool, ToolCall toolCall, CancellationToken cancellationToken)
    {
        await cancellation.CancelAsync();
        await Task.Delay(Timeout.Infinite, cancellationToken);
        return Approval.Granted;
    }
}
