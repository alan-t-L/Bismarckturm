<#
.SYNOPSIS
    Bismarckturm UI - choose options, get the PowerShell command, copy or run it.

.DESCRIPTION
    A Windows Forms front end for the Bismarckturm scripts in the sibling
    folders "Bismarckturm 3D" and "Bismarckturm 2D":
      - 3D tab:     build_bismarckturm_model_scaled.ps1      (STL files)
      - 2D tab:     generate_bismarckturm_laser_parts.ps1    (SVG / DXF parts)
      - Guides tab: reads the user guides and READMEs

    The app only builds commands for those two scripts, from fixed script paths
    and validated options. "Run" opens a NEW PowerShell window (without your
    $PROFILE) in the right folder and runs the command; "Copy" puts the same
    command on the clipboard for pasting into your own session.

    Start it with Start-BismarckturmUI.cmd (double-click).
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

try {

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

# ----------------------------------------------------------------------------
# Locations (everything is found relative to this script)
# ----------------------------------------------------------------------------
$Inv         = [System.Globalization.CultureInfo]::InvariantCulture
$AppRoot     = $PSScriptRoot
$ProjectRoot = Split-Path -Path $AppRoot -Parent
$Dir3D       = Join-Path $ProjectRoot 'Bismarckturm 3D'
$Dir2D       = Join-Path $ProjectRoot 'Bismarckturm 2D'
$Build3DName = 'build_bismarckturm_model_scaled.ps1'
$Laser2DName = 'generate_bismarckturm_laser_parts.ps1'
$Build3DPath = Join-Path $Dir3D $Build3DName
$Laser2DPath = Join-Path $Dir2D $Laser2DName
$RunSession  = Join-Path $AppRoot 'RunSession.ps1'

$script:Ready      = $false
$script:AutoOut    = $true
$script:SettingOut = $false
$script:StlSets    = @()
$script:CurrentSets = @()
$script:GuideFiles = @()

# ----------------------------------------------------------------------------
# Helper functions
# ----------------------------------------------------------------------------
function ConvertTo-Q {
    param([string]$Text)
    return "'" + $Text.Replace("'", "''") + "'"
}

function ConvertTo-DoubleOrNull {
    param([string]$Text)
    $t = $Text.Trim().Replace(',', '.')
    $d = 0.0
    if ([double]::TryParse($t, [System.Globalization.NumberStyles]::Float, $Inv, [ref]$d)) {
        return $d
    }
    return $null
}

function Format-Num {
    param([double]$Value)
    return $Value.ToString('0.######', $Inv)
}

function Format-Command {
    param(
        [string]$Folder,
        [string]$ScriptName,
        [string[]]$ArgList,
        [bool]$SingleLine
    )
    $setLocation = 'Set-Location -LiteralPath ' + (ConvertTo-Q $Folder)
    $call = '.\' + $ScriptName

    if ($SingleLine) {
        return $setLocation + '; ' + $call + ' ' + ($ArgList -join ' ')
    }

    $sb = New-Object System.Text.StringBuilder
    [void]$sb.AppendLine($setLocation)
    [void]$sb.Append($call)
    foreach ($a in $ArgList) {
        [void]$sb.AppendLine(' `')
        [void]$sb.Append('  ' + $a)
    }
    return $sb.ToString()
}

function Get-StlSets {
    # Finds matching base/tower/crown STL triples in scaled_output and model_sets\*.
    $folders = @()
    $scaledOutput = Join-Path $Dir3D 'scaled_output'
    if (Test-Path -LiteralPath $scaledOutput) { $folders += $scaledOutput }

    $modelSets = Join-Path $Dir3D 'model_sets'
    if (Test-Path -LiteralPath $modelSets) {
        $folders += @(Get-ChildItem -LiteralPath $modelSets -Directory | Select-Object -ExpandProperty FullName)
    }

    $found = @()
    foreach ($folder in $folders) {
        $baseFiles = @(Get-ChildItem -LiteralPath $folder -File -Filter '01_base_and_hopper_*.stl')
        foreach ($base in $baseFiles) {
            if ($base.Name -match '^01_base_and_hopper_(birdfeeder|tealight)_scale([0-9.]+)mm_(open|closed)\.stl$') {
                $variant = $Matches[1]
                $height  = $Matches[2]
                $mode    = $Matches[3]
                $tower = Join-Path $folder "02_hollow_tower_shaft_${variant}_scale${height}mm_${mode}.stl"
                $crown = Join-Path $folder "03_lift_off_crown_lid_${variant}_scale${height}mm_${mode}.stl"
                if ((Test-Path -LiteralPath $tower) -and (Test-Path -LiteralPath $crown)) {
                    $variantName = $variant.Substring(0, 1).ToUpper() + $variant.Substring(1)
                    $found += [pscustomobject]@{
                        Variant = $variant
                        Height  = $height
                        HeightNumber = [double]::Parse($height, $Inv)
                        Mode    = $mode
                        Base    = $base.FullName
                        Tower   = $tower
                        Crown   = $crown
                        Label   = "$variantName - $height mm - $mode   [$(Split-Path $folder -Leaf)]"
                    }
                }
            }
        }
    }
    return @($found | Sort-Object Variant, HeightNumber, Mode)
}

function Start-InNewWindow {
    param(
        [string]$Command,
        [string]$WorkingFolder
    )
    if (-not (Test-Path -LiteralPath $RunSession)) {
        [System.Windows.Forms.MessageBox]::Show("RunSession.ps1 was not found next to the app:`r`n$RunSession", 'Bismarckturm', 'OK', 'Error') | Out-Null
        return
    }
    $tempFile = Join-Path ([System.IO.Path]::GetTempPath()) ('bismarckturm_cmd_{0}.ps1' -f [guid]::NewGuid().ToString('N'))
    [System.IO.File]::WriteAllText($tempFile, $Command, (New-Object System.Text.UTF8Encoding($true)))

    $arguments = @(
        '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass',
        '-File', ('"' + $RunSession + '"'),
        '-WorkingFolder', ('"' + $WorkingFolder + '"'),
        '-CommandFile', ('"' + $tempFile + '"')
    )
    Start-Process -FilePath 'powershell.exe' -WorkingDirectory $WorkingFolder -WindowStyle Normal -ArgumentList $arguments
}

function Open-Folder {
    param([string]$Path)
    if (Test-Path -LiteralPath $Path) {
        Start-Process -FilePath 'explorer.exe' -ArgumentList ('"' + $Path + '"')
    }
    else {
        [System.Windows.Forms.MessageBox]::Show("The folder does not exist yet:`r`n$Path", 'Bismarckturm', 'OK', 'Information') | Out-Null
    }
}

# ----------------------------------------------------------------------------
# Control factories
# ----------------------------------------------------------------------------
function New-Label {
    param([string]$Text, [bool]$Bold = $false)
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $Text
    $l.AutoSize = $true
    $l.Anchor = 'Left'
    $l.Margin = New-Object System.Windows.Forms.Padding(3, 6, 3, 3)
    if ($Bold) { $l.Font = New-Object System.Drawing.Font($l.Font, [System.Drawing.FontStyle]::Bold) }
    return $l
}

function New-Note {
    param([string]$Text)
    $l = New-Object System.Windows.Forms.Label
    $l.Text = $Text
    $l.AutoSize = $true
    $l.MaximumSize = New-Object System.Drawing.Size(640, 0)
    $l.ForeColor = [System.Drawing.Color]::DimGray
    $l.Margin = New-Object System.Windows.Forms.Padding(3, 3, 3, 3)
    return $l
}

function New-Radio {
    param([string]$Text, [bool]$Checked = $false)
    $r = New-Object System.Windows.Forms.RadioButton
    $r.Text = $Text
    $r.AutoSize = $true
    $r.Checked = $Checked
    return $r
}

function New-Check {
    param([string]$Text, [bool]$Checked = $false)
    $c = New-Object System.Windows.Forms.CheckBox
    $c.Text = $Text
    $c.AutoSize = $true
    $c.Checked = $Checked
    return $c
}

function New-Text {
    param([string]$Text, [int]$Width = 80)
    $t = New-Object System.Windows.Forms.TextBox
    $t.Text = $Text
    $t.Width = $Width
    $t.Anchor = 'Left'
    return $t
}

function New-Button {
    param([string]$Text, [int]$Width = 150)
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $Text
    $b.Width = $Width
    $b.Height = 30
    return $b
}

function New-FlowRow {
    param($Controls)
    $f = New-Object System.Windows.Forms.FlowLayoutPanel
    $f.AutoSize = $true
    $f.AutoSizeMode = 'GrowAndShrink'
    $f.FlowDirection = 'LeftToRight'
    $f.WrapContents = $true
    $f.Anchor = 'Left'
    foreach ($c in $Controls) { $f.Controls.Add($c) }
    return $f
}

function New-OptionTable {
    $t = New-Object System.Windows.Forms.TableLayoutPanel
    $t.ColumnCount = 2
    $t.Dock = 'Top'
    $t.AutoSize = $true
    $t.AutoSizeMode = 'GrowAndShrink'
    $t.Padding = New-Object System.Windows.Forms.Padding(8)
    [void]$t.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute, 190)))
    [void]$t.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
    return $t
}

