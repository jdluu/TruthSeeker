"""Streamlit UI entry point for Streamlit Cloud deployment.

This file exists to satisfy Streamlit Cloud's requirement for a streamlit_ui.py file.
It simply imports and runs the main application.
"""

from src.truthseeker.interfaces.streamlit.app import create_app

if __name__ == "__main__":
    create_app()

