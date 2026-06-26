# !/usr/bin/env python
# -*- coding: utf-8 -*-

"""
codex-acl-cleaner - 一键清理 Codex (AI 编程助手) 卸载后残留在本地用户
                    目录中的 CodexSandboxUsers 组 ACE.

典型场景 / Background
--------------------
Codex 在安装/使用期间, 会创建一个本地用户组
``<COMPUTERNAME>\CodexSandboxUsers``, 并把它作为 ACE 写入
``C:\Users\<当前用户>\`` 目录下大量文件与子文件夹的 NTFS ACL.
卸载 Codex 后, 该本地组通常还在 (``lusrmgr.msc`` 可见), 但已经
**没有成员也没有服务依赖**, 因此可以在 ``lusrmgr.msc`` 中**正常删除**.

真正的麻烦在这一步之后:

  - 删除该组后, 文件 ACL 中的对应项**不会自动消失**, 而是变成
    "未知用户" (Unknown User), 在每个文件/文件夹的 "属性 -> 安全"
    列表里只显示一个 SID 字符串 (形如 ``S-1-5-21-...``).
  - 此时按名字执行 ``icacls /remove CodexSandboxUsers`` 会失败,
    因为 SID 已经无法反向解析回名字.
  - 这些孤儿 ACE 还会跟随用户目录的备份/同步扩散到外部存储.

本脚本可以在删除组**之前** (按名字清理) 或**之后** (按 SID 清理)
使用, 一键递归扫描并清理. 由于 NTFS 继承机制, 子项的继承 ACE
会被系统自动清除, 无需对每个文件单独处理.

通用用途 / Generic usage
------------------------
脚本本身是通用的: 扫描任意目录中包含指定用户/组的 ACE, 支持任意
用户名 (``DOMAIN\User`` / 本地组 / ``*SID`` 等). 因此也可用于清理
其他类似场景 (旧员工离职、测试账号残留、第三方软件遗留 ACL 等).

SID 形式说明 / SID form
-----------------------
PowerShell 的 ``Get-Acl`` 对孤儿 SID 返回的是裸 SID 字符串
(无 ``*`` 前缀, 也无 "Unknown User" 前缀). ``icacls`` 则要求
``*SID`` 形式. 本脚本自动处理这一差异: 写入 PowerShell 脚本前会
去掉前导 ``*``, 传给 ``icacls`` 前会按需补上 ``*``.

写法自动适配 / Flexible input
-----------------------------
``TARGET_USER`` 接受任意以下写法 (PowerShell 与 icacls 的差异脚本全包):

  - 裸名 (例 ``"CodexSandboxUsers"``) -- 脚本用 ``*\\name`` 通配匹配,
    并给 icacls 自动补本机前缀.
  - 全限定名 (例 ``"MYPC\\CodexSandboxUsers"`` / ``"CONTOSO\\bob"``)
  - 裸 SID (例 ``"S-1-5-21-..."``)
  - 带星号 SID (例 ``"*S-1-5-21-..."``)

继承说明 / Inheritance
----------------------
子项出现目标用户, 可能是从父目录继承而来. 只要把目标用户从父目录
显式权限中移除, 子项的继承 ACE 会被系统自动清理, 无需单独处理.
因此本脚本只对 "显式" 包含该用户的项进行报告/删除, 对仅 "继承" 的项
只做计数, 不做修改.

依赖 / Dependencies
-------------------
  - Windows 自带 PowerShell 与 icacls
  - Python 3 标准库
  - 无需第三方包

致谢 / Credits
--------------
本脚本由 Claude Code (Claude Agent SDK) 配合 MiniMax-M3 大模型协作实现.
"""

import os
import subprocess

# ================================================================
# 全局配置 (在此修改, 不使用环境变量与命令行参数)
# ================================================================

# 1) 目标扫描根目录 - 修改为要扫描的目录
#    例如: r"D:\shared\folder" 或 r"C:\Users\Public\Documents"
TARGET_DIR = r"D:\example\path\to\scan"

# 2) 目标用户/组 -- 二选一: 填"名字" 或 填"SID". 两种都能在删除组
#    前后正常工作.
#
#    方式 A - 填名字 (组还没删时推荐, 最直观):
#         TARGET_USER = r"CodexSandboxUsers"
#         # 脚本会自动用 PowerShell 的 *\CodexSandboxUsers 通配符匹配
#         # MACHINENAME\CodexSandboxUsers, 并给 icacls 自动补本机前缀.
#
#    方式 B - 填 SID (组已删 或 想最稳妥):
#         TARGET_USER = r"S-1-5-21-xxxxxxxxxx-xxxxxxxxxx-xxxxxxxxxx-xxxx"
#         # 脚本对 PowerShell 与 icacls 两种写法的 SID 形式差异自动适配.
#
#    不知道填哪个? 看下面"如何查找并复制 SID" -- 卸载 Codex **之前** 在
#    PowerShell 里跑一句, 把 SID 复制下来贴到这里.
TARGET_USER = r"CodexSandboxUsers"

