# Automates importing a GPX file from a Garmin GPS. Backs up Driving.kml,
# copies the GPX track log from the Garmin to a GPX archive folder (named with
# a UTC timestamp) and imports the GPX tracks into Driving.kml using a Python
# script.

Set-Location -Path C:\Users\paulb\OneDrive\Projects\Maps\GPS\Auto
$Time = Get-Date
$UTCTime = $Time.ToUniversalTime().ToString("yyyyMMddTHHmmZ")

# Back up Driving.kml.
# Not needed, as update_kml.py handles the backup.
# Write-Host "Backing up driving_canonical.kml ..."
# Copy-Item ".\driving_canonical.kml" -Destination ".\.backup\driving_canonical.backup.kml"
# Write-Host "...done."


# Copy current.gpx to backup.
# Copy from MTP device concept derived from:
# https://plusontech.com/2019/01/05/weekend-powershell-script-copy-files-from-phone-camera-by-month/

Write-Host "Copying Current.gpx from Garmin to GPX Archive ..."

# $SourcePath = "DriveSmart 50\Internal Storage\GPX\Current.gpx"
# $SourcePath = "Garmin DriveSmart 55\Internal Storage\GPX\Current.gpx"
$SourcePath = "Garmin DriveSmart 66\Internal Storage\GPX\Current.gpx"
$SourcePathArray = $SourcePath -split "\\"

$Shell = New-Object -ComObject Shell.Application
$CurrentGPX = $Shell.NameSpace(17).Self
foreach($item in $SourcePathArray){
  $CurrentGPX = $CurrentGPX.GetFolder.Items() | Where-Object{$_.Name -eq $item}
}

$TargetFolderShell = $Shell.NameSpace("C:\Users\paulb\OneDrive\Projects\Maps\GPS\Auto\raw\garmin").self
$TargetFolderShell.GetFolder.CopyHere($CurrentGPX)

Rename-Item -Path ".\raw\garmin\Current.gpx" -NewName "$($UTCTime).gpx"
Write-Host "...done."


# Import GPX with Python script.
python C:\Users\paulb\version_controlled\gps-log-tools\update_kml.py ".\raw\garmin\$($UTCTime).gpx"


# pause # Not needed, since Python script already pauses.
