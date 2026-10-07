# DGStudio 模块市场（dgstudio-modules-market）

本仓库是 **DGStudio**（[DG-LAB-Studio](https://github.com/KelierAndes/DG-Lab-Studio)）
的**模块市场总仓库**，采用与 AstrBot 插件生态一致的仓库管理方式：

* **每个联动模块一个独立仓库**，命名 `dgstudio-modules-<模块 id>`；
* 本总仓库通过 **GitHub Actions** 自动发现、拉取并解析各子仓库，
  生成统一的市场清单 [`market.yaml`](market.yaml)；
* DGStudio「模块」页（模组市场）**只读取 market.yaml** 这一个配置文件，
  下载模块时再按清单指向的子仓库取文件。

```
dgstudio-modules-osc_bridge ─────┐
dgstudio-modules-alice_cradle ───┤   GitHub Actions（每日 / 手动）
dgstudio-modules-vision_link ────┼──────────────────────► market.yaml ◄── DGStudio 模块页读取
dgstudio-modules-strength_logger─┘      拉取 + 解析 META / requirements.txt
```

## 模块列表

| 模块 | 仓库 | 版本 | 依赖 | 说明 |
|---|---|---|---|---|
| **VRChat OSC 联动** | [dgstudio-modules-osc_bridge](https://github.com/KelierAndes/dgstudio-modules-osc_bridge) | 1.11.0 | `python-osc` | 头像参数动态建表，核心参数映射表双向表达式驱动 |
| **Alice in Cradle 联动** | [dgstudio-modules-alice_cradle](https://github.com/KelierAndes/dgstudio-modules-alice_cradle) | 0.6.5 | 无（标准库） | 游戏侧 MOD 上报 HP/MP 等数值，映射表求值驱动设备并回传状态；携带 BepInEx 游戏模组 |
| **画面识别联动** | [dgstudio-modules-vision_link](https://github.com/KelierAndes/dgstudio-modules-vision_link) | 0.3.2 | `opencv-python-headless`（OCR 可选） | OpenCV 检测屏幕画面（颜色/图片/数值/数值条）产生实时参数 |
| **音频联动** | [dgstudio-modules-sound_link](https://github.com/KelierAndes/dgstudio-modules-sound_link) | 0.3.2 | `numpy` / `sounddevice` / `pyaudiowpatch` | 采集麦克风/系统声音输出响度、频率等映射变量，输出频率跟随声音音高 |
| **灵猫边控联动** | [dgstudio-modules-margin_control](https://github.com/KelierAndes/dgstudio-modules-margin_control) | 0.11.0 | 无（标准库） | 灵猫气压 / 官方边控会话驱动的闭环边控，达限自动释放 |
| **手柄震动联动** | [dgstudio-modules-xinput_oscillate](https://github.com/KelierAndes/dgstudio-modules-xinput_oscillate) | 0.2.1 | ViGEm 驱动 | 经虚拟手柄接收游戏原生 XInput 震动，按映射表派发到核心参数 |
| **强度日志示例** | [dgstudio-modules-strength_logger](https://github.com/KelierAndes/dgstudio-modules-strength_logger) | 0.1.0 | 无（标准库） | 最小完整示例：订阅强度变化写入日志 |

实际可用版本以 [`market.yaml`](market.yaml) 为准。

## 安装方式

### 方式一：DGStudio「模块」页（推荐）

1. 打开 DGStudio → 左侧导航「模块」→「获取在线列表」（首次打开自动获取）；
2. 点「下载」取回模块文件（自动放入应用目录 `modules/`）；
3. 点「安装并启动」——安装时**自动读取模块仓库的 `requirements.txt`** 并
   pip 补装依赖，无需手动处理；卸载 / 更新均**热重载**生效，无需重启。

之后可在「模块」页启停 / 卸载 / 删除，有新版本时在线列表会出现「更新」按钮。

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
