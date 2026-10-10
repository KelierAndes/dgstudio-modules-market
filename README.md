# DGStudio 模块市场（dgstudio-modules-market）

本仓库是 **DGStudio**（[DG-LAB-Studio](https://github.com/KelierAndes/DG-Lab-Studio)）
的**模块市场总仓库**，采用与 AstrBot 插件生态一致的仓库管理方式：

* **每个联动模块一个独立仓库**，命名 `dgstudio-modules-<模块 id>`；
* 本总仓库通过 **GitHub Actions** 自动发现、拉取并解析各子仓库，
  生成统一的市场清单 [`market.yaml`](market.yaml)；
* DGStudio「模块」页（模组市场）**只读取 market.yaml** 这一个配置文件，
  下载模块时再按清单指向的子仓库取文件。

```
dgstudio-modules-osc_bridge          ──────┐
dgstudio-modules-alice_cradle        ──────┤
dgstudio-modules-vision_link         ──────┤
dgstudio-modules-sound_link          ──────┼──────► market.yaml ◄── DGStudio 模块页读取
dgstudio-modules-margin_control      ──────┤
dgstudio-modules-xinput_oscillate    ──────┤
dgstudio-modules-strength_logger     ──────┘
```

（GitHub Actions 定时 / 手动拉取各子仓库，解析其 `META` 与 `requirements.txt`
生成 `market.yaml`。）

## 模块列表

所有模块都是**纯输入设备**：只把外部数据（头像参数、游戏数值、画面检测、声音
采集、手柄震动…）**登记成 DGStudio「事件流」页右侧变量表的变量**，供画布上的卡片
取用与运算；任何设备动作（强度 / 波形 / 开火 / 脉冲流）都由用户在事件流里用
**写入卡片**驱动，模块内部不再有映射表，也不再自己下发（核心会拦截并记日志）。

| 模块 | 仓库 | 版本 | 依赖 | 说明 |
|---|---|---|---|---|
| **VRChat OSC 联动** | [dgstudio-modules-osc_bridge](https://github.com/KelierAndes/dgstudio-modules-osc_bridge) | 1.16.0 | `python-osc` | 设备接入即把全部 OSC 路径按变量登记（变量名 = `avatar/parameters/<名>` / `<前缀>/<名>`，落在可改名栏，改名即改收发地址）；可读 / 可写按参数语义标注 |
| **Alice in Cradle 联动** | [dgstudio-modules-alice_cradle](https://github.com/KelierAndes/dgstudio-modules-alice_cradle) | 0.7.1 | 无（标准库） | 游戏侧 BepInEx 模组上报 HP / MP / EP 等通道数值，登记成只读变量；携带游戏模组可一键释放 |
| **画面识别联动** | [dgstudio-modules-vision_link](https://github.com/KelierAndes/dgstudio-modules-vision_link) | 0.4.1 | `opencv-python-headless`（OCR 可选） | OpenCV 检测屏幕画面（颜色 / 图片 / 数值 / 数值条）与 OCR，检测值登记成只读变量 |
| **音频联动** | [dgstudio-modules-sound_link](https://github.com/KelierAndes/dgstudio-modules-sound_link) | 0.5.1 | `numpy` / `sounddevice` / `pyaudiowpatch` | 麦克风与系统声音（WASAPI 回环）各输出左右响度 / 频率共 8 个只读变量，接到写入卡即可让输出频率跟音高、电平跟响度 |
| **灵猫边控联动** | [dgstudio-modules-margin_control](https://github.com/KelierAndes/dgstudio-modules-margin_control) | 0.13.0 | 无（标准库） | 灵猫气压 / 官方边控会话驱动的闭环边控，达限自动释放；登记气压与边控状态变量，按键动作可暂停 / 恢复闭环 |
| **手柄震动联动** | [dgstudio-modules-xinput_oscillate](https://github.com/KelierAndes/dgstudio-modules-xinput_oscillate) | 0.3.0 | ViGEm 驱动 | 经虚拟手柄接收游戏原生 XInput 震动，登记左右震动量与合成状态变量，由事件流回写设备强度 |
| **强度日志示例** | [dgstudio-modules-strength_logger](https://github.com/KelierAndes/dgstudio-modules-strength_logger) | 0.1.0 | 无（标准库） | 最小完整示例：订阅强度变化写入日志，不登记任何变量 |

实际可用版本以 [`market.yaml`](market.yaml) 为准。模块接口与「登记变量」的写法见
**[联动模块开发文档 `EXTENSIONS.md`](EXTENSIONS.md)**。

## 安装方式

### 方式一：DGStudio「模块」页（推荐）

1. 打开 DGStudio → 左侧导航「模块」→「获取在线列表」（首次打开自动获取）；
2. 点「下载」取回模块文件（自动放入应用目录 `modules/`）；
3. 点「安装并启动」——安装时**自动读取模块仓库的 `requirements.txt`** 并
   pip 补装依赖，无需手动处理；卸载 / 更新均**热重载**生效，无需重启。

之后可在「模块」页启停 / 卸载 / 删除，有新版本时在线列表会出现「更新」按钮。

编译型依赖靠各模块仓库自带的 `wheels/` **离线**装进 `modules/<id>/_deps/`，
正常情况不需要网络；自带 wheel 与 DGStudio 内置 Python 的 ABI 不符时宿主只跳过
那几个（其余照用），并记在日志里。ABI 纪律见
**[EXTENSIONS.md §1.4](EXTENSIONS.md)**。

### 方式二：手动放置

把子仓库内容整个放入 DGStudio 应用目录 `modules/<模块 id>/`，重启（或点
「扫描模块目录」）后即可在模块页看到；第三方依赖需自行
`pip install -r requirements.txt`。

## 模块 API

模块 API（生命周期、`ModuleContext`、配置声明、按键动作、联动参数模型）见
**[EXTENSIONS.md](EXTENSIONS.md)**。

## 许可

与 DGStudio 相同，以 **GNU General Public License v3.0**（GPL-3.0）发布，
全文见 [LICENSE](LICENSE)。各模块仓库同许可；模块运行于 DGStudio 宿主并
链接其核心代码。
