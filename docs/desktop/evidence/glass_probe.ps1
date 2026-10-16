# Probe: does a non-activated, click-through, topmost overlay keep a live blur of what's behind it?
# Compares DWM system backdrop (Win11 Acrylic) vs SetWindowCompositionAttribute accent blur.
Add-Type -ReferencedAssemblies System.Windows.Forms,System.Drawing -TypeDefinition @'
using System; using System.Drawing; using System.Windows.Forms; using System.Runtime.InteropServices;
public class Checker : Form {
  public Checker(){ FormBorderStyle=FormBorderStyle.None; StartPosition=FormStartPosition.Manual; Bounds=new Rectangle(60,60,600,400); TopMost=true; ShowInTaskbar=false; }
  protected override void OnPaint(PaintEventArgs e){ for(int y=0;y<400;y+=10) for(int x=0;x<600;x+=10) e.Graphics.FillRectangle(((x+y)/10)%2==0?Brushes.White:Brushes.Black,x,y,10,10); }
}
public class Glass : Form {
  [StructLayout(LayoutKind.Sequential)] struct ACCENT { public int State; public int Flags; public uint Gradient; public int Anim; }
  [StructLayout(LayoutKind.Sequential)] struct WCAD { public int Attr; public IntPtr Data; public int Size; }
  [DllImport("user32.dll")] static extern int SetWindowCompositionAttribute(IntPtr h, ref WCAD d);
  [DllImport("dwmapi.dll")] static extern int DwmSetWindowAttribute(IntPtr h, int a, ref int v, int s);
  [StructLayout(LayoutKind.Sequential)] struct MARGINS { public int l,r,t,b; }
  [DllImport("dwmapi.dll")] static extern int DwmExtendFrameIntoClientArea(IntPtr h, ref MARGINS m);
  public string Mode; public bool Act;
  public Glass(string mode, bool act){ Act=act; Mode=mode; FormBorderStyle=FormBorderStyle.None; StartPosition=FormStartPosition.Manual; Bounds=new Rectangle(140,90,220,160); TopMost=true; ShowInTaskbar=false; BackColor=Color.Black; }
  protected override bool ShowWithoutActivation { get { return !Act; } }
  protected override CreateParams CreateParams { get { var c=base.CreateParams; c.ExStyle |= 0x00000080 | 0x8; if(!Act) c.ExStyle |= 0x08000000 /*NOACTIVATE*/ | 0x00000020 /*TRANSPARENT*/ | 0x00080000 /*LAYERED*/; return c; } }
  protected override void OnHandleCreated(EventArgs e){ base.OnHandleCreated(e);
    if (Mode=="dwm"){ var m=new MARGINS{l=-1,r=-1,t=-1,b=-1}; DwmExtendFrameIntoClientArea(Handle, ref m); int dark=1; DwmSetWindowAttribute(Handle,20,ref dark,4); int t=3; DwmSetWindowAttribute(Handle,38,ref t,4); }
    else { var a=new ACCENT{State=4, Flags=2, Gradient=0x66100C0A}; int sz=Marshal.SizeOf(a); IntPtr p=Marshal.AllocHGlobal(sz); Marshal.StructureToPtr(a,p,false); var d=new WCAD{Attr=19,Data=p,Size=sz}; SetWindowCompositionAttribute(Handle, ref d); Marshal.FreeHGlobal(p); }
  }
}
public static class Probe {
  [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
  static double Score(Bitmap b){ // mean abs horizontal gradient inside the glass rect: sharp checker = high, blurred = low
    double s=0; int n=0; for(int y=20;y<b.Height-20;y+=3) for(int x=20;x<b.Width-21;x++){ s+=Math.Abs(b.GetPixel(x,y).GetBrightness()-b.GetPixel(x+1,y).GetBrightness()); n++; } return s/n; }
  static Bitmap Grab(){ var b=new Bitmap(220,160); using(var g=Graphics.FromImage(b)) g.CopyFromScreen(140,90,0,0,b.Size,CopyPixelOperation.SourceCopy); return b; }
  public static void Run(string outDir){
    SetProcessDPIAware(); Application.EnableVisualStyles();
    var chk=new Checker(); chk.Show(); Application.DoEvents(); System.Threading.Thread.Sleep(400); Application.DoEvents();
    var baseB=Grab(); baseB.Save(outDir+"\\0_checker_only.png"); Console.WriteLine("baseline(no overlay) sharpness="+Score(baseB).ToString("F3"));
    foreach (var mode in new[]{"dwm","accent","dwm-active"}) {
      var g=new Glass(mode=="dwm-active"?"dwm":mode, mode=="dwm-active"); g.Show();
      if(mode=="dwm-active"){ g.Activate(); SetForegroundWindow(g.Handle); } else { SetForegroundWindow(chk.Handle); chk.Activate(); } // the "game" has focus; overlay is inactive
      for(int i=0;i<12;i++){ Application.DoEvents(); System.Threading.Thread.Sleep(100); }
      bool overlayFocused = GetForegroundWindow()==g.Handle;
      var b=Grab(); b.Save(outDir+"\\"+(mode=="dwm"?"1":mode=="accent"?"2":"3")+"_"+mode+"_inactive.png");
      Console.WriteLine(mode+": overlayFocused="+overlayFocused+" sharpness="+Score(b).ToString("F3"));
      g.Close(); Application.DoEvents();
    }
    chk.Close();
  }
}
'@
[Probe]::Run($args[0])
