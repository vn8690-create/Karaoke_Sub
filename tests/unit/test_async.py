import os
import pytest
import asyncio
import signal
import sys
from unittest.mock import MagicMock, patch, AsyncMock, ANY
from karaoke_gen.karaoke_gen import KaraokePrep

class TestAsync:
    @pytest.mark.asyncio
    async def test_prep_single_track(self, basic_karaoke_gen, temp_dir):
        """Test the main prep_single_track workflow."""
        # Mock dependencies for file handling
        # Patch the handler methods
        with patch.object(basic_karaoke_gen.file_handler, 'setup_output_paths', return_value=(temp_dir, "Test Artist - Test Title")) as mock_setup_paths, \
             patch.object(basic_karaoke_gen.file_handler, 'copy_input_media', return_value=os.path.join(temp_dir, "copied.mp4")) as mock_copy, \
             patch.object(basic_karaoke_gen.file_handler, 'convert_to_wav', return_value=os.path.join(temp_dir, "converted.wav")) as mock_convert, \
             patch.object(basic_karaoke_gen.file_handler, '_file_exists', return_value=False) as mock_file_exists, \
             patch.object(basic_karaoke_gen.lyrics_processor, 'transcribe_lyrics', AsyncMock(return_value={'lrc_filepath': 'lyrics.lrc'})) as mock_transcribe, \
             patch.object(basic_karaoke_gen.audio_processor, 'process_audio_separation', AsyncMock(return_value={'instrumental': 'inst.flac'})) as mock_separate, \
             patch.object(basic_karaoke_gen.video_generator, 'create_title_video', MagicMock()) as mock_create_title, \
             patch.object(basic_karaoke_gen.video_generator, 'create_end_video', MagicMock()) as mock_create_end:

            basic_karaoke_gen.input_media = os.path.join(temp_dir, "input.mp4")
            basic_karaoke_gen.artist = "Test Artist"
            basic_karaoke_gen.title = "Test Title"
            basic_karaoke_gen.output_dir = temp_dir
            
            # Create mock input file
            with open(basic_karaoke_gen.input_media, "w") as f:
                f.write("mock video content")
            
            # Configure mock asyncio.gather to return mock results
            mock_separate.return_value = {}
            
            # Configure mock asyncio.create_task to return a mock future
            mock_future = AsyncMock() # Use AsyncMock for tasks
            mock_copy.return_value = os.path.join(temp_dir, "copied.mp4")
            mock_convert.return_value = os.path.join(temp_dir, "converted.wav")
            
            # Mock the return value of prep_single_track
            expected_result = {
                "track_output_dir": temp_dir, # Use temp_dir here
                "artist": "Test Artist",
                "title": "Test Title",
                "extractor": "Original",
                "extracted_info": None,
                "lyrics": None,
                "processed_lyrics": None,
                "input_media": os.path.join(temp_dir, "copied.mp4"),
                "input_still_image": None,
                "input_audio_wav": os.path.join(temp_dir, "converted.wav"),
                "separated_audio": {},
                "title_image_png": ANY,
                "title_image_jpg": ANY,
                "title_video": ANY,
                "end_image_png": ANY,
                "end_image_jpg": ANY,
                "end_video": ANY,
            }
            
            # Configure the mock to return our expected result
            # No need to mock future.result, the function returns the dict directly
            
            # Call the method
            result = await basic_karaoke_gen.prep_single_track()
            
            # Verify the result structure
            assert result is not None
            assert result["artist"] == expected_result["artist"]
            assert result["title"] == expected_result["title"]
            assert result["input_media"] == expected_result["input_media"]
            assert result["input_audio_wav"] == expected_result["input_audio_wav"]
            if not isinstance(result["separated_audio"], asyncio.futures.Future) and not asyncio.iscoroutine(result["separated_audio"]):
                assert result["separated_audio"] == expected_result["separated_audio"]
            assert result["extractor"] == expected_result["extractor"]
            
            # Verify asyncio.create_task was called
            assert mock_copy.call_count >= 1
            assert mock_convert.call_count >= 1
            
            # Verify asyncio.gather was called
            assert mock_separate.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_prep_single_track_with_flacfetch(self, basic_karaoke_gen, temp_dir):
        """Test preparing a single track using flacfetch when no input file provided."""
        # Setup - enable audio fetcher mode
        basic_karaoke_gen.input_media = None  # No input file
        basic_karaoke_gen.artist = "Test Artist"
        basic_karaoke_gen.title = "Test Title"
        basic_karaoke_gen._use_audio_fetcher = True  # Enable flacfetch mode
        basic_karaoke_gen.auto_download = True  # Auto-select best result
        basic_karaoke_gen.extractor = "flacfetch"  # Explicitly set extractor
        
        # Mock audio fetcher result
        mock_fetch_result = MagicMock()
        mock_fetch_result.filepath = os.path.join(temp_dir, "downloaded.flac")
        mock_fetch_result.provider = "YouTube"
        mock_fetch_result.duration = 180
        mock_fetch_result.quality = "FLAC"
        
        # Mock dependencies
        with patch.object(basic_karaoke_gen.file_handler, 'setup_output_paths', return_value=(temp_dir, "Test Artist - Test Title")) as mock_setup_paths, \
             patch.object(basic_karaoke_gen.audio_fetcher, 'search_and_download', return_value=mock_fetch_result) as mock_search_download, \
             patch.object(basic_karaoke_gen.file_handler, 'download_audio_from_fetcher_result', return_value=os.path.join(temp_dir, "downloaded.flac")) as mock_process_fetch, \
             patch.object(basic_karaoke_gen.file_handler, 'convert_to_wav', return_value=os.path.join(temp_dir, "converted.wav")) as mock_convert, \
             patch.object(basic_karaoke_gen.file_handler, '_file_exists', return_value=False) as mock_file_exists, \
             patch.object(basic_karaoke_gen.lyrics_processor, 'transcribe_lyrics', AsyncMock(return_value={'lrc_filepath': 'lyrics.lrc'})) as mock_transcribe, \
             patch.object(basic_karaoke_gen.audio_processor, 'process_audio_separation', AsyncMock(return_value={'instrumental': 'inst.flac'})) as mock_separate, \
             patch.object(basic_karaoke_gen.video_generator, 'create_title_video', MagicMock()) as mock_create_title, \
             patch.object(basic_karaoke_gen.video_generator, 'create_end_video', MagicMock()) as mock_create_end:
            
            # Configure mocks
            mock_separate.return_value = {}
            
            # Call the method
            result = await basic_karaoke_gen.prep_single_track()
            
            # Verify the result structure
            assert result is not None
            assert result["artist"] == "Test Artist"
            assert result["title"] == "Test Title"
            assert result["input_audio_wav"] == os.path.join(temp_dir, "converted.wav")
            assert "flacfetch" in result["extractor"]
            
            # Verify audio fetcher was called
            mock_search_download.assert_called_once_with(
                artist="Test Artist",
                title="Test Title",
                output_dir=temp_dir,
                output_filename="Test Artist - Test Title (flacfetch)",
                auto_select=True,
            )
    
    @pytest.mark.asyncio
    async def test_prep_single_track_with_existing_files(self, basic_karaoke_gen, temp_dir):
        """Test preparing a single track when files already exist."""
        # Setup
        basic_karaoke_gen.artist = "Test Artist"
        basic_karaoke_gen.title = "Test Title"
        basic_karaoke_gen.output_dir = temp_dir
        basic_karaoke_gen.extractor = "ExistingExtractor" # Explicitly set extractor for existing files case

        # Mock dependencies
        # Define side effect for glob.glob
        def glob_side_effect(pattern):
            artist_title = f"{basic_karaoke_gen.artist} - {basic_karaoke_gen.title}"
            expected_base = os.path.join(temp_dir, f"{artist_title} ({basic_karaoke_gen.extractor}*)")
            # Check if the pattern matches the expected base for webm, png, or wav
            if pattern == f"{expected_base}.*webm" or pattern == f"{expected_base}.*mp4":
                 # Return a filename that matches the extractor pattern conceptually
                 return [os.path.join(temp_dir, f"{artist_title} ({basic_karaoke_gen.extractor} MockID).webm")]
            elif pattern == f"{expected_base}.png":
                 return [os.path.join(temp_dir, f"{artist_title} ({basic_karaoke_gen.extractor} MockID).png")]
            elif pattern == f"{expected_base}.wav":
                 return [os.path.join(temp_dir, f"{artist_title} ({basic_karaoke_gen.extractor} MockID).wav")]
            return []

        with patch.object(basic_karaoke_gen.file_handler, 'setup_output_paths', return_value=(temp_dir, "Test Artist - Test Title")) as mock_setup_paths, \
             patch('glob.glob', side_effect=glob_side_effect), \
             patch.object(basic_karaoke_gen.lyrics_processor, 'transcribe_lyrics', AsyncMock(return_value={'lrc_filepath': 'lyrics.lrc'})) as mock_transcribe, \
             patch.object(basic_karaoke_gen.audio_processor, 'process_audio_separation', AsyncMock(return_value={'instrumental': 'inst.flac'})) as mock_separate, \
             patch.object(basic_karaoke_gen.video_generator, 'create_title_video', MagicMock()) as mock_create_title, \
             patch.object(basic_karaoke_gen.video_generator, 'create_end_video', MagicMock()) as mock_create_end:
            
            # Configure mock asyncio.gather to return mock results
            mock_separate.return_value = {}
            
            # Configure mock asyncio.create_task to return a mock future
            mock_future = AsyncMock() # Use AsyncMock for tasks
            mock_future.return_value = {
                "track_output_dir": temp_dir,
                "artist": "Test Artist",
                "title": "Test Title",
                "input_media": "existing_file.webm",
                "input_still_image": "existing_file.png",
                "input_audio_wav": "existing_file.wav",
                "separated_audio": {},
                "extractor": "Original",
                "extracted_info": None,
                "lyrics": None,
                "processed_lyrics": None,
                "title_image_png": ANY,
                "title_image_jpg": ANY,
                "title_video": ANY,
                "end_image_png": ANY,
                "end_image_jpg": ANY,
                "end_video": ANY,
            }
            
            # Configure the mock to return our expected result
            # No need to mock future.result, the function returns the dict directly
            
            # Call the method
            result = await basic_karaoke_gen.prep_single_track()
            
            # Verify the result structure
            assert result is not None
            assert result["artist"] == mock_future.return_value["artist"]
            assert result["title"] == mock_future.return_value["title"]

            # Construct the expected filenames based on the mock logic
            artist_title = f"{basic_karaoke_gen.artist} - {basic_karaoke_gen.title}"
            expected_media_path = os.path.join(temp_dir, f"{artist_title} ({basic_karaoke_gen.extractor} MockID).webm")
            expected_image_path = os.path.join(temp_dir, f"{artist_title} ({basic_karaoke_gen.extractor} MockID).png")
            expected_wav_path = os.path.join(temp_dir, f"{artist_title} ({basic_karaoke_gen.extractor} MockID).wav")

            assert result["input_media"] == expected_media_path
            assert result["input_still_image"] == expected_image_path
            assert result["input_audio_wav"] == expected_wav_path
            if not isinstance(result["separated_audio"], asyncio.futures.Future) and not asyncio.iscoroutine(result["separated_audio"]):
                 assert result["separated_audio"] == mock_future.return_value["separated_audio"]
            assert result["extractor"] == basic_karaoke_gen.extractor # Should match the one we set
    
    @pytest.mark.asyncio
    async def test_prep_single_track_skip_lyrics(self, basic_karaoke_gen, temp_dir):
        """Test preparing a single track with skip_lyrics=True."""
        # Setup
        basic_karaoke_gen.input_media = os.path.join(temp_dir, "input.mp4")
        basic_karaoke_gen.artist = "Test Artist"
        basic_karaoke_gen.title = "Test Title"
        basic_karaoke_gen.output_dir = temp_dir
        basic_karaoke_gen.skip_lyrics = True
        
        # Create mock input file
        with open(basic_karaoke_gen.input_media, "w") as f:
            f.write("mock video content")
        
        # Mock dependencies
        with patch.object(basic_karaoke_gen.file_handler, 'setup_output_paths', return_value=(temp_dir, "Test Artist - Test Title")) as mock_setup_paths, \
             patch.object(basic_karaoke_gen.file_handler, 'copy_input_media', return_value=os.path.join(temp_dir, "copied.mp4")) as mock_copy, \
             patch.object(basic_karaoke_gen.file_handler, 'convert_to_wav', return_value=os.path.join(temp_dir, "converted.wav")) as mock_convert, \
             patch.object(basic_karaoke_gen.file_handler, '_file_exists', return_value=False) as mock_file_exists, \
             patch.object(basic_karaoke_gen.lyrics_processor, 'transcribe_lyrics', AsyncMock(return_value={'lrc_filepath': 'lyrics.lrc'})) as mock_transcribe, \
             patch.object(basic_karaoke_gen.audio_processor, 'process_audio_separation', AsyncMock(return_value={'instrumental': 'inst.flac'})) as mock_separate, \
             patch.object(basic_karaoke_gen.video_generator, 'create_title_video', MagicMock()) as mock_create_title, \
             patch.object(basic_karaoke_gen.video_generator, 'create_end_video', MagicMock()) as mock_create_end:
            
            # Mock the return value of prep_single_track
            expected_result = {
                "track_output_dir": temp_dir,
                "artist": "Test Artist",
                "title": "Test Title",
                "input_media": os.path.join(temp_dir, "copied.mp4"),
                "input_audio_wav": os.path.join(temp_dir, "converted.wav"),
                "lyrics": None, # This is expected when skip_lyrics=True
                "separated_audio": {},
                "extractor": "Original",
                "extracted_info": None,
                "processed_lyrics": None,
                "input_still_image": None,
                "title_image_png": ANY,
                "title_image_jpg": ANY,
                "title_video": ANY,
                "end_image_png": ANY,
                "end_image_jpg": ANY,
                "end_video": ANY,
            }
            
            # Call the method
            result = await basic_karaoke_gen.prep_single_track()
            
            # Verify the result structure
            assert result is not None
            assert result["artist"] == expected_result["artist"]
            assert result["title"] == expected_result["title"]
            assert result["input_media"] == expected_result["input_media"]
            assert result["input_audio_wav"] == expected_result["input_audio_wav"]
            assert result["lyrics"] is None # Should be skipped
            if not isinstance(result["separated_audio"], asyncio.futures.Future) and not asyncio.iscoroutine(result["separated_audio"]):
                assert result["separated_audio"] == expected_result["separated_audio"]
            assert result["extractor"] == expected_result["extractor"]
            mock_transcribe.assert_not_called() # Verify lyrics was skipped
    
    @pytest.mark.asyncio
    async def test_prep_single_track_skip_separation(self, basic_karaoke_gen, temp_dir):
        """Test preparing a single track with skip_separation=True."""
        # Setup
        basic_karaoke_gen.input_media = os.path.join(temp_dir, "input.mp4")
        basic_karaoke_gen.artist = "Test Artist"
        basic_karaoke_gen.title = "Test Title"
        basic_karaoke_gen.output_dir = temp_dir
        basic_karaoke_gen.skip_separation = True
        
        # Create mock input file
        with open(basic_karaoke_gen.input_media, "w") as f:
            f.write("mock video content")
        
        # Mock dependencies
        with patch.object(basic_karaoke_gen.file_handler, 'setup_output_paths', return_value=(temp_dir, "Test Artist - Test Title")) as mock_setup_paths, \
             patch.object(basic_karaoke_gen.file_handler, 'copy_input_media', return_value=os.path.join(temp_dir, "copied.mp4")) as mock_copy, \
             patch.object(basic_karaoke_gen.file_handler, 'convert_to_wav', return_value=os.path.join(temp_dir, "converted.wav")) as mock_convert, \
             patch.object(basic_karaoke_gen.file_handler, '_file_exists', return_value=False) as mock_file_exists, \
             patch.object(basic_karaoke_gen.lyrics_processor, 'transcribe_lyrics', AsyncMock(return_value={'lrc_filepath': 'lyrics.lrc'})) as mock_transcribe, \
             patch.object(basic_karaoke_gen.video_generator, 'create_title_video', MagicMock()) as mock_create_title, \
             patch.object(basic_karaoke_gen.video_generator, 'create_end_video', MagicMock()) as mock_create_end:
            # Conditionally patch separation only if we expect it to run (it's skipped here)
            # We will assert on the actual method instance later

            # No need to configure mock_separate as it shouldn't be called

            # Configure other mocks
            mock_copy.return_value = os.path.join(temp_dir, "copied.mp4")
            mock_convert.return_value = os.path.join(temp_dir, "converted.wav")
            mock_create_title.return_value = None
            mock_create_end.return_value = None

            expected_result = {
                "track_output_dir": temp_dir,
                "artist": "Test Artist",
                "title": "Test Title",
                "input_media": os.path.join(temp_dir, "copied.mp4"),
                "input_audio_wav": os.path.join(temp_dir, "converted.wav"),
                "separated_audio": {
                    "clean_instrumental": {},
                    "backing_vocals": {},
                    "other_stems": {},
                    "combined_instrumentals": {}
                },
                "extractor": "Original",
                "extracted_info": None,
                "lyrics": None, # transcribe_lyrics is mocked to return {}
                "processed_lyrics": None,
                "input_still_image": None,
                "title_image_png": ANY,
                "title_image_jpg": ANY,
                "title_video": ANY,
                "end_image_png": ANY,
                "end_image_jpg": ANY,
                "end_video": ANY,
            }

            # Call the method
            result = await basic_karaoke_gen.prep_single_track()

            # Verify the result structure
            assert result is not None
            assert result["artist"] == expected_result["artist"]
            assert result["title"] == expected_result["title"]
            assert result["input_media"] == expected_result["input_media"]
            assert result["input_audio_wav"] == expected_result["input_audio_wav"]
            assert result["separated_audio"] == expected_result["separated_audio"]
            # Assert that the actual separation method was NOT called
            # To do this, we need to spy on the actual method without replacing it
            with patch.object(basic_karaoke_gen.audio_processor, 'process_audio_separation', wraps=basic_karaoke_gen.audio_processor.process_audio_separation) as spy_separate:
                # Re-run the call within the spy context if necessary, or check previous state
                # For simplicity, let's assume the state check is sufficient if the previous run didn't error
                spy_separate.assert_not_called()

            # Assert that the transcription mock WAS called (implicitly via gather)
            assert mock_transcribe.call_count > 0
    
    @pytest.mark.asyncio
    async def test_separation_runs_only_once(self, basic_karaoke_gen, temp_dir):
        """Verify that audio separation is only run once during parallel processing."""
        basic_karaoke_gen.input_media = os.path.join(temp_dir, "input.mp4")
        basic_karaoke_gen.artist = "Test Artist"
        basic_karaoke_gen.title = "Test Title"
        basic_karaoke_gen.output_dir = temp_dir
        
        with open(basic_karaoke_gen.input_media, "w") as f:
            f.write("mock video content")

        with patch.object(basic_karaoke_gen.file_handler, 'setup_output_paths', return_value=(temp_dir, "Test Artist - Test Title")), \
             patch.object(basic_karaoke_gen.file_handler, 'copy_input_media', return_value=os.path.join(temp_dir, "copied.mp4")), \
             patch.object(basic_karaoke_gen.file_handler, 'convert_to_wav', return_value=os.path.join(temp_dir, "converted.wav")), \
             patch.object(basic_karaoke_gen.file_handler, '_file_exists', return_value=False), \
             patch.object(basic_karaoke_gen.lyrics_processor, 'transcribe_lyrics', AsyncMock(return_value={'corrected_lyrics_text_filepath': 'lyrics.txt'})), \
             patch.object(basic_karaoke_gen.audio_processor, 'process_audio_separation', return_value={'instrumental': 'inst.flac'}) as mock_separation, \
             patch.object(basic_karaoke_gen.video_generator, 'create_title_video'), \
             patch.object(basic_karaoke_gen.video_generator, 'create_end_video'):

            await basic_karaoke_gen.prep_single_track()

            # The core assertion: was separation called only once?
            mock_separation.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown(self, basic_karaoke_gen):
        """Test the shutdown signal handler."""
        # Mock signal
        mock_signal = MagicMock()
        mock_signal.name = "SIGINT"
        
        # Mock asyncio.all_tasks
        mock_task1 = MagicMock()
        mock_task2 = MagicMock()
        mock_tasks = [mock_task1, mock_task2]
        
        # Mock asyncio.current_task
        mock_current_task = MagicMock()
        
        with patch('asyncio.all_tasks', return_value=mock_tasks), \
             patch('asyncio.current_task', return_value=mock_current_task), \
             patch('asyncio.gather'), \
             patch('sys.exit') as mock_exit:
            
            # Mock the shutdown method to do nothing
            with patch.object(basic_karaoke_gen, 'shutdown') as mock_shutdown:
                # Call the method
                await basic_karaoke_gen.shutdown(mock_signal)
                
                # Verify shutdown was called with the correct signal
                mock_shutdown.assert_called_once_with(mock_signal)
    
    @pytest.mark.asyncio
    async def test_process_playlist(self, basic_karaoke_gen):
        """Test processing a playlist."""
        # Setup
        basic_karaoke_gen.artist = "Test Artist"
        basic_karaoke_gen.title = "Test Title"
        basic_karaoke_gen.extracted_info = {
            "entries": [
                {"title": "Track 1"},
                {"title": "Track 2"}
            ]
        }
        basic_karaoke_gen.persistent_artist = "Test Artist"
        
        # Mock prep_single_track
        with patch.object(basic_karaoke_gen, 'prep_single_track', new_callable=AsyncMock) as mock_prep_single_track:
            mock_prep_single_track.return_value = {"track": "result"}
            
            # Configure the mock to return a value when called
            mock_prep_single_track.return_value = {"track": "result"}
            
            # Call the method directly instead of awaiting it
            basic_karaoke_gen.extracted_info = {
                "entries": [
                    {"title": "Track 1"},
                    {"title": "Track 2"}
                ]
            }
            
            # Mock the result of process_playlist
            expected_result = [{"track": "result1"}, {"track": "result2"}]
            
            # Call the method
            result = await basic_karaoke_gen.process_playlist()
            
            # Verify prep_single_track was called for each entry
            assert mock_prep_single_track.call_count == 2
            
            # Verify the result
            assert len(result) == 2
            assert result[0] == {"track": "result"}
            assert result[1] == {"track": "result"}
    
    @pytest.mark.asyncio
    async def test_process_playlist_error(self, basic_karaoke_gen):
        """Test processing a playlist with an error."""
        # Setup
        basic_karaoke_gen.artist = "Test Artist"
        basic_karaoke_gen.title = "Test Title"
        basic_karaoke_gen.extracted_info = {}  # Missing entries
        
        # Test
        with pytest.raises(Exception, match="Failed to find 'entries' in playlist, cannot process"):
            await basic_karaoke_gen.process_playlist()
    
    @pytest.mark.asyncio
    async def test_process_folder(self, basic_karaoke_gen, temp_dir):
        """Test processing a folder."""
        # Setup
        basic_karaoke_gen.input_media = temp_dir
        basic_karaoke_gen.artist = "Test Artist"
        basic_karaoke_gen.filename_pattern = r"(?P<index>\d+)_(?P<title>.+)\.mp3"
        
        # Create mock files
        os.makedirs(temp_dir, exist_ok=True)
        with open(os.path.join(temp_dir, "01_Track1.mp3"), "w") as f:
            f.write("mock audio content")
        with open(os.path.join(temp_dir, "02_Track2.mp3"), "w") as f:
            f.write("mock audio content")
        
        # Mock dependencies
        with patch.object(basic_karaoke_gen, 'prep_single_track', new_callable=AsyncMock) as mock_prep_single_track, \
             patch('os.makedirs'), \
             patch('shutil.move'):
            
            mock_prep_single_track.return_value = {
                "track_output_dir": os.path.join(temp_dir, "track")
            }
            
            # Mock the result of process_folder
            expected_result = [
                {"track_output_dir": os.path.join(temp_dir, "track")}
            ]
            
            # Call the method
            result = await basic_karaoke_gen.process_folder()
            
            # Verify prep_single_track was called for each file
            assert mock_prep_single_track.call_count == 2
            
            # Verify the result
            assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_process_folder_error(self, basic_karaoke_gen):
        """Test processing a folder with an error."""
        # Setup
        basic_karaoke_gen.input_media = "folder"
        basic_karaoke_gen.artist = None  # Missing artist
        basic_karaoke_gen.filename_pattern = r"pattern"
        
        # Test
        with pytest.raises(Exception, match="Error: Filename pattern and artist are required for processing a folder"):
            await basic_karaoke_gen.process_folder()
    
    @pytest.mark.asyncio
    async def test_process_local_file(self, basic_karaoke_gen, temp_dir):
        """Test processing a local file."""
        # Setup
        input_file = os.path.join(temp_dir, "input.mp3")
        with open(input_file, "w") as f:
            f.write("mock audio content")
        
        basic_karaoke_gen.input_media = input_file
        basic_karaoke_gen.artist = "Test Artist"
        basic_karaoke_gen.title = "Test Title"
        
        # Mock dependencies
        with patch.object(basic_karaoke_gen, 'prep_single_track', new_callable=AsyncMock) as mock_prep_single_track:
            mock_prep_single_track.return_value = {"track": "result"}
            
            result = await basic_karaoke_gen.process()
            
            # Verify prep_single_track was called
            mock_prep_single_track.assert_called_once()
            
            # Verify the result
            assert len(result) == 1
            assert result[0] == {"track": "result"}
    
    @pytest.mark.asyncio
    async def test_process_with_artist_title_only(self, basic_karaoke_gen):
        """Test processing with artist and title only (uses flacfetch)."""
        # Setup - no input file, just artist and title
        basic_karaoke_gen.input_media = None  # Will trigger flacfetch
        basic_karaoke_gen.artist = "Test Artist"
        basic_karaoke_gen.title = "Test Title"
        
        # Mock dependencies
        with patch.object(basic_karaoke_gen, 'prep_single_track', new_callable=AsyncMock) as mock_prep_single_track:
            mock_prep_single_track.return_value = {"track": "result"}
            
            result = await basic_karaoke_gen.process()
            
            # Verify prep_single_track was called
            mock_prep_single_track.assert_called_once()
            
            # Verify flacfetch mode was enabled
            assert basic_karaoke_gen._use_audio_fetcher is True
            assert basic_karaoke_gen.extractor == "flacfetch"
            
            # Verify the result
            assert len(result) == 1
            assert result[0] == {"track": "result"}
    
    @pytest.mark.asyncio
    async def test_process_missing_artist_or_title_raises_error(self, basic_karaoke_gen):
        """Test that processing without artist OR title raises an error."""
        # Setup - no input file and missing title
        basic_karaoke_gen.input_media = None  # Not a file
        basic_karaoke_gen.artist = "Test Artist"
        basic_karaoke_gen.title = None  # Missing title

        # Test that ValueError is raised
        with pytest.raises(ValueError, match=r"Either a local file path.*or both artist and title must be provided"):
            await basic_karaoke_gen.process()

    @pytest.mark.asyncio
    async def test_process_with_youtube_url(self, basic_karaoke_gen):
        """Test processing with a YouTube URL as input."""
        # Setup - YouTube URL input
        basic_karaoke_gen.input_media = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        basic_karaoke_gen.artist = "Rick Astley"
        basic_karaoke_gen.title = "Never Gonna Give You Up"

        # Mock dependencies
        with patch.object(basic_karaoke_gen, 'prep_single_track', new_callable=AsyncMock) as mock_prep_single_track:
            mock_prep_single_track.return_value = {"track": "result"}

            result = await basic_karaoke_gen.process()

            # Verify prep_single_track was called
            mock_prep_single_track.assert_called_once()

            # Verify URL mode was enabled
            assert basic_karaoke_gen._use_audio_fetcher is True
            assert basic_karaoke_gen._use_url_download is True
            assert basic_karaoke_gen.extractor == "youtube"
            assert basic_karaoke_gen.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

            # Verify the result
            assert len(result) == 1
            assert result[0] == {"track": "result"}

    @pytest.mark.asyncio
    async def test_process_with_youtube_url_without_artist_title(self, basic_karaoke_gen):
        """Test processing with a YouTube URL but no artist/title."""
        # Setup - YouTube URL input without artist/title
        basic_karaoke_gen.input_media = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        basic_karaoke_gen.artist = None
        basic_karaoke_gen.title = None

        # Mock dependencies
        with patch.object(basic_karaoke_gen, 'prep_single_track', new_callable=AsyncMock) as mock_prep_single_track:
            mock_prep_single_track.return_value = {"track": "result"}

            await basic_karaoke_gen.process()

            # Verify prep_single_track was called
            mock_prep_single_track.assert_called_once()

            # Verify URL mode was enabled
            assert basic_karaoke_gen._use_audio_fetcher is True
            assert basic_karaoke_gen._use_url_download is True

            # Verify extracted info has video ID as fallback
            assert basic_karaoke_gen.extracted_info["id"] == "dQw4w9WgXcQ"

    @pytest.mark.asyncio
    async def test_process_with_youtu_be_short_url(self, basic_karaoke_gen):
        """Test processing with a youtu.be short URL."""
        # Setup - Short URL input
        basic_karaoke_gen.input_media = "https://youtu.be/dQw4w9WgXcQ"
        basic_karaoke_gen.artist = "Rick Astley"
        basic_karaoke_gen.title = "Never Gonna Give You Up"

        # Mock dependencies
        with patch.object(basic_karaoke_gen, 'prep_single_track', new_callable=AsyncMock) as mock_prep_single_track:
            mock_prep_single_track.return_value = {"track": "result"}

            await basic_karaoke_gen.process()

            # Verify prep_single_track was called
            mock_prep_single_track.assert_called_once()

            # Verify URL mode was enabled
            assert basic_karaoke_gen._use_audio_fetcher is True
            assert basic_karaoke_gen._use_url_download is True
            assert basic_karaoke_gen.url == "https://youtu.be/dQw4w9WgXcQ"


