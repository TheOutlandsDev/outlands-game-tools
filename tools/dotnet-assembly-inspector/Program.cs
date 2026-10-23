// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Connor O'Shea (TheOutlandsDev) and contributors
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Buffers.Binary;
using System.Text.Json;

internal static class Program
{
    private const int MaxInputBytes = 32 * 1024 * 1024;
    private const int MaxOutputBytes = 16 * 1024 * 1024;
    private const int MaxDecodedBytes = 8 * 1024 * 1024;
    private const int MaxValueBytes = 1024 * 1024;
    private const int MaxRows = 100_000;

    private static int Main(string[] args)
    {
        if (args.Length == 1 && args[0] is "--help" or "-h")
        {
            Console.WriteLine("Usage: dotnet Outlands.AssemblyInspector.dll <managed-assembly.dll-or.exe>\n" +
                "Inspect one managed assembly as static PE metadata. JSON goes to stdout.\n" +
                "Limits: 32 MiB input, 100000 metadata rows, 1 MiB individual values,\n" +
                "8 MiB decoded value budget, 16 MiB JSON. Reports can reveal private literals.\n" +
                "Exit: 0 complete report/help/version; 2 invalid, unsupported or bounded input.");
            return 0;
        }
        if (args.Length == 1 && args[0] == "--version")
        {
            Console.WriteLine("Outlands .NET Assembly Inspector 1.0.0");
            return 0;
        }
        if (args.Length != 1 || args[0].StartsWith("--", StringComparison.Ordinal))
        {
            Console.Error.WriteLine("Expected one assembly path. Use --help for usage.");
            return 2;
        }

        try
        {
            byte[] source = ReadSnapshot(args[0]);
            using var pe = new PEReader(new MemoryStream(source, writable: false));
            if (!pe.HasMetadata)
                throw new InvalidDataException("Input has no managed metadata.");
            var metadata = pe.GetMetadataReader(MetadataReaderOptions.None);
            if (!metadata.IsAssembly)
                throw new InvalidDataException("Managed netmodules are unsupported; an assembly is required.");

            long rows = 0;
            foreach (var table in Enum.GetValues<TableIndex>())
                rows += metadata.GetTableRowCount(table);
            if (rows > MaxRows)
                throw new InvalidDataException("Metadata row limit exceeded.");

            var values = new Values(metadata);
            string S(StringHandle handle) => values.String(handle);
            string Blob(BlobHandle handle) => values.Blob(handle);
            string Token(EntityHandle handle) => values.Token(handle);
            var assembly = metadata.GetAssemblyDefinition();
            var references = metadata.AssemblyReferences.Select(handle =>
            {
                var value = metadata.GetAssemblyReference(handle);
                return new { name = S(value.Name), version = value.Version.ToString(), culture = S(value.Culture),
                    publicKey = Blob(value.PublicKeyOrToken), flags = value.Flags.ToString() };
            }).ToArray();
            var types = metadata.TypeDefinitions.Select(handle =>
            {
                var value = metadata.GetTypeDefinition(handle);
                return new { token = Token(handle), name = S(value.Name), ns = S(value.Namespace),
                    attributes = value.Attributes.ToString(), baseType = Token(value.BaseType),
                    interfaces = value.GetInterfaceImplementations().Select(item =>
                        Token(metadata.GetInterfaceImplementation(item).Interface)).ToArray() };
            }).ToArray();
            var fields = metadata.FieldDefinitions.Select(handle =>
            {
                var value = metadata.GetFieldDefinition(handle);
                return new { token = Token(handle), name = S(value.Name), attributes = value.Attributes.ToString(),
                    signature = Blob(value.Signature), offset = value.GetOffset(),
                    constant = Token(value.GetDefaultValue()), rva = value.GetRelativeVirtualAddress() };
            }).ToArray();
            var methods = metadata.MethodDefinitions.Select(handle =>
            {
                var value = metadata.GetMethodDefinition(handle);
                MethodBodyBlock? body = value.RelativeVirtualAddress == 0 ? null : pe.GetMethodBody(value.RelativeVirtualAddress);
                return new { token = Token(handle), name = S(value.Name), signature = Blob(value.Signature),
                    attributes = value.Attributes.ToString(), implAttributes = value.ImplAttributes.ToString(),
                    locals = body == null ? "" : Token(body.LocalSignature), initLocals = body?.LocalVariablesInitialized,
                    maxStack = body?.MaxStack, il = body == null ? "" : values.Hex(body.GetILContent().AsSpan()),
                    exceptions = body?.ExceptionRegions.Select(region => new {
                        kind = region.Kind.ToString(), tryOffset = region.TryOffset, tryLength = region.TryLength,
                        handlerOffset = region.HandlerOffset, handlerLength = region.HandlerLength,
                        catchType = region.Kind == ExceptionRegionKind.Catch ? Token(region.CatchType) : "",
                        filterOffset = region.Kind == ExceptionRegionKind.Filter ? (int?)region.FilterOffset : null
                    }).ToArray() };
            }).ToArray();
            var typeReferences = metadata.TypeReferences.Select(handle =>
            {
                var value = metadata.GetTypeReference(handle);
                return new { token = Token(handle), name = S(value.Name), ns = S(value.Namespace), scope = Token(value.ResolutionScope) };
            }).ToArray();
            var memberReferences = metadata.MemberReferences.Select(handle =>
            {
                var value = metadata.GetMemberReference(handle);
                return new { token = Token(handle), name = S(value.Name), parent = Token(value.Parent), signature = Blob(value.Signature) };
            }).ToArray();
            var attributes = metadata.CustomAttributes.Select(handle =>
            {
                var value = metadata.GetCustomAttribute(handle);
                return new { parent = Token(value.Parent), constructor = Token(value.Constructor), value = Blob(value.Value) };
            }).ToArray();
            var standalone = Enumerable.Range(1, metadata.GetTableRowCount(TableIndex.StandAloneSig))
                .Select(index => Blob(metadata.GetStandaloneSignature(MetadataTokens.StandaloneSignatureHandle(index)).Signature)).ToArray();
            var userStrings = ReadUserStrings(pe, metadata, values);
            var module = metadata.GetModuleDefinition();
            var debug = pe.ReadDebugDirectory();
            if (debug.Length > MaxRows)
                throw new InvalidDataException("Debug entry limit exceeded.");
            var report = new {
                schemaVersion = "1.0", toolVersion = "1.0.0", inspection = "static-managed-metadata",
                assembly = new { name = S(assembly.Name), version = assembly.Version.ToString(), culture = S(assembly.Culture),
                    publicKey = Blob(assembly.PublicKey), flags = assembly.Flags.ToString() },
                refs = references, types, fields, methods, typeRefs = typeReferences, memberRefs = memberReferences,
                attrs = attributes, standalone, userStrings,
                module = new { name = S(module.Name), mvid = metadata.GetGuid(module.Mvid).ToString() },
                debug = debug.Select(value => new { type = value.Type.ToString(), size = value.DataSize,
                    stamp = value.Stamp, major = value.MajorVersion, minor = value.MinorVersion }).ToArray()
            };
            using var output = new LimitedStream(MaxOutputBytes);
            JsonSerializer.Serialize(output, report, new JsonSerializerOptions { WriteIndented = true });
            output.WriteByte((byte)'\n');
            output.Position = 0;
            output.CopyTo(Console.OpenStandardOutput());
            return 0;
        }
        catch (Exception exception) when (exception is IOException or InvalidDataException or UnauthorizedAccessException or BadImageFormatException
            or ArgumentException or InvalidOperationException or NotSupportedException or OverflowException)
        {
            // Never echo exception messages: parsers/OS errors may contain private input paths or values.
            Console.Error.WriteLine("Inspection failed: invalid, unreadable, unsupported or limit-exceeding input. No complete report produced.");
            return 2;
        }
    }

