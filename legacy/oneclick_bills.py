# oneclick_bills.py
# -*- coding: utf-8 -*-
"""
一键运行：合并账单 -> 生成 PDF
- 自动调用本目录下的 merged.py 和 generate_report.py
- 合并输出优先识别：output/merged.csv 或 output/merged_bills.csv
- 自动修正路径（打包后也不怕 cwd 变化）
- 自动把 ./fonts/*.ttf/ttc/otf 加进 generate_report 的字体候选
"""

import os, sys, time, glob, traceback, importlib.util, runpy

# ---------------- 路径与目录 ----------------
def BASE_DIR():
    return os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))

ROOT = BASE_DIR()
INPUT_DIR = os.path.join(ROOT, "input")
OUTPUT_DIR = os.path.join(ROOT, "output")
FONTS_DIR = os.path.join(ROOT, "fonts")

def banner(msg):
    print("=" * 78)
    print(msg)
    print("=" * 78)

# ---------------- 动态加载 .py ----------------
def import_from_path(module_name: str, file_path: str):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块：{module_name}（{file_path}）")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def try_import_script(candidates):
    for name in candidates:
        fp = os.path.join(ROOT, name)
        if os.path.exists(fp):
            try:
                return import_from_path(os.path.splitext(name)[0], fp), fp
            except Exception:
                return None, fp
    return None, ""

# ---------------- 查找合并后的 CSV ----------------
def find_merged_csv():
    prefer = [
        os.path.join(OUTPUT_DIR, "merged.csv"),
        os.path.join(OUTPUT_DIR, "merged_bills.csv"),
    ]
    for p in prefer:
        if os.path.exists(p):
            return p
    candidates = glob.glob(os.path.join(OUTPUT_DIR, "merged*.csv"))
    if candidates:
        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates[0]
    return ""

# ---------------- 主流程 ----------------
def main():
    if not os.path.isdir(INPUT_DIR) or not os.path.isdir(OUTPUT_DIR):
        print("❌ 缺少 input/ 或 output/ 文件夹，请在项目根目录下手动创建。")
        sys.exit(1)

    # 1) 合并账单
    banner("步骤 1/2：合并账单")
    merge_mod, merge_path = try_import_script(["merged.py", "merge_bills.py"])
    if not merge_path:
        print("❌ 未找到 merged.py 或 merge_bills.py。")
        sys.exit(2)

    try:
        if merge_mod and hasattr(merge_mod, "main"):
            for attr, val in [("INPUT_DIR", INPUT_DIR), ("OUTPUT_DIR", OUTPUT_DIR)]:
                if hasattr(merge_mod, attr):
                    setattr(merge_mod, attr, val)
            merge_mod.main()
        else:
            print("ℹ️ 合并脚本未暴露 main()，直接执行：", merge_path)
            runpy.run_path(merge_path, run_name="__main__")
    except Exception:
        print("❌ 合并过程出错：")
        traceback.print_exc()
        sys.exit(3)

    csv_path = find_merged_csv()
    if not csv_path:
        print("❌ 未找到合并输出 CSV（output/merged.csv 或 merged_bills.csv）。")
        sys.exit(4)
    print(f"✅ 合并成功：{os.path.relpath(csv_path, ROOT)}")

    # 2) 生成 PDF
    banner("步骤 2/2：生成 PDF 报告")
    gen_mod, gen_path = try_import_script(["generate_report.py", "generate_bills.py"])
    if not gen_path:
        print("❌ 未找到 generate_report.py 或 generate_bills.py。")
        sys.exit(5)

    output_pdf = os.path.join(ROOT, "financial_report.pdf")

    try:
        if gen_mod:
            for attr, val in [("CSV_PATH", csv_path), ("OUTPUT_PDF", output_pdf)]:
                if hasattr(gen_mod, attr):
                    setattr(gen_mod, attr, val)

            if hasattr(gen_mod, "FONT_CANDIDATES"):
                extra = [
                    os.path.join(FONTS_DIR, "msyh.ttc"),
                    os.path.join(FONTS_DIR, "simhei.ttf"),
                    os.path.join(FONTS_DIR, "NotoSansSC-Regular.otf"),
                ]
                if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
                    meipass_fonts = [
                        os.path.join(sys._MEIPASS, "fonts", "msyh.ttc"),
                        os.path.join(sys._MEIPASS, "fonts", "simhei.ttf"),
                        os.path.join(sys._MEIPASS, "fonts", "NotoSansSC-Regular.otf"),
                    ]
                    extra = meipass_fonts + extra
                gen_mod.FONT_CANDIDATES = extra + list(gen_mod.FONT_CANDIDATES)

            if hasattr(gen_mod, "main"):
                gen_mod.main()
            else:
                print("ℹ️ 报表脚本未暴露 main()，直接执行：", gen_path)
                os.environ["OBILLS_CSV_PATH"] = csv_path
                os.environ["OBILLS_OUTPUT_PDF"] = output_pdf
                runpy.run_path(gen_path, run_name="__main__")
        else:
            print("ℹ️ 直接执行：", gen_path)
            os.environ["OBILLS_CSV_PATH"] = csv_path
            os.environ["OBILLS_OUTPUT_PDF"] = output_pdf
            runpy.run_path(gen_path, run_name="__main__")

    except Exception:
        print("❌ 生成 PDF 失败：")
        traceback.print_exc()
        sys.exit(6)

    print(f"🎉 完成！PDF 已生成：{os.path.relpath(output_pdf, ROOT)}")
    try:
        if sys.platform.startswith("win"):
            os.startfile(output_pdf)  # noqa
    except Exception:
        pass
    
    input("按回车键退出...")
    time.sleep(0.5)

if __name__ == "__main__":
    main()