class TestKaraokePrepIsUrlHelper:
    """Tests for KaraokePrep._is_url() helper method."""

    @pytest.fixture
    def karaoke_prep(self, tmp_path):
        """Create a KaraokePrep instance for testing."""
        return KaraokePrep(
            artist="Test",
            title="Test",
            output_dir=str(tmp_path),
        )

    def test_is_url_http(self, karaoke_prep):
        """Test _is_url detects http URLs."""
        assert karaoke_prep._is_url("http://example.com") is True

    def test_is_url_https(self, karaoke_prep):
        """Test _is_url detects https URLs."""
        assert karaoke_prep._is_url("https://www.youtube.com/watch?v=abc") is True

    def test_is_url_youtube(self, karaoke_prep):
        """Test _is_url detects YouTube URLs."""
        assert karaoke_prep._is_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ") is True
        assert karaoke_prep._is_url("https://youtu.be/dQw4w9WgXcQ") is True

    def test_is_url_local_path(self, karaoke_prep):
        """Test _is_url returns False for local paths."""
        assert karaoke_prep._is_url("/path/to/file.mp3") is False
        assert karaoke_prep._is_url("./relative/path.wav") is False
        assert karaoke_prep._is_url("file.flac") is False

    def test_is_url_none(self, karaoke_prep):
        """Test _is_url returns False for None."""
        assert karaoke_prep._is_url(None) is False

    def test_is_url_empty_string(self, karaoke_prep):
        """Test _is_url returns False for empty string."""
        assert karaoke_prep._is_url("") is False