    private static List<object> ReadUserStrings(PEReader pe, MetadataReader metadata, Values values)
    {
        // GetNextHandle can return nil for an invalid compressed length. Validate
        // #US framing explicitly so malformed entries cannot look like a clean end.
        var root = pe.GetMetadata().GetContent().AsSpan();
        if (root.Length < 20 || BinaryPrimitives.ReadUInt32LittleEndian(root) != 0x424A5342)
            throw new BadImageFormatException();
        int versionLength = checked((int)BinaryPrimitives.ReadUInt32LittleEndian(root[12..]));
        int cursor = checked((16 + versionLength + 3) & ~3);
        if (cursor > root.Length - 4)
            throw new BadImageFormatException();
        int streams = BinaryPrimitives.ReadUInt16LittleEndian(root[(cursor + 2)..]);
        cursor += 4;
        int heapOffset = 0;
        int heapSize = 0;
        bool found = false;
        for (int index = 0; index < streams; index++)
        {
            if (cursor > root.Length - 8)
                throw new BadImageFormatException();
            int offset = checked((int)BinaryPrimitives.ReadUInt32LittleEndian(root[cursor..]));
            int size = checked((int)BinaryPrimitives.ReadUInt32LittleEndian(root[(cursor + 4)..]));
            int nameStart = cursor + 8;
            int end = nameStart;
            while (end < root.Length && end - nameStart < 32 && root[end] != 0)
                end++;
            if (end >= root.Length || end - nameStart >= 32 || size < 0 || offset > root.Length - size)
                throw new BadImageFormatException();
            if (root[nameStart..end].SequenceEqual("#US"u8))
            {
                if (found) throw new BadImageFormatException();
                found = true;
                heapOffset = offset;
                heapSize = size;
            }
            cursor = checked((end + 1 + 3) & ~3);
        }
        if (heapSize != metadata.GetHeapSize(HeapIndex.UserString))
            throw new BadImageFormatException();
        var result = new List<object>();
        if (heapSize == 0) return result;
        var heap = root.Slice(heapOffset, heapSize);
        if (heap[0] != 0) throw new BadImageFormatException();
        cursor = 1;
        while (cursor < heap.Length)
        {
            int offset = cursor;
            if (heap[cursor] == 0)
            {
                // Only zero alignment padding may follow the final entry.
                foreach (byte padding in heap[cursor..])
                    if (padding != 0) throw new BadImageFormatException();
                break;
            }
            if (result.Count >= MaxRows) throw new InvalidDataException("User string entry limit exceeded.");
            int length = ReadCompressedLength(heap, ref cursor);
            if (length < 1 || (length & 1) == 0 || length > heap.Length - cursor)
                throw new BadImageFormatException();
            if (heap[cursor + length - 1] > 1) throw new BadImageFormatException();
            result.Add(new { offset, value = values.UserString(MetadataTokens.UserStringHandle(offset)) });
            cursor += length;
        }
        return result;
    }

