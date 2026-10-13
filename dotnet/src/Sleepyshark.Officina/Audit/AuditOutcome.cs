namespace Sleepyshark.Officina;

/// <summary>The outcomes a tool call's end records in the audit trail, the same words in every implementation.</summary>
internal static class AuditOutcome
{
    internal const string Ok = "ok";

    /// <summary>An error result, a refused call, or a write blocked as its attempt could not be audited.</summary>
    internal const string Error = "error";

    /// <summary>A call left without a result when the application stopped mid-reply.</summary>
    internal const string Interrupted = "interrupted";
}
