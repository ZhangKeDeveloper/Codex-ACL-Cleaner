# Changelog

All notable changes to `codex-acl-cleaner` are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-26

### Added
- Initial public release.
- Recursive scan of every file and folder under a configurable root directory
  via PowerShell `Get-ChildItem -Recurse | Get-Acl`.
- Detection of NTFS DACL entries referencing a configurable target user,
  local group, or raw SID (supports `MACHINENAME\Group`, `DOMAIN\User`,
  built-in group names like `Everyone`, and SID forms).
- Inheritance-aware reporting: explicit ACEs are listed individually;
  inherited-only entries are counted but never modified.
- Optional one-step removal of the target user from every explicit ACE,
  powered by `icacls <path> /remove <user>`.
- **Automatic SID-form adaptation**: the script transparently bridges the
  difference between PowerShell (returns bare SID like `S-1-5-21-...` for
  orphaned entries) and `icacls` (requires `*S-1-5-21-...`). Users can
  supply `TARGET_USER` in any natural form — name, bare SID, or
  `*`-prefixed SID — and the script normalizes it for each tool.
- Single global toggle `DELETE_USER` to switch between dry-run and
  report-and-clean mode.
- On-start ACL dump of the target directory to help users confirm the
  exact spelling of the target user.
- Optional append-only UTF-8 log file via the `LOG_FILE` global.
- Configurable hidden-item inclusion, file-vs-folder scope, encoding and
  timeouts — all as global variables at the top of `main.py`.
- README section explaining how to look up the SID of the
  `CodexSandboxUsers` group both before and after it has been removed.
- Acknowledgement of [Claude Code](https://claude.com/product/claude-code)
  and the [MiniMax-M3](https://MiniMax.com) large language model as
  co-implementers of this script.

### Notes
- The script is designed primarily to clean up the orphan ACEs left behind
  by **Codex (the AI coding assistant)** after uninstall, but works
  generically for any user, group, or SID cleanup on NTFS volumes.

### Security
- No third-party Python packages required.
- Only built-in Windows tools (`powershell.exe`, `icacls.exe`) are invoked
  via `subprocess.run`, with explicit `timeout` guards.

[1.0.0]: https://github.com/<your-account>/codex-acl-cleaner/releases/tag/v1.0.0
