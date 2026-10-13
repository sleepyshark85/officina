namespace Sleepyshark.Officina;

/// <summary>An approver's answer; a denial's reason is told to the model.</summary>
public sealed record Approval(bool Approved, string? Reason = null)
{
    public static Approval Granted { get; } = new(true);

    /// <summary>The answer in a word, as the audit trail and telemetry record it.</summary>
    internal string Answer => Approved ? "approved" : "denied";

    public static Approval Denied(string reason) => new(false, reason);
}
