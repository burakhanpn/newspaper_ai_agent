"""Pytest yapilandirmasi: proje kokunu import yoluna ekler.

Boylece tests/ altindaki dosyalar 'import tools', 'import main' diyebilir;
projeyi paket haline getirmeye gerek kalmaz.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
