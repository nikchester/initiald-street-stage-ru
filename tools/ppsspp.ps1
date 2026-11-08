# Drive PPSSPP for testing: start an ISO, press keys, take screenshots.
#   . tools\ppsspp.ps1; Start-Game <iso>; Shot <png>; Press X; Press Right
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class PW {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
  [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [DllImport("user32.dll")] public static extern uint MapVirtualKey(uint code, uint type);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  public struct RECT { public int L, T, R, B; }
}
"@
[PW]::SetProcessDPIAware() | Out-Null

$script:Exe = 'C:\Program Files\PPSSPP\PPSSPPWindows64.exe'
$script:Keys = @{ X = 0x58; Z = 0x5A; A = 0x41; S = 0x53; Up = 0x26; Down = 0x28; Left = 0x25; Right = 0x27;
                  Enter = 0x0D; Space = 0x20; Esc = 0x1B; Tab = 0x09 }

function Get-Game { Get-Process PPSSPPWindows64 -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1 }

function Start-Game([string]$iso) {
  Get-Process PPSSPPWindows64 -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Milliseconds 500
  Start-Process $script:Exe -ArgumentList "`"$iso`""
  for ($i = 0; $i -lt 40 -and -not (Get-Game); $i++) { Start-Sleep -Milliseconds 250 }
}

function Shot([string]$out) {
  $p = Get-Game
  $r = New-Object PW+RECT; [PW]::GetWindowRect($p.MainWindowHandle, [ref]$r) | Out-Null
  $bmp = New-Object System.Drawing.Bitmap ($r.R - $r.L), ($r.B - $r.T)
  $g = [System.Drawing.Graphics]::FromImage($bmp); $hdc = $g.GetHdc()
  [PW]::PrintWindow($p.MainWindowHandle, $hdc, 2) | Out-Null; $g.ReleaseHdc($hdc)
  $bmp.Save($out); $g.Dispose(); $bmp.Dispose()
}

function Press([string]$key, [int]$holdMs = 120, [int]$afterMs = 400) {
  $p = Get-Game
  # an Alt tap lets a background process take the foreground
  [PW]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero); [PW]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
  [PW]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 80
  $vk = [byte]$script:Keys[$key]; $sc = [byte][PW]::MapVirtualKey($vk, 0)
  $ext = if ($key -in 'Up','Down','Left','Right') { 1 } else { 0 }
  [PW]::keybd_event($vk, $sc, $ext, [UIntPtr]::Zero); Start-Sleep -Milliseconds $holdMs
  [PW]::keybd_event($vk, $sc, 2 -bor $ext, [UIntPtr]::Zero); Start-Sleep -Milliseconds $afterMs
}
