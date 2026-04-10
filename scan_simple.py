import os, shutil

out = "d:\\code\\Python\\research_data_agent\\hdrbench_mvp\\scan_out.txt"

with open(out, "w", encoding="utf-8") as f:
    try:
        total, used, free = shutil.disk_usage("C:\\")
        f.write(f"C盘: 总{total//(1024**3)}GB 已用{used//(1024**3)}GB 剩余{free//(1024**3)}GB 使用率{used/total*100:.1f}%\n\n")
    except Exception as e:
        f.write(f"磁盘信息获取失败: {e}\n")

    user = os.environ.get("USERNAME", "Xinghanrui")
    
    dirs_to_scan = {
        "用户Temp": f"C:\\Users\\{user}\\AppData\\Local\\Temp",
        "WinTemp": "C:\\Windows\\Temp",
        "Prefetch": "C:\\Windows\\Prefetch",
        "WinUpdate缓存": "C:\\Windows\\SoftwareDistribution\\Download",
        "pip缓存": f"C:\\Users\\{user}\\AppData\\Local\\pip\\cache",
        "npm缓存": f"C:\\Users\\{user}\\AppData\\Local\\npm-cache",
        "uv缓存": f"C:\\Users\\{user}\\AppData\\Local\\uv\\cache",
        "WER用户": f"C:\\Users\\{user}\\AppData\\Local\\Microsoft\\Windows\\WER",
        "WER系统": "C:\\ProgramData\\Microsoft\\Windows\\WER",
        "CrashDumps": f"C:\\Users\\{user}\\AppData\\Local\\CrashDumps",
        "Minidump": "C:\\Windows\\Minidump",
        "conda_pkgs_mini": f"C:\\Users\\{user}\\miniconda3\\pkgs",
        "conda_pkgs_ana": f"C:\\Users\\{user}\\anaconda3\\pkgs",
        "conda_pkgs_dot": f"C:\\Users\\{user}\\.conda\\pkgs",
        "WinLogs": "C:\\Windows\\Logs",
        "Windows.old": "C:\\Windows.old",
        "ChromeCache": f"C:\\Users\\{user}\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cache",
        "EdgeCache": f"C:\\Users\\{user}\\AppData\\Local\\Microsoft\\Edge\\User Data\\Default\\Cache",
    }
    
    for name, path in dirs_to_scan.items():
        if not os.path.exists(path):
            continue
        sz = 0
        try:
            for dp, dn, fns in os.walk(path):
                for fn in fns:
                    try:
                        sz += os.path.getsize(os.path.join(dp, fn))
                    except:
                        pass
        except:
            pass
        mb = sz / (1024*1024)
        if mb > 0.5:
            f.write(f"{name}: {mb:.1f} MB  -> {path}\n")
    
    # Downloads大文件
    dl = f"C:\\Users\\{user}\\Downloads"
    if os.path.exists(dl):
        f.write("\n--- Downloads大文件(>50MB) ---\n")
        for fn in os.listdir(dl):
            fp = os.path.join(dl, fn)
            try:
                if os.path.isfile(fp):
                    sz = os.path.getsize(fp)/(1024*1024)
                    if sz > 50:
                        f.write(f"  {fn}: {sz:.0f} MB\n")
            except:
                pass
    
    f.write("\nDONE\n")
