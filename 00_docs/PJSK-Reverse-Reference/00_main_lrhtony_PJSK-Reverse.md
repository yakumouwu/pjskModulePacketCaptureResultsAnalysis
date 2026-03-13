# PJSK研究

- 来源：<https://lrhtony.cn/2024/11/11/PJSK-Reverse/>
- 作者：lrhtony
- 日期：2024-11-12

## 目录

- [环境准备](#环境准备)
- [Hook 思路](#hook-思路)
- [碎碎念](#碎碎念)
- [参考文章](#参考文章)

## 环境准备

作者使用的是可 `root`、可运行 Frida 的 ARM 真机（文中为 Pixel 6）。

文中明确提到一个常见坑：

- x86 模拟器虽然能跑游戏，但 Frida 很难稳定追踪经过 `libhoudini` 转译后的 ARM 库。
- 这会导致你在模拟器环境里很难稳定定位 `libil2cpp.so` 的关键逻辑。

另外还有系统版本兼容问题：

- 文中在 Pixel 6 刷到 Android 15（`AP3A.241105.007`，2024 年 11 月补丁）后，Frida 一度无法正常工作。
- 原因与当时安全补丁和 Frida 的兼容性冲突有关。
- 回退到 A14（7 月补丁）后恢复可用，后续 Frida 版本修复后才再次可用。

这部分给出的核心经验是：

1. 优先 ARM 真机。
2. 不要盲目升系统补丁。
3. Frida 异常时优先做“系统版本 x Frida 版本”矩阵回归。

## Hook 思路

主线流程：

1. 在 `libil2cpp.so` 中定位 metadata 解密流程。
2. 解出 `global-metadata.dat`。
3. 用 `Il2CppDumper` 恢复符号与类型信息。
4. 用 `frida-il2cpp-bridge` 跑调用追踪与函数覆盖。

具体到判定逻辑，文中重点关注：

- `NoteState`
- `JudgeInfo`
- `NoteResult`
- `NoteResultDescription`

并提到 `JudgeInfo` 里会组合判定信息（`System.ValueTuple` 相关泛型实例化引用可作为定位入口）。

对 Note 生命周期的关键观察：

- 一个 Note 在 Miss 前，状态会先到 `Last`。
- 判定结果被设为 Miss 后，状态再进入 `Done`，生命周期结束。

据此可做的 Hook 思路：

- 基于状态流转点（`Last -> Done`）修改判定结果。
- 或者在判定函数入口覆盖入参/返回值。

文中也记录了风控差异：

- 多人 Live 修改判定后很快触发封禁（打一局即 Ban）。
- 单人多次测试未立即封禁。

推测服务端仍有额外校验，可能包括：

- 判定序列一致性（例如 `Last` 与 `Miss` 的配对关系）。
- 触控统计数据（Touch 轨迹/矢量信息等）。
- 其他行为统计字段。

作者还尝试过在 `get_Progress` 上做文章：

- `Progress == 1` 可近似判定点。
- 但该函数按帧高频调用，Note 多时会明显卡顿，工程价值不高。

## 碎碎念

文中补充了几个实操层面的观察：

- 本地确实能看到 Root/Frida 检测相关库与代码路径。
- 但“看到检测逻辑”不等于“当前版本必定强触发封禁”。
- 实际策略可能按服、按场景、按行为特征动态变化。

metadata 方面：

- 日服 `global-metadata.dat` 存在简单异或处理。
- 可通过 `global-metadata.dat` 字符串回溯加载函数，找到 128 bytes 异或序列，再解密。

国服/其他服的内存提取思路：

1. 通过 `ps -ef | grep [包名]` 找 PID。
2. `cat /proc/[pid]/maps | grep global-metadata` 定位内存映射。
3. 使用 `dd` 从进程内存导出 metadata。
4. 按版本特征处理头部（文中提到“删前 8 字节后可用于 Dumper”的场景）。

## 参考文章

- <https://dev.moe/2157>
- <https://mos9527.github.io/posts/pjsk/archive-20240105/>
- <https://blog.mid.red/2023_09_30-58_B2_F1_D5-AF_1B_B1_FA>
- <https://aza.moe/blog?post=2024-10-24-PJSK-Reversing>
- <https://www.neko.ink/2023/10/15/dump-il2cpp-executable-from-memory/>
