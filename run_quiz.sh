#!/bin/bash
echo "Installing dependencies..."
pip install streamlit pandas openpyxl plotly watchdog

echo "Starting Quiz App..."
streamlit run quiz_app.py
