import subprocess
import sys


def test_cli_invalid_json(tmpdir):
    """CLI should exit with error message when given invalid JSON."""
    # Create a temporary file with invalid JSON
    invalid_json_file = tmpdir.join("invalid.json")
    invalid_json_file.write('{ not valid json')

    # Run the CLI
    result = subprocess.run(
        [sys.executable, "-m", "figma2css", str(invalid_json_file)],
        capture_output=True,
        text=True
    )

    # Check that it exits with non-zero
    assert result.returncode != 0
    # Check that stderr contains an error message
    assert "Error" in result.stderr or "error" in result.stderr.lower()