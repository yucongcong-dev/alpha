#!/usr/bin/env python3
"""
数据目录结构优化工具
评估并简化过深的目录结构
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, List, Tuple


def analyze_directory_structure(root: Path) -> Dict[str, int]:
    """分析目录结构，统计各级目录深度"""
    depth_counts: Dict[str, int] = {}
    
    for dirpath, dirnames, filenames in os.walk(root):
        rel_path = os.path.relpath(dirpath, root)
        depth = rel_path.count(os.sep) + 1
        depth_counts[rel_path] = depth
    
    return depth_counts


def find_deep_directories(root: Path, max_depth: int = 3) -> List[str]:
    """找出超过最大深度的目录"""
    depth_counts = analyze_directory_structure(root)
    return [path for path, depth in depth_counts.items() if depth > max_depth]


def list_files_by_depth(root: Path) -> List[Tuple[int, str]]:
    """按深度列出所有文件"""
    files_by_depth: List[Tuple[int, str]] = []
    
    for dirpath, dirnames, filenames in os.walk(root):
        rel_path = os.path.relpath(dirpath, root)
        depth = rel_path.count(os.sep) + 1
        for filename in filenames:
            files_by_depth.append((depth, os.path.join(rel_path, filename)))
    
    return sorted(files_by_depth, key=lambda x: x[0], reverse=True)


def optimize_model51_directory(data_dir: Path) -> None:
    """优化 model51 目录结构"""
    model51_dir = data_dir / "templates" / "model51"
    refine_dir = model51_dir / "refine"
    fields_dir = refine_dir / "fields"
    
    if not fields_dir.exists():
        print("fields 目录不存在，跳过优化")
        return
    
    print(f"正在优化 model51 目录结构...")
    print(f"  原始结构:")
    for depth, path in list_files_by_depth(refine_dir):
        print(f"    {'  ' * (depth - 1)}{path}")
    
    new_fields_dir = model51_dir / "refine_fields"
    print(f"\n  创建新目录: {new_fields_dir}")
    new_fields_dir.mkdir(exist_ok=True)
    
    for file in fields_dir.iterdir():
        if file.is_file():
            target = new_fields_dir / file.name
            print(f"    移动: {file.name} -> {target}")
            shutil.move(str(file), str(target))
    
    if not any(fields_dir.iterdir()):
        print(f"    删除空目录: {fields_dir}")
        fields_dir.rmdir()
    
    print(f"\n  优化完成后的结构:")
    for depth, path in list_files_by_depth(model51_dir):
        print(f"    {'  ' * (depth - 1)}{path}")


def main():
    """主函数"""
    data_dir = Path(__file__).parent.parent / "data"
    
    print("=" * 60)
    print("数据目录结构分析")
    print("=" * 60)
    
    print(f"\n分析目录: {data_dir}")
    
    depth_counts = analyze_directory_structure(data_dir)
    print("\n目录深度统计:")
    for path, depth in sorted(depth_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {depth}层: {path}")
    
    deep_dirs = find_deep_directories(data_dir, max_depth=3)
    if deep_dirs:
        print(f"\n超过3层的目录:")
        for dir_path in deep_dirs:
            print(f"  - {dir_path}")
    else:
        print("\n没有超过3层的目录")
    
    files_by_depth = list_files_by_depth(data_dir)
    print(f"\n文件按深度排序（最深的前20个）:")
    for depth, path in files_by_depth[:20]:
        print(f"  {depth}层: {path}")
    
    print("\n" + "=" * 60)
    print("执行目录优化")
    print("=" * 60)
    
    optimize_model51_directory(data_dir)
    
    print("\n" + "=" * 60)
    print("优化完成")
    print("=" * 60)


if __name__ == "__main__":
    main()