function Add-Row {
    param($Table, [string]$Label, $Control)
    $row = $Table.RowCount
    $Table.RowCount = $row + 1
    [void]$Table.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
    if ($Label) {
        $Table.Controls.Add((New-Label $Label), 0, $row)
        $Table.Controls.Add($Control, 1, $row)
    }
    else {
        $Table.Controls.Add($Control, 0, $row)
        $Table.SetColumnSpan($Control, 2)
    }
}

function New-TabLayout {
    # Options area (scrolls), status line, command box, button bar.
    param($Tab)
    $main = New-Object System.Windows.Forms.TableLayoutPanel
    $main.Dock = 'Fill'
    $main.ColumnCount = 1
    $main.RowCount = 4
    [void]$main.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 100)))
    [void]$main.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 56)))
    [void]$main.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 150)))
    [void]$main.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 44)))

    $options = New-Object System.Windows.Forms.Panel
    $options.Dock = 'Fill'
    $options.AutoScroll = $true

    $status = New-Object System.Windows.Forms.Label
    $status.Dock = 'Fill'
    $status.AutoEllipsis = $false

    $box = New-Object System.Windows.Forms.TextBox
    $box.Multiline = $true
    $box.ReadOnly = $true
    $box.ScrollBars = 'Both'
    $box.WordWrap = $false
    $box.Dock = 'Fill'
    $box.Font = New-Object System.Drawing.Font('Consolas', 10)
    $box.BackColor = [System.Drawing.SystemColors]::Window

    $bar = New-Object System.Windows.Forms.FlowLayoutPanel
    $bar.Dock = 'Fill'
    $bar.FlowDirection = 'LeftToRight'

    $copy = New-Button 'Copy command' 130
    $run  = New-Button 'Run in new PowerShell window' 220
    $open = New-Button 'Open output folder' 150
    $single = New-Check 'Single-line command' $false
    $single.Margin = New-Object System.Windows.Forms.Padding(12, 8, 3, 3)
    $bar.Controls.AddRange(@($copy, $run, $open, $single))

    $main.Controls.Add($options, 0, 0)
    $main.Controls.Add($status, 0, 1)
    $main.Controls.Add($box, 0, 2)
    $main.Controls.Add($bar, 0, 3)
    $Tab.Controls.Add($main)

    return @{
        Options = $options
        Status  = $status
        Box     = $box
        Copy    = $copy
        Run     = $run
        Open    = $open
        Single  = $single
    }
}

