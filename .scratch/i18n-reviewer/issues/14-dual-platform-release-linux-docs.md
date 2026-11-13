# 14: Dual-Platform GitHub Release (Windows + Linux AppImage) & Docs

**What to build:** Extend the automated GitHub Release pipeline and user documentation so every tagged release (`v*`) or manual release dispatch builds, verifies, and publishes both Windows (`.exe` installer + portable `.zip`) and Linux (`x86_64` `.AppImage`) downloads side-by-side with unified SHA-256 checksums, while documenting Linux download/execution (`chmod +x`, FUSE vs `--appimage-extract-and-run`), build instructions, and Linux library attributions.

**Blocked by:** 13: Linux AppImage Bundle, Desktop Integration & Automated `--self-test`

**Status:** done

- [x] Release workflow builds Windows (`windows-latest`) and Linux (`ubuntu-24.04`) artifacts in parallel, runs `--self-test` on each platform's built binary, and publishes the `.exe` installer, portable `.zip`, `.AppImage`, and combined `SHA256SUMS.txt` on the same GitHub Release.
- [x] User documentation covers downloading and running the Linux `.AppImage` (executable permission, FUSE/extract fallback) and building it from source on Linux.
- [x] Third-party notices and changelog reflect the Linux AppImage bundling and any newly bundled Linux runtime components.
