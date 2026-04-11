"""
compress_images.py
==================
Scandi Personal Website · archive 页面图片批量压缩工具

使用前提：
  1. 将此脚本放在仓库根目录（与 archive.html 同级）
  2. 确保已安装依赖：pip install Pillow

运行方式：
  python compress_images.py

完成后执行：
  git add .
  git commit -m "perf: compress all archive images to WebP"
  git push
"""

import os
import re
import shutil
from pathlib import Path
from PIL import Image

# ═══════════════════════════════════════════════════════
#  配置区（无需修改，已根据你的项目结构精确配置）
# ═══════════════════════════════════════════════════════
IMAGE_FOLDER  = "imgs"           # 仓库中存放图片的文件夹
HTML_FILE     = "archive.html"   # archive 页面文件名
MAX_WIDTH     = 2000             # 图片最大宽度（px），超出则等比缩小
WEBP_QUALITY  = 82               # WebP 质量（0-100），82 = 质量与体积最佳平衡
BACKUP_FOLDER = "_originals_backup"  # 原图备份文件夹（脚本自动创建）

# archive_01 ~ archive_64 中已知为 PNG 的文件（其余默认为 JPG）
# 从 HTML 读到 archive_62 是 .png，其余全为 .jpg
PNG_FILES = {"archive_62"}


# ═══════════════════════════════════════════════════════
#  工具函数
# ═══════════════════════════════════════════════════════

def fix_orientation(img: Image.Image) -> Image.Image:
    """根据 EXIF 方向信息修正图片旋转，防止压缩后图片倒置。"""
    try:
        exif = img._getexif()
        if exif:
            orientation = exif.get(274)  # 274 = Orientation tag
            rotations = {3: 180, 6: 270, 8: 90}
            if orientation in rotations:
                img = img.rotate(rotations[orientation], expand=True)
    except Exception:
        pass
    return img


def get_original_ext(stem: str) -> str:
    """根据文件名判断原始扩展名。"""
    if stem in PNG_FILES:
        return ".png"
    return ".jpg"


def format_size(bytes_: int) -> str:
    mb = bytes_ / 1024 / 1024
    return f"{mb:.2f} MB"


# ═══════════════════════════════════════════════════════
#  Step 1：备份原图
# ═══════════════════════════════════════════════════════

def backup_originals():
    backup_path = Path(BACKUP_FOLDER)
    backup_path.mkdir(exist_ok=True)
    backed = 0
    for i in range(1, 65):
        stem = f"archive_{i:02d}"
        ext = get_original_ext(stem)
        src = Path(IMAGE_FOLDER) / (stem + ext)
        if src.exists():
            shutil.copy2(src, backup_path / src.name)
            backed += 1
    print(f"  ✓ 已备份 {backed} 张原图到 ./{BACKUP_FOLDER}/")


# ═══════════════════════════════════════════════════════
#  Step 2：批量压缩为 WebP
# ═══════════════════════════════════════════════════════

def compress_images():
    results = []
    total_before = 0
    total_after  = 0

    for i in range(1, 65):
        stem = f"archive_{i:02d}"
        ext  = get_original_ext(stem)
        src_path = Path(IMAGE_FOLDER) / (stem + ext)
        dst_path = Path(IMAGE_FOLDER) / (stem + ".webp")

        if not src_path.exists():
            print(f"  ⚠ 未找到文件：{src_path}，跳过")
            continue

        size_before = src_path.stat().st_size

        with Image.open(src_path) as img:
            img = fix_orientation(img)

            # 等比缩放（仅当宽度超过 MAX_WIDTH 时）
            if img.width > MAX_WIDTH:
                ratio    = MAX_WIDTH / img.width
                new_size = (MAX_WIDTH, int(img.height * ratio))
                img      = img.resize(new_size, Image.LANCZOS)

            # 统一色彩模式
            if img.mode == "RGBA":
                img.save(dst_path, "WEBP", quality=WEBP_QUALITY,
                         method=6, lossless=False)
            else:
                img = img.convert("RGB")
                img.save(dst_path, "WEBP", quality=WEBP_QUALITY, method=6)

        size_after  = dst_path.stat().st_size
        ratio_pct   = (1 - size_after / size_before) * 100
        total_before += size_before
        total_after  += size_after

        print(f"  [{i:02d}/64] {stem}{ext:5s} "
              f"{format_size(size_before):>9s} → "
              f"{stem}.webp {format_size(size_after):>9s}  "
              f"(-{ratio_pct:.0f}%)")

        # 压缩成功后删除原图
        src_path.unlink()
        results.append(stem)

    print(f"\n  总体积：{format_size(total_before)} → {format_size(total_after)} "
          f"(-{(1-total_after/total_before)*100:.0f}%)")
    return results


