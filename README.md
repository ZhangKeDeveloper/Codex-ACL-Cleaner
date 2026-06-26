# codex-acl-cleaner

> 一键清理 Codex (AI 编程助手) 卸载后残留在本地用户目录中的 `CodexSandboxUsers` 组 ACE.
> One-shot cleanup of the `CodexSandboxUsers` group ACE that **Codex** leaves behind in your Windows user profile after uninstall.

---

# 中文文档

## 项目简介

`codex-acl-cleaner` 是一个**单文件 Python 工具**, 用于在 Windows NTFS 卷上递归扫描指定目录的所有子文件夹与子文件的 ACL (安全标签页), 找出包含指定用户或组的项, 并通过总开关一键删除.

**核心优势**: 子项的"用户存在"如果是继承自父目录, 那么从父目录删除即可, 子项无需单独处理 — 脚本据此只对"显式"ACE 进行报告/删除, 对仅"继承"ACE 只做计数.

## 为什么需要这个工具

**Codex (AI 编程助手)** 在卸载时, 并不会清理它在本地用户目录里写入的 NTFS ACL. 整个流程通常是:

1. **使用期间**: Codex 创建一个本地用户组 `<COMPUTERNAME>\CodexSandboxUsers`, 并把它作为 ACE 写入 `C:\Users\<当前用户>\` 下大量文件与子文件夹的 ACL;
2. **卸载 Codex**: 这个本地组通常**仍然存在** (`lusrmgr.msc` 可见), 但已经**没有成员、也没有服务依赖**, 因此可以在 `lusrmgr.msc` 中**正常删除该组**;
3. **删除组后**: 文件 ACL 中的对应项**不会自动消失**, 而是变成 **"未知用户"** (Unknown User), 在每个文件/文件夹的 "属性 → 安全" 列表里只显示一个 SID 字符串 (形如 `S-1-5-21-...`);
4. **此时按名字 `icacls /remove CodexSandboxUsers` 会失败**, 因为 SID 已经无法反向解析回名字. 必须改用 SID 才能清理.

这些孤儿 ACE 还会跟随用户目录的备份/同步扩散到外部存储. 手工 `icacls /remove` 几十万个文件既慢又容易遗漏.

`codex-acl-cleaner` 在步骤 2 之前 (按名字清理) 或步骤 3 之后 (按 SID 清理) 都可以使用, 用一次递归扫描找出所有 **"显式"** 包含该用户/组的项, 一键清理.

## 典型场景

无论你有没有在 `lusrmgr.msc` 中删除 `CodexSandboxUsers` 组, 都可以观察到:

| 阶段 | 位置 | 现象 |
| --- | --- | --- |
| 卸载后, 组还在 | `lusrmgr.msc` → 组 | 存在 `CodexSandboxUsers` 组, 可正常删除 (无成员、无依赖) |
| 卸载后, 组还在 | 任意 `Users\<你>\` 下的文件 → 属性 → 安全 | 列表中出现 `<COMPUTERNAME>\CodexSandboxUsers` 项 |
| **删除组后** | 任意 `Users\<你>\` 下的文件 → 属性 → 安全 | 列表中出现 **"未知用户"**, 后面跟着一个 SID |
| 删除组后 | 命令行 `icacls <file>` | 该条目显示为 `*S-1-5-21-...:(...)` |
| 删除组后 | 备份/同步工具的冲突日志 | 频繁报 ACL 相关差异 |

## 通用用途

虽然本项目因 Codex 而生, 但脚本本身**是通用的**: 它扫描任意目录中包含任意指定用户/组的 ACE, 因此也可以用来清理:

- 旧员工/测试账号在文件服务器上的残留 ACE;
- 其他第三方软件卸载后遗留的组 ACE;
- 任何需要批量审计/清理 NTFS 权限的场景.

## 核心特性

- ✅ **零第三方依赖** — 仅使用 Python 标准库 + Windows 自带的 PowerShell 与 icacls.
- ✅ **一次性递归扫描** — 通过 PowerShell `Get-ChildItem -Recurse | Get-Acl` 一次完成全树遍历, 性能优于逐项调用.
- ✅ **继承感知** — 只对显式 ACE 执行删除; 继承 ACE 仅做计数, 不会触发越权的子项修改.
- ✅ **总开关可控** — `DELETE_USER = False` 时只报告, `True` 时删除. 推荐先 dry-run 一遍确认无误.
- ✅ **写法自动适配** — `TARGET_USER` 接受裸名 / 全限定名 / 裸 SID / 带前缀 SID 任意一种, 脚本自动适配 PowerShell 与 icacls 的差异.
- ✅ **运行样例** — 启动时自动打印目标目录当前 ACL, 方便确认写法.
- ✅ **可选日志** — 可指定日志文件路径, 留痕便于审计.

## 适用环境

| 项 | 要求 |
| --- | --- |
| 操作系统 | Windows 7 或更高 (推荐 Windows 10/11) |
| PowerShell | 5.1+ (系统自带即可) |
| Python | 3.6+ (需要 `subprocess.run(timeout=...)` 与 f-string) |
| 权限 | 修改 ACL 需要对应目录的所有者 / WriteOwner 权限, 跨用户/系统目录通常需要"以管理员身份运行" |
| 文件系统 | NTFS (FAT/exFAT 无 ACL 概念) |

## 快速开始

### 1. 克隆或下载

```bash
git clone https://github.com/<your-account>/codex-acl-cleaner.git
cd codex-acl-cleaner
```

或者直接把 `main.py` 复制到本地.

### 2. 编辑配置

用任意编辑器打开 `main.py`, 在顶部 **全局配置** 区, 至少修改以下两项:

```python
TARGET_DIR  = r"C:\Users\<你>"              # 1) 要扫描的根目录
TARGET_USER = r"CodexSandboxUsers"          # 2) 名字 或 SID (二选一)
DELETE_USER = False                         # 3) 先 False 报告, 确认后改 True
```

`TARGET_USER` **二选一**:

- **方式 A — 填名字** (组还没删时推荐, 最直观): 直接填 `CodexSandboxUsers`. 脚本会同时给 PowerShell 用 `*\CodexSandboxUsers` 通配匹配, 给 icacls 自动补本机前缀.
- **方式 B — 填 SID** (组已删 或 想最稳妥): 填 `S-1-5-21-xxxxxxxxxx-xxxxxxxxxx-xxxxxxxxxx-xxxx`. 脚本对 PowerShell 与 icacls 两种写法的 SID 形式差异自动适配.

### 3. Dry-run (仅报告)

```bash
python main.py
```

此时 `DELETE_USER = False`, 脚本只会列出"显式包含该用户的项"以及"仅继承的项的数量", 不会修改任何 ACL. 启动时还会先打印目标目录当前 ACL 样例, 方便确认 `TARGET_USER` 的写法是否正确.

### 4. 真正删除

将 `main.py` 中 `DELETE_USER` 改为 `True`, 再次执行:

```bash
python main.py
```

脚本会逐项调用 `icacls <path> /remove <user>`, 并把成功/失败写入日志 (若配置了 `LOG_FILE`).

## 配置项

`main.py` 顶部的所有全局变量:

| 变量 | 含义 | 默认 |
| --- | --- | --- |
| `TARGET_DIR` | 扫描的根目录 | 示例占位符, **必须修改** |
| `TARGET_USER` | 要查找/删除的用户 / SID (二选一) | `r"CodexSandboxUsers"` |
| `DELETE_USER` | `True` 删除, `False` 仅报告 | `False` |
| `INCLUDE_FILES` | 是否同时处理文件 (`False`=只处理文件夹) | `True` |
| `INCLUDE_HIDDEN` | 是否包含隐藏/系统项 | `True` |
| `LOG_FILE` | 日志文件路径, `None` 不写文件 | `None` |
| `CONSOLE_ENCODING` | 控制台编码 (中文 Windows 通常 `gbk`) | `"gbk"` |
| `SCAN_TIMEOUT` | 扫描超时 (秒) | `3600` |
| `OP_TIMEOUT` | 单次 icacls 操作超时 (秒) | `60` |

`TARGET_USER` 的写法 (任意一种都可):

| 场景 | 写法 | 示例 |
| --- | --- | --- |
| 组还在 (按名字) | 裸名 | `r"CodexSandboxUsers"` |
| 组还在 (按名字) | 全限定本地组 | `r"MYPC\CodexSandboxUsers"` |
| 组还在 (按名字) | 内置组 | `r"Everyone"` |
| 组还在 (按名字) | 域账号 | `r"CONTOSO\bob"` |
| **组已删除 (按 SID)** | 裸 SID (脚本自动加 `*`) | `r"S-1-5-21-xxxxxxxxxx-..."` |
| **组已删除 (按 SID)** | 带前缀 SID | `r"*S-1-5-21-xxxxxxxxxx-..."` |

> 💡 **关于 SID 写法的细节**: PowerShell 的 `Get-Acl` 对孤儿 SID 返回的是裸 SID 字符串 (无 `*` 前缀), 而 `icacls` 要求 `*SID` 形式. 本脚本**自动适配**这一差异 — 你按上面任意一种最自然的写法填入即可.

## 如何查找并复制 SID

**删除组之前** (推荐 — 一定要先把 SID 记下来):

打开 PowerShell, 跑下面其中一句:

```powershell
# 方法 1: 直接从本地组查
(Get-LocalGroup -Name 'CodexSandboxUsers' -ErrorAction SilentlyContinue).SID.Value