function Set-StatusText {
    param($Layout, $Errors, $Warnings)
    if ($Errors.Count -gt 0) {
        $Layout.Status.ForeColor = [System.Drawing.Color]::Firebrick
        $Layout.Status.Text = 'Fix before running: ' + ($Errors -join '  |  ')
    }
    elseif ($Warnings.Count -gt 0) {
        $Layout.Status.ForeColor = [System.Drawing.Color]::DarkOrange
        $Layout.Status.Text = 'Note: ' + ($Warnings -join '  |  ')
    }
    else {
        $Layout.Status.ForeColor = [System.Drawing.Color]::SeaGreen
        $Layout.Status.Text = 'The options are valid. Copy the command or run it.'
    }
}

# ----------------------------------------------------------------------------
# Main form
# ----------------------------------------------------------------------------
$form = New-Object System.Windows.Forms.Form
$form.Text = 'Bismarckturm - model generator'
$form.StartPosition = 'CenterScreen'
$form.ClientSize = New-Object System.Drawing.Size(885, 650)
$form.MinimumSize = New-Object System.Drawing.Size(800, 620)

$tabs = New-Object System.Windows.Forms.TabControl
$tabs.Dock = 'Fill'
$tab3D = New-Object System.Windows.Forms.TabPage
$tab3D.Text = '3D model (STL)'
$tab2D = New-Object System.Windows.Forms.TabPage
$tab2D.Text = '2D laser parts (SVG / DXF)'
$tabGuides = New-Object System.Windows.Forms.TabPage
$tabGuides.Text = 'User guides'
[void]$tabs.TabPages.Add($tab3D)
[void]$tabs.TabPages.Add($tab2D)
[void]$tabs.TabPages.Add($tabGuides)
$form.Controls.Add($tabs)

# ----------------------------------------------------------------------------
# 3D tab
# ----------------------------------------------------------------------------
$L3 = New-TabLayout $tab3D
$c3 = @{}
$t3 = New-OptionTable
$L3.Options.Controls.Add($t3)

$c3.Bird   = New-Radio 'Birdfeeder' $true
$c3.Tealight = New-Radio 'Tealight' $false
Add-Row $t3 'Model variant' (New-FlowRow @($c3.Bird, $c3.Tealight))

$c3.Open   = New-Radio 'Open (real windows, slits and door)' $true
$c3.Closed = New-Radio 'Closed (recesses only)' $false
Add-Row $t3 'Mode' (New-FlowRow @($c3.Open, $c3.Closed))

$c3.Scale = New-Object System.Windows.Forms.ComboBox
$c3.Scale.DropDownStyle = 'DropDown'
$c3.Scale.Width = 100
$c3.Scale.Anchor = 'Left'
foreach ($s in @('1.0', '0.7', '0.5', '0.3', '0.25', '0.2', '0.1', '0.05')) { [void]$c3.Scale.Items.Add($s) }
$c3.Scale.Text = '0.3'
$c3.Height = New-Label ''
Add-Row $t3 'Scale (1.0 = about 1000 mm tall)' (New-FlowRow @($c3.Scale, $c3.Height))

