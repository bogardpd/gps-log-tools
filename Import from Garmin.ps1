# Automates importing a GPX file from a Garmin GPS. Copies the GPX track log
# from the Garmin to a GPX archive folder (named with a UTC timestamp) and
# imports the GPX tracks into driving_canonical.kml using a Python script.

function Get-MTP-Object {
  # Converts an MTP path string into a ComObject. Derived from:
  # https://plusontech.com/2019/01/05/weekend-powershell-script-copy-files-from-phone-camera-by-month/
  param(
    $Shell,
    [string]$PathString
  )
  $PathArray = $SourcePath -split "\\"
  $MTPObject = $Shell.NameSpace(17).Self
  foreach($item in $PathArray){
    $MTPObject = $MTPObject.GetFolder.Items() | Where-Object{$_.Name -eq $item}
  }
  return $MTPObject
}

Set-Location -Path C:\Users\paulb\OneDrive\Projects\Maps\GPS\Auto
$Shell = New-Object -ComObject Shell.Application
$Time = Get-Date
$UTCTime = $Time.ToUniversalTime().ToString("yyyyMMddTHHmmZ")


# Copy current.gpx to backup.
Write-Host "Copying Current.gpx from Garmin to GPX Archive ..."
# $DeviceName = "Garmin DriveSmart 55"
# $DeviceName = "Garmin DriveSmart 66"
$DeviceName = "DriveSmart 50"
$SourceGPXPath = $DeviceName + "\Internal Storage\GPX\Current.gpx"
$SourceGPX = Get-MTP-Object $Shell $SourceGPXPath

$TargetFolderShell = $Shell.NameSpace("C:\Users\paulb\OneDrive\Projects\Maps\GPS\Auto\raw\garmin").self
$TargetFolderShell.GetFolder.CopyHere($SourceGPX)

Rename-Item -Path ".\raw\garmin\Current.gpx" -NewName "$($UTCTime).gpx"
Write-Host "...done."


# Import GPX with Python script.
python C:\Users\paulb\version_controlled\gps-log-tools\update_kml.py ".\raw\garmin\$($UTCTime).gpx"


# pause # Not needed, since Python script already pauses.