// Native process boundary, C# 5 / .NET Framework 4.8 only. No interpretation of prompts.
using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;

internal static class CaptureShim
{
    private static readonly UTF8Encoding Utf8 = new UTF8Encoding(false, true);
    private static int captureFailed;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CreateDirectoryW(string path, IntPtr attributes);

    private static string Stamp(DateTime value)
    {
        return value.ToUniversalTime().ToString("o", CultureInfo.InvariantCulture);
    }

    private static string Hex(byte[] value)
    {
        return BitConverter.ToString(value).Replace("-", "").ToLowerInvariant();
    }

    private static string Hash(byte[] value)
    {
        using (SHA256 hash = SHA256.Create()) { return Hex(hash.ComputeHash(value)); }
    }

    private static Dictionary<string, object> Record(params object[] pairs)
    {
        Dictionary<string, object> value = new Dictionary<string, object>();
        for (int i = 0; i < pairs.Length; i += 2)
            value.Add((string)pairs[i], pairs[i + 1]);
        return value;
    }

    private static JavaScriptSerializer Serializer()
    {
        JavaScriptSerializer value = new JavaScriptSerializer();
        value.MaxJsonLength = Int32.MaxValue;
        return value;
    }

    private static FileStream DurableFile(string path)
    {
        return new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read,
                              65536, FileOptions.WriteThrough);
    }

    private static void WriteBytes(string path, byte[] bytes)
    {
        using (FileStream file = DurableFile(path))
        {
            file.Write(bytes, 0, bytes.Length);
            file.Flush(true);
        }
    }

    private static void WriteJson(string path, object value)
    {
        WriteBytes(path, Utf8.GetBytes(Serializer().Serialize(value) + "\n"));
    }

    private static void Fail(string stage, Exception error)
    {
        // Do not print exception messages, command lines or environment values.
        Console.Error.WriteLine("capture shim: " + stage + " failed (" + error.GetType().Name + ")");
    }

    private static string Absolute(string value)
    {
        if (String.IsNullOrEmpty(value) ||
            !Regex.IsMatch(value, @"^(?:[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/][^\\/]+(?:[\\/]|$))"))
            throw new ArgumentException("absolute path required");
        return Path.GetFullPath(value);
    }

    private static int Configure(string[] args, string config)
    {
        string temporary = config + "." + Guid.NewGuid().ToString("N") + ".tmp";
        try
        {
            if (args.Length != 5) throw new ArgumentException("configure arguments");
            Dictionary<string, string> options = new Dictionary<string, string>();
            for (int i = 1; i < args.Length; i += 2) options.Add(args[i], args[i + 1]);
            if (!options.ContainsKey("--real-exe") || !options.ContainsKey("--capture-root"))
                throw new ArgumentException("configure options");
            string real = Absolute(options["--real-exe"]);
            string root = Absolute(options["--capture-root"]);
            if (!File.Exists(real)) throw new FileNotFoundException();
            if (String.Equals(real, Assembly.GetExecutingAssembly().Location,
                              StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("recursive shim");
            Directory.CreateDirectory(root);
            WriteJson(temporary, Record("real_exe", real, "capture_root", root));
            if (File.Exists(config)) File.Replace(temporary, config, null);
            else File.Move(temporary, config);
            return 0;
        }
        catch (Exception error) { Fail("configuration", error); return 1; }
        finally
        {
            try { if (File.Exists(temporary)) File.Delete(temporary); }
            catch (IOException) { }
            catch (UnauthorizedAccessException) { }
        }
    }

    private static string CommandTail()
    {
        // argv[0] has the CRT's special quote rule: quotes group the executable name;
        // backslashes are literal. Retain every separator and argument byte thereafter.
        string raw = Environment.CommandLine;
        bool quoted = false;
        int i = 0;
        for (; i < raw.Length; i++)
        {
            char ch = raw[i];
            if (ch == '"') quoted = !quoted;
            else if (!quoted && (ch == ' ' || ch == '\t')) break;
        }
        return raw.Substring(i);
    }

    private sealed class Pump
    {
        private readonly Stream input;
        private Stream forward;
        private readonly string path;
        internal long Length;
        internal string Digest = Hash(new byte[0]);

        internal Pump(Stream inputStream, Stream outputStream, string capturePath)
        {
            input = inputStream;
            forward = outputStream;
            path = capturePath;
        }

        private static void Failed() { Interlocked.Exchange(ref captureFailed, 1); }

        internal void Run()
        {
            FileStream file = null;
            try { file = DurableFile(path); file.Flush(true); }
            catch (Exception) { Failed(); }
            try
            {
                using (SHA256 hash = SHA256.Create())
                {
                    byte[] buffer = new byte[65536];
                    int count;
                    while ((count = input.Read(buffer, 0, buffer.Length)) != 0)
                    {
                        Length += count;
                        hash.TransformBlock(buffer, 0, count, buffer, 0);
                        if (forward != null)
                        {
                            try { forward.Write(buffer, 0, count); forward.Flush(); }
                            catch (Exception) { Failed(); forward = null; }
                        }
                        if (file != null)
                        {
                            try { file.Write(buffer, 0, count); file.Flush(true); }
                            catch (Exception)
                            {
                                Failed();
                                try { file.Dispose(); } catch (Exception) { Failed(); }
                                file = null;
                            }
                        }
                    }
                    hash.TransformFinalBlock(new byte[0], 0, 0);
                    Digest = Hex(hash.Hash);
                }
            }
            catch (Exception) { Failed(); }
            finally
            {
                if (file != null)
                {
                    try { file.Flush(true); file.Dispose(); }
                    catch (Exception) { Failed(); }
                }
            }
        }
    }

    private static void Heartbeat(Process child, string path, ManualResetEvent ready)
    {
        try
        {
            using (FileStream file = DurableFile(path))
            {
                while (!child.HasExited)
                {
                    byte[] line = Utf8.GetBytes(Stamp(DateTime.UtcNow) + "\n");
                    file.Write(line, 0, line.Length);
                    file.Flush(true);
                    ready.Set();
                    if (child.WaitForExit(1000)) break;
                }
            }
        }
        catch (Exception) { Interlocked.Exchange(ref captureFailed, 1); }
        finally { ready.Set(); }
    }

    private static int Run(string[] args, string config)
    {
        string folder;
        string real;
        string cwd;
        string tail;
        byte[] stdin;
        // This entire preflight must succeed before the only Process.Start below.
        try
        {
            Dictionary<string, object> settings =
                Serializer().Deserialize<Dictionary<string, object>>(File.ReadAllText(config, Utf8));
            real = Absolute((string)settings["real_exe"]);
            string root = Absolute((string)settings["capture_root"]);
            if (String.Equals(real, Assembly.GetExecutingAssembly().Location,
                              StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("recursive shim");
            using (MemoryStream bytes = new MemoryStream())
            {
                Console.OpenStandardInput().CopyTo(bytes);
                stdin = bytes.ToArray();
            }
            DateTime now = DateTime.UtcNow;
            Process self = Process.GetCurrentProcess();
            string calls = Path.Combine(root, "calls");
            Directory.CreateDirectory(calls);
            folder = Path.Combine(calls, now.ToString("yyyyMMdd'T'HHmmssfff'Z'", CultureInfo.InvariantCulture)
                                  + "-" + self.Id.ToString(CultureInfo.InvariantCulture));
            if (!CreateDirectoryW(folder, IntPtr.Zero))
                throw new IOException("exclusive call directory failed");
            WriteBytes(Path.Combine(folder, "stdin.bin"), stdin);
            string active;
            try { active = Utf8.GetString(File.ReadAllBytes(Path.Combine(root, "active_case.json"))); }
            catch (FileNotFoundException) { active = null; }
            FileInfo executable = new FileInfo(real);
            List<string> names = new List<string>();
            foreach (DictionaryEntry entry in Environment.GetEnvironmentVariables())
                names.Add((string)entry.Key);
            names.Sort(StringComparer.Ordinal);
            cwd = Environment.CurrentDirectory;
            tail = CommandTail();
            WriteJson(Path.Combine(folder, "start.json"), Record(
                "schema", "codex-capture-shim/1", "utc", Stamp(now),
                "shim_pid", self.Id, "process_start_utc", Stamp(self.StartTime),
                "command_line_tail", tail, "argv", args, "cwd", cwd,
                "stdin_length", stdin.LongLength, "stdin_sha256", Hash(stdin),
                "active_case", active, "real_exe", real,
                "real_exe_size", executable.Length, "real_exe_mtime_utc", Stamp(executable.LastWriteTimeUtc),
                "environment_names", names));
        }
        catch (Exception error) { Fail("capture preflight", error); return 1; }

        using (Process child = new Process())
        {
            child.StartInfo = new ProcessStartInfo(real, tail);
            child.StartInfo.WorkingDirectory = cwd;
            child.StartInfo.UseShellExecute = false;
            child.StartInfo.CreateNoWindow = true;
            child.StartInfo.RedirectStandardInput = true;
            child.StartInfo.RedirectStandardOutput = true;
            child.StartInfo.RedirectStandardError = true;
            // Do not touch EnvironmentVariables: the provider's allow-list is inherited.
            try { if (!child.Start()) throw new IOException("spawn failed"); }
            catch (Exception error) { Fail("spawn", error); return 1; }
            try
            {
                WriteJson(Path.Combine(folder, "spawned.json"),
                          Record("child_pid", child.Id, "utc", Stamp(DateTime.UtcNow)));
            }
            catch (Exception) { Interlocked.Exchange(ref captureFailed, 1); }

            ManualResetEvent aliveReady = new ManualResetEvent(false);
            Thread aliveThread = new Thread(delegate()
            {
                Heartbeat(child, Path.Combine(folder, "alive.log"), aliveReady);
            });
            aliveThread.IsBackground = true;
            aliveThread.Start();
            // Persist the first heartbeat before feeding a fast stdin-driven child.
            aliveReady.WaitOne();

            Pump stdout = new Pump(child.StandardOutput.BaseStream, Console.OpenStandardOutput(),
                                   Path.Combine(folder, "stdout.bin"));
            Pump stderr = new Pump(child.StandardError.BaseStream, Console.OpenStandardError(),
                                   Path.Combine(folder, "stderr.bin"));
            Thread outThread = new Thread(stdout.Run);
            Thread errThread = new Thread(stderr.Run);
            outThread.Start();
            errThread.Start();
            try
            {
                child.StandardInput.BaseStream.Write(stdin, 0, stdin.Length);
                child.StandardInput.BaseStream.Flush();
            }
            catch (Exception) { Interlocked.Exchange(ref captureFailed, 1); }
            finally
            {
                try { child.StandardInput.Close(); }
                catch (Exception) { Interlocked.Exchange(ref captureFailed, 1); }
            }
            child.WaitForExit();
            aliveThread.Join();
            aliveReady.Dispose();
            outThread.Join();
            errThread.Join();
            try
            {
                WriteJson(Path.Combine(folder, "end.json"), Record(
                    "exit_code", child.ExitCode, "utc", Stamp(DateTime.UtcNow),
                    "stdout_length", stdout.Length, "stdout_sha256", stdout.Digest,
                    "stderr_length", stderr.Length, "stderr_sha256", stderr.Digest,
                    "capture_ok", captureFailed == 0));
            }
            catch (Exception) { Interlocked.Exchange(ref captureFailed, 1); }
            return captureFailed == 0 ? child.ExitCode : 1;
        }
    }

    public static int Main(string[] args)
    {
        string config = Path.Combine(Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location),
                                     "capture_shim.json");
        if (args.Length > 0 && args[0] == "--configure") return Configure(args, config);
        try { return Run(args, config); }
        catch (Exception error) { Fail("forwarding", error); return 1; }
    }
}
