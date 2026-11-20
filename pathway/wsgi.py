"""WSGI entry point: point a production WSGI server at wsgi:app."""

from app import create_app

app = create_app()
