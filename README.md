# GPS Log Tools

This repository contains a collection of scripts used for maintaining my [GPS driving logs](https://paulbogard.net/driving-logs/).

## Import Scripts

### update_kml.py

This script is the heart of my GPS processing; it maintains my [canonical driving KML file](https://paulbogard.net/blog/20210209-how-i-store-my-driving-logs-2021/), imports GPX files into it (by providing one or more GPX files as arguments), and exports a processed KMZ file.

The import function ensures duplicate tracks are not imported (tracks are uniquely identified by the UTC timestamp of their first waypoint). As tracks may have been edited in the canonical KML file after import (see below), in the case of a matching timestamp, the existing track in the canonical KML file is kept and the matching GPX track is ignored.

The import function also does some processing on the GPX data due to the idiosyncrasies of the device that generated the GPS track. Which processing is performed on each device’s tracks is defined in `config.yaml`.

Since I’m maintaining several decades of driving data, I want my KML files to be more optimized for size than Google Earth typically saves them as. In particular:

- Google Earth by default maintains the a separate style for each [Placemark](https://developers.google.com/kml/documentation/kmlreference#placemark), even if the styles are identical. Since all of my Placemarks are tracks with the same line width and color, this script generates KML/KMZ files with the style defined once, and every Placemark using it.
- By default, most GPS logging data includes latitude, longitude, and altitude. However, for my driving log, altitudes are irrelevant (all of my tracks have [`altitudeMode`](https://developers.google.com/kml/documentation/altitudemode) set as `clampToGround`). This script strips all altitude values, saving a significant amount of space over millions of waypoints.

Sometimes, it’s necessary to manually edit waypoints in the canonical file (for example, noisy data that it was not possible to remove with automated processing upon import). Likewise, it’s sometimes necessary to [merge two consecutive tracks together](https://paulbogard.net/blog/20211221-fixing-driving-log-inter-track-gaps/) (which can be done by grouping tracks that need to be merged into KML sub-folders). Once that editing has been done in the canonical KML file, this script can be run without (or with) import arguments to apply the above optimizations to the newly-edited tracks.

### import_bad_elf_gpx.py

When downloading tracks from my Bad Elf GPS Pro+ datalogger, I end up with either individual GPX files or a zipfile of GPX files. This script:

- looks at a designated import folder for any zipfiles matching Bad Elf's naming conventions, extracts the GPX files, and deletes the zipfiles,
- imports all GPX files in the import folder using `update_kml.py`, and
- moves all the GPX files to an archival folder, renaming them to a particular UTC timestamp format as necessary (using `rename_bad_elf_gpx.py`).

### Import from Garmin.ps1

Garmin automotive devices store all driving tracks in a single `current.gpx` file; the oldest tracks are removed as new tracks are recorded to maintain a roughly constant file size. This PowerShell script is designed to import this file on Windows, by:

- copies the `current.gpx` to an archive folder, renaming it with the UTC timestamp of the time the script is run, and
- imports the archived GPX file using `update_kml.py`.

### MacOS Download Garmin GPX.scpt

I’ve had difficulty mounting Garmin devices as directories under recent versions of MacOS. Instead, to get the Garmin’s `current.gpx` file, this AppleScript runs a backup using the Garmin Express application, then opens the backup folder (which contains `current.gpx`) in Finder. From there, `current.gpx` can be imported using `update_kml.py`.

## Utility Scripts

### rename_bad_elf_gpx.py

Bad Elf GPX files are named as a timestamp, but the timestamp string filename format is slightly different depending on whether the GPX files were downloaded directly from the device over USB, or downloaded using the Bad Elf smartphone app over Bluetooth. This script renames the GPX files to a consistent timestamp format. 

### simplify_gpx.py

GPX tracks are often recorded at a given frequency (e.g. one waypoint per second). However, a lot of these points are unnecessary: while curvy parts of the track need a lot of points for smooth curves, straight parts of the track can have a lot of intermediate points removed without changing the shape of the track. This script runs the [Ramer–Douglas–Peucker algorithm](https://en.wikipedia.org/wiki/Ramer%E2%80%93Douglas%E2%80%93Peucker_algorithm) on the tracks of a GPX file to remove unneeded points, resulting in smaller data files.

<img src="img/simplify.animated.png" width="800">

### split_kmz.py

For a number of years, I kept all my driving data in a separate KMZ file for each trip I took, plus an annual KMZ file for local driving. When I converted the original GPX files into KMZ, I had also merged GPX [tracks](https://www.topografix.com/GPX/1/1/#type_trkType) with multiple [track segments](https://www.topografix.com/GPX/1/1/#type_trksegType) into a single KML [Placemark](https://developers.google.com/kml/documentation/kmlreference#placemark). Unfortunately, I only kept a single timestamp for the whole merged Placemark, and the timestamp was in the track's local timezone, rather than UTC.

This script helps me split these old merged KML Placemarks back into GPX tracks. It allows me to specify a timezone so that the timestamp can be converted to UTC, and it helps me generate reasonable unique timestamps for tracks which I don’t still have timestamp data for.

### trim_gpx.py

The GPS devices I use the most often are plugged into a car for power; when the car starts, the GPS devices turn on and start recording. When a GPS device is turned on, it may take a small amount of time to lock onto satellites and build up its confidence in its position. Thus, the initial points of the track may jump around a lot, resulting in the start of many tracks looking somewhat like a scribble. Also, the car is often not moving immediately after starting, so a lot of these noisy points may not be needed since the car is sitting still.

For GPX files which have a speed associated with each trackpoint, this script looks through each track for the first time a rolling median of speeds exceeds a certain threshold, and removes the points before that.

<img src="img/trim.animated.png" width="800">

Note that when using this script during an import, it’s important to record the first trackpoint’s timestamp before running this script, as the first trackpoint could be removed.