# 方法 2: 从任意残留 ACE 上抓
(Get-Acl "$env:USERPROFILE").Access |
    Where-Object { $_.IdentityReference.Value -like '*CodexSandboxUsers*' } |
    ForEach-Object {
        $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
    }
```

输出形如:

```
S-1-5-21-xxxxxxxxxx-xxxxxxxxxx-xxxxxxxxxx-xxxx
```

**复制这个 SID 的三种方法**:

1. **鼠标选中 + 回车**: 在 PowerShell 里**用鼠标左键拖动选中**那一长串 SID 字符串 (从 `S-` 开始, 到最后一个数字), 然后按 `Enter` 就复制到剪贴板了 (PowerShell 默认 "标记" 模式下选中文本后回车即复制).
2. **右键菜单**: 选中后右键, 在弹出的菜单里点 "复制".
3. **`| Set-Clipboard` 一键复制**: 把上面的命令末尾加个管道, 自动放进剪贴板:
   ```powershell
   (Get-LocalGroup -Name 'CodexSandboxUsers' -ErrorAction SilentlyContinue).SID.Value | Set-Clipboard
   ```
   然后到 `main.py` 里按 `Ctrl+V` 粘贴即可.

**删除组之后** (从任意残留 ACE 上抓):

```powershell
# 在用户目录下随便挑一个文件, 找到变成 "未知用户" 的 SID
(Get-Acl "$env:USERPROFILE").Access |
    Where-Object { $_.IdentityReference.Value -match '^S-1-' } |
    ForEach-Object { $_.IdentityReference.Value }
