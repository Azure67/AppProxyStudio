# Third-party components

- Mihomo v1.19.1, MetaCubeX, GPL-3.0: https://github.com/MetaCubeX/mihomo/tree/v1.19.1 . The executable was copied from the user's existing local installation and is unmodified. Source: https://github.com/MetaCubeX/mihomo/archive/refs/tags/v1.19.1.zip . Documentation: https://wiki.metacubex.one/ . License: licenses/mihomo-GPL-3.0.txt .
- PySide6-Essentials / Shiboken6 6.12.0, The Qt Company. Licensing and third-party notices: https://doc.qt.io/qtforpython-6/licenses.html . Corresponding sources: https://download.qt.io/official_releases/QtForPython/pyside6/ . Runtime libraries are dynamically loaded and replaceable in app/AppProxyStudio/_runtime. Original wheel metadata and license files are retained under vendor/*dist-info.
- Qt 6.12, The Qt Company: https://download.qt.io/official_releases/qt/6.12/ . Licensed under the applicable open-source Qt licenses; see vendor/PySide6 and its distribution metadata.
- PyYAML 6.0.3, MIT: https://github.com/yaml/pyyaml .
- psutil 7.2.2, BSD-3-Clause: https://github.com/giampaolo/psutil .
- Python 3.10, PSF License: https://www.python.org/ .
- PyInstaller 6.22.3 (build tool), GPL with bootloader exception: https://pyinstaller.org/en/stable/license.html .

This local project includes the application source and reproducible build instructions. Third-party components retain their own licenses. Do not omit their notices when redistributing a build.
Application source in src/ and tests/ is licensed under GPL-3.0-or-later.
Third-party components remain under their original licenses, as described in THIRD_PARTY.md.
