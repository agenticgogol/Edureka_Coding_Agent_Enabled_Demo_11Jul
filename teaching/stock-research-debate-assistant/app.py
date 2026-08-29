"""Convenience entrypoint for the full Streamlit teaching demo.

Run this file from the demo directory with ``streamlit run app.py``. The
implementation remains in ``frontend/app.py`` so the backend/frontend split
stays explicit for classroom discussion.
"""
from __future__ import annotations

from pathlib import Path
import runpy


runpy.run_path(str(Path(__file__).parent / "frontend" / "app.py"), run_name="__main__")