```

把拿到的 SID 字符串填到 `main.py` 的 `TARGET_USER` 即可, 脚本会自动加 `*` 前缀传给 `icacls`.

## 工作原理

```
┌────────────────────────────────────────────────────────┐
│  1. Python 进程启动, 读取 main.py 顶部的全局配置        │
└────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│  2. 调用 PowerShell: Get-ChildItem -Recurse | Get-Acl   │
│     一次性递归遍历, 找出每条 IsInherited=True/False 的   │
│     ACE, 按名字/SID 分别匹配 TARGET_USER                │
└────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│  3. Python 解析输出, 分桶:                              │
│     • 显式 (IsInherited=False) -> 报告/删除             │
│     • 继承 (IsInherited=True ) -> 仅计数                │
└────────────────────────────────────────────────────────┘
                          │
                          ▼ (仅当 DELETE_USER=True)
┌────────────────────────────────────────────────────────┐
│  4. 对每个显式项调用: icacls <path> /remove <user>      │
│     • PowerShell 端: 裸名按 *\Name 通配, SID 按等值    │
│     • icacls 端: 裸名自动补本机前缀, SID 自动加 * 前缀  │
│     • 父目录上的 ACE 被移除, 子项的继承 ACE 由          │
│       NTFS 自动清除 (无需单独处理)                      │
└────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│  5. 输出统计: 显式项数 / 继承项数 / 删除成功 / 删除失败   │
└────────────────────────────────────────────────────────┘
```

为什么子项的继承 ACE 不需要单独处理? 因为 NTFS 在每次访问 ACL 时都会根据父目录的可继承 ACE 重新计算子项的继承 ACE; 一旦父目录移除了该 ACE, 子项上的继承 ACE 就会在下一次访问时自动消失.

## 风险提示

- ⚠️ **删除操作不可逆**. 请先用 `DELETE_USER = False` 跑一次 dry-run, 人工核对输出后再打开开关.
- ⚠️ **权限要求**: 修改 ACL 需要当前进程对该路径拥有相应的写权限 (WriteDAC / WriteOwner). 如果遇到"拒绝访问"错误, 请以管理员身份运行 Python.
- ⚠️ **大目录扫描**: 极深的目录树或含数十万文件的网络共享盘可能耗时较长. 必要时可调小 `SCAN_TIMEOUT` 或分批扫描.
- ⚠️ **符号链接**: `Get-ChildItem -Recurse` 会跟随目录符号链接, 但有内置环路检测, 一般安全; 若担心可以拆分子树分别扫描.
- ⚠️ **非 NTFS**: 本脚本对 FAT/exFAT/网络共享 SMB (无 NTFS 风格 ACL) 无意义, 会得到空结果.

## 致谢

本脚本由 [**Claude Code**](https://claude.com/product/claude-code) (Claude Agent SDK) 配合 [**MiniMax-M3**](https://MiniMax.com) 大模型协作实现.

## 许可证

本项目基于 **MIT License** 开源, 详见 [LICENSE](./LICENSE) 文件.

---

# English Documentation

## Overview

`codex-acl-cleaner` is a **single-file Python utility** that recursively scans a Windows directory's NTFS ACL (Security tab), locates every entry that references a configurable target user or group, and optionally strips those ACEs in one pass — gated by a single global toggle.

**Key insight**: When a child's "user present" only comes from inheritance, removing the ACE on the parent is enough — NTFS automatically clears inherited ACEs on the child. The script exploits this by only acting on **explicit** ACEs; inherited-only entries are merely counted, never modified.

## Why this exists

After uninstall, **Codex (the AI coding assistant)** does not clean up the NTFS ACL entries it added during use. The typical flow is:

1. **During use**: Codex creates a local group `<COMPUTERNAME>\CodexSandboxUsers` and writes it as an ACE into the ACL of many files and subfolders under `C:\Users\<you>\`.
2. **Uninstall Codex**: the local group is **usually still there** (visible in `lusrmgr.msc`), but with **no members and no service dependency**, so you **can delete it normally from `lusrmgr.msc`**.
3. **After deleting the group**: the corresponding entries in file ACLs **do NOT disappear automatically** — they become **"Unknown User"**, showing only a raw SID string (e.g. `S-1-5-21-...`) in every "Properties → Security" tab.
4. **`icacls /remove CodexSandboxUsers` then fails**, because the SID can no longer be resolved back to the name. You **must use the SID** to clean them up.

These orphan ACEs also leak into any backup/sync of your user profile. Manually running `icacls /remove` against hundreds of thousands of files is slow and error-prone.

`codex-acl-cleaner` works both **before step 2** (clean up by name) and **after step 3** (clean up by SID). It performs a single recursive scan to find every **explicit** ACE that references the target user/group, and removes them all in one pass.

## Background

Regardless of whether you've already deleted the `CodexSandboxUsers` group from `lusrmgr.msc`, you'll observe:

| Stage | Location | What you see |
| --- | --- | --- |
| After uninstall, group still exists | `lusrmgr.msc` → Groups | A `CodexSandboxUsers` group, can be deleted normally (no members, no dependencies) |
| After uninstall, group still exists | Any `Users\<you>\` file → Properties → Security | `<COMPUTERNAME>\CodexSandboxUsers` entry in the list |
| **After deleting the group** | Any `Users\<you>\` file → Properties → Security | **"Unknown User"** entry followed by a SID |
| After deleting the group | `icacls <file>` on the command line | Entry shown as `*S-1-5-21-...:(...)` |
| After deleting the group | Backup/sync tool conflict logs | Frequent ACL-related diffs |

## Generic usage

Although this project was born out of a Codex pain point, the script itself is **fully generic**. It scans any directory for ACEs that reference any user/group, so it can also clean up:

- Orphan ACEs of departed employees / test accounts on file servers;
- ACEs left behind by other third-party software after uninstall;
- Any bulk NTFS-permission audit / cleanup scenario.

## Features

- ✅ **Zero third-party dependencies** — Python stdlib + Windows built-in PowerShell and icacls only.
- ✅ **Single-pass recursive scan** — `Get-ChildItem -Recurse | Get-Acl` walks the entire tree in one shot; much faster than per-item subprocess calls.
- ✅ **Inheritance-aware** — only explicit ACEs are acted on; inherited ACEs are counted but never modified.
- ✅ **Single toggle** — `DELETE_USER = False` for report-only, `True` to delete. Always run a dry-run first.
- ✅ **Flexible input** — `TARGET_USER` accepts bare names, fully-qualified names, bare SIDs, and `*`-prefixed SIDs; the script bridges PowerShell vs. icacls differences automatically.
- ✅ **Live ACL dump** — prints the target directory's current ACL at startup so you can confirm the exact spelling.
- ✅ **Optional log file** — write everything to disk via `LOG_FILE` for audit.

## Requirements

| Item | Requirement |
| --- | --- |
| OS | Windows 7 or newer (Windows 10/11 recommended) |
| PowerShell | 5.1+ (ships with Windows) |
| Python | 3.6+ (requires `subprocess.run(timeout=...)` and f-strings) |
| Privileges | Write-owner / `WriteDAC` on the target directory. "Run as administrator" is usually required for system / cross-user paths. |
| File system | NTFS (FAT/exFAT have no ACL concept) |

## Quick Start

### 1. Clone or download

```bash
git clone https://github.com/<your-account>/codex-acl-cleaner.git
cd codex-acl-cleaner
```

Or just copy `main.py` anywhere locally.

### 2. Edit the config

Open `main.py` and change at least these two lines in the **Global Configuration** section:

```python
TARGET_DIR  = r"C:\Users\<you>"             # 1) root directory to scan
TARGET_USER = r"CodexSandboxUsers"          # 2) name OR SID (pick one)
DELETE_USER = False                         # 3) False to report, True to delete
```

`TARGET_USER` — **pick one of**:

- **Option A — name** (recommended when the group still exists, most intuitive): just put `CodexSandboxUsers`. The script will use the PowerShell wildcard `*\CodexSandboxUsers` for matching, and auto-prepend your machine name when calling `icacls`.
- **Option B — SID** (use after the group is deleted, or when you want maximum reliability): put `S-1-5-21-xxxxxxxxxx-xxxxxxxxxx-xxxxxxxxxx-xxxx`. The script normalizes the SID form for both PowerShell and icacls automatically.

### 3. Dry-run (report only)

```bash
python main.py
```

With `DELETE_USER = False` the script only reports explicit matches and counts inherited-only entries. At startup it also prints the target directory's current ACL so you can confirm your `TARGET_USER` spelling is correct.

### 4. Run with deletion

Flip `DELETE_USER = True` in `main.py` and run again:

```bash
python main.py
```

The script calls `icacls <path> /remove <user>` per entry and writes success/failure to the log file (if `LOG_FILE` is set).

## Configuration

All global variables at the top of `main.py`:

| Variable | Meaning | Default |
| --- | --- | --- |
| `TARGET_DIR` | Root directory to scan | Placeholder, **must change** |
| `TARGET_USER` | User / SID to find and remove (pick one) | `r"CodexSandboxUsers"` |
| `DELETE_USER` | `True` to delete, `False` to report only | `False` |
| `INCLUDE_FILES` | Process files too (else folders only) | `True` |
| `INCLUDE_HIDDEN` | Include hidden / system entries | `True` |
| `LOG_FILE` | Log file path, `None` to disable | `None` |
| `CONSOLE_ENCODING` | Console encoding (CJK Windows: `"gbk"`) | `"gbk"` |
| `SCAN_TIMEOUT` | Scan timeout in seconds | `3600` |
| `OP_TIMEOUT` | Per-icacls-call timeout in seconds | `60` |

Valid `TARGET_USER` forms (any one works):

| Scenario | Form | Example |
| --- | --- | --- |
| Group still exists (by name) | Bare name | `r"CodexSandboxUsers"` |
| Group still exists (by name) | Fully-qualified local group | `r"MYPC\CodexSandboxUsers"` |
| Group still exists (by name) | Built-in group | `r"Everyone"` |
| Group still exists (by name) | Domain account | `r"CONTOSO\bob"` |
| **Group already deleted (by SID)** | Bare SID (script auto-adds `*`) | `r"S-1-5-21-xxxxxxxxxx-..."` |
| **Group already deleted (by SID)** | Prefixed SID | `r"*S-1-5-21-xxxxxxxxxx-..."` |

> 💡 **About the SID form**: PowerShell's `Get-Acl` returns a bare SID string (no `*` prefix) for orphaned entries, while `icacls` requires `*SID`. The script **adapts automatically** — you can use whichever form feels natural.

## How to find and copy the SID

**Before deleting the group** (recommended — capture the SID first):

Open PowerShell and run any of the following:

```powershell
# Method 1: directly from the local group
(Get-LocalGroup -Name 'CodexSandboxUsers' -ErrorAction SilentlyContinue).SID.Value

