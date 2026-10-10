# Creates the two desktop shortcuts for install.bat. Not meant to be run
# directly - install.bat calls this with the package folder as its own
# location, so $PSScriptRoot is reliable even if the package was moved
# or renamed after unzipping.

$desktop = [Environment]::GetFolderPath("Desktop")
$root = $PSScriptRoot
$ws = New-Object -ComObject WScript.Shell

function New-KiaraShortcut {
    param([string]$Name, [string]$Target, [string]$WorkDir)
    $shortcut = $ws.CreateShortcut((Join-Path $desktop "$Name.lnk"))
    $shortcut.TargetPath = $Target
    $shortcut.WorkingDirectory = $WorkDir
    $shortcut.Save()
    Write-Host "Created: $Name.lnk"
}

New-KiaraShortcut -Name "Kiara (Godot)" -Target (Join-Path $root "launch_godot.bat") -WorkDir $root
New-KiaraShortcut -Name "Kiara (Train MuJoCo)" -Target (Join-Path $root "launch_mujoco.bat") -WorkDir $root
