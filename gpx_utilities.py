def gpx_profile(creator):
    """Determines which config profile to use for a GPX file."""
    if "Bad Elf" in creator:
        profile = 'bad_elf'
    elif "DriveSmart" in creator:
        profile = 'garmin'
    elif "myTracks" in creator:
        profile = 'mytracks'
    else:
        profile = '_default'
    return profile