#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抖音视频采集数据本地导出脚本

支持将采集到的视频数据导出为 CSV、JSON 或 Markdown 格式。

用法:
    python export_to_local.py --input data.json --format csv --output ./output
    python export_to_local.py --input data.json --format json --output ./output
    python export_to_local.py --input data.json --format markdown --output ./output
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime


# 标准字段顺序（CSV/Markdown 用）
FIELD_ORDER = [
    "视频链接",
    "视频标题",
    "内容结构",
    "观点(Point)",
    "理由(Reason)",
    "例子(Example)",
    "总结(Point)",
    "完整逐字稿",
    "文案介绍",
    "一句话主题",
    "选题方向",
]


def load_data(input_path):
    """加载 JSON 数据文件，支持单条对象或对象数组"""
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("输入数据必须是 JSON 对象或对象数组")
    return data


def export_csv(data, output_dir, filename=None):
    """导出为 CSV 格式（UTF-8 with BOM，Excel 兼容）"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"douyin_analysis_{timestamp}.csv"

    output_path = os.path.join(output_dir, filename)

    # 收集所有出现过的字段，保持标准顺序优先
    all_fields = []
    seen = set()
    for field in FIELD_ORDER:
        for item in data:
            if field in item and field not in seen:
                all_fields.append(field)
                seen.add(field)
                break
    # 追加非标准字段
    for item in data:
        for key in item.keys():
            if key not in seen:
                all_fields.append(key)
                seen.add(key)

    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        for item in data:
            # 列表类型转字符串
            row = {}
            for k, v in item.items():
                if isinstance(v, list):
                    row[k] = ", ".join(str(x) for x in v)
                elif v is None:
                    row[k] = ""
                else:
                    row[k] = v
            writer.writerow(row)

    return output_path


def export_json(data, output_dir, filename=None):
    """导出为 JSON 格式（缩进美化）"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"douyin_analysis_{timestamp}.json"

    output_path = os.path.join(output_dir, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return output_path


def export_markdown(data, output_dir, filename=None):
    """导出为 Markdown 格式，每条视频一个章节"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"douyin_analysis_{timestamp}.md"

    output_path = os.path.join(output_dir, filename)

    lines = []
    lines.append("# 抖音视频采集分析报告")
    lines.append("")
    lines.append(f"> 采集时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"> 共采集 {len(data)} 条视频")
    lines.append("")
    lines.append("---")
    lines.append("")

    for idx, item in enumerate(data, 1):
        title = item.get("视频标题", "无标题")
        lines.append(f"## {idx}. {title}")
        lines.append("")
        if item.get("视频链接"):
            lines.append(f"**视频链接**：{item['视频链接']}")
        if item.get("视频时长(秒)"):
            lines.append(f"**时长**：{item['视频时长(秒)']} 秒")
        lines.append("")

        if item.get("一句话主题"):
            lines.append("### 一句话主题")
            lines.append("")
            lines.append(item["一句话主题"])
            lines.append("")

        if item.get("文案介绍"):
            lines.append("### 文案介绍")
            lines.append("")
            lines.append(item["文案介绍"])
            lines.append("")

        if item.get("完整逐字稿"):
            lines.append("### 完整逐字稿")
            lines.append("")
            lines.append(item["完整逐字稿"])
            lines.append("")

        if item.get("选题方向"):
            lines.append("### 选题方向")
            lines.append("")
            lines.append(item["选题方向"])
            lines.append("")

        if item.get("内容结构"):
            lines.append("### 内容结构")
            lines.append("")
            lines.append(item["内容结构"])
            lines.append("")

        for field in ["观点(Point)", "理由(Reason)", "例子(Example)", "总结(Point)"]:
            if item.get(field):
                lines.append(f"### {field}")
                lines.append("")
                lines.append(item[field])
                lines.append("")

        lines.append("---")
        lines.append("")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path


def main():
    parser = argparse.ArgumentParser(description="抖音视频采集数据本地导出工具")
    parser.add_argument("--input", required=True, help="输入 JSON 数据文件路径")
    parser.add_argument(
        "--format",
        choices=["csv", "json", "markdown"],
        default="csv",
        help="导出格式（默认 csv）",
    )
    parser.add_argument("--output", default=".", help="输出目录（默认当前目录）")
    parser.add_argument("--filename", default=None, help="自定义输出文件名（可选）")

    args = parser.parse_args()

    # 校验输入文件
    if not os.path.isfile(args.input):
        print(f"错误：输入文件不存在 - {args.input}", file=sys.stderr)
        sys.exit(1)

    # 创建输出目录
    os.makedirs(args.output, exist_ok=True)

    # 加载数据
    try:
        data = load_data(args.input)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"错误：输入数据解析失败 - {e}", file=sys.stderr)
        sys.exit(1)

    print(f"已加载 {len(data)} 条视频数据")

    # 按格式导出
    if args.format == "csv":
        output_path = export_csv(data, args.output, args.filename)
    elif args.format == "json":
        output_path = export_json(data, args.output, args.filename)
    elif args.format == "markdown":
        output_path = export_markdown(data, args.output, args.filename)
    else:
        print(f"错误：不支持的格式 - {args.format}", file=sys.stderr)
        sys.exit(1)

    print(f"导出成功：{output_path}")
    print(f"文件大小：{os.path.getsize(output_path):,} 字节")


if __name__ == "__main__":
    main()