$c3.Clearance = New-Text '0' 80
Add-Row $t3 'Joint clearance (mm)' (New-FlowRow @($c3.Clearance, (New-Note '0 = proportional to scale (0.35 mm x scale)')))

$c3.P1   = New-Check '1  Base and hopper' $true
$c3.P2   = New-Check '2  Hollow tower shaft' $true
$c3.P3   = New-Check '3  Lift-off crown lid' $true
$c3.PAsm = New-Check 'asm  Full assembly (viewing only)' $true
Add-Row $t3 'Parts to generate' (New-FlowRow @($c3.P1, $c3.P2, $c3.P3, $c3.PAsm))

Add-Row $t3 '' (New-Note ('3D model output (STL files) are output to folder "...\Bismarckturm 3D\scaled_output".' + "`r`n" + 'A build could take a few minutes, needs a few GB of free memory and writes STL files' + "`r`n" + 'of roughly 60-125 MB each (the assembly about 300 MB).' + "`r`n" + 'If you intend to use the STL files as source files for making 2D laser-cutter parts,' + "`r`n" + 'select parts 1, 2 and 3, and ensure that the same model scale is selected for generation' + "`r`n" + 'on the "2D laser-cutter parts (SVG / DXF)" tab.'))

function Update-3D {
    if (-not $script:Ready) { return }
    $errs = New-Object 'System.Collections.Generic.List[string]'
    $warns = New-Object 'System.Collections.Generic.List[string]'
    $argList = New-Object 'System.Collections.Generic.List[string]'

    $scale = ConvertTo-DoubleOrNull $c3.Scale.Text
    if ($null -eq $scale -or $scale -le 0) {
        $errs.Add('Enter a scale above 0, for example 0.3 for a model about 300 mm tall.')
        $c3.Height.Text = ''
    }
    else {
        $c3.Height.Text = 'Model height: about ' + ([math]::Round($scale * 1000, 1)).ToString($Inv) + ' mm'
        $argList.Add('-Scale ' + (Format-Num $scale))
        if ($scale -lt 0.32) {
            $warns.Add('Below scale 0.32 the BISMARCK lettering strokes are under about 1.2 mm: fine for laser parts, unreliable for a 0.4 mm nozzle.')
        }
        if ($scale -gt 1.0) {
            $warns.Add('Scales above 1.0 make very large models; check memory and print size.')
        }
    }

    if ($c3.Bird.Checked) { $argList.Add('-Birdfeeder') } else { $argList.Add('-Tealight') }
    if ($c3.Open.Checked) { $argList.Add('-Open') } else { $argList.Add('-Closed') }

    $clearance = ConvertTo-DoubleOrNull $c3.Clearance.Text
    if ($null -eq $clearance -or $clearance -lt 0) {
        $errs.Add('Joint clearance must be 0 or a positive number.')
    }
    elseif ($clearance -gt 0) {
        $argList.Add('-Clearance ' + (Format-Num $clearance))
    }

    $parts = New-Object 'System.Collections.Generic.List[string]'
    if ($c3.P1.Checked)   { $parts.Add('1') }
    if ($c3.P2.Checked)   { $parts.Add('2') }
    if ($c3.P3.Checked)   { $parts.Add('3') }
    if ($c3.PAsm.Checked) { $parts.Add('asm') }
    if ($parts.Count -eq 0) {
        $errs.Add('Select at least one part.')
    }
    elseif ($parts.Count -lt 4) {
        $quoted = @($parts | ForEach-Object { ConvertTo-Q $_ })
        $argList.Add('-Parts ' + ($quoted -join ','))
        if ($c3.PAsm.Checked -and ($parts.Count -lt 4)) {
            $warns.Add('The full assembly is assembled from parts 1-3; keep them selected together with asm.')
        }
    }

    if (-not (Test-Path -LiteralPath $Build3DPath)) {
        $errs.Add("Build script not found: $Build3DPath")
    }

    Set-StatusText $L3 $errs $warns
    if ($errs.Count -eq 0) {
        $L3.Box.Text = Format-Command -Folder $Dir3D -ScriptName $Build3DName -ArgList ($argList.ToArray()) -SingleLine $L3.Single.Checked
    }
    else {
        $L3.Box.Text = '# Correct the problems shown above to generate the command.'
    }
    $L3.Copy.Enabled = ($errs.Count -eq 0)
    $L3.Run.Enabled  = ($errs.Count -eq 0)
}

foreach ($ctl in @($c3.Bird, $c3.Open, $c3.P1, $c3.P2, $c3.P3, $c3.PAsm, $L3.Single)) {
    if ($ctl -is [System.Windows.Forms.RadioButton] -or $ctl -is [System.Windows.Forms.CheckBox]) {
        $ctl.Add_CheckedChanged({ Update-3D })
    }
}
$c3.Scale.Add_TextChanged({ Update-3D })
$c3.Scale.Add_SelectedIndexChanged({ Update-3D })
$c3.Clearance.Add_TextChanged({ Update-3D })

