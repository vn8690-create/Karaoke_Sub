import logging


def extract_info_for_online_media(input_url, input_artist, input_title, logger, cookies_str=None):
    """
    Creates metadata info dict from provided artist and title.
    
    Note: This function no longer supports URL-based metadata extraction.
    Audio search and download is now handled by the AudioFetcher class using flacfetch.
    
    When both artist and title are provided, this creates a metadata dict that can be
    used by the rest of the pipeline.
    
    Args:
        input_url: Deprecated - URLs should be provided as local file paths or use AudioFetcher
        input_artist: The artist name
        input_title: The track title
        logger: Logger instance
        cookies_str: Deprecated - no longer used
        
    Returns:
        A dict with metadata if artist and title are provided
        
    Raises:
        ValueError: If URL is provided (deprecated) or if artist/title are missing
    """
    logger.info(f"Extracting info for input_url: {input_url} input_artist: {input_artist} input_title: {input_title}")
    
    # URLs are no longer supported - use AudioFetcher for search and download
    if input_url is not None:
        raise ValueError(
            "URL-based audio fetching has been replaced with flacfetch. "
            "Please provide a local file path instead, or use artist and title only "
            "to search for audio via flacfetch."
        )
    
    # When artist and title are provided, create a synthetic metadata dict
    # The actual search and download is handled by AudioFetcher
    if input_artist and input_title:
        logger.info(f"Creating metadata for: {input_artist} - {input_title}")
        return {
            "title": f"{input_artist} - {input_title}",
            "artist": input_artist,
            "track_title": input_title,
            "extractor_key": "flacfetch",
            "id": f"flacfetch_{input_artist}_{input_title}".replace(" ", "_"),
            "url": None,  # URL will be determined by flacfetch during download
            "source": "flacfetch",
        }
    
    # No valid input provided
    raise ValueError(
        f"Artist and title are required for audio search. "
        f"Received artist: {input_artist}, title: {input_title}"
    )


def parse_track_metadata(extracted_info, current_artist, current_title, persistent_artist, logger):
    """
    Parses extracted_info to determine URL, extractor, ID, artist, and title.
    Returns a dictionary with the parsed values.
    
    This function now supports both legacy yt-dlp style metadata and 
    the new flacfetch-based metadata format.
    """
    parsed_data = {
        "url": None,
        "extractor": None,
        "media_id": None,
        "artist": current_artist,
        "title": current_title,
    }

    metadata_artist = ""
    metadata_title = ""

    # Handle flacfetch-style metadata (no URL required)
    if extracted_info.get("source") == "flacfetch":
        parsed_data["url"] = None  # URL determined at download time
        parsed_data["extractor"] = "flacfetch"
        parsed_data["media_id"] = extracted_info.get("id")
        
        # Use the provided artist/title directly
        if extracted_info.get("artist"):
            parsed_data["artist"] = extracted_info["artist"]
        if extracted_info.get("track_title"):
            parsed_data["title"] = extracted_info["track_title"]
            
        if persistent_artist:
            parsed_data["artist"] = persistent_artist
            
        logger.info(f"Using flacfetch metadata: artist: {parsed_data['artist']}, title: {parsed_data['title']}")
        return parsed_data

    # Legacy yt-dlp style metadata handling (for backward compatibility)
    if "url" in extracted_info:
        parsed_data["url"] = extracted_info["url"]
    elif "webpage_url" in extracted_info:
        parsed_data["url"] = extracted_info["webpage_url"]
    else:
        # For flacfetch results without URL, this is now acceptable
        logger.debug("No URL in extracted info - will be determined at download time")
        parsed_data["url"] = None

    if "extractor_key" in extracted_info:
        parsed_data["extractor"] = extracted_info["extractor_key"]
    elif "ie_key" in extracted_info:
        parsed_data["extractor"] = extracted_info["ie_key"]
    elif extracted_info.get("source") == "flacfetch":
        parsed_data["extractor"] = "flacfetch"
    else:
        # Default to flacfetch if no extractor specified
        parsed_data["extractor"] = "flacfetch"

    if "id" in extracted_info:
        parsed_data["media_id"] = extracted_info["id"]

    # Example: "Artist - Title"
    if "title" in extracted_info and "-" in extracted_info["title"]:
        try:
            metadata_artist, metadata_title = extracted_info["title"].split("-", 1)
            metadata_artist = metadata_artist.strip()
            metadata_title = metadata_title.strip()
        except ValueError:
             logger.warning(f"Could not split title '{extracted_info['title']}' on '-', using full title.")
             metadata_title = extracted_info["title"].strip()
             if "uploader" in extracted_info:
                 metadata_artist = extracted_info["uploader"]

    elif "uploader" in extracted_info:
        # Fallback to uploader as artist if title parsing fails
        metadata_artist = extracted_info["uploader"]
        if "title" in extracted_info:
            metadata_title = extracted_info["title"].strip()

    # If unable to parse, log an appropriate message
    if not metadata_artist or not metadata_title:
        logger.warning("Could not parse artist and title from the input media metadata.")

    if not parsed_data["artist"] and metadata_artist:
        logger.warning(f"Artist not provided as input, setting to {metadata_artist} from input media metadata...")
        parsed_data["artist"] = metadata_artist

    if not parsed_data["title"] and metadata_title:
        logger.warning(f"Title not provided as input, setting to {metadata_title} from input media metadata...")
        parsed_data["title"] = metadata_title

    if persistent_artist:
        logger.debug(
            f"Resetting artist from {parsed_data['artist']} to persistent artist: {persistent_artist} for consistency while processing playlist..."
        )
        parsed_data["artist"] = persistent_artist

    if parsed_data["artist"] and parsed_data["title"]:
        logger.info(f"Parsed metadata - artist: {parsed_data['artist']}, title: {parsed_data['title']}")
    else:
        logger.debug(extracted_info)
        raise Exception("Failed to extract artist and title from the input media metadata.")

    return parsed_data
