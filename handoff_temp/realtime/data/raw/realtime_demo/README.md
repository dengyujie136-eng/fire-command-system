# 实时火情监测演示数据

此目录与 `data/raw/fir​ms`、Dixie Fire 历史数据完全独立。

课程演示使用 Park Fire 2024 时段的 GOES-18 ABI 公共数据，模拟“卫星数据按 10 分钟到达”：

- C07：3.9 um 短波红外；
- C14：11.2 um 长波红外；
- FDCC：NOAA 官方火点检测参考产品。

数据来源为 NOAA GOES-18 公共 S3，不需要 API Key：

```text
https://noaa-goes18.s3.amazonaws.com/
```

生成清单但不下载：

```powershell
python scripts/download_realtime_demo_goes.py
```

实际下载：

```powershell
python scripts/download_realtime_demo_goes.py --download
```

默认下载 3 个连续的 10 分钟时相。原始 NetCDF 文件较大，程序支持断点式跳过已经存在的完整文件。下载前请确认磁盘空间和网络稳定。

页面和接口中必须将该数据标记为：

```text
pre_downloaded_real_satellite_simulated_reception
```

它是真实卫星数据，但“实时到达”过程是课程演示模拟；不能称作当前时刻实时卫星影像。