$L3.Copy.Add_Click({
    if ($L3.Box.Text.Length -gt 0) {
        [System.Windows.Forms.Clipboard]::SetText($L3.Box.Text)
        $L3.Status.ForeColor = [System.Drawing.Color]::SeaGreen
        $L3.Status.Text = 'Command copied to the clipboard.'
    }
})
$L3.Run.Add_Click({
    $answer = [System.Windows.Forms.MessageBox]::Show(
        "This 3D build takes a few minutes and needs a few GB of free memory.`r`n`r`nRun it now in a new PowerShell window?",
        'Run 3D build', 'YesNo', 'Question')
    if ($answer -eq 'Yes') { Start-InNewWindow $L3.Box.Text $Dir3D }
})
$L3.Open.Add_Click({
    $so = Join-Path $Dir3D 'scaled_output'
    if (Test-Path -LiteralPath $so) { Open-Folder $so } else { Open-Folder $Dir3D }
})

# ----------------------------------------------------------------------------
# 2D tab
# ----------------------------------------------------------------------------
$L2 = New-TabLayout $tab2D
$c2 = @{}
$t2 = New-OptionTable
$L2.Options.Controls.Add($t2)

$c2.Bird = New-Radio 'Birdfeeder' $true
$c2.Tealight = New-Radio 'Tealight' $false
Add-Row $t2 'Model variant' (New-FlowRow @($c2.Bird, $c2.Tealight))

$c2.Coupon = New-Check 'Test coupon only (joint fit test - no STL needed)' $false
Add-Row $t2 '' $c2.Coupon

$c2.Stl = New-Object System.Windows.Forms.ComboBox
$c2.Stl.DropDownStyle = 'DropDownList'
$c2.Stl.Width = 460
$c2.Refresh = New-Button 'Rescan' 80
$c2.StlInfo = New-Note ''
Add-Row $t2 'STL set (same scale)' (New-FlowRow @($c2.Stl, $c2.Refresh))
Add-Row $t2 '' $c2.StlInfo

$c2.Thickness = New-Text '4' 60
Add-Row $t2 'Material thickness (mm)' $c2.Thickness
$c2.Kerf = New-Text '0.2' 60
Add-Row $t2 'Laser kerf (mm)' $c2.Kerf
$c2.Clear = New-Text '0.2' 60
Add-Row $t2 'Joint clearance (mm)' $c2.Clear

$c2.Fit = New-Object System.Windows.Forms.ComboBox
$c2.Fit.DropDownStyle = 'DropDownList'
$c2.Fit.Width = 100
$c2.Fit.Anchor = 'Left'
foreach ($f in @('slip', 'snug', 'press')) { [void]$c2.Fit.Items.Add($f) }
$c2.Fit.SelectedIndex = 0
Add-Row $t2 'Fit' (New-FlowRow @($c2.Fit, (New-Note 'slip = clearance as given, snug = half, press = unreliable')))

$c2.Method = New-Object System.Windows.Forms.ComboBox
$c2.Method.DropDownStyle = 'DropDownList'
$c2.Method.Width = 100
$c2.Method.Anchor = 'Left'
foreach ($m in @('Faceted', 'Stacked')) { [void]$c2.Method.Items.Add($m) }
$c2.Method.SelectedIndex = 0
Add-Row $t2 'Construction method' (New-FlowRow @($c2.Method, (New-Note 'Faceted = interlocking panels; Stacked = glued layers (many more parts)')))

$c2.Svg = New-Check 'SVG' $true
$c2.Dxf = New-Check 'DXF' $true
Add-Row $t2 'Output formats' (New-FlowRow @($c2.Svg, $c2.Dxf))

$c2.Out = New-Text '' 460
$c2.Browse = New-Button 'Browse...' 80
$c2.Auto = New-Button 'Auto name' 80
Add-Row $t2 'Output folder' (New-FlowRow @($c2.Out, $c2.Browse, $c2.Auto))

$c2.TabWidth = New-Text '10' 50
$c2.TabCount = New-Text '3' 50
$c2.Corner = New-Text '0' 50
Add-Row $t2 'Tab width / tabs per edge / corner radius' (New-FlowRow @($c2.TabWidth, $c2.TabCount, $c2.Corner))
$c2.SheetW = New-Text '600' 50
$c2.SheetH = New-Text '400' 50
$c2.Margin = New-Text '10' 50
$c2.Spacing = New-Text '3' 50
Add-Row $t2 'Sheet width / height / margin / spacing' (New-FlowRow @($c2.SheetW, $c2.SheetH, $c2.Margin, $c2.Spacing))
$c2.Preview = New-Check 'Write PNG previews (-Preview, needs matplotlib)' $false
$c2.Narrow  = New-Check 'Allow narrow tabs (-AllowNarrowTabs)' $false
$c2.Install = New-Check 'Install missing Python modules (-InstallDependencies)' $false
Add-Row $t2 'Extras' (New-FlowRow @($c2.Preview, $c2.Narrow, $c2.Install))
Add-Row $t2 '' (New-Note 'Options left at their default value (tab width 10, 3 tabs, corner radius 0, sheet 600 x 400, margin 10, spacing 3) are not added to the command. Use a separate output folder for each run: file names do not contain the scale or thickness.')

