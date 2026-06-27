#!/usr/bin/env python
"""
Ruff 代码检查和格式化工具运行脚本

用法:
    python scripts/run_ruff.py check              # 检查代码问题
    python scripts/run_ruff.py fix                # 自动修复可修复的问题
    python scripts/run_ruff.py format             # 格式化代码
    python scripts/run_ruff.py all                # 检查+修复+格式化

示例:
    # 检查特定文件
    python scripts/run_ruff.py check src/alpha/core/simulation.py
    
    # 检查并自动修复
    python scripts/run_ruff.py fix
    
    # 格式化特定目录
    python scripts/run_ruff.py format src/alpha/core
    
    # 生成 JSON 报告
    python scripts/run_ruff.py check --output json
    
    # 使用不安全修复（谨慎使用）
    python scripts/run_ruff.py fix --unsafe
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], description: str) -> int:
    """运行命令并返回退出码"""
    print(f"\n{'='*80}")
    print(f"执行: {description}")
    print(f"命令: {' '.join(cmd)}")
    print('='*80)
    
    result = subprocess.run(cmd)
    return result.returncode


def check(args: argparse.Namespace) -> int:
    """检查代码问题"""
    cmd = [
        sys.executable, "-m", "ruff", "check",
        "--config", "pyproject.toml",
    ]
    
    if args.output:
        cmd.extend(["--output-format", args.output])
    
    if args.statistics:
        cmd.append("--statistics")
    
    if args.files:
        cmd.extend(args.files)
    else:
        cmd.append("src/alpha")
    
    return run_command(cmd, "Ruff 代码检查")


def fix(args: argparse.Namespace) -> int:
    """自动修复可修复的问题"""
    cmd = [
        sys.executable, "-m", "ruff", "check",
        "--config", "pyproject.toml",
        "--fix",
    ]
    
    if args.unsafe:
        cmd.append("--unsafe-fixes")
    
    if args.diff:
        cmd.append("--diff")
    
    if args.files:
        cmd.extend(args.files)
    else:
        cmd.extend(["src/alpha", "tests"])
    
    action = "Ruff 自动修复（含不安全修复）" if args.unsafe else "Ruff 自动修复"
    return run_command(cmd, action)


def format_code(args: argparse.Namespace) -> int:
    """格式化代码"""
    cmd = [
        sys.executable, "-m", "ruff", "format",
        "--config", "pyproject.toml",
    ]
    
    if args.check:
        cmd.append("--check")
    
    if args.diff:
        cmd.append("--diff")
    
    if args.files:
        cmd.extend(args.files)
    else:
        cmd.extend(["src/alpha", "tests"])
    
    action = "Ruff 格式化检查" if args.check else "Ruff 代码格式化"
    return run_command(cmd, action)


def run_all(args: argparse.Namespace) -> int:
    """运行所有操作：检查 -> 修复 -> 格式化"""
    print("\n" + "="*80)
    print("Ruff 完整代码质量检查流程")
    print("="*80)
    
    # 步骤 1: 初始检查
    print("\n[步骤 1/3] 初始代码检查")
    check_result = check(args)
    
    # 步骤 2: 自动修复
    print("\n[步骤 2/3] 自动修复")
    fix_args = argparse.Namespace(
        unsafe=args.unsafe,
        diff=False,
        files=args.files if args.files else None,
    )
    fix_result = fix(fix_args)
    
    # 步骤 3: 格式化
    print("\n[步骤 3/3] 代码格式化")
    format_args = argparse.Namespace(
        check=False,
        diff=False,
        files=args.files if args.files else None,
    )
    format_result = format_code(format_args)
    
    # 总结
    print("\n" + "="*80)
    print("执行总结")
    print("="*80)
    print(f"  初始检查: {'[PASS]' if check_result == 0 else '[FAIL]'}")
    print(f"  自动修复: {'[PASS]' if fix_result == 0 else '[FIXED]'}")
    print(f"  代码格式化: {'[PASS]' if format_result == 0 else '[FORMATTED]'}")
    
    # 最终检查
    print("\n[最终验证] 修复后检查")
    final_check_result = check(args)
    
    if final_check_result == 0:
        print("\n[PASS] 所有代码质量检查通过！")
    else:
        print("\n[WARN] 仍存在无法自动修复的问题，请手动处理")
    
    return final_check_result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ruff 代码检查和格式化工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # check 子命令
    check_parser = subparsers.add_parser("check", help="检查代码问题")
    check_parser.add_argument(
        "--output",
        choices=["concise", "full", "json", "github", "gitlab", "pylint"],
        default="concise",
        help="输出格式",
    )
    check_parser.add_argument(
        "--statistics",
        action="store_true",
        help="显示统计信息",
    )
    check_parser.add_argument(
        "files",
        nargs="*",
        help="要检查的文件或目录",
    )
    check_parser.set_defaults(func=check)
    
    # fix 子命令
    fix_parser = subparsers.add_parser("fix", help="自动修复可修复的问题")
    fix_parser.add_argument(
        "--unsafe",
        action="store_true",
        help="启用不安全修复（谨慎使用）",
    )
    fix_parser.add_argument(
        "--diff",
        action="store_true",
        help="显示差异而不应用修复",
    )
    fix_parser.add_argument(
        "files",
        nargs="*",
        help="要修复的文件或目录",
    )
    fix_parser.set_defaults(func=fix)
    
    # format 子命令
    format_parser = subparsers.add_parser("format", help="格式化代码")
    format_parser.add_argument(
        "--check",
        action="store_true",
        help="仅检查格式而不修改",
    )
    format_parser.add_argument(
        "--diff",
        action="store_true",
        help="显示格式差异",
    )
    format_parser.add_argument(
        "files",
        nargs="*",
        help="要格式化的文件或目录",
    )
    format_parser.set_defaults(func=format_code)
    
    # all 子命令
    all_parser = subparsers.add_parser("all", help="运行完整流程（检查+修复+格式化）")
    all_parser.add_argument(
        "--unsafe",
        action="store_true",
        help="启用不安全修复",
    )
    all_parser.add_argument(
        "files",
        nargs="*",
        help="要处理的文件或目录",
    )
    all_parser.set_defaults(func=run_all)
    
    args = parser.parse_args()
    
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