# ═══════════════════════════════════════════════════════
#  Step 3：更新 archive.html
# ═══════════════════════════════════════════════════════

def update_html():
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    original = content

    # --- 3a. 修复 JS 动态生成逻辑中硬编码的 ext = 'jpg' ---
    # 原行：const ext = 'jpg';
    # 改为：const ext = 'webp';
    content = re.sub(
        r"(const ext\s*=\s*)'jpg'",
        r"\1'webp'",
        content
    )

    # --- 3b. 修复 Hero 背景图（archive_64.jpg） ---
    content = re.sub(
        r"(imgs/archive_\d+)\.(jpg|jpeg|png)",
        r"\1.webp",
        content
    )

    # --- 3c. 修复 Card Carousel 中硬编码的 5 张图片 ---
    # （archive_59 ~ archive_63，其中 archive_62 是 .png）
    # 上一步的正则已覆盖，无需额外处理

    # --- 3d. 保险：替换所有剩余的 .jpg / .jpeg / .png 引用（含 imgs/ 路径） ---
    content = re.sub(
        r"(imgs/archive_\d+)\.(jpg|jpeg|png)",
        r"\1.webp",
        content
    )

    if content == original:
        print("  ⚠ HTML 未发生变更，请手动检查路径是否匹配。")
    else:
        with open(HTML_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✓ {HTML_FILE} 已更新")

    # 统计替换次数
    jpg_remaining = len(re.findall(r'imgs/archive_\d+\.(jpg|jpeg|png)', content))
    webp_count    = len(re.findall(r'imgs/archive_\d+\.webp', content))
    print(f"  · WebP 引用数：{webp_count}")
    if jpg_remaining:
        print(f"  ⚠ 仍有 {jpg_remaining} 处旧格式引用未替换，请手动检查！")


# ═══════════════════════════════════════════════════════
#  主流程
# ═══════════════════════════════════════════════════════

def main():
    print("=" * 58)
    print("  Scandi Archive · 图片批量压缩工具")
    print("=" * 58)

    # 环境检查
    if not Path(IMAGE_FOLDER).is_dir():
        print(f"\n❌ 未找到图片文件夹 ./{IMAGE_FOLDER}/，请确认脚本位于仓库根目录。")
        return
    if not Path(HTML_FILE).exists():
        print(f"\n❌ 未找到 {HTML_FILE}，请确认脚本位于仓库根目录。")
        return

    # Step 1
    print(f"\n【Step 1】备份原图 → ./{BACKUP_FOLDER}/")
    backup_originals()

    # Step 2
    print(f"\n【Step 2】批量压缩为 WebP（质量={WEBP_QUALITY}，最大宽度={MAX_WIDTH}px）")
    converted = compress_images()

    # Step 3
    print(f"\n【Step 3】更新 {HTML_FILE} 中的图片引用")
    update_html()

    # 完成提示
    print("\n" + "=" * 58)
    print(f"  ✅ 完成！共处理 {len(converted)} 张图片")
    print("=" * 58)
    print("\n接下来执行以下命令提交到 GitHub：\n")
    print("  git add .")
    print('  git commit -m "perf: compress all archive images to WebP"')
    print("  git push")
    print(f"\n原始图片已备份至 ./{BACKUP_FOLDER}/（确认网站正常后可删除）")
    print()


if __name__ == "__main__":
    main()