# 3) 总开关: True=扫描并删除; False=仅扫描报告
DELETE_USER = False

# 4) 是否同时处理子文件 (False=只处理文件夹)
INCLUDE_FILES = True

# 5) 是否包含隐藏/系统项
INCLUDE_HIDDEN = True

# 6) 日志文件路径, 设为 None 不写日志文件
LOG_FILE = None

# 7) 控制台编码
#    中文 Windows 一般是 "gbk"; 英文系统是 "utf-8"
CONSOLE_ENCODING = "gbk"

# 8) 扫描超时(秒)
SCAN_TIMEOUT = 3600

# 9) 单次操作超时(秒)
OP_TIMEOUT = 60

# ================================================================
# 内部常量
# ================================================================

PWSH = "powershell.exe"
ICACLS = "icacls.exe"


# ================================================================
# 工具函数
# ================================================================

def _ps_quote(s):
    """PowerShell 单引号字符串转义."""
    return s.replace("'", "''")


def _user_for_powershell(user):
    """把用户/SID 形式转换为 PowerShell 比较时使用的字符串.

    PowerShell 的 Get-Acl 对孤儿 SID 返回的是裸 SID (无 * 前缀),
    所以发送给 PowerShell 的 user 需要去掉前导 *.
    """
    return user.lstrip("*")


def _user_for_icacls(user):
    """把用户/SID 形式转换为 icacls 接受的字符串.

    icacls 要求:
      - SID 带 * 前缀 (脚本自动补)
      - 本地组必须带机器前缀 ``MACHINENAME\\`` (脚本自动补)
      - 已经带 ``\\`` 或 ``/`` 的视为已限定, 原样使用
    """
    if not user:
        return user
    # SID 形式: 必须带 * 前缀
    if user.startswith("*"):
        return user
    if user.startswith("S-1-"):
        return "*" + user
    # 已经是限定形式 (DOMAIN\\User 或 MACHINENAME\\Group)
    if "\\" in user or "/" in user:
        return user
    # 裸名 (例 "CodexSandboxUsers") - 自动补本机前缀
    machine = os.environ.get("COMPUTERNAME", "").strip()
    if machine:
        return f"{machine}\\{user}"
    return user


def _out(msg, log_file):
    """打印一行到控制台, 同时追加到日志文件."""
    print(msg)
    if log_file:
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except OSError as _e:
            print(f"[警告] 写日志失败: {_e}")


def _init_log(log_file):
    """初始化日志文件(清空/创建)."""
    if not log_file:
        return
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("")
    except OSError as _e:
        print(f"[警告] 初始化日志失败: {_e}")


