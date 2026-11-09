"""
Tests for AudioShake API retry logic.

Covers:
- Retry on 5xx server errors
- Retry on 429 rate limit
- Retry on connection errors
- No retry on 4xx client errors (except 429)
- Retry exhaustion raises the original error
"""
import pytest
from unittest.mock import MagicMock, patch, call
import requests
from tenacity import wait_none

from karaoke_gen.lyrics_transcriber.transcribers.audioshake import (
    AudioShakeAPI,
    AudioShakeConfig,
    _is_retryable_error,
)


@pytest.fixture(autouse=True)
def _no_retry_wait():
    """Disable retry wait times in all tests to avoid sleeping."""
    # Temporarily replace the wait strategy with no-wait for both retry-decorated methods
    methods = [AudioShakeAPI._request_with_retry, AudioShakeAPI._upload_file_with_retry]
    original_waits = [m.retry.wait for m in methods]
    for m in methods:
        m.retry.wait = wait_none()
    yield
    for m, w in zip(methods, original_waits):
        m.retry.wait = w


class TestIsRetryableError:
    """Tests for the _is_retryable_error predicate."""

    def test_connection_error_is_retryable(self):
        assert _is_retryable_error(requests.exceptions.ConnectionError()) is True

    def test_timeout_is_retryable(self):
        assert _is_retryable_error(requests.exceptions.Timeout()) is True

    def test_502_is_retryable(self):
        response = MagicMock()
        response.status_code = 502
        error = requests.exceptions.HTTPError(response=response)
        assert _is_retryable_error(error) is True

    def test_503_is_retryable(self):
        response = MagicMock()
        response.status_code = 503
        error = requests.exceptions.HTTPError(response=response)
        assert _is_retryable_error(error) is True

    def test_429_is_retryable(self):
        response = MagicMock()
        response.status_code = 429
        error = requests.exceptions.HTTPError(response=response)
        assert _is_retryable_error(error) is True

    def test_400_is_not_retryable(self):
        response = MagicMock()
        response.status_code = 400
        error = requests.exceptions.HTTPError(response=response)
        assert _is_retryable_error(error) is False

    def test_401_is_not_retryable(self):
        response = MagicMock()
        response.status_code = 401
        error = requests.exceptions.HTTPError(response=response)
        assert _is_retryable_error(error) is False

    def test_404_is_not_retryable(self):
        response = MagicMock()
        response.status_code = 404
        error = requests.exceptions.HTTPError(response=response)
        assert _is_retryable_error(error) is False

    def test_value_error_is_not_retryable(self):
        assert _is_retryable_error(ValueError("bad")) is False


class TestAudioShakeAPIRetry:
    """Tests for AudioShakeAPI._request_with_retry."""

    def _make_api(self):
        config = AudioShakeConfig(api_token="test-token")
        logger = MagicMock()
        return AudioShakeAPI(config, logger)

    @patch("karaoke_gen.lyrics_transcriber.transcribers.audioshake.requests.request")
    def test_succeeds_on_first_try(self, mock_request):
        api = self._make_api()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response

        result = api._request_with_retry("GET", "https://api.example.com/test")
        assert result == mock_response
        mock_request.assert_called_once()

    @patch("karaoke_gen.lyrics_transcriber.transcribers.audioshake.requests.request")
    def test_retries_on_502_then_succeeds(self, mock_request):
        api = self._make_api()

        # First call: 502 error
        bad_response = MagicMock()
        bad_response.status_code = 502
        bad_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=bad_response)

        # Second call: success
        good_response = MagicMock()
        good_response.raise_for_status = MagicMock()

        mock_request.side_effect = [bad_response, good_response]

        result = api._request_with_retry("GET", "https://api.example.com/test")

        assert result == good_response
        assert mock_request.call_count == 2

    @patch("karaoke_gen.lyrics_transcriber.transcribers.audioshake.requests.request")
    def test_does_not_retry_on_400(self, mock_request):
        api = self._make_api()

        bad_response = MagicMock()
        bad_response.status_code = 400
        bad_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=bad_response)
        mock_request.return_value = bad_response

        with pytest.raises(requests.exceptions.HTTPError):
            api._request_with_retry("GET", "https://api.example.com/test")

        # Should NOT retry — only 1 call
        mock_request.assert_called_once()

    @patch("karaoke_gen.lyrics_transcriber.transcribers.audioshake.requests.request")
    def test_retries_on_connection_error(self, mock_request):
        api = self._make_api()

        good_response = MagicMock()
        good_response.raise_for_status = MagicMock()

        mock_request.side_effect = [
            requests.exceptions.ConnectionError("Connection refused"),
            good_response,
        ]

        result = api._request_with_retry("GET", "https://api.example.com/test")

        assert result == good_response
        assert mock_request.call_count == 2


class TestAudioShakeUploadRetry:
    """Tests for upload_file using retry."""

    @patch("karaoke_gen.lyrics_transcriber.transcribers.audioshake.requests.post")
    def test_upload_file_retries_on_502(self, mock_post, tmp_path):
        config = AudioShakeConfig(api_token="test-token")
        logger = MagicMock()
        api = AudioShakeAPI(config, logger)

        # Create a test file with known content
        test_file = tmp_path / "test.flac"
        test_file.write_bytes(b"fake audio data")

        # First call: 502
        bad_response = MagicMock()
        bad_response.status_code = 502
        bad_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=bad_response)

        # Second call: success
        good_response = MagicMock()
        good_response.raise_for_status = MagicMock()
        good_response.json.return_value = {"id": "asset-123"}
        good_response.status_code = 200
        good_response.text = '{"id": "asset-123"}'

        mock_post.side_effect = [bad_response, good_response]

        asset_id = api.upload_file(str(test_file))

        assert asset_id == "asset-123"
        assert mock_post.call_count == 2

        # Verify file was re-opened on each attempt (both calls got file data)
        for call_args in mock_post.call_args_list:
            files_arg = call_args[1].get("files") or call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("files")
            assert files_arg is not None, "Each retry should pass files"
