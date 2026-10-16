// Minmatar Fleet desktop - native window helper.
// Read-only towards EVE: it watches which window is in front and where the EVE client windows are.
// It never reads EVE memory, never injects, never sends input to EVE.
// The only windows it changes are the overlay's own (glass + square corners).
//
// Compiled at launch by PowerShell Add-Type (C# 5, .NET Framework, ships with Windows) so the app needs no native build step.
//
// Protocol: JSON lines on stdout, plain-text commands on stdin.
//   out: {"t":"ready"} {"t":"fg",...} {"t":"clients","list":[...]} {"t":"glass","hwnd":"..","ok":true,"code":0}
//   in : glass <hwnd> <AABBGGRR hex>     quit
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public static class MfoHelper {
  delegate void WinEventProc(IntPtr hook, uint ev, IntPtr hwnd, int idObject, int idChild, uint thread, uint time);
  delegate bool EnumProc(IntPtr h, IntPtr l);

  [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] struct POINT { public int X, Y; }
  [StructLayout(LayoutKind.Sequential)] struct MSG { public IntPtr hwnd; public uint message; public IntPtr w; public IntPtr l; public uint time; public POINT pt; }
  [StructLayout(LayoutKind.Sequential)] struct ACCENT { public int State; public int Flags; public uint Gradient; public int Anim; }
  [StructLayout(LayoutKind.Sequential)] struct WCAD { public int Attr; public IntPtr Data; public int Size; }

  [DllImport("user32.dll")] static extern IntPtr SetWinEventHook(uint min, uint max, IntPtr mod, WinEventProc fn, uint pid, uint tid, uint flags);
  [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] static extern int GetMessage(out MSG m, IntPtr h, uint a, uint b);
  [DllImport("user32.dll")] static extern bool PostThreadMessage(uint tid, uint msg, IntPtr w, IntPtr l);
  [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
  [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr ctx);
  [DllImport("user32.dll", SetLastError = true)] static extern int SetWindowCompositionAttribute(IntPtr h, ref WCAD d);
  [DllImport("dwmapi.dll")] static extern int DwmSetWindowAttribute(IntPtr h, int a, ref int v, int s);

  const uint EVENT_SYSTEM_FOREGROUND = 0x0003, EVENT_SYSTEM_MINIMIZEEND = 0x0017;
  const uint EVENT_OBJECT_LOCATIONCHANGE = 0x800B, EVENT_OBJECT_NAMECHANGE = 0x800C;
  const uint WM_APP = 0x8000, WM_APP_CMD = WM_APP + 1, WM_APP_SCAN = WM_APP + 2;

  static WinEventProc fgProc, objProc;   // keep delegates alive (GC would free the callback otherwise)
  static uint mainTid;
  static readonly Queue<string> cmds = new Queue<string>();
  static readonly HashSet<string> procNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
  static readonly Dictionary<uint, string> pidNames = new Dictionary<uint, string>();
  static readonly HashSet<long> clientHwnds = new HashSet<long>();
  static string lastClients = "";

  static void Out(string s) { lock (Console.Out) { Console.Out.WriteLine(s); Console.Out.Flush(); } }
  static string J(string s) {
    if (s == null) return "\"\"";
    var b = new StringBuilder("\"");
    foreach (char c in s) {
      if (c == '"' || c == '\\') b.Append('\\').Append(c);
      else if (c < 0x20) b.Append("\\u").Append(((int)c).ToString("x4"));
      else b.Append(c);
    }
    return b.Append('"').ToString();
  }

  static string Title(IntPtr h) { var sb = new StringBuilder(256); GetWindowText(h, sb, 256); return sb.ToString(); }
  static string ProcName(IntPtr h, out uint pid) {
    GetWindowThreadProcessId(h, out pid);
    string n;
    if (pidNames.TryGetValue(pid, out n)) return n;
    try { n = Process.GetProcessById((int)pid).ProcessName; } catch { n = ""; }
    pidNames[pid] = n;
    return n;
  }
  // An EVE client = a visible top-level window of exefile.exe whose title is "EVE" (character select) or "EVE - <Character>".
  static bool IsClient(IntPtr h) {
    uint pid; string n = ProcName(h, out pid);
    if (!procNames.Contains(n)) return false;
    string t = Title(h);
    return t == "EVE" || t.StartsWith("EVE - ");
  }
  static string ClientJson(IntPtr h) {
    RECT r; GetClientRect(h, out r);
    var p = new POINT(); ClientToScreen(h, ref p);
    uint pid; ProcName(h, out pid);
    return "{\"hwnd\":\"" + h.ToInt64() + "\",\"pid\":" + pid + ",\"title\":" + J(Title(h)) + ",\"min\":" + (IsIconic(h) ? "true" : "false") +
           ",\"x\":" + p.X + ",\"y\":" + p.Y + ",\"w\":" + (r.R - r.L) + ",\"h\":" + (r.B - r.T) + "}";
  }

  static void Scan() {
    var found = new List<IntPtr>();
    EnumWindows(delegate (IntPtr h, IntPtr l) { if (IsWindowVisible(h) && IsClient(h)) found.Add(h); return true; }, IntPtr.Zero);
    clientHwnds.Clear();
    var parts = new List<string>();
    foreach (var h in found) { clientHwnds.Add(h.ToInt64()); parts.Add(ClientJson(h)); }
    string line = "{\"t\":\"clients\",\"list\":[" + string.Join(",", parts.ToArray()) + "]}";
    if (line != lastClients) { lastClients = line; Out(line); }
  }

  static void OnForeground(IntPtr hook, uint ev, IntPtr h, int obj, int child, uint thread, uint time) {
    uint pid; string n = ProcName(h, out pid);
    bool client = IsClient(h);   // only an EVE client's title is reported; other apps' titles never leave this process
    var cls = new StringBuilder(64); GetClassName(h, cls, 64);   // process + window class let the app recognise the shell and screenshot tools
    Out("{\"t\":\"fg\",\"hwnd\":\"" + h.ToInt64() + "\",\"pid\":" + pid + ",\"proc\":" + J(n) + ",\"cls\":" + J(cls.ToString()) +
        ",\"title\":" + J(client ? Title(h) : "") + ",\"client\":" + (client ? "true" : "false") + "}");
    Scan();
  }
  static void OnObject(IntPtr hook, uint ev, IntPtr h, int obj, int child, uint thread, uint time) {
    if (obj != 0 || child != 0) return;            // OBJID_WINDOW only (ignore caret/cursor/child objects)
    if (ev == EVENT_OBJECT_NAMECHANGE) { if (IsClient(h) || clientHwnds.Contains(h.ToInt64())) Scan(); return; }
    if (clientHwnds.Contains(h.ToInt64())) Scan(); // client moved/resized/minimised
  }

  static void Glass(string[] p) {
    // glass <hwnd> <AABBGGRR>: live blur-behind that keeps working while the window is NOT focused.
    // (Windows 11's DWMWA_SYSTEMBACKDROP_TYPE acrylic falls back to a flat colour when inactive - see evidence/.)
    var h = new IntPtr(long.Parse(p[1]));
    uint tint = Convert.ToUInt32(p.Length > 2 ? p[2] : "B0080808", 16);
    var a = new ACCENT { State = 4 /*ACCENT_ENABLE_ACRYLICBLURBEHIND*/, Flags = 2, Gradient = tint, Anim = 0 };
    int sz = Marshal.SizeOf(a); IntPtr mem = Marshal.AllocHGlobal(sz);
    Marshal.StructureToPtr(a, mem, false);
    var d = new WCAD { Attr = 19 /*WCA_ACCENT_POLICY*/, Data = mem, Size = sz };
    int ok = SetWindowCompositionAttribute(h, ref d);
    int err = Marshal.GetLastWin32Error();
    Marshal.FreeHGlobal(mem);
    int corner = 1; // DWMWCP_DONOTROUND: EVE windows are square; Windows 11 rounds top-level windows by default
    int hr = DwmSetWindowAttribute(h, 33 /*DWMWA_WINDOW_CORNER_PREFERENCE*/, ref corner, 4);
    // Don't set DWMWA_TRANSITIONS_FORCEDISABLED here: on Electron's frameless windows it makes Windows draw
    // a native title bar over the page (seen in 0.3.2 - 0.4.0-dev.2).
    Out("{\"t\":\"glass\",\"hwnd\":\"" + p[1] + "\",\"ok\":" + (ok != 0 ? "true" : "false") + ",\"err\":" + err + ",\"cornerHr\":" + hr + "}");
  }

  public static void Run(string procs) {
    foreach (var s in procs.Split(',')) if (s.Trim().Length > 0) procNames.Add(s.Trim());
    SetProcessDpiAwarenessContext(new IntPtr(-4));  // per-monitor v2: all coordinates are physical pixels
    mainTid = GetCurrentThreadId();
    fgProc = OnForeground; objProc = OnObject;
    SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND, IntPtr.Zero, fgProc, 0, 0, 0 /*OUTOFCONTEXT*/);
    SetWinEventHook(EVENT_SYSTEM_MINIMIZEEND, EVENT_SYSTEM_MINIMIZEEND, IntPtr.Zero, fgProc, 0, 0, 0);
    SetWinEventHook(EVENT_OBJECT_LOCATIONCHANGE, EVENT_OBJECT_NAMECHANGE, IntPtr.Zero, objProc, 0, 0, 2 /*SKIPOWNPROCESS*/);

    var reader = new Thread(delegate () {
      string l;
      while ((l = Console.In.ReadLine()) != null) { lock (cmds) cmds.Enqueue(l); PostThreadMessage(mainTid, WM_APP_CMD, IntPtr.Zero, IntPtr.Zero); }
      Environment.Exit(0);   // parent closed stdin: exit with it
    });
    reader.IsBackground = true; reader.Start();
    var ticker = new Thread(delegate () { while (true) { Thread.Sleep(1000); PostThreadMessage(mainTid, WM_APP_SCAN, IntPtr.Zero, IntPtr.Zero); } });
    ticker.IsBackground = true; ticker.Start();

    Out("{\"t\":\"ready\"}");
    Scan();
    OnForeground(IntPtr.Zero, 0, GetForegroundWindow(), 0, 0, 0, 0);

    MSG m;
    while (GetMessage(out m, IntPtr.Zero, 0, 0) > 0) {   // WinEvent callbacks are delivered inside this loop
      if (m.message == WM_APP_SCAN) { Scan(); continue; }
      if (m.message != WM_APP_CMD) continue;
      while (true) {
        string c; lock (cmds) { if (cmds.Count == 0) break; c = cmds.Dequeue(); }
        var p = c.Trim().Split(' ');
        try {
          if (p[0] == "glass") Glass(p);
          else if (p[0] == "quit") return;
        } catch (Exception e) { Out("{\"t\":\"error\",\"msg\":" + J(e.Message) + "}"); }
      }
    }
  }
}
