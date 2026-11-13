# 13: Linux AppImage Bundle, Desktop Integration & Automated `--self-test`

**What to build:** Package the application as a self-contained `x86_64` Linux `.AppImage` that launches cleanly on mainstream distributions without requiring Python, Qt, Enchant, or Hunspell installed on the host. The bundle includes a PyInstaller Linux spec, bundled Qt 6 + Enchant/Hunspell shared libraries with portable runtime discovery, application icon, `.desktop` desktop entry, executable `AppRun` forwarding CLI arguments (such as `--self-test` or a Foundry manifest path), and a reproducible build/verification script tested under both normal and non-ASCII paths with `APPIMAGE_EXTRACT_AND_RUN=1`.

**Blocked by:** 12: Linux Runtime Portability, Enchant Discovery & Offline `en_US` Dictionaries

**Status:** done

- [x] Linux PyInstaller build specification bundles the application, PySide6/Qt6 runtime, Enchant/Hunspell shared libraries (`libenchant-2`, `enchant_hunspell`, `libhunspell`), all 5 bundled Hunspell dictionaries, and third-party license notices.
- [x] AppDir metadata includes a valid `.desktop` file, application icon (`.DirIcon`), and `AppRun` entrypoint configuring runtime library/Enchant/Qt paths and forwarding CLI arguments.
- [x] Linux packaging script builds `i18n-reviewer-<Version>-x86_64.AppImage` and executes `--self-test` against the built AppImage (with `APPIMAGE_EXTRACT_AND_RUN=1` compatibility for container/FUSE-less environments) from both normal and non-ASCII directory paths.
- [x] Automated packaging checks verify AppImage metadata, desktop integration files, and Linux build configuration.
