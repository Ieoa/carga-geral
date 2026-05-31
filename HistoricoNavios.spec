# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_submodules


def merge_collect_all(*packages):
    datas = []
    binaries = []
    hiddenimports = []

    for package in packages:
        package_datas, package_binaries, package_hiddenimports = collect_all(package)
        datas += package_datas
        binaries += package_binaries
        hiddenimports += package_hiddenimports

    return datas, binaries, hiddenimports


package_datas, package_binaries, package_hiddenimports = merge_collect_all(
    'bs4',
    'chardet',
    'decouple',
    'dj_database_url',
    'PIL',
    'psycopg',
    'qrcode',
    'reportlab',
    'requests',
    'whitenoise',
)

project_datas = [
    ('config', 'config'),
    ('historico\\templates', 'historico\\templates'),
    ('historico\\static', 'historico\\static'),
    ('historico\\migrations', 'historico\\migrations'),
    ('estoque\\templates', 'estoque\\templates'),
    ('estoque\\migrations', 'estoque\\migrations'),
    ('static', 'static'),
    ('media', 'media'),
    ('db.sqlite3', '.'),
]

project_hiddenimports = [
    'config.settings',
    'config.urls',
    'historico',
    'historico.apps',
    'historico.backends',
    'historico.templatetags.custom_filters',
    'historico.urls',
    'estoque',
    'estoque.apps',
    'estoque.urls',
    'whitenoise.middleware',
    'whitenoise.storage',
]
project_hiddenimports += collect_submodules('historico')
project_hiddenimports += collect_submodules('estoque')
project_hiddenimports += collect_submodules('django.contrib.admin')
project_hiddenimports += collect_submodules('django.contrib.auth')
project_hiddenimports += collect_submodules('django.contrib.contenttypes')
project_hiddenimports += collect_submodules('django.contrib.messages')
project_hiddenimports += collect_submodules('django.contrib.sessions')
project_hiddenimports += collect_submodules('django.contrib.staticfiles')


a = Analysis(
    ['desktop_launcher.py'],
    pathex=[],
    binaries=package_binaries,
    datas=project_datas + package_datas,
    hiddenimports=sorted(set(project_hiddenimports + package_hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='HistoricoNavios',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