function Fill-StlCombo {
    $variant = 'tealight'
    if ($c2.Bird.Checked) { $variant = 'birdfeeder' }
    $script:CurrentSets = @($script:StlSets | Where-Object { $_.Variant -eq $variant })
    $c2.Stl.Items.Clear()
    foreach ($s in $script:CurrentSets) { [void]$c2.Stl.Items.Add($s.Label) }
    if ($c2.Stl.Items.Count -gt 0) { $c2.Stl.SelectedIndex = 0 }
}

function Add-OptionalNumber {
    param($Text, [string]$Name, [double]$Default, [string]$Param, $ArgList, $Errs, [bool]$IsInt, [bool]$Positive)
    $t = $Text.Trim()
    if ($t -eq '') { return }
    $v = ConvertTo-DoubleOrNull $t
    if ($null -eq $v -or $v -lt 0 -or ($Positive -and $v -le 0)) {
        if ($Positive) { $Errs.Add("$Name must be a number above 0.") } else { $Errs.Add("$Name must be 0 or more.") }
        return
    }
    if ($IsInt -and $v -ne [math]::Floor($v)) {
        $Errs.Add("$Name must be a whole number.")
        return
    }
    if ($v -ne $Default) { $ArgList.Add("$Param " + (Format-Num $v)) }
}

function Update-2D {
    if (-not $script:Ready) { return }
    $errs = New-Object 'System.Collections.Generic.List[string]'
    $warns = New-Object 'System.Collections.Generic.List[string]'
    $argList = New-Object 'System.Collections.Generic.List[string]'

    $coupon = $c2.Coupon.Checked
    $c2.Stl.Enabled = (-not $coupon)
    $c2.Refresh.Enabled = (-not $coupon)

    $variant = 'tealight'
    if ($c2.Bird.Checked) { $variant = 'birdfeeder' }

    $selected = $null
    if (-not $coupon) {
        $index = $c2.Stl.SelectedIndex
        if ($index -ge 0 -and $index -lt $script:CurrentSets.Count) { $selected = $script:CurrentSets[$index] }
        if ($null -eq $selected) {
            $errs.Add("No $variant STL set found. Generate STL files on the 3D tab first (parts 1, 2 and 3), then click Rescan.")
            $c2.StlInfo.Text = ''
        }
        else {
            $c2.StlInfo.Text = "Base: $(Split-Path $selected.Base -Leaf)`r`nTower: $(Split-Path $selected.Tower -Leaf)`r`nCrown: $(Split-Path $selected.Crown -Leaf)"
            if ($selected.Mode -eq 'closed') {
                $warns.Add('Closed STLs: windows and slits are engraved instead of cut.')
            }
        }
    }
    else {
        $c2.StlInfo.Text = ''
    }

    $thickness = ConvertTo-DoubleOrNull $c2.Thickness.Text
    $kerf = ConvertTo-DoubleOrNull $c2.Kerf.Text
    $clear = ConvertTo-DoubleOrNull $c2.Clear.Text
    if ($null -eq $thickness -or $thickness -le 0) { $errs.Add('Material thickness must be above 0.') }
    if ($null -eq $kerf -or $kerf -lt 0) { $errs.Add('Kerf must be 0 or more.') }
    elseif ($null -ne $thickness -and $kerf -ge $thickness) { $errs.Add('Kerf must be smaller than the material thickness.') }
    if ($null -eq $clear) { $errs.Add('Joint clearance must be a number.') }

    # Default output folder name
    if ($script:AutoOut) {
        $name = $variant
        if ($coupon) { $name = 'test_coupon' }
        elseif ($null -ne $selected) { $name = "${variant}_$($selected.Height)mm" }
        if ($null -ne $thickness -and $thickness -gt 0) { $name = "${name}_$(Format-Num $thickness)mm" }
        $script:SettingOut = $true
        $c2.Out.Text = Join-Path (Join-Path $Dir2D '2D CAD output') $name
        $script:SettingOut = $false
    }
    $outDir = $c2.Out.Text.Trim()
    if ($outDir -eq '') { $errs.Add('Choose an output folder.') }

    $formats = New-Object 'System.Collections.Generic.List[string]'
    if ($c2.Svg.Checked) { $formats.Add('SVG') }
    if ($c2.Dxf.Checked) { $formats.Add('DXF') }

    if ($coupon) {
        $argList.Add('-TestCoupon')
    }
    else {
        if ($variant -eq 'birdfeeder') { $argList.Add('-Birdfeeder') } else { $argList.Add('-Tealight') }
        if ($null -ne $selected) {
            $argList.Add('-BaseStl ' + (ConvertTo-Q $selected.Base))
            $argList.Add('-TowerStl ' + (ConvertTo-Q $selected.Tower))
            $argList.Add('-CrownStl ' + (ConvertTo-Q $selected.Crown))
        }
    }

    if ($null -ne $thickness) { $argList.Add('-MaterialThickness ' + (Format-Num $thickness)) }
    if ($null -ne $kerf) { $argList.Add('-Kerf ' + (Format-Num $kerf)) }
    if ($null -ne $clear) { $argList.Add('-JointClearance ' + (Format-Num $clear)) }

    if (-not $coupon) {
        $argList.Add('-Fit ' + $c2.Fit.SelectedItem)
        $argList.Add('-ConstructionMethod ' + $c2.Method.SelectedItem)
        if ($formats.Count -eq 0) { $errs.Add('Select at least one output format (SVG or DXF).') }
        else { $argList.Add('-OutputFormat ' + ($formats -join ',')) }

        Add-OptionalNumber $c2.TabWidth.Text 'Tab width' 10 '-TabWidth' $argList $errs $false $true
        Add-OptionalNumber $c2.TabCount.Text 'Tabs per edge' 3 '-TabCount' $argList $errs $true $true
        Add-OptionalNumber $c2.Corner.Text 'Corner radius' 0 '-CornerRadius' $argList $errs $false $false
        Add-OptionalNumber $c2.SheetW.Text 'Sheet width' 600 '-SheetWidth' $argList $errs $false $true
        Add-OptionalNumber $c2.SheetH.Text 'Sheet height' 400 '-SheetHeight' $argList $errs $false $true
        Add-OptionalNumber $c2.Margin.Text 'Sheet margin' 10 '-SheetMargin' $argList $errs $false $false
        Add-OptionalNumber $c2.Spacing.Text 'Part spacing' 3 '-PartSpacing' $argList $errs $false $false

        if ($c2.Preview.Checked) { $argList.Add('-Preview') }
        if ($c2.Narrow.Checked)  { $argList.Add('-AllowNarrowTabs') }
    }
    if ($c2.Install.Checked) { $argList.Add('-InstallDependencies') }

    if ($outDir -ne '') { $argList.Add('-OutputDirectory ' + (ConvertTo-Q $outDir)) }

    if (-not (Test-Path -LiteralPath $Laser2DPath)) { $errs.Add("Laser-parts script not found: $Laser2DPath") }

    Set-StatusText $L2 $errs $warns
    if ($errs.Count -eq 0) {
        $L2.Box.Text = Format-Command -Folder $Dir2D -ScriptName $Laser2DName -ArgList ($argList.ToArray()) -SingleLine $L2.Single.Checked
    }
    else {
        $L2.Box.Text = '# Correct the problems shown above to generate the command.'
    }
    $L2.Copy.Enabled = ($errs.Count -eq 0)
    $L2.Run.Enabled  = ($errs.Count -eq 0)
}

