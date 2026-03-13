# 世界计划 缤纷舞台！feat. IL2Cpp

- 来源：<https://aza.moe/blog?post=2024-10-24-PJSK-Reversing>
- 日期：2024-10-24
- 标题副注：从零开始解密 pjsk 的网络请求

## 目录

- [背景](#背景)
- [1. 获取 APK 与基础分析](#1-获取-apk-与基础分析)
- [2. metadata 提取](#2-metadata-提取)
- [3. API 加解密定位](#3-api-加解密定位)
- [4. 报文解密验证](#4-报文解密验证)

## 背景

作者的目标是分析 PJSK 排行等数据并做自动化，因此先从抓包入手。使用 Reqable 抓到请求后发现：

- 请求体与响应体都不是明文。
- 不是简单编码问题，CyberChef 等常规“糊糊器”无法直接还原。

随后确认业务层有 AES 加密，且关键入口在 `APIManager` 相关逻辑中。

## 1. 获取 APK 与基础分析

文章从 `4.0.0` 的 XAPK 开始，拆包后得到：

- 共享资源安装包
- 架构相关安装包（arm64）

用 `apktool` 解包后，先定位两类关键文件：

1. `lib/arm64-v8a/libil2cpp.so`
2. `assets/bin/Data/Managed/Metadata/global-metadata.dat`

作者尝试直接把这两者喂给 `Il2CppDumper`，报错：

- `Metadata file supplied is not valid metadata file`

对比标准 metadata 头后确认：

- 正常头应为 `0xAF1BB1FA`
- 当前文件头不符，说明 metadata 被处理（加壳/加密）

## 2. metadata 提取

作者先试了自动化方案（Zygisk-IL2CppDumper），未成功产出可用结果，改走内存提取：

1. 运行游戏并附加 Game Guardian。
2. 搜索内存中的 `AF1BB1FA` 特征。
3. 导出命中区间为新的 `global-metadata.dat`。

导出后重新运行 `Il2CppDumper` 可成功生成 `dump.cs` 等输出。

文中提到虽然有 `This file may be protected` 提示，但该场景主要是 `JNI_OnLoad` 命中触发的预警，不代表流程失败。实际结果中已能拿到 APIManager 定义与相关类型信息，说明 metadata 提取已有效。

## 3. API 加解密定位

在 `dump.cs` 里可看到 API 管理与加密对象结构，但函数实现体仍在二进制内，需要回到 `libil2cpp.so` / IDA。

文章的定位策略是：

- 先用 metadata 输出建立类型与方法名锚点。
- 再在 IDA 中对照字符串与调用关系反推实现。
- 沿着 `APIManager` / `Crypt` / AES 初始化路径追 Key/IV。

作者还补充了动态链路思路：

- 静态找到可疑位置后，再用 Frida 做运行时确认。
- 通过 hook 或对象读取拿到最终有效参数。

## 4. 报文解密验证

拿到加密参数后，流程变成：

1. 导出抓包得到的请求/响应二进制 payload。
2. 用同参数执行 AES-CBC 解密。
3. 对还原结果做结构化解析（如 MessagePack/JSON 转换）。

作者记录了最终结果：

- 报文可稳定还原。
- 可以继续围绕排行榜、资源清单、接口字段做自动化。

## 备注

- 本文内容来自站点实际 post 数据（`2024-10-24-PJSK-Reversing`）。
- 已去除站点导航、索引组件、脚本样式等与正文无关部分，仅保留与逆向流程直接相关内容。