# Method 2: extract from any leftover ACE
(Get-Acl "$env:USERPROFILE").Access |
    Where-Object { $_.IdentityReference.Value -like '*CodexSandboxUsers*' } |
    ForEach-Object {
        $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
    }
```

Output looks like:

```
S-1-5-21-xxxxxxxxxx-xxxxxxxxxx-xxxxxxxxxx-xxxx
```

**Three ways to copy that SID**:

1. **Select with mouse + Enter** (default PowerShell "Mark" mode): drag-select the SID string with the left mouse button (from `S-` to the last digit), then press `Enter` — it's copied to the clipboard.
2. **Right-click menu**: select the text, right-click, choose "Copy".
3. **`| Set-Clipboard` one-liner**: pipe the output to `Set-Clipboard` so it's already on the clipboard when the command finishes:
   ```powershell
   (Get-LocalGroup -Name 'CodexSandboxUsers' -ErrorAction SilentlyContinue).SID.Value | Set-Clipboard
   ```
   Then in `main.py`, just press `Ctrl+V` to paste.

**After deleting the group** (extract from any leftover ACE):

```powershell
# Pick any file under your profile and find the SID that became "Unknown User"
(Get-Acl "$env:USERPROFILE").Access |
    Where-Object { $_.IdentityReference.Value -match '^S-1-' } |
    ForEach-Object { $_.IdentityReference.Value }