    private static int ReadCompressedLength(ReadOnlySpan<byte> bytes, ref int offset)
    {
        byte first = bytes[offset++];
        if ((first & 0x80) == 0) return first;
        if ((first & 0xC0) == 0x80)
        {
            if (offset >= bytes.Length) throw new BadImageFormatException();
            int value = ((first & 0x3F) << 8) | bytes[offset++];
            if (value < 0x80) throw new BadImageFormatException();
            return value;
        }
        if ((first & 0xE0) == 0xC0)
        {
            if (offset > bytes.Length - 3) throw new BadImageFormatException();
            int value = ((first & 0x1F) << 24) | (bytes[offset] << 16) | (bytes[offset + 1] << 8) | bytes[offset + 2];
            offset += 3;
            if (value < 0x4000) throw new BadImageFormatException();
            return value;
        }
        throw new BadImageFormatException();
    }

    private static byte[] ReadSnapshot(string path)
    {
        using var input = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read);
        if (input.Length > MaxInputBytes)
            throw new InvalidDataException("Input limit exceeded.");
        var bytes = new byte[checked((int)input.Length)];
        input.ReadExactly(bytes);
        if (input.ReadByte() != -1 || input.Length != bytes.Length)
            throw new InvalidDataException("Input changed while reading.");
        return bytes;
    }

    private sealed class Values(MetadataReader metadata)
    {
        private int remaining = MaxDecodedBytes;

        private void Charge(int bytes)
        {
            if (bytes > MaxValueBytes || bytes < 0 || bytes > remaining)
                throw new InvalidDataException("Decoded value limit exceeded.");
            remaining -= bytes;
        }

        public string String(StringHandle handle)
        {
            string value = metadata.GetString(handle);
            Charge(checked(value.Length * sizeof(char)));
            return value;
        }

        public string UserString(UserStringHandle handle)
        {
            string value = metadata.GetUserString(handle);
            Charge(checked(value.Length * sizeof(char)));
            return value;
        }

        public string Blob(BlobHandle handle)
        {
            var reader = metadata.GetBlobReader(handle);
            Charge(checked(reader.Length * 4)); // Two hex characters, two bytes per .NET character.
            return Convert.ToHexString(reader.ReadBytes(reader.Length));
        }

        public string Token(EntityHandle handle)
        {
            Charge(16);
            return handle.IsNil ? "" : MetadataTokens.GetToken(handle).ToString("X8");
        }

        public string Hex(ReadOnlySpan<byte> bytes)
        {
            Charge(checked(bytes.Length * 4));
            return Convert.ToHexString(bytes);
        }
    }

    private sealed class LimitedStream(int maximum) : MemoryStream
    {
        public override void Write(byte[] buffer, int offset, int count)
        {
            Check(count);
            base.Write(buffer, offset, count);
        }

        public override void Write(ReadOnlySpan<byte> buffer)
        {
            Check(buffer.Length);
            base.Write(buffer);
        }

        public override void WriteByte(byte value)
        {
            Check(1);
            base.WriteByte(value);
        }

        private void Check(int count)
        {
            if (count > maximum - Length)
                throw new InvalidDataException("Output limit exceeded.");
        }
    }
}
