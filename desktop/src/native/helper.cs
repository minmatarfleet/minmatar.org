// Minmatar Fleet desktop - native window helper.
// Read-only towards EVE: it watches which window is in front and where the EVE client windows are.
// It never reads EVE memory, never injects, never sends input to EVE.
// The only windows it changes are the overlay's own (glass, square corners, no native caption, their place in
// the window order, a repaint after they lose focus). EVE's windows are only looked at, never moved or restyled.
// While "fade on right-click" is on and a client is in front, it reads the mouse buttons' state (GetAsyncKeyState
// polling, no input hook) so the app can hide windows over a context menu. It never sends input.
//
// Compiled at launch by PowerShell Add-Type (C# 5, .NET Framework, ships with Windows) so the app needs no native build step.
//
// Protocol: JSON lines on stdout, plain-text commands on stdin.
//   out: {"t":"ready"} {"t":"fg",...} {"t":"clients","list":[...]} {"t":"glass","hwnd":"..","ok":true,"code":0}
//        {"t":"btn","b":"r","down":true,"x":..,"y":..,"eve":true}
//   in : glass <hwnd> <AABBGGRR hex>     stack <eve hwnd> <hwnd>...     buttons on|off     quit
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
  [DllImport("user32.dll", EntryPoint = "GetWindowLongPtrW")] static extern IntPtr GetWindowLongPtr(IntPtr h, int i);
  [DllImport("user32.dll", EntryPoint = "SetWindowLongPtrW")] static extern IntPtr SetWindowLongPtr(IntPtr h, int i, IntPtr v);
  [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr h, uint cmd);
  [DllImport("user32.dll")] static extern bool IsWindow(IntPtr h);
  [DllImport("user32.dll")] static extern bool RedrawWindow(IntPtr h, IntPtr rect, IntPtr rgn, uint flags);
  [DllImport("user32.dll")] static extern short GetAsyncKeyState(int key);
  [DllImport("user32.dll")] static extern int GetSystemMetrics(int index);
  [DllImport("user32.dll")] static extern bool GetCursorPos(out POINT p);
  [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(POINT p);
  [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr h, uint flags);

  const uint EVENT_SYSTEM_FOREGROUND = 0x0003, EVENT_SYSTEM_MINIMIZEEND = 0x0017;
  const uint EVENT_OBJECT_LOCATIONCHANGE = 0x800B, EVENT_OBJECT_NAMECHANGE = 0x800C;
  const int GWL_STYLE = -16, GWL_EXSTYLE = -20;
  const long WS_CAPTION = 0x00C00000, WS_EX_TOPMOST = 0x8;
  const uint GW_HWNDPREV = 3;
  static readonly IntPtr HWND_TOP = IntPtr.Zero;
  const uint RDW_INVALIDATE = 0x1, RDW_ERASE = 0x4, RDW_ALLCHILDREN = 0x80, RDW_UPDATENOW = 0x100, RDW_FRAME = 0x400;
  const uint SWP_NOSIZE = 0x1, SWP_NOMOVE = 0x2, SWP_NOZORDER = 0x4, SWP_NOACTIVATE = 0x10, SWP_FRAMECHANGED = 0x20;
  const uint WM_APP = 0x8000, WM_APP_CMD = WM_APP + 1, WM_APP_SCAN = WM_APP + 2, WM_APP_BTN = WM_APP + 3;
  const int VK_LBUTTON = 1, VK_RBUTTON = 2, VK_MBUTTON = 4, SM_SWAPBUTTON = 23;
  const uint GA_ROOT = 2;

  static WinEventProc fgProc, objProc;   // keep delegates alive (GC would free the callback otherwise)
  static uint mainTid;
  static readonly Queue<string> cmds = new Queue<string>();
  static readonly HashSet<string> procNames = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
  static readonly Dictionary<uint, string> pidNames = new Dictionary<uint, string>();
  static readonly HashSet<long> clientHwnds = new HashSet<long>();
  static readonly HashSet<long> ownHwnds = new HashSet<long>();   // our windows (every one gets glass)
  static long lastFg;
  static string lastClients = "";
  static bool buttonsWanted;              // "buttons on" from the app
  static volatile bool watchButtons;      // ...and a client is in front: the poll thread only reads this

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
    if (ownHwnds.Contains(lastFg) || ownHwnds.Contains(h.ToInt64())) Repaint();
    lastFg = h.ToInt64();
    uint pid; string n = ProcName(h, out pid);
    bool client = IsClient(h);   // only an EVE client's title is reported; other apps' titles never leave this process
    var cls = new StringBuilder(64); GetClassName(h, cls, 64);   // process + window class let the app recognise the shell and screenshot tools
    Out("{\"t\":\"fg\",\"hwnd\":\"" + h.ToInt64() + "\",\"pid\":" + pid + ",\"proc\":" + J(n) + ",\"cls\":" + J(cls.ToString()) +
        ",\"title\":" + J(client ? Title(h) : "") + ",\"client\":" + (client ? "true" : "false") + "}");
    Scan();
    watchButtons = buttonsWanted && client;
  }

  // Mouse buttons, for "fade on right-click": EVE draws its context menus inside the client, under our windows,
  // so the app hides windows near a right-click until the next click closes the menu. A button change is
  // reported with where the cursor is and whether it's over a client (WindowFromPoint passes through our
  // click-through windows, so a click on one of our buttons is not "eve").
  static void OnButton(int bit, bool down) {
    POINT p; GetCursorPos(out p);
    IntPtr root = GetAncestor(WindowFromPoint(p), GA_ROOT);
    bool eve = clientHwnds.Contains(root.ToInt64());
    string b = bit == 0 ? "l" : bit == 1 ? "r" : "m";
    Out("{\"t\":\"btn\",\"b\":\"" + b + "\",\"down\":" + (down ? "true" : "false") + ",\"x\":" + p.X + ",\"y\":" + p.Y +
        ",\"eve\":" + (eve ? "true" : "false") + "}");
  }

  // Polls the logical left/right/middle buttons every 25 ms while watchButtons is set. Polling instead of a
  // WH_MOUSE_LL hook keeps us out of the input path entirely: nothing waits on this process before a click
  // reaches EVE. GetAsyncKeyState reads the physical buttons, so swapped buttons are mapped back to logical.
  static void PollButtons() {
    int state = 0;
    while (true) {
      Thread.Sleep(25);
      if (!watchButtons) { state = 0; continue; }
      bool swap = GetSystemMetrics(SM_SWAPBUTTON) != 0;
      int now = 0;
      if (GetAsyncKeyState(swap ? VK_RBUTTON : VK_LBUTTON) < 0) now |= 1;
      if (GetAsyncKeyState(swap ? VK_LBUTTON : VK_RBUTTON) < 0) now |= 2;
      if (GetAsyncKeyState(VK_MBUTTON) < 0) now |= 4;
      int changed = now ^ state;
      state = now;
      for (int bit = 0; bit < 3; bit++) {
        if ((changed & (1 << bit)) == 0) continue;
        PostThreadMessage(mainTid, WM_APP_BTN, new IntPtr(bit), new IntPtr((now >> bit) & 1));
      }
    }
  }
  static void OnObject(IntPtr hook, uint ev, IntPtr h, int obj, int child, uint thread, uint time) {
    if (obj != 0 || child != 0) return;            // OBJID_WINDOW only (ignore caret/cursor/child objects)
    if (ev == EVENT_OBJECT_NAMECHANGE) { if (IsClient(h) || clientHwnds.Contains(h.ToInt64())) Scan(); return; }
    if (clientHwnds.Contains(h.ToInt64())) Scan(); // client moved/resized/minimised
  }

  // When one of our windows loses focus (pin/unpin, or a click on it while unpinned), Windows paints its classic
  // inactive caption into the window's GDI surface even without WS_CAPTION: Chromium counts the frame as
  // system-drawn, so the undocumented caption-draw messages reach DefWindowProc. The page is drawn over that
  // surface and is see-through at the header, so the light-blue "Intel" bar shows and stays. Removing the
  // window's theme or turning off DWM non-client rendering doesn't stop it; a full repaint wipes it.
  static void Repaint() {
    var gone = new List<long>();
    foreach (var id in ownHwnds) {
      var h = new IntPtr(id);
      if (!IsWindow(h)) { gone.Add(id); continue; }
      RedrawWindow(h, IntPtr.Zero, IntPtr.Zero, RDW_INVALIDATE | RDW_ERASE | RDW_ALLCHILDREN | RDW_UPDATENOW | RDW_FRAME);
    }
    foreach (var id in gone) ownHwnds.Remove(id);
  }

  static void Glass(string[] p) {
    // glass <hwnd> <AABBGGRR>: live blur-behind that keeps working while the window is NOT focused.
    // (Windows 11's DWMWA_SYSTEMBACKDROP_TYPE acrylic falls back to a flat colour when inactive - see evidence/.)
    var h = new IntPtr(long.Parse(p[1]));
    ownHwnds.Add(h.ToInt64());
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
    // Electron leaves WS_CAPTION on frameless windows. Windows then paints its classic caption over the page
    // whenever the window gets a non-client activation: clicking the drag-region header, or a screenshot tool
    // taking focus. Without the style there is no caption to paint; dragging by the header still works.
    long style = GetWindowLongPtr(h, GWL_STYLE).ToInt64();
    bool caption = (style & WS_CAPTION) != 0;
    if (caption) {
      SetWindowLongPtr(h, GWL_STYLE, new IntPtr(style & ~WS_CAPTION));
      SetWindowPos(h, IntPtr.Zero, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED);
    }
    Out("{\"t\":\"glass\",\"hwnd\":\"" + p[1] + "\",\"ok\":" + (ok != 0 ? "true" : "false") + ",\"err\":" + err + ",\"cornerHr\":" + hr +
        ",\"captionRemoved\":" + (caption ? "true" : "false") + "}");
  }

  static void Stack(string[] p) {
    // stack <eve hwnd> <hwnd>...: "Stay with EVE". Put our (non-topmost) windows directly above that EVE
    // client in the window order, without activating them, so any app brought in front of EVE covers them too.
    // Windows already in one unbroken run of ours right above the client stay put, so calling this again
    // (on every focus change) doesn't reshuffle them.
    var eve = new IntPtr(long.Parse(p[1]));
    if (!IsWindow(eve)) return;
    var ours = new HashSet<long>();
    for (int i = 2; i < p.Length; i++) ours.Add(long.Parse(p[i]));
    var placed = new HashSet<long>();
    for (IntPtr w = GetWindow(eve, GW_HWNDPREV); w != IntPtr.Zero && ours.Contains(w.ToInt64()); w = GetWindow(w, GW_HWNDPREV)) placed.Add(w.ToInt64());
    foreach (long id in ours) {
      if (placed.Contains(id)) continue;
      var h = new IntPtr(id);
      if (h == eve || !IsWindow(h)) continue;
      // Insert after (= just below) the window directly above the client. When that's a topmost window (or
      // there is none), the client leads the normal band, and HWND_TOP lands at the top of it, still above the client.
      IntPtr above = GetWindow(eve, GW_HWNDPREV);
      bool top = above == IntPtr.Zero || (GetWindowLongPtr(above, GWL_EXSTYLE).ToInt64() & WS_EX_TOPMOST) != 0;
      SetWindowPos(h, top ? HWND_TOP : above, 0, 0, 0, 0, SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE);
      placed.Add(id);
    }
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
    var buttons = new Thread(PollButtons);
    buttons.IsBackground = true; buttons.Start();

    Out("{\"t\":\"ready\"}");
    Scan();
    OnForeground(IntPtr.Zero, 0, GetForegroundWindow(), 0, 0, 0, 0);

    MSG m;
    while (GetMessage(out m, IntPtr.Zero, 0, 0) > 0) {   // WinEvent callbacks are delivered inside this loop
      if (m.message == WM_APP_SCAN) { Scan(); continue; }
      if (m.message == WM_APP_BTN) { OnButton(m.w.ToInt32(), m.l.ToInt32() != 0); continue; }
      if (m.message != WM_APP_CMD) continue;
      while (true) {
        string c; lock (cmds) { if (cmds.Count == 0) break; c = cmds.Dequeue(); }
        var p = c.Trim().Split(' ');
        try {
          if (p[0] == "glass") Glass(p);
          else if (p[0] == "stack") Stack(p);
          else if (p[0] == "buttons") { buttonsWanted = p.Length > 1 && p[1] == "on"; watchButtons = buttonsWanted && clientHwnds.Contains(lastFg); }
          else if (p[0] == "quit") return;
        } catch (Exception e) { Out("{\"t\":\"error\",\"msg\":" + J(e.Message) + "}"); }
      }
    }
  }
}
