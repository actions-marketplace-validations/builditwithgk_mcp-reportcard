# Entry point for cPanel "Setup Python App" (Phusion Passenger) on shared hosting.
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app import app as application  # noqa: E402,F401
