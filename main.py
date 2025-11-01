"""Main entry point for TruthSeeker.

This file serves as the entry point for the Streamlit UI.
For CLI usage, use: truthseeker <statement>
Or run directly: python -m src.truthseeker.interfaces.cli.cli <statement>
"""

import sys

from src.truthseeker.interfaces.streamlit.app import create_app

if __name__ == "__main__":
    # Check if running as CLI (if truthseeker command is used, this won't be called)
    # But if someone runs `python main.py --test`, handle it as CLI
    if len(sys.argv) > 1 and sys.argv[1] in ("--test", "--json", "--help", "-h"):
        print(
            "Note: For CLI usage, use: truthseeker <statement>",
            file=sys.stderr,
        )
        print(
            "Or: python -m src.truthseeker.interfaces.cli.cli <statement>",
            file=sys.stderr,
        )
        print("\nRunning Streamlit UI instead...\n", file=sys.stderr)

    create_app()
