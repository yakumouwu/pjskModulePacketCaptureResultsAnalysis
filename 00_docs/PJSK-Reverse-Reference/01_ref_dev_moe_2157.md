# Project SEKAI 游戏分析

- 来源：<https://dev.moe/2157>
- 作者：Coxxs
- 发布：2020-11-29（更新 2020-12-01）

## 目录

- [问题背景](#问题背景)
- [资源分析](#资源分析)
- [网络通信分析](#网络通信分析)
- [总结](#总结)

## 问题背景

作者起初是在真机环境中遇到 `通信エラー`，一开始怀疑是 SafetyNet / MagiskHide 相关问题，但进一步排查发现核心原因并不在 Root 本身，而在网络环境。

文中记录到：

- 游戏对代理/加速器/匿名出口有明显检测。
- 可能使用了类似 GeoIP 匿名地址库的策略。
- 排除网络因素后游戏可正常进入。

文章同时给出了当时可观察到的核心域名：

- `assetbundle.sekai.colorfulpalette.org`
- `assetbundle-info.sekai.colorfulpalette.org`
- `game-version.sekai.colorfulpalette.org`
- `production-game-api.sekai.colorfulpalette.org`
- `production-web.sekai.colorfulpalette.org`

## 资源分析

### 资源类型

游戏基于 Unity IL2CPP，资源按来源分为两大类：

1. 本地随包资源。
2. 按需下载（OnDemand）资源。

本地资源可直接使用 AssetStudio 解包；按需下载资源位于：

- `sdcard/Android/data/{package}/data`

### 资源混淆

按需资源存在轻量混淆，关键点如下：

- 相关函数：`Sekai.AssetBundleManager.XORStream`（`libil2cpp.so`）。
- 去掉前 `0x4` 字节标志位后，头部 `0x80` 字节做异或处理。
- 异或模式：与 `FF FF FF FF FF 00 00 00` 循环作用。

结论：

- 这不是强加密，更像“低成本拖慢分析”的工程折中。
- 处理后可以还原出标准 UnityFS 头。

文中给出了对应工具：

- `sekai-xor`：<https://github.com/Coxxs/sekai-xor>

### Live2D 资源

文章指出 Live2D 资源“未加密但不直观”：

- 模型文件（`.moc3` / `.model3.json` / `.physics3.json` / 贴图）可直接导出。
- 动作资源是 Unity `.anim`，不是直接的 `.motion3.json`。

难点在参数名：

- `.anim` 内记录的是 `crc32(参数类型 + '/' + 参数名)`，不是明文字符串。
- 无法直接套用原版 `UnityLive2DExtractor` 流程。

作者的处理方法：

1. 从 `.moc3` 中提取可见 ASCII 参数名。
2. 对参数名计算 CRC32，反查 `.anim` 轨道键。
3. 批量转回 `.motion3.json`。

工具：

- `SEKAI2DMotionExtractor`：<https://github.com/Coxxs/SEKAI2DMotionExtractor>

### 音频资源

文中记录：

- 音频封装为 `.acb`（CRIWare 体系）。
- 可通过 CriTools 解包处理。
- 当时观察到其密钥与某些同类手游一致，但密钥落点在本文里未完全追到。

### 按需资源规模

按需资源体量很大（文中约 4GB），且部分资源需要触发特定场景才会下载。

这意味着：

- 若只靠“手动跑流程”难以拿全量资源。
- 结合网络层抓包与清单分析更高效。

## 网络通信分析

作者将链路分成三层：

1. 业务序列化：MessagePack。
2. 业务加密：固定 `AES-128-CBC`（Key/IV）。
3. 传输层加密：TLS。

### TLS 校验

文中提到仅导入用户根证书不足以完成 MITM，推测校验在 `libunity.so` 内部 curl 路径执行。

通过二进制 patch 可关闭 curl 的证书校验，之后抓包链路才可控。

### AES 密钥定位

密钥初始化位置：

- `Sekai.APIManager` 构造流程。

密钥材料来源：

- 编译时写入 `global-metadata.dat`。

因此可通过 metadata 静态定位得到 Key/IV，再对请求和响应进行还原。

### 报文可读化

在拿到 AES 参数后：

- 解密 MessagePack 负载。
- 转换 JSON 便于分析。
- 可进一步挖出资源清单、下载路径等关键信息。

## 总结

文章给出的逆向路线比较完整：

1. 先解决运行环境与网络进入问题。
2. 再处理资源层（AB 混淆 / Live2D / 音频封装）。
3. 最后打通网络层（TLS + AES + 序列化）。

工程上最关键的经验是：

- 不要一开始就陷入“解某个算法细节”，先把完整链路跑通。
- 把高频重复步骤（解混淆、导出、转换）脚本化，后续版本跟进成本会显著降低。