def _sample_acl(path):
    """读取并返回目标目录的 ACL 样例, 帮助用户确认 TARGET_USER 的格式."""
    script = (
        "$ErrorActionPreference = 'SilentlyContinue'; "
        f"$p = '{_ps_quote(path)}'; "
        "if (-not (Test-Path -LiteralPath $p)) { return }; "
        "$acl = Get-Acl -LiteralPath $p; "
        "foreach ($r in $acl.Access) { "
        "  Write-Output ('  * ' + $r.IdentityReference.Value + "
        "    '  (inherited=' + $r.IsInherited + "
        "    ', rights=' + $r.FileSystemRights + "
        "    ', type=' + $r.AccessControlType + ')') "
        "}"
    )
    try:
        result = subprocess.run(
            [PWSH, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True,
            encoding=CONSOLE_ENCODING, errors="ignore",
            timeout=OP_TIMEOUT,
        )
    except Exception as _e:
        return [f"  [读取样例失败: {_e}]"]
    return [line for line in (result.stdout or "").splitlines() if line.strip()]


def _scan_all(root_dir, target_user, include_files, include_hidden):
    """
    一次性用 PowerShell 递归扫描整个目录的 ACL.
    返回 (findings, errors):
        findings: list[dict] 每条匹配: {path, is_dir, inherited, identity, rights, type}
        errors:   list[str]   扫描过程中遇到的问题
    """
    safe_root = _ps_quote(root_dir)
    safe_user = _ps_quote(_user_for_powershell(target_user))

    file_filter = "if (-not $isDir) { continue }\n" if not include_files else ""
    force_arg = "-Force" if include_hidden else ""

    script = (
        "$ErrorActionPreference = 'SilentlyContinue'; "
        f"$u = '{safe_user}'; "
        f"$isSid = ($u -match '^S-\\d-\\d+'); "
        f"$root = '{safe_root}'; "
        f"$items = Get-ChildItem -LiteralPath $root -Recurse {force_arg}"
        " -ErrorAction SilentlyContinue; "
        "foreach ($it in $items) { "
        "  $isDir = $it.PSIsContainer; "
        f"  {file_filter}"
        "  $path = $it.FullName; "
        "  try { "
        "    $acl = Get-Acl -LiteralPath $path -ErrorAction SilentlyContinue; "
        "    if ($null -eq $acl) { continue }; "
        "    foreach ($r in $acl.Access) { "
        "      $id = $r.IdentityReference.Value; "
        "      $matched = $false; "
        "      if ($isSid) { "
        "        # SID 输入: 等值比较 (PowerShell 对孤儿返回裸 SID, 无 *) "
        "        $matched = ($id -eq $u); "
        "      } else { "
        "        # 名字输入: 三种匹配策略, 让 'CodexSandboxUsers' 也能命中 'MACHINENAME\\CodexSandboxUsers' "
        "        if ($id -eq $u) { $matched = $true } "
        "        elseif ($id -like ('*\\' + $u)) { $matched = $true } "
        "        elseif ($id -like ('*' + $u)) { $matched = $true } "
        "      } "
        "      if ($matched) { "
        "        Write-Output ('F|' + $path + '|' + $isDir + '|'"
        " + $r.IsInherited + '|' + $id + '|'"
        " + $r.FileSystemRights + '|' + $r.AccessControlType) "
        "      } "
        "    } "
        "  } catch { "
        "    Write-Output ('E|' + $path + '|' + $isDir + '|' + $_.Exception.Message) "
        "  } "
        "}"
    )
    try:
        result = subprocess.run(
            [PWSH, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True,
            encoding=CONSOLE_ENCODING, errors="ignore",
            timeout=SCAN_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return [], ["PowerShell 扫描超时"]
    except Exception as _e:
        return [], [f"PowerShell 调用失败: {_e}"]

    findings = []
    errors = []
    for line in (result.stdout or "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if line.startswith("F|") and len(parts) == 7:
            findings.append({
                "path": parts[1],
                "is_dir": parts[2] == "True",
                "inherited": parts[3] == "True",
                "identity": parts[4],
                "rights": parts[5],
                "type": parts[6],
            })
        elif line.startswith("E|"):
            errors.append("|".join(parts[1:]))
    return findings, errors


def _icacls_remove(path, user):
    """用 icacls 移除指定用户在该路径上的所有 ACE. 返回 (ok, message)."""
    icacls_user = _user_for_icacls(user)
    try:
        result = subprocess.run(
            [ICACLS, path, "/remove", icacls_user],
            capture_output=True, text=True,
            encoding=CONSOLE_ENCODING, errors="ignore",
            timeout=OP_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False, "icacls 超时"
    except Exception as _e:
        return False, str(_e)
    msg = ((result.stdout or "") + (result.stderr or "")).strip()
    return result.returncode == 0, msg


# ================================================================
# 主流程
# ================================================================

def main():
    _init_log(LOG_FILE)

    def out(_msg):
        _out(_msg, LOG_FILE)

    out("=" * 80)
    out("开始扫描")
    out(f"  目标目录: {TARGET_DIR}")
    out(f"  目标用户: {TARGET_USER}")
    out(f"  删除模式: {'是' if DELETE_USER else '否 (仅扫描报告)'}")
    out(f"  处理文件: {'是' if INCLUDE_FILES else '否'}")
    out(f"  包含隐藏: {'是' if INCLUDE_HIDDEN else '否'}")
    out("-" * 80)
    out("目标目录的 ACL 样例 (用于确认 TARGET_USER 的写法):")
    for line in _sample_acl(TARGET_DIR):
        out(line)
    out("=" * 80)

    if not os.path.isdir(TARGET_DIR):
        out(f"[错误] 目标目录不存在或不是目录: {TARGET_DIR}")
        return

    out("调用 PowerShell 递归扫描 ACL, 请稍候...")
    findings, errors = _scan_all(
        TARGET_DIR, TARGET_USER, INCLUDE_FILES, INCLUDE_HIDDEN
    )

    for _e in errors:
        out(f"[错误] {_e}")

    out(f"扫描完成, 共发现 {len(findings)} 条匹配的 ACL 项.")
    out("-" * 80)

    n_explicit = 0
    n_inherited = 0
    n_removed = 0
    n_failed = 0

    for f in findings:
        # 继承自父目录的项不处理 (从父目录删除后, 系统会自动清理子项的继承 ACE)
        if f["inherited"]:
            n_inherited += 1
            continue

        n_explicit += 1
        kind = "目录" if f["is_dir"] else "文件"
        out(
            f"[显式-{kind}] {f['path']}  "
            f"权限={f['rights']} 类型={f['type']}"
        )

        if DELETE_USER:
            ok, msg = _icacls_remove(f["path"], TARGET_USER)
            if ok:
                n_removed += 1
                out(f"  [删除-{kind}-成功] {f['path']}")
            else:
                n_failed += 1
                out(f"  [删除-{kind}-失败] {f['path']}  {msg}")

    out("-" * 80)
    out("扫描结束")
    out(f"  显式包含 '{TARGET_USER}' 的项: {n_explicit}")
    out(f"  仅继承自父目录的项 (无需处理): {n_inherited}")
    if DELETE_USER:
        out(f"  删除成功: {n_removed}")
        out(f"  删除失败: {n_failed}")
    out(f"  错误项: {len(errors)}")
    out("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[中断] 用户取消")
    except Exception as e:
        print(f"\n[致命错误] {e}")
        import traceback

        traceback.print_exc()