```

Paste the SID into `TARGET_USER` in `main.py`; the script will add the `*` prefix automatically when calling `icacls`.

## How It Works

```
┌────────────────────────────────────────────────────────┐
│  1. Python process starts, reads global config         │
└────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│  2. PowerShell: Get-ChildItem -Recurse | Get-Acl       │
│     One-shot recursive walk. For every ACE:             │
│       - if target is a SID  -> exact match             │
│       - if target is a name -> exact / *\name / *name  │
└────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│  3. Python parses output, buckets:                      │
│     • explicit  (IsInherited=False) -> report / delete │
│     • inherited (IsInherited=True ) -> count only      │
└────────────────────────────────────────────────────────┘
                          │
                          ▼ (only when DELETE_USER=True)
┌────────────────────────────────────────────────────────┐
│  4. Per explicit entry: icacls <path> /remove <user>   │
│     • bare names get machine prefix auto-added         │
│     • SIDs get * prefix auto-added                     │
│     • Once the parent's ACE is removed, NTFS auto-     │
│       clears the inherited ACEs on children            │
└────────────────────────────────────────────────────────┘
                          │
                          ▼
┌────────────────────────────────────────────────────────┐
│  5. Final summary: explicit / inherited / removed / failed │
└────────────────────────────────────────────────────────┘
```

Why don't we touch children when the ACE only came from inheritance? NTFS recomputes inherited ACEs from the parent on every ACL access. Once the parent's ACE is removed, the inherited ACE on the child disappears automatically.

## Caveats

- ⚠️ **Deletion is irreversible**. Always run with `DELETE_USER = False` first and review the output before flipping the switch.
- ⚠️ **Privilege required**: the script needs `WriteDAC` / `WriteOwner` on the target path. If you see "Access Denied", run Python "as Administrator".
- ⚠️ **Large trees**: very deep trees or network shares with hundreds of thousands of files may take a while. You can lower `SCAN_TIMEOUT` or split the scan into subtrees.
- ⚠️ **Symbolic links**: `Get-ChildItem -Recurse` follows directory symlinks but has built-in cycle detection; generally safe. If you're paranoid, split the scan by subtree.
- ⚠️ **Non-NTFS**: useless on FAT/exFAT / non-NTFS SMB shares — you'll just get empty results.

## Credits

This script was implemented collaboratively by [**Claude Code**](https://claude.com/product/claude-code) (Claude Agent SDK) with the [**MiniMax-M3**](https://MiniMax.com) large language model.

## License

Released under the **MIT License** — see [LICENSE](./LICENSE) for details.
