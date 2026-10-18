# 1. 安装 pip（如果还没有的话）
# apt update && apt install -y python3-pip fio

# 2. 安装绘图依赖包
# pip install matplotlib --break-system-packages  # 新版系统可能需要加后面这个参数

####RUN####
# python3 fio-test.py --mode mix --time 60
# python3 fio-test.py --mode write --time 120
# 读 写--测4k写惩罚

# #!/usr/bin/env python3
import argparse
import glob
import json
import os
import subprocess
import sys

try:
    import matplotlib.pyplot as plt
except ImportError:
    print("❌ 错误: 未安装 'matplotlib' 库。请运行: pip install matplotlib")
    sys.exit(1)

def cleanup_logs():
    for f in glob.glob("fio_run_log*"):
        try:
            os.remove(f)
        except Exception:
            pass

def run_fio(mode, filename, runtime, size):
    cleanup_logs()
    
    file_size = size if size else ("10G" if mode == "write" else "4G")
    
    base_cmd = [
        "fio",
        "--ioengine=libaio",
        "--direct=1",
        "--bs=4k",
        "--iodepth=32",
        "--numjobs=1",
        f"--runtime={runtime}",
        "--time_based",
        "--group_reporting",
        "--output-format=json",
        "--write_iops_log=fio_run_log",
        "--log_avg_msec=1000",
        f"--size={file_size}",
        f"--filename={filename}"
    ]
    
    if mode == "write":
        cmd = base_cmd + [
            "--name=4k_randwrite_test",
            "--rw=randwrite"
        ]
    else:
        cmd = base_cmd + [
            "--name=4k_randrw_test",
            "--rw=randrw",
            "--rwmixread=70"
        ]
        
    print(f"🎬 正在启动 FIO 测试 [模式: {mode.upper()}, 文件大小: {file_size}]，预计耗时 {runtime} 秒...")
    print(f"💻 执行命令: {' '.join(cmd)}\n")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ FIO 执行失败:\n{result.stderr}")
        sys.exit(1)
        
    return json.loads(result.stdout)

def parse_time_series_log():
    log_files = glob.glob("fio_run_log_iops.*.log")
    if not log_files:
        return None, None
        
    log_file = log_files[0]
    read_timeline, read_iops = [], []
    write_timeline, write_iops = [], []
    
    with open(log_file, "r") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 3:
                try:
                    time_sec = int(parts[0].strip()) / 1000.0
                    iops_val = int(parts[1].strip())
                    direction = int(parts[2].strip())
                    
                    if direction == 0:
                        read_timeline.append(time_sec)
                        read_iops.append(iops_val)
                    else:
                        write_timeline.append(time_sec)
                        write_iops.append(iops_val)
                except ValueError:
                    continue
    return (read_timeline, read_iops), (write_timeline, write_iops)

def generate_chart(mode, read_data, write_data):
    plt.figure(figsize=(11, 5))
    has_plot = False
    
    if read_data and read_data[0]:
        plt.plot(read_data[0], read_data[1], label="Read IOPS", color="#1f77b4", linewidth=2, marker='o', markersize=3)
        has_plot = True
    if write_data and write_data[0]:
        plt.plot(write_data[0], write_data[1], label="Write IOPS", color="#ff7f0e", linewidth=2, marker='s', markersize=3)
        has_plot = True
        
    if not has_plot:
        print("⚠️ 未找到时序日志数据，跳过图表绘制。")
        return
        
    plt.title(f"VPS Storage Performance Timeline ({mode.upper()} Mode)", fontsize=14, fontweight='bold')
    plt.xlabel("Time (Seconds)", fontsize=12)
    plt.ylabel("IOPS", fontsize=12)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="upper right", fontsize=11)
    
    output_png = f"vps_io_trend_{mode}.png"
    plt.tight_layout()
    plt.savefig(output_png, dpi=150)
    print(f"📊 趋势分析图表已成功保存至: {output_png}")

def print_pretty_summary(json_data, mode):
    job = json_data["jobs"][0]
    print("\n" + "=" * 50)
    print(f"🏆  测试结果摘要报告 ({mode.upper()} 模式)")
    print("=" * 50)
    
    target_modes = ["read", "write"] if mode == "mix" else ["write"]
    
    for m in target_modes:
        stats = job[m]
        iops = stats.get("iops", 0)
        bw_mib = stats.get("bw", 0) / 1024
        
        lat_dict = stats.get("lat_ns") or stats.get("lat") or {}
        is_ns = "lat_ns" in stats
        avg_raw = lat_dict.get("mean", 0)
        avg_lat_ms = (avg_raw / 1_000_000.0) if is_ns else (avg_raw / 1_000.0)
        
        clat_dict = stats.get("clat_ns") or stats.get("clat") or {}
        percentiles = clat_dict.get("percentile", {})
        is_clat_ns = "clat_ns" in stats
        p99_raw = percentiles.get("99.000000") or percentiles.get("99.00") or 0
        p99_lat_ms = (p99_raw / 1_000_000.0) if is_clat_ns else (p99_raw / 1_000.0)
        
        print(f"📌 [{m.upper()}] 性能指标:")
        print(f"   平均 IOPS     : {iops:,.0f}")
        print(f"   平均吞吐量   : {bw_mib:.2f} MiB/s ({bw_mib*1.04858:.2f} MB/s)")
        print(f"   平均响应延迟 : {avg_lat_ms:.3f} ms")
        print(f"   p99 核心延迟  : {p99_lat_ms:.3f} ms")
        print("-" * 50)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VPS FIO 自动化测试与可视化脚本")
    parser.add_argument("-m", "--mode", choices=["write", "mix"], default="mix",
                        help="测试模式: write (4K随机写) 或 mix (70/30随机读写混合)。默认: mix")
    parser.add_argument("-f", "--file", default="./test_file.img",
                        help="测试文件路径。默认: ./test_file.img")
    parser.add_argument("-s", "--size", default=None,
                        help="测试文件大小 (例如 1G, 2G, 4G)。若未指定，write 默认 10G，mix 默认 4G")
    parser.add_argument("-t", "--time", type=int, default=60,
                        help="测试持续时间（秒）。默认: 60秒")
                        
    args = parser.parse_args()
    
    try:
        raw_json = run_fio(args.mode, args.file, args.time, args.size)
        print_pretty_summary(raw_json, args.mode)
        read_series, write_series = parse_time_series_log()
        generate_chart(args.mode, read_series, write_series)
        cleanup_logs()
        print("\n✨ 测试全部完成！")
    except KeyboardInterrupt:
        print("\n🛑 测试被用户中断。")
        cleanup_logs()
