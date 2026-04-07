"""
Script para generar el .exe con PyInstaller.

Uso:
    python build_exe.py

Genera: dist/AsistenteTutorial.exe (un solo archivo, ~60-80 MB)
"""
import PyInstaller.__main__
import sys

PyInstaller.__main__.run([
    "tutorial_coach/__main__.py",
    "--onefile",
    "--windowed",
    "--name", "AsistenteTutorial",
    "--add-data", "tutorial_coach;tutorial_coach",
    # Ocultar consola en Windows
    "--noconsole",
    # Optimizar
    "--noupx",
    # Limpiar build anterior
    "--clean",
])