foreach ($ctl in @($c2.Coupon, $c2.Svg, $c2.Dxf, $c2.Preview, $c2.Narrow, $c2.Install, $L2.Single)) {
    $ctl.Add_CheckedChanged({ Update-2D })
}
$c2.Bird.Add_CheckedChanged({ if ($script:Ready) { Fill-StlCombo; Update-2D } })
$c2.Stl.Add_SelectedIndexChanged({ Update-2D })
$c2.Fit.Add_SelectedIndexChanged({ Update-2D })
$c2.Method.Add_SelectedIndexChanged({ Update-2D })
foreach ($ctl in @($c2.Thickness, $c2.Kerf, $c2.Clear, $c2.TabWidth, $c2.TabCount, $c2.Corner, $c2.SheetW, $c2.SheetH, $c2.Margin, $c2.Spacing)) {
    $ctl.Add_TextChanged({ Update-2D })
}
$c2.Out.Add_TextChanged({
    if (-not $script:SettingOut) { $script:AutoOut = $false }
    Update-2D
})
$c2.Auto.Add_Click({ $script:AutoOut = $true; Update-2D })
$c2.Browse.Add_Click({
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = 'Choose the output folder for the 2D parts'
    if (Test-Path -LiteralPath $Dir2D) { $dialog.SelectedPath = $Dir2D }
    if ($dialog.ShowDialog() -eq 'OK') {
        $script:AutoOut = $false
        $c2.Out.Text = $dialog.SelectedPath
    }
})
$c2.Refresh.Add_Click({
    $script:StlSets = @(Get-StlSets)
    Fill-StlCombo
    Update-2D
})

$L2.Copy.Add_Click({
    if ($L2.Box.Text.Length -gt 0) {
        [System.Windows.Forms.Clipboard]::SetText($L2.Box.Text)
        $L2.Status.ForeColor = [System.Drawing.Color]::SeaGreen
        $L2.Status.Text = 'Command copied to the clipboard.'
    }
})
$L2.Run.Add_Click({ Start-InNewWindow $L2.Box.Text $Dir2D })
$L2.Open.Add_Click({
    $folder = $c2.Out.Text.Trim()
    if ($folder -ne '' -and (Test-Path -LiteralPath $folder)) { Open-Folder $folder }
    else { Open-Folder (Join-Path $Dir2D '2D CAD output') }
})

