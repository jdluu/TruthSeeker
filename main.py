"""Main entry point for TruthSeeker Streamlit application.

Run with:
    streamlit run main.py
"""

from src.truthseeker.interfaces.streamlit.app import create_app

if __name__ == "__main__":
    create_app()
