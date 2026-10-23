// SPDX-License-Identifier: MIT
// Entirely self-authored synthetic inspection data; no game or external implementation.
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

namespace Outlands.Synthetic;

[AttributeUsage(AttributeTargets.Class)]
public sealed class SampleAttribute(string value) : Attribute
{
    public string Value { get; } = value;
}

public interface IExample { string Echo(); }

[Sample("synthetic attribute")]
public sealed class Example : IExample
{
    public const int Meaning = 42;
    public int Counter;

    public string Echo() => "synthetic fixture: quotation \" newline\nUnicode Ω";

    public int Handle(int value)
    {
        try
        {
            if (value == 0) throw new InvalidOperationException("synthetic exception");
            return 10 / value;
        }
        catch (InvalidOperationException) when (value == 0) { return -1; }
        finally { Counter++; }
    }
}

public abstract class AbstractExample
{
    public abstract void NoBody();
}

[StructLayout(LayoutKind.Explicit)]
public struct Positioned
{
    [FieldOffset(4)] public int Number;
}

public static class ExecutionSentinel
{
    [ModuleInitializer]
    public static void Initialize()
    {
        var path = Environment.GetEnvironmentVariable("OUTLANDS_INSPECTOR_FIXTURE_SENTINEL");
        if (path != null) File.WriteAllText(path, "fixture was executed");
    }
}
