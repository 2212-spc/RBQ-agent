"""C盘安全清理脚本 - 扫描结果写入文件"""
import os
import shutil
import sys

RESULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scan_result.txt")

def get_dir_size(path):
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                try:
                    total += os.path.getsize(fp)
                except (OSError, PermissionError):
                    pass
    except (OSError, PermissionError):
        pass
    return total / (1024 * 1024)

def safe_delete_dir_contents(path):
    freed = 0
    if not os.path.exists(path):
        return 0
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                size = os.path.getsize(item_path) / (1024 * 1024)
                os.unlink(item_path)
                freed += size
            elif os.path.isdir(item_path):
                size = get_dir_size(item_path)
                shutil.rmtree(item_path, ignore_errors=True)
                freed += size
        except (OSError, PermissionError):
            pass
    return freed

def main():
    lines = []
    
    total, used, free = shutil.disk_usage("C:\\")
    lines.append("=" * 60)
    lines.append(f"C盘总容量: {total // (1024**3)} GB")
    lines.append(f"已使用:    {used // (1024**3)} GB")
    lines.append(f"剩余空间:  {free // (1024**3)} GB")
    lines.append(f"使用率:    {used / total * 100:.1f}%")
    lines.append("=" * 60)

    user = os.environ.get("USERNAME", "Xinghanrui")
    
    scan_list = [
        ("用户临时文件 (Temp)", os.path.join("C:\\Users", user, "AppData", "Local", "Temp"), True),
        ("Windows 临时文件", "C:\\Windows\\Temp", True),
        ("Windows 预取文件", "C:\\Windows\\Prefetch", True),
        ("Windows 更新下载缓存", "C:\\Windows\\SoftwareDistribution\\Download", True),
        ("pip 缓存", os.path.join("C:\\Users", user, "AppData", "Local", "pip", "cache"), True),
        ("npm 缓存", os.path.join("C:\\Users", user, "AppData", "Local", "npm-cache"), True),
        ("uv 缓存", os.path.join("C:\\Users", user, "AppData", "Local", "uv", "cache"), True),
        ("Windows 错误报告 (用户)", os.path.join("C:\\Users", user, "AppData", "Local", "Microsoft", "Windows", "WER"), True),
        ("Windows 错误报告 (系统)", "C:\\ProgramData\\Microsoft\\Windows\\WER", True),
        ("Chrome 缓存", os.path.join("C:\\Users", user, "AppData", "Local", "Google", "Chrome", "User Data", "Default", "Cache"), True),
        ("Chrome Code Cache", os.path.join("C:\\Users", user, "AppData", "Local", "Google", "Chrome", "User Data", "Default", "Code Cache"), True),
        ("Edge 缓存", os.path.join("C:\\Users", user, "AppData", "Local", "Microsoft", "Edge", "User Data", "Default", "Cache"), True),
        ("Edge Code Cache", os.path.join("C:\\Users", user, "AppData", "Local", "Microsoft", "Edge", "User Data", "Default", "Code Cache"), True),
        ("Crash Dumps (用户)", os.path.join("C:\\Users", user, "AppData", "Local", "CrashDumps"), True),
        ("Crash Dumps (系统)", "C:\\Windows\\Minidump", True),
        ("conda 包缓存 (miniconda3)", os.path.join("C:\\Users", user, "miniconda3", "pkgs"), False),
        ("conda 包缓存 (anaconda3)", os.path.join("C:\\Users", user, "anaconda3", "pkgs"), False),
        ("conda 包缓存 (.conda)", os.path.join("C:\\Users", user, ".conda", "pkgs"), False),
        ("Windows 日志", "C:\\Windows\\Logs", False),
        ("Windows.old", "C:\\Windows.old", False),
    ]

    lines.append("\n--- 扫描可清理目录 ---\n")
    total_cleanable = 0
    cleanup_targets = []
    
    for name, path, auto_clean in scan_list:
        if os.path.exists(path):
            size = get_dir_size(path)
            if size > 1:
                status = "[可清理]" if auto_clean else "[仅报告-需手动处理]"
                lines.append(f"  {status} {name}: {size:.1f} MB  ({path})")
                if auto_clean:
                    total_cleanable += size
                    cleanup_targets.append((name, path, size))
        
    lines.append(f"\n总计可安全清理: {total_cleanable:.1f} MB ({total_cleanable/1024:.2f} GB)")
    
    downloads = os.path.join("C:\\Users", user, "Downloads")
    if os.path.exists(downloads):
        lines.append(f"\n--- Downloads 文件夹中的大文件 (>100MB，仅提示不删) ---\n")
        big_files = []
        for f in os.listdir(downloads):
            fp = os.path.join(downloads, f)
            try:
                if os.path.isfile(fp):
                    size = os.path.getsize(fp) / (1024 * 1024)
                    if size > 100:
                        big_files.append((f, size))
            except (OSError, PermissionError):
                pass
        if big_files:
            big_files.sort(key=lambda x: -x[1])
            for f, size in big_files:
                lines.append(f"  {f}: {size:.1f} MB")
        else:
            lines.append("  没有大于100MB的文件")

    if "--clean" in sys.argv:
        lines.append("\n" + "=" * 60)
        lines.append("开始清理...")
        lines.append("=" * 60)
        total_freed = 0
        for name, path, size in cleanup_targets:
            freed = safe_delete_dir_contents(path)
            lines.append(f"  清理 {name}: 释放 {freed:.1f} MB")
            total_freed += freed
        
        _, _, new_free = shutil.disk_usage("C:\\")
        lines.append(f"\n{'=' * 60}")
        lines.append(f"清理完成! 总计释放约 {total_freed:.1f} MB ({total_freed/1024:.2f} GB)")
        lines.append(f"当前剩余空间: {new_free // (1024**3)} GB")
        lines.append("=" * 60)
    else:
        lines.append("\n[DRY RUN] 以上是扫描结果，未执行删除。")

    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"DONE: results written to {RESULT_FILE}")

if __name__ == "__main__":
    main()
