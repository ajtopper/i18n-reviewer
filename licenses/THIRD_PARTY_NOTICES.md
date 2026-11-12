# Third-Party Software Notices and Source Code Information

This distribution of **i18n Reviewer** includes third-party open-source software and linguistic data. Verbatim copies of the applicable license texts (`LGPL-2.1.txt`, `LGPL-3.0.txt`, `GPL-2.0.txt`, `GPL-3.0.txt`, and `MPL-2.0.txt`) are located alongside this file in the `licenses/` directory.

---

## 1. Qt 6 / PySide6-Essentials & Shiboken6

- **Version:** `6.12.0`
- **Copyright:** The Qt Company Ltd. and contributors
- **License:** GNU Lesser General Public License v3.0 (`LGPL-3.0-only`, see `LGPL-3.0.txt`)
- **Source Code:** https://code.qt.io/ and https://download.qt.io/official_releases/QtForPython/pyside6/
- **Compliance Note:** Dynamically linked against bundled Qt shared libraries in this `--onedir` distribution so users can replace compatible Qt libraries in compliance with LGPL-3.0.

---

## 2. PyEnchant & Enchant (`libenchant-2.dll`, `enchant_hunspell.dll`)

- **PyEnchant Version:** `3.3.0`
- **Copyright:** Ryan Kelly and PyEnchant contributors; Enchant authors (AbiWord / Reuben Thomas)
- **License:** GNU Lesser General Public License v2.1 or later (`LGPL-2.1-or-later`, see `LGPL-2.1.txt`) with PyEnchant linking exception
- **Source Code:**
  - PyEnchant: https://github.com/pyenchant/pyenchant
  - Enchant: https://github.com/AbiWord/enchant
- **Compliance Note:** Built with `module_collection_mode={'enchant': 'py'}` so the `enchant` Python bindings and Enchant shared libraries remain replaceable in the application directory.

---

## 3. Hunspell (`libhunspell-1.7-0.dll`) & MinGW-w64 / MSYS2 Support Libraries

This distribution bundles only the shared libraries required by `libenchant-2.dll` and `enchant_hunspell.dll`:

- **Hunspell** (`libhunspell-1.7-0.dll`): `LGPL-2.1-or-later` / `GPL-2.0-or-later` / `MPL-1.1` tri-license — https://github.com/hunspell/hunspell
- **GLib / GModule** (`libglib-2.0-0.dll`, `libgmodule-2.0-0.dll`): `LGPL-2.1-or-later` — https://gitlab.gnome.org/GNOME/glib
- **GNU libiconv / gettext-runtime** (`libiconv-2.dll`, `libintl-8.dll`): `LGPL-2.1-or-later` — https://www.gnu.org/software/libiconv/ and https://www.gnu.org/software/gettext/
- **PCRE2** (`libpcre2-8-0.dll`): BSD-3-Clause — https://github.com/PCRE2Project/pcre2
- **GCC / MinGW-w64 Runtime** (`libgcc_s_seh-1.dll`, `libstdc++-6.dll`, `libwinpthread-1.dll`): `GPL-3.0-or-later` with GCC Runtime Library Exception (`GPL-3.0.txt`) & MIT/ZPL — https://gcc.gnu.org/ and https://www.mingw-w64.org/
- **MSYS2 Binary & Source Packages:** https://packages.msys2.org/

---

## 4. Bundled Hunspell Dictionaries

- **`pt_BR` (VERO — Verificador Ortográfico em Português do Brasil):**
  - **Copyright:** Raimundo Santos Moura and VERO / LibreOffice-pt-BR contributors
  - **License:** `LGPL-3.0` / `MPL-2.0` (`LGPL-3.0.txt`, `MPL-2.0.txt`)
  - **Source:** https://git.libreoffice.org/dictionaries/+/refs/heads/master/pt_BR/ and https://pt-br.libreoffice.org/projetos/vero/
- **`es_ES` (Spanish Hunspell Dictionary):**
  - **Copyright:** Santiago Rodríguez, Jesús Carretero, and LibreOffice Spanish dictionary contributors
  - **License:** `GPL-3.0` / `LGPL-3.0` / `MPL-2.0` (`GPL-3.0.txt`, `LGPL-3.0.txt`, `MPL-2.0.txt`)
  - **Source:** https://git.libreoffice.org/dictionaries/+/refs/heads/master/es/
- **`fr_FR` (Grammalecte / Dicollecte French Dictionary):**
  - **Copyright:** Olivier R. and Dicollecte / Grammalecte contributors
  - **License:** `MPL-2.0` (`MPL-2.0.txt`)
  - **Source:** https://git.libreoffice.org/dictionaries/+/refs/heads/master/fr_FR/
- **`de_DE` (`de_DE_frami` German Dictionary):**
  - **Copyright:** Björn Jacke, Franz Michael Baumann, and igerman98 contributors
  - **License:** `GPL-2.0` / `GPL-3.0` (`GPL-2.0.txt`, `GPL-3.0.txt`)
  - **Source:** https://git.libreoffice.org/dictionaries/+/refs/heads/master/de/
- **`en_US` (SCOWL / LibreOffice English US Dictionary):**
  - **Copyright:** Kevin Atkinson and SCOWL contributors
  - **License:** MIT / BSD-like (SCOWL) and `LGPL-2.1` (`LGPL-2.1.txt`)
  - **Source:** https://github.com/pyenchant/pyenchant and https://git.libreoffice.org/dictionaries/+/refs/heads/master/en/

---

## 5. CPython & PyInstaller Bootloader

- **CPython 3.14:** Python Software Foundation License v2 (`PSF-2.0`) — https://www.python.org/
- **PyInstaller 6.22.3 Bootloader:** `GPL-2.0-or-later` with PyInstaller Bootloader Exception (`GPL-2.0.txt`) — https://github.com/pyinstaller/pyinstaller

