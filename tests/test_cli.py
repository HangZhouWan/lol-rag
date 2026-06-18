import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.cli import parse_args, main


class TestCLI:
    def test_default_args(self):
        with patch("sys.argv", ["cli"]):
            args = parse_args()
        assert args.force is False
        assert args.concurrency == 5
        assert args.output_dir == "data"

    def test_force_flag(self):
        with patch("sys.argv", ["cli", "--force"]):
            args = parse_args()
        assert args.force is True

    def test_concurrency(self):
        with patch("sys.argv", ["cli", "--concurrency", "10"]):
            args = parse_args()
        assert args.concurrency == 10

    def test_output_dir(self):
        with patch("sys.argv", ["cli", "--output-dir", "/tmp/lol_data"]):
            args = parse_args()
        assert args.output_dir == "/tmp/lol_data"

    def test_invalid_concurrency(self):
        with patch("sys.argv", ["cli", "--concurrency", "0"]):
            with pytest.raises(SystemExit):
                parse_args()

    @pytest.mark.asyncio
    async def test_main_calls_orchestrator(self):
        with patch("src.cli.parse_args") as mock_args:
            mock_args.return_value = MagicMock(
                force=False, concurrency=5, output_dir="/tmp/test",
                delay=0.2, max_retries=3, log_level="INFO",
            )
            with patch("src.cli.Orchestrator") as mock_orch:
                mock_instance = MagicMock()
                mock_instance.run = AsyncMock(return_value={"total": 0, "success": 0, "failed": 0, "skipped": 0})
                mock_orch.return_value = mock_instance

                await main()

                mock_orch.assert_called_once()
                mock_instance.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_main_exits_nonzero_on_failure(self):
        with patch("src.cli.parse_args") as mock_args:
            mock_args.return_value = MagicMock(
                force=False, concurrency=5, output_dir="/tmp/test",
                delay=0.2, max_retries=3, log_level="INFO",
            )
            with patch("src.cli.Orchestrator") as mock_orch:
                mock_instance = MagicMock()
                mock_instance.run = AsyncMock(return_value={"total": 5, "success": 3, "failed": 2, "skipped": 0})
                mock_orch.return_value = mock_instance

                with pytest.raises(SystemExit) as exc:
                    await main()
                assert exc.value.code == 1
