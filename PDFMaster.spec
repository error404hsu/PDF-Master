# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None
current_dir = os.path.abspath(os.getcwd())

a = Analysis(
    ['gui_main.py'],
    pathex=[current_dir],
    binaries=[],
    datas=[
        ('core', 'core'),
        ('adapters', 'adapters'),
    ],
    hiddenimports=[
        'fitz',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy',
        'notebook', 'jedi', 'IPython', 'PIL.ImageQt'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PDF排列哥',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='PDF.ico', # 已指向根目錄的 PDF.ico
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PDFMaster_App',
)