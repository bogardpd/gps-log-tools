# Automates importing a GPX file from a Garmin GPS. Copies the GPX track log
# from the Garmin to a GPX data folder (named with a UTC timestamp) and
# imports the GPX tracks into driving_canonical.kml using a Python script.

function Get-MTP-Object {
  # Converts an MTP path string into a ComObject. Derived from:
  # https://plusontech.com/2019/01/05/weekend-powershell-script-copy-files-from-phone-camera-by-month/
  param(
    $Shell,
    [string]$PathString
  )
  $PathArray = $PathString -split "\\"
  $MTPObject = $Shell.NameSpace(17).Self
  foreach($item in $PathArray){
    $MTPObject = $MTPObject.GetFolder.Items() | Where-Object{$_.Name -eq $item}
    if (-Not $MTPObject) {
      return $false
    }
  }
  return $MTPObject
}

$ScriptPath = Split-Path ($MyInvocation.MyCommand.Path)
$Shell = New-Object -ComObject Shell.Application
$Time = Get-Date
$UTCTime = $Time.ToUniversalTime().ToString("yyyyMMddTHHmmZ")

$Devices = @{
  "DriveSmart 50" = "50LMT";
  "Garmin DriveSmart 50" = "50LMTHD";
  "Garmin DriveSmart 55" = "55LM";
}

foreach($Device in $Devices.GetEnumerator()) {
  
  $SourceGPXPath = $Device.Name + "\Internal Storage\GPX\Current.gpx"
  Write-Host "Reading GPX file from `"$($SourceGPXPath)`"..." -ForegroundColor Yellow
  $SourceGPX = Get-MTP-Object $Shell $SourceGPXPath
  
  if ($SourceGPX) {
    # Copy GPX to raw data folder.
    $TargetFolderPath = "C:\Users\paulb\OneDrive\Projects\Driving-Logs\Raw-Data\garmin"
    Write-Host "Copying GPX to `"$($TargetFolderPath)`"..."
    $TargetFolderShell = $Shell.NameSpace($TargetFolderPath).self
    $TargetFolderShell.GetFolder.CopyHere($SourceGPX)
    
    # Rename raw data file.
    $RawFileName = "$($UTCTime)_$($Device.Value).gpx"
    Write-Host "Renaming GPX to `"$($RawFileName)`"..."
    Rename-Item -Path "$($TargetFolderPath)\Current.gpx" -NewName $RawFileName
    Write-Host "...done."
  
    # Import GPX with Python script.
    python "$($ScriptPath)\update_kml.py" "$($TargetFolderPath)\$($RawFileName)" --nopause

  } else {
    
    Write-Host "No GPX file found at `"$($SourceGPXPath)`"."

  }
}

Pause