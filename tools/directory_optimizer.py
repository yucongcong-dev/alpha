#!/usr/bin/env python3
"""
目录结构优化工具
用于优化和扁平化过深的目录结构
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class DirectoryStats:
    """目录统计信息"""
    path: Path
    depth: int
    file_count: int
    dir_count: int
    total_size: int
    max_depth: int
    
    def __str__(self) -> str:
        return (f"{self.path}: depth={self.depth}, "
                f"files={self.file_count}, dirs={self.dir_count}, "
                f"size={self.total_size:,} bytes, max_depth={self.max_depth}")


class DirectoryOptimizer:
    """目录优化器"""
    
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.stats: Dict[Path, DirectoryStats] = {}
    
    def analyze_directory(self, path: Optional[Path] = None, depth: int = 0) -> DirectoryStats:
        """分析目录结构"""
        if path is None:
            path = self.root_dir
        
        file_count = 0
        dir_count = 0
        total_size = 0
        max_depth = depth
        
        for item in path.iterdir():
            if item.is_file():
                file_count += 1
                total_size += item.stat().st_size
            elif item.is_dir():
                dir_count += 1
                child_stats = self.analyze_directory(item, depth + 1)
                file_count += child_stats.file_count
                dir_count += child_stats.dir_count
                total_size += child_stats.total_size
                max_depth = max(max_depth, child_stats.max_depth)
        
        stats = DirectoryStats(
            path=path,
            depth=depth,
            file_count=file_count,
            dir_count=dir_count,
            total_size=total_size,
            max_depth=max_depth
        )
        
        self.stats[path] = stats
        return stats
    
    def find_deep_directories(self, max_depth: int = 4) -> List[DirectoryStats]:
        """查找过深的目录"""
        deep_dirs = []
        for stats in self.stats.values():
            if stats.max_depth >= max_depth:
                deep_dirs.append(stats)
        
        # 按深度排序
        deep_dirs.sort(key=lambda x: x.max_depth, reverse=True)
        return deep_dirs
    
    def find_small_directories(self, max_files: int = 3) -> List[DirectoryStats]:
        """查找文件数过少的目录"""
        small_dirs = []
        for stats in self.stats.values():
            if stats.file_count <= max_files and stats.file_count > 0:
                small_dirs.append(stats)
        
        # 按文件数排序
        small_dirs.sort(key=lambda x: x.file_count)
        return small_dirs
    
    def find_duplicate_files(self) -> Dict[str, List[Path]]:
        """查找重复文件（基于文件名）"""
        file_groups: Dict[str, List[Path]] = {}
        
        for stats in self.stats.values():
            for item in stats.path.iterdir():
                if item.is_file():
                    filename = item.name
                    if filename not in file_groups:
                        file_groups[filename] = []
                    file_groups[filename].append(item)
        
        # 只返回有重复的文件
        duplicates = {k: v for k, v in file_groups.items() if len(v) > 1}
        return duplicates
    
    def flatten_directory(self, source_dir: Path, target_dir: Path, 
                         max_depth: int = 2, preserve_structure: bool = False) -> List[Tuple[Path, Path]]:
        """扁平化目录结构"""
        moved_files = []
        
        def _flatten(current: Path, relative_path: Path):
            for item in current.iterdir():
                if item.is_file():
                    # 确定目标文件名
                    if preserve_structure:
                        # 保留部分结构
                        target_name = relative_path / item.name
                    else:
                        # 完全扁平化
                        target_name = item.name
                    
                    # 处理文件名冲突
                    target_path = target_dir / target_name
                    counter = 1
                    while target_path.exists():
                        stem = item.stem
                        suffix = item.suffix
                        target_path = target_dir / f"{stem}_{counter}{suffix}"
                        counter += 1
                    
                    # 移动文件
                    shutil.move(str(item), str(target_path))
                    moved_files.append((item, target_path))
                    
                elif item.is_dir():
                    # 递归处理子目录
                    new_relative = relative_path / item.name if preserve_structure else Path("")
                    if len(new_relative.parts) < max_depth:
                        _flatten(item, new_relative)
                    else:
                        # 超过最大深度，直接扁平化
                        _flatten(item, relative_path)
        
        _flatten(source_dir, Path(""))
        return moved_files
    
    def merge_json_files(self, source_files: List[Path], target_file: Path) -> bool:
        """合并多个JSON文件"""
        merged_data = {}
        
        for source_file in source_files:
            try:
                with open(source_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if isinstance(data, dict):
                    # 合并字典，后出现的覆盖先出现的
                    for key, value in data.items():
                        merged_data[key] = value
                elif isinstance(data, list):
                    # 合并列表
                    if "items" not in merged_data:
                        merged_data["items"] = []
                    merged_data["items"].extend(data)
            
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"Warning: Failed to read {source_file}: {e}")
                continue
        
        if merged_data:
            try:
                with open(target_file, 'w', encoding='utf-8') as f:
                    json.dump(merged_data, f, indent=2, ensure_ascii=False)
                return True
            except Exception as e:
                print(f"Error: Failed to write {target_file}: {e}")
        
        return False
    
    def create_index_file(self, target_file: Path) -> bool:
        """创建目录索引文件"""
        index = {
            "root": str(self.root_dir),
            "total_directories": len(self.stats),
            "total_files": sum(s.file_count for s in self.stats.values()),
            "total_size": sum(s.total_size for s in self.stats.values()),
            "max_depth": max(s.max_depth for s in self.stats.values()),
            "directories": []
        }
        
        for stats in sorted(self.stats.values(), key=lambda x: str(x.path)):
            dir_info = {
                "path": str(stats.path.relative_to(self.root_dir)),
                "depth": stats.depth,
                "file_count": stats.file_count,
                "dir_count": stats.dir_count,
                "size": stats.total_size,
                "max_depth": stats.max_depth
            }
            index["directories"].append(dir_info)
        
        try:
            with open(target_file, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error: Failed to create index file: {e}")
            return False
    
    def print_report(self) -> None:
        """打印分析报告"""
        print("=" * 80)
        print(f"目录分析报告: {self.root_dir}")
        print("=" * 80)
        
        # 总体统计
        total_stats = self.stats.get(self.root_dir)
        if total_stats:
            print(f"\n总体统计:")
            print(f"  目录总数: {len(self.stats)}")
            print(f"  文件总数: {total_stats.file_count}")
            print(f"  总大小: {total_stats.total_size:,} bytes")
            print(f"  最大深度: {total_stats.max_depth}")
        
        # 过深目录
        deep_dirs = self.find_deep_directories(max_depth=4)
        if deep_dirs:
            print(f"\n过深目录 (深度 >= 4):")
            for stats in deep_dirs[:10]:  # 只显示前10个
                print(f"  {stats.path.relative_to(self.root_dir)}: 深度={stats.max_depth}")
            if len(deep_dirs) > 10:
                print(f"  ... 还有 {len(deep_dirs) - 10} 个目录")
        
        # 文件过少的目录
        small_dirs = self.find_small_directories(max_files=3)
        if small_dirs:
            print(f"\n文件过少的目录 (<= 3 个文件):")
            for stats in small_dirs[:10]:
                rel_path = stats.path.relative_to(self.root_dir)
                print(f"  {rel_path}: {stats.file_count} 个文件")
            if len(small_dirs) > 10:
                print(f"  ... 还有 {len(small_dirs) - 10} 个目录")
        
        # 重复文件
        duplicates = self.find_duplicate_files()
        if duplicates:
            print(f"\n重复文件:")
            for filename, paths in list(duplicates.items())[:10]:
                print(f"  {filename}:")
                for path in paths:
                    rel_path = path.relative_to(self.root_dir)
                    print(f"    - {rel_path}")
            if len(duplicates) > 10:
                print(f"  ... 还有 {len(duplicates) - 10} 个重复文件")
        
        # 目录深度分布
        depth_distribution: Dict[int, int] = {}
        for stats in self.stats.values():
            depth = stats.depth
            depth_distribution[depth] = depth_distribution.get(depth, 0) + 1
        
        if depth_distribution:
            print(f"\n目录深度分布:")
            for depth in sorted(depth_distribution.keys()):
                count = depth_distribution[depth]
                print(f"  深度 {depth}: {count} 个目录")
        
        print("\n" + "=" * 80)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="目录结构优化工具")
    parser.add_argument("directory", help="要分析的目录路径")
    parser.add_argument("--analyze", action="store_true", help="分析目录结构")
    parser.add_argument("--flatten", metavar="TARGET", help="扁平化目录到目标路径")
    parser.add_argument("--max-depth", type=int, default=2, help="扁平化时保留的最大深度")
    parser.add_argument("--preserve-structure", action="store_true", 
                       help="扁平化时保留部分目录结构")
    parser.add_argument("--merge-json", metavar="TARGET", 
                       help="合并JSON文件到目标文件")
    parser.add_argument("--create-index", metavar="FILE", 
                       help="创建目录索引文件")
    parser.add_argument("--dry-run", action="store_true", 
                       help="模拟运行，不实际修改文件")
    
    args = parser.parse_args()
    
    root_dir = Path(args.directory).resolve()
    if not root_dir.exists() or not root_dir.is_dir():
        print(f"错误: 目录不存在或不是目录: {root_dir}")
        return 1
    
    optimizer = DirectoryOptimizer(root_dir)
    
    # 分析目录
    print(f"正在分析目录: {root_dir}")
    optimizer.analyze_directory()
    
    if args.analyze:
        optimizer.print_report()
    
    if args.flatten:
        target_dir = Path(args.flatten).resolve()
        if args.dry_run:
            print(f"\n[模拟运行] 将扁平化目录:")
            print(f"  源目录: {root_dir}")
            print(f"  目标目录: {target_dir}")
            print(f"  最大保留深度: {args.max_depth}")
            print(f"  保留结构: {args.preserve_structure}")
        else:
            print(f"\n正在扁平化目录...")
            target_dir.mkdir(parents=True, exist_ok=True)
            moved_files = optimizer.flatten_directory(
                root_dir, target_dir, 
                max_depth=args.max_depth,
                preserve_structure=args.preserve_structure
            )
            print(f"已移动 {len(moved_files)} 个文件")
    
    if args.merge_json:
        # 查找所有JSON文件
        json_files = []
        for stats in optimizer.stats.values():
            for item in stats.path.iterdir():
                if item.is_file() and item.suffix.lower() == ".json":
                    json_files.append(item)
        
        if json_files:
            target_file = Path(args.merge_json).resolve()
            if args.dry_run:
                print(f"\n[模拟运行] 将合并 {len(json_files)} 个JSON文件到: {target_file}")
            else:
                print(f"\n正在合并 {len(json_files)} 个JSON文件...")
                if optimizer.merge_json_files(json_files, target_file):
                    print(f"已合并到: {target_file}")
                else:
                    print("合并失败")
        else:
            print("没有找到JSON文件")
    
    if args.create_index:
        target_file = Path(args.create_index).resolve()
        if args.dry_run:
            print(f"\n[模拟运行] 将创建目录索引到: {target_file}")
        else:
            print(f"\n正在创建目录索引...")
            if optimizer.create_index_file(target_file):
                print(f"索引已创建: {target_file}")
            else:
                print("索引创建失败")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())