"""C盘安全清理脚本 - 只清理确定无用的临时文件"""
import os
import shutil
import glob
import sys

def get_dir_size(path):
    """获取目录大小(MB)"""
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

def safe_delete_dir_contents(path, dry_run=False):
    """安全删除目录内容，返回释放的空间(MB)"""
    freed = 0
    if not os.path.exists(path):
        return 0
    for item in os.listdir(path):
        item_path = os.path.join(path, item)
        try:
            if os.path.isfile(item_path) or os.path.islink(item_path):
                size = os.path.getsize(item_path) / (1024 * 1024)
                if not dry_run:
                    os.unlink(item_path)
                freed += size
            elif os.path.isdir(item_path):
                size = get_dir_size(item_path)
                if not dry_run:
                    shutil.rmtree(item_path, ignore_errors=True)
                freed += size
        except (OSError, PermissionError):
            pass
    return freed

def main():
    # 1. 磁盘概览
    total, used, free = shutil.disk_usage("C:\\")
    print("=" * 60)
    print(f"C盘总容量: {total // (1024**3)} GB")
    print(f"已使用:    {used // (1024**3)} GB")
    print(f"剩余空间:  {free // (1024**3)} GB")
    print(f"使用率:    {used / total * 100:.1f}%")
    print("=" * 60)

    user = os.environ.get("USERNAME", "Xinghanrui")
    
    # 2. 扫描可清理目录
    cleanup_targets = []
    
    # 用户临时文件
    user_temp = os.path.join("C:\\Users", user, "AppData", "Local", "Temp")
    # Windows 临时文件
    win_temp = "C:\\Windows\\Temp"
    # 预取文件
    prefetch = "C:\\Windows\\Prefetch"
    # Windows 更新清理缓存
    win_update = "C:\\Windows\\SoftwareDistribution\\Download"
    # 缩略图缓存
    thumb_cache = os.path.join("C:\\Users", user, "AppData", "Local", "Microsoft", "Windows", "Explorer")
    # pip 缓存
    pip_cache = os.path.join("C:\\Users", user, "AppData", "Local", "pip", "cache")
    # npm 缓存
    npm_cache = os.path.join("C:\\Users", user, "AppData", "Local", "npm-cache")
    # conda pkgs 缓存
    conda_pkgs = os.path.join("C:\\Users", user, "miniconda3", "pkgs")
    conda_pkgs2 = os.path.join("C:\\Users", user, "anaconda3", "pkgs")
    conda_pkgs3 = os.path.join("C:\\Users", user, ".conda", "pkgs")
    # Windows 错误报告
    wer_local = os.path.join("C:\\Users", user, "AppData", "Local", "Microsoft", "Windows", "WER")
    wer_sys = "C:\\ProgramData\\Microsoft\\Windows\\WER"
    # 回收站
    recycle_bin = "C:\\$Recycle.Bin"
    # Chrome 缓存
    chrome_cache = os.path.join("C:\\Users", user, "AppData", "Local", "Google", "Chrome", "User Data", "Default", "Cache")
    chrome_code_cache = os.path.join("C:\\Users", user, "AppData", "Local", "Google", "Chrome", "User Data", "Default", "Code Cache")
    # Edge 缓存
    edge_cache = os.path.join("C:\\Users", user, "AppData", "Local", "Microsoft", "Edge", "User Data", "Default", "Cache")
    edge_code_cache = os.path.join("C:\\Users", user, "AppData", "Local", "Microsoft", "Edge", "User Data", "Default", "Code Cache")
    # Windows 旧安装
    windows_old = "C:\\Windows.old"
    # 日志文件
    win_logs = "C:\\Windows\\Logs"
    # Crash dumps
    crash_dumps_local = os.path.join("C:\\Users", user, "AppData", "Local", "CrashDumps")
    crash_dumps_sys = "C:\\Windows\\Minidump"
    # Recent files (快捷方式，可清理)
    recent = os.path.join("C:\\Users", user, "AppData", "Roaming", "Microsoft", "Windows", "Recent")
    # uv cache
    uv_cache = os.path.join("C:\\Users", user, "AppData", "Local", "uv", "cache")

    scan_list = [
        ("用户临时文件 (Temp)", user_temp, True),
        ("Windows 临时文件", win_temp, True),
        ("Windows 预取文件", prefetch, True),
        ("Windows 更新下载缓存", win_update, True),
        ("pip 缓存", pip_cache, True),
        ("npm 缓存", npm_cache, True),
        ("conda 包缓存 (miniconda3)", conda_pkgs, False),
        ("conda 包缓存 (anaconda3)", conda_pkgs2, False),
        ("conda 包缓存 (.conda)", conda_pkgs3, False),
        ("uv 缓存", uv_cache, True),
        ("Windows 错误报告 (用户)", wer_local, True),
        ("Windows 错误报告 (系统)", wer_sys, True),
        ("Chrome 缓存", chrome_cache, True),
        ("Chrome Code Cache", chrome_code_cache, True),
        ("Edge 缓存", edge_cache, True),
        ("Edge Code Cache", edge_code_cache, True),
        ("Crash Dumps (用户)", crash_dumps_local, True),
        ("Crash Dumps (系统)", crash_dumps_sys, True),
        ("Windows 日志", win_logs, False),  # 不自动清，只报告
        ("Windows.old", windows_old, False),  # 不自动清，只报告
    ]

    print("\n--- 扫描可清理目录 ---\n")
    total_cleanable = 0
    for name, path, auto_clean in scan_list:
        if os.path.exists(path):
            size = get_dir_size(path)
            if size > 1:  # 只显示大于1MB的
                status = "[可清理]" if auto_clean else "[仅报告]"
                print(f"  {status} {name}: {size:.1f} MB  ({path})")
                if auto_clean:
                    total_cleanable += size
                    cleanup_targets.append((name, path, size))
        
    print(f"\n总计可安全清理: {total_cleanable:.1f} MB ({total_cleanable/1024:.2f} GB)")
    
    # 3. 检查大文件 (Downloads 文件夹中的大文件)
    downloads = os.path.join("C:\\Users", user, "Downloads")
    if os.path.exists(downloads):
        print(f"\n--- Downloads 文件夹中的大文件 (>100MB，仅提示，不自动删除) ---\n")
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
                print(f"  {f}: {size:.1f} MB")
        else:
            print("  没有大于100MB的文件")

    # 4. 执行清理
    if "--clean" in sys.argv:
        print("\n" + "=" * 60)
        print("开始清理...")
        print("=" * 60)
        total_freed = 0
        for name, path, size in cleanup_targets:
            print(f"\n  清理 {name}...", end=" ")
            freed = safe_delete_dir_contents(path)
            print(f"释放 {freed:.1f} MB")
            total_freed += freed
        
        _, _, new_free = shutil.disk_usage("C:\\")
        print(f"\n{'=' * 60}")
        print(f"清理完成! 总计释放约 {total_freed:.1f} MB")
        print(f"当前剩余空间: {new_free // (1024**3)} GB")
        print("=" * 60)
    else:
        print("\n提示: 以上是扫描结果(dry run)。")
        print("如需执行清理，请运行: python c_drive_cleanup.py --clean")

if __name__ == "__main__":
    main()
