"""
Tests for remote CLI distribution parameters.

Verifies that the remote CLI properly handles the new native API
distribution parameters (--dropbox_path, --gdrive_folder_id).
"""
import pytest
from unittest.mock import MagicMock, patch


class TestRemoteCLIDistributionArgs:
    """Tests for distribution arguments in remote CLI."""

    def test_cli_args_has_dropbox_path(self):
        """Test that CLI args includes --dropbox_path argument."""
        from karaoke_gen.utils.cli_args import create_parser
        
        parser = create_parser()
        args = parser.parse_args([
            "--dropbox_path", "/Karaoke/Tracks-Organized",
        ])
        
        assert hasattr(args, 'dropbox_path')
        assert args.dropbox_path == "/Karaoke/Tracks-Organized"

    def test_cli_args_has_gdrive_folder_id(self):
        """Test that CLI args includes --gdrive_folder_id argument."""
        from karaoke_gen.utils.cli_args import create_parser
        
        parser = create_parser()
        args = parser.parse_args([
            "--gdrive_folder_id", "1abc123xyz",
        ])
        
        assert hasattr(args, 'gdrive_folder_id')
        assert args.gdrive_folder_id == "1abc123xyz"

    def test_cli_args_distribution_params_optional(self):
        """Test that distribution parameters are optional."""
        from karaoke_gen.utils.cli_args import create_parser
        
        parser = create_parser()
        # Parse with no distribution args - should still work
        args = parser.parse_args([])
        
        # Should not raise an error
        assert getattr(args, 'dropbox_path', None) is None
        assert getattr(args, 'gdrive_folder_id', None) is None

    def test_cli_args_combined_distribution_params(self):
        """Test that multiple distribution parameters can be combined."""
        from karaoke_gen.utils.cli_args import create_parser
        
        parser = create_parser()
        args = parser.parse_args([
            "--brand_prefix", "NOMAD",
            "--dropbox_path", "/Karaoke/Organized",
            "--gdrive_folder_id", "1abc123xyz",
            "--discord_webhook_url", "https://discord.com/api/webhooks/123",
        ])
        
        assert args.brand_prefix == "NOMAD"
        assert args.dropbox_path == "/Karaoke/Organized"
        assert args.gdrive_folder_id == "1abc123xyz"
        assert args.discord_webhook_url == "https://discord.com/api/webhooks/123"


class TestRemoteCLIClientSubmitJob:
    """Tests for RemoteKaraokeClient.submit_job with distribution parameters."""

    def test_submit_job_signature_has_dropbox_path(self):
        """Test that submit_job accepts dropbox_path parameter."""
        import inspect
        from karaoke_gen.utils.remote_cli import RemoteKaraokeClient
        
        sig = inspect.signature(RemoteKaraokeClient.submit_job)
        param_names = list(sig.parameters.keys())
        
        assert "dropbox_path" in param_names

    def test_submit_job_signature_has_gdrive_folder_id(self):
        """Test that submit_job accepts gdrive_folder_id parameter."""
        import inspect
        from karaoke_gen.utils.remote_cli import RemoteKaraokeClient
        
        sig = inspect.signature(RemoteKaraokeClient.submit_job)
        param_names = list(sig.parameters.keys())
        
        assert "gdrive_folder_id" in param_names


class TestRemoteCLIClientDataPayload:
    """Tests for the data payload sent by RemoteKaraokeClient."""

    def test_main_function_passes_distribution_params(self):
        """Test that the main function passes distribution params to submit_job."""
        # This is a structural test to verify the wiring exists
        from karaoke_gen.utils import remote_cli
        import inspect
        
        # Get the main function source and check it references the params
        main_source = inspect.getsource(remote_cli.main)
        
        assert "dropbox_path" in main_source
        assert "gdrive_folder_id" in main_source


class TestDistributionParamsHelpText:
    """Tests for help text of distribution parameters."""

    def test_dropbox_path_help_indicates_remote_mode(self):
        """Test that dropbox_path help text mentions remote mode."""
        from karaoke_gen.utils.cli_args import create_parser
        
        parser = create_parser()
        
        # Find the dropbox_path action
        dropbox_action = None
        for action in parser._actions:
            if action.dest == 'dropbox_path':
                dropbox_action = action
                break
        
        assert dropbox_action is not None
        assert 'remote' in dropbox_action.help.lower()

    def test_gdrive_folder_id_help_indicates_remote_mode(self):
        """Test that gdrive_folder_id help text mentions remote mode."""
        from karaoke_gen.utils.cli_args import create_parser
        
        parser = create_parser()
        
        # Find the gdrive_folder_id action
        gdrive_action = None
        for action in parser._actions:
            if action.dest == 'gdrive_folder_id':
                gdrive_action = action
                break
        
        assert gdrive_action is not None
        assert 'remote' in gdrive_action.help.lower()
