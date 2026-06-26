"""
Alpha 测试系统命令行入口模块

支持通过 `python -m alpha` 方式运行 Alpha 测试系统。

Usage:
    python -m alpha [OPTIONS]

Example:
    python -m alpha --dataset-id fundamental6 --region USA --universe TOP3000
"""

import sys


def main() -> int:
    """
    Alpha 测试系统的命令行入口函数。

    从 alpha.main 模块导入并调用主入口函数。
    支持 Ctrl+C 中断和异常处理。

    Returns:
        int: 退出状态码。
            - 0: 正常完成
            - 1: 发生错误
            - 130: 用户中断（Ctrl+C）
    """
    try:
        from .main import main as _main

        return _main()
    except KeyboardInterrupt:
        print("\n[abort] 用户中断", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
