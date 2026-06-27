#!/usr/bin/env python
"""
Mypy 类型检查运行脚本

用法:
    python scripts/run_mypy.py              # 检查所有源代码
    python scripts/run_mypy.py --strict     # 使用严格模式
    python scripts/run_mypy.py --watch      # 监视模式（需要 watchfiles）

示例:
    # 基本检查
    python scripts/run_mypy.py
    
    # 检查特定文件
    python scripts/run_mypy.py src/alpha/core/simulation.py
    
    # 生成类型检查报告
    python scripts/run_mypy.py --junit-xml mypy-report.xml
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="运行 mypy 类型检查",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "files",
        nargs="*",
        help="要检查的文件或目录（默认：src/alpha）",
    )
    
    parser.add_argument(
        "--strict",
        action="store_true",
        help="启用严格模式",
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="pyproject.toml",
        help="配置文件路径（默认：pyproject.toml）",
    )
    
    parser.add_argument(
        "--junit-xml",
        type=str,
        help="生成 JUnit XML 报告文件",
    )
    
    parser.add_argument(
        "--html-report",
        type=str,
        help="生成 HTML 报告目录",
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细信息",
    )
    
    args = parser.parse_args()
    
    # 构建命令
    cmd = [
        sys.executable,
        "-m",
        "mypy",
    ]
    
    # 添加配置文件
    cmd.extend(["--config-file", args.config])
    
    # 严格模式
    if args.strict:
        cmd.append("--strict")
    
    # 详细输出
    if args.verbose:
        cmd.append("--verbose")
    
    # 报告格式
    if args.junit_xml:
        cmd.extend(["--junit-xml", args.junit_xml])
    
    if args.html_report:
        cmd.extend(["--html-report", args.html_report])
    
    # 添加检查目标
    if args.files:
        cmd.extend(args.files)
    else:
        cmd.append("src/alpha")
    
    print(f"运行命令: {' '.join(cmd)}")
    print("-" * 80)
    
    # 执行命令
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n[PASS] 类型检查通过！")
    else:
        print("\n[FAIL] 发现类型错误，请修复后重试")
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
