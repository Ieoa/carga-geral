# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_submodules


def is_runtime_module(module_name):
    """Remove pacotes de teste que nao sao usados em producao."""
    parts = module_name.split('.')
    return not any(
        part in {'test', 'tests', 'testing', 'conftest'}
        or part.startswith('test_')
        for part in parts
    )


def runtime_submodules(package):
    return [
        module_name
        for module_name in collect_submodules(package)
        if is_runtime_module(module_name)
    ]


def merge_collect_all(*packages):
    datas = []
    binaries = []
    hiddenimports = []

    for package in packages:
        package_datas, package_binaries, package_hiddenimports = collect_all(package)
        datas += package_datas
        binaries += package_binaries
        hiddenimports += [
            module_name
            for module_name in package_hiddenimports
            if is_runtime_module(module_name)
        ]

    return datas, binaries, hiddenimports


package_datas, package_binaries, package_hiddenimports = merge_collect_all(
    'cryptography',
    'decouple',
    'dj_database_url',
    'pymysql',
    'ldap3',
    'joblib',
    'numpy',
    'PIL',
    'qrcode',
    'reportlab',
    'sklearn',
    'scipy',
    'threadpoolctl',
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
    ('staticfiles', 'staticfiles'),
]

project_hiddenimports = [
    'config.settings',
    'config.urls',
    'config.auth_backends',
    'historico',
    'historico.apps',
    'historico.templatetags.custom_filters',
    'historico.urls',
    'estoque',
    'estoque.apps',
    'estoque.urls',
    'whitenoise.middleware',
    'whitenoise.storage',
]
project_hiddenimports += runtime_submodules('historico')
project_hiddenimports += runtime_submodules('estoque')
project_hiddenimports += runtime_submodules('django.contrib.admin')
project_hiddenimports += runtime_submodules('django.contrib.auth')
project_hiddenimports += runtime_submodules('django.contrib.contenttypes')
project_hiddenimports += runtime_submodules('django.contrib.messages')
project_hiddenimports += runtime_submodules('django.contrib.sessions')
project_hiddenimports += runtime_submodules('django.contrib.staticfiles')

embedded_database_driver = ''.join(('sql', 'ite3'))


a = Analysis(
    ['desktop_launcher.py'],
    pathex=[],
    binaries=package_binaries,
    datas=project_datas + package_datas,
    hiddenimports=sorted(set(project_hiddenimports + package_hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # O aplicativo usa exclusivamente MySQL/MariaDB. Evita embutir o driver
    # local do Python e impede uma troca acidental de banco no executavel.
    excludes=[
        embedded_database_driver,
        f'django.db.backends.{embedded_database_driver}',
    ],
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