# ----------------------------------------------------------------------------
# Guides tab
# ----------------------------------------------------------------------------
$guideLayout = New-Object System.Windows.Forms.TableLayoutPanel
$guideLayout.Dock = 'Fill'
$guideLayout.ColumnCount = 1
$guideLayout.RowCount = 2
[void]$guideLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Absolute, 44)))
[void]$guideLayout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 100)))

$guideBar = New-Object System.Windows.Forms.FlowLayoutPanel
$guideBar.Dock = 'Fill'
$guideCombo = New-Object System.Windows.Forms.ComboBox
$guideCombo.DropDownStyle = 'DropDownList'
$guideCombo.Width = 520
$guideCombo.Margin = New-Object System.Windows.Forms.Padding(6, 8, 3, 3)
$guideOpen = New-Button 'Open in default app' 150
$guideFolder = New-Button 'Show in folder' 110
$guideBar.Controls.AddRange(@($guideCombo, $guideOpen, $guideFolder))

$guideText = New-Object System.Windows.Forms.RichTextBox
$guideText.Dock = 'Fill'
$guideText.ReadOnly = $true
$guideText.WordWrap = $true
$guideText.Font = New-Object System.Drawing.Font('Consolas', 10)
$guideText.BackColor = [System.Drawing.SystemColors]::Window

$guideLayout.Controls.Add($guideBar, 0, 0)
$guideLayout.Controls.Add($guideText, 0, 1)
$tabGuides.Controls.Add($guideLayout)

function Get-GuideFiles {
    $locations = @(
        @{ Path = $Dir3D; Tag = '3D' },
        @{ Path = $Dir2D; Tag = '2D' },
        @{ Path = $ProjectRoot; Tag = 'Project' },
        @{ Path = $AppRoot; Tag = 'UI' }
    )
    $items = @()
    foreach ($loc in $locations) {
        if (Test-Path -LiteralPath $loc.Path) {
            foreach ($f in @(Get-ChildItem -LiteralPath $loc.Path -File -Filter '*.md')) {
                $isGuide = ($f.Name -like '*User_Guide*')
                $prefix = '   '
                if ($isGuide) { $prefix = '* ' }
                $items += [pscustomobject]@{
                    Label = "$prefix[$($loc.Tag)] $($f.Name)"
                    Path = $f.FullName
                    Sort = $(if ($isGuide) { 0 } else { 1 })
                }
            }
        }
    }
    return @($items | Sort-Object Sort, Label)
}

function Show-Guide {
    $index = $guideCombo.SelectedIndex
    if ($index -lt 0 -or $index -ge $script:GuideFiles.Count) { return }
    $path = $script:GuideFiles[$index].Path
    $guideText.Text = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8).Replace("`r`n", "`n").Replace("`n", "`r`n")
    $guideText.SelectionStart = 0
    $guideText.ScrollToCaret()
}

$guideCombo.Add_SelectedIndexChanged({ Show-Guide })
$guideOpen.Add_Click({
    $i = $guideCombo.SelectedIndex
    if ($i -ge 0) { Start-Process -FilePath $script:GuideFiles[$i].Path }
})
$guideFolder.Add_Click({
    $i = $guideCombo.SelectedIndex
    if ($i -ge 0) { Start-Process -FilePath 'explorer.exe' -ArgumentList ('/select,"' + $script:GuideFiles[$i].Path + '"') }
})

# ----------------------------------------------------------------------------
# Start-up
# ----------------------------------------------------------------------------
$form.Add_Shown({
    $script:StlSets = @(Get-StlSets)
    $script:GuideFiles = @(Get-GuideFiles)
    foreach ($g in $script:GuideFiles) { [void]$guideCombo.Items.Add($g.Label) }
    if ($guideCombo.Items.Count -gt 0) { $guideCombo.SelectedIndex = 0 }

    Fill-StlCombo
    $script:Ready = $true
    Update-3D
    Update-2D

    $missing = @()
    if (-not (Test-Path -LiteralPath $Build3DPath)) { $missing += $Build3DPath }
    if (-not (Test-Path -LiteralPath $Laser2DPath)) { $missing += $Laser2DPath }
    if ($missing.Count -gt 0) {
        [System.Windows.Forms.MessageBox]::Show(
            ("Some project scripts were not found. Keep this folder next to 'Bismarckturm 3D' and 'Bismarckturm 2D'.`r`n`r`n" + ($missing -join "`r`n")),
            'Bismarckturm', 'OK', 'Warning') | Out-Null
    }
})

[void]$form.ShowDialog()

}
catch {
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show(
        "The Bismarckturm UI stopped with an error:`r`n`r`n$($_.Exception.Message)`r`n`r`n$($_.ScriptStackTrace)",
        'Bismarckturm', 'OK', 'Error') | Out-Null
}



