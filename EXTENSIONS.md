# DGStudio 联动模块开发文档

> 本文档维护在模块市场总仓库 **dgstudio-modules-market**。DGStudio 的联动能力
> 全部由**联动模块**提供：每个模块一个独立仓库（`dgstudio-modules-<id>`），总仓库
> 经 Actions 聚合各仓库生成市场清单 `market.yaml`，用户在应用「模块」页按需下载、
> 启停与更新。模块运行在 Python 宿主 `DGStudio-bridge.exe` 里，通过
> `ModuleContext`（下称 `ctx`）读取设备状态、登记变量、订阅事件；界面是 Flutter
> 外壳，模块不需要写任何界面代码。

---

## 1. 快速开始

### 1.1 目录与文件

**模块仓库**（每模块一个，命名 `dgstudio-modules-<id>`）：

```
dgstudio-modules-<id>/
├── modules/<id>/plugin.py       模块入口：META + 模块类（也可直放仓库根）
├── modules/<id>/requirements.txt  pip 依赖（可选，见 §1.4）
├── modules/<id>/flow/            默认事件流配置（可选，见 §1.2.1）
├── modules/<id>/bindings/        默认按键映射（可选，见 §1.2.1）
├── modules/<id>/mods/            游戏端模组（可选，见 §2.3）
├── tests/                        模块单测（可选，见 §7）
└── README.md / LICENSE
```

**市场总仓库**（本仓库）：

```
dgstudio-modules-market/
├── market.yaml                  市场清单（Actions 自动生成，勿手改）
├── sources.txt                  API 发现失败时的手动兜底清单
├── _tools/build_market.py       清单生成工具（CI / 本地双模式）
└── .github/workflows/market.yml 定时 / 手动重建 market.yaml
```

**应用目录**（DGStudio 运行时）：

```
DGStudio/
├── DGStudio.exe / DGStudio-bridge.exe   界面外壳 / 模块宿主
├── modules/<id>/                        已下载模块（含私有依赖 _deps/）
├── config.json                          主配置
└── config/
    ├── modules.json                     各模块启用状态
    └── <settings_key|id>.json           各模块私有设置
```

每个模块最少只需一个 `plugin.py`。包形式（带 `__init__.py` 的多文件模块）与单文件
形式都能被市场解析、被宿主加载；用户把新模块放进应用目录 `modules/` 同样生效。
第三方依赖不进核心、不随主程序分发，写在模块仓库的 `requirements.txt` 里。

### 1.2 最小模块

`modules/hello/plugin.py`：

```python
META = {
    "id": "hello",                # 全局唯一，与文件夹同名
    "name": "示例模块",
    "short": "HELLO",             # 事件流卡片与概览页的来源简写（可省）
    "version": "0.1.0",
    "description": "一句话说明（显示在模块页）。",
}

from plugins import ModuleBase

class HelloModule(ModuleBase):
    id = META["id"]
    name = META["name"]
    version = META["version"]
    description = META["description"]
    settings_key = ""             # 留空 → 设置文件 config/hello.json

    def on_load(self, ctx):       # 加载时一次：读配置、订阅事件
        self.ctx = ctx

    def on_unload(self):          # 卸载时一次：退订事件、释放资源
        pass

    async def start(self):        # 启动（引擎 asyncio 循环上）
        pass

    async def stop(self):         # 停止（卸载前宿主先调用）
        pass
```

要点：

* `META` 由模块页与市场**不执行代码**读取（AST 解析字面量），必须是纯字面量字典；
* 宿主取 `plugin.py` 中**第一个**符合协议的类：继承 `ModuleBase`，或鸭子类型
  （提供 `id` / `name` / `on_load` / `on_unload` 即可）。鸭子类型缺失的
  `start` / `stop` / `is_running` 自动补空实现；
* 常用 `META` 键：

| 键 | 用途 |
|---|---|
| `id`（必填）/ `name` / `version` / `description` | 基本信息 |
| `short` | 事件流卡片标题与概览页数据流的来源简写（大写，如 `OSC` / `AIC`） |
| `settings_key` | 设置文件名；留空用模块 id |
| `actions` | 按键动作静态声明（§3），供模块未加载时反查 |
| `config` | 设置项声明（§4.1） |
| `default_enabled` | 未被显式启停过时是否默认启用 |
| `mods` | 游戏模组释放目标与定位标记（§2.3） |
| `realtime_manager` | 声明本模块有「参数名 ← 检测行为」的实时管理表（如画面识别） |
| `params` / `reads` | 模块自用的静态声明表，宿主不直接读取；登记仍靠实例钩子（§4.2） |
| `temps` | 静态兜底行，实例没有 `temp_specs()` 时使用（§4.2） |

### 1.2.1 自带默认配置（flow/ 与 bindings/）

模块可在仓库里放 `flow/<名称>.json`（单配置事件流）与 `bindings/<名称>.json`
（`{"bindings": {按键位: 动作}}` 或直接映射表）。**不需要写注入代码**，宿主统一处理：

* 模块装载时登记为**可选**配置档；停用 / 卸载时移除，正在使用的那份自动切回「默认」；
* 只在配置缺失（首次注入或用户删掉后补回）或**模块版本升级**时写盘，且只刷新自己
  注入过的那几份；用户自建的同名配置永不被覆盖；
* 登记不切换当前配置。模块卡「一键套用」才切换：事件流取文件名以「默认」开头的
  第一份（否则取排序第一份），按键映射只切换以「默认」开头的，其余仅进入下拉列表；
* 配置文件夹被清空后，重新装载模块会自动补注。

### 1.3 生命周期

```
市场「安装」   下载 → 补依赖 → load()（不启用）
详情「启动」   补依赖 → load() → start() → 置启用（重启后自启）
「停止」       stop() → on_unload() → 收回默认配置档 → 置停用
「更新」       停用旧版 → 下载新版 → load()（回到未启用，再点启动）
「卸载」       停止 + 删除模块文件（设置文件保留，重装即恢复）
```

* `start` / `stop` 运行在引擎 asyncio 循环上，可直接 `await`；非异步上下文用
  `ctx.submit(coro)` 提交（返回 Future）；
* 事件回调运行在引擎线程或协议接收线程：只做轻量处理，**不操作 UI、不阻塞**，
  耗时逻辑用 `ctx.submit()` 切回引擎循环；
* **热重载**：卸载会清理该模块的导入缓存、`__pycache__` 与私有依赖路径，所以
  「卸载 → 启动」或「更新 → 启动」即运行新代码，无需重启应用；
* 模块**未启用**时，模块页只显示详情（说明、依赖、README、游戏模组），设置卡与
  「一键套用」隐藏——此时改了设置也不会生效。

### 1.4 依赖声明（requirements.txt）

第三方依赖写在模块目录的 `requirements.txt`，随模块一起下载；「安装」与「启动」时
自动补装缺失项，「安装依赖」按钮可手动重试：

```
python-osc>=1.9                      # 必装依赖
# 「!」前缀 = 可选依赖：--no-deps 尽力安装，失败不阻断
!some-optional-addon>=1.0
```

无 `requirements.txt` 时回退读 `META["dependencies"]`（旧式声明，仅作兼容）。

* **源码运行**：装进当前解释器环境（建议 venv）。引擎单独跑用
  `python -m bridge.server`，界面用 `flutter run -d windows`；
* **打包版**：**首选模块自带的 `wheels/`**——安装时逐个解包合并进私有
  `modules/<id>/_deps/`（离线、按 dist-info 幂等），剩余缺失才经宿主内置的
  `_python/` 子进程 pip 兜底；`_deps/` 会在模块装载前挂到 `sys.path` 最前；
* 可用性探测按「环境元数据 → `_deps` 元数据 → import 名」进行，
  `opencv-python-headless` → `cv2` 这类包名 / import 名差异自动映射；
* 市场清单由总仓库 Actions 解析各仓库的 `requirements.txt` 生成，模块页下载前
  即可展示依赖。

**自带 wheel 的 ABI 纪律**：打包版内置 Python 是构建机解释器版本（当前 `cp314`）。
`abi3` 与 `py3-none-any` 通用，其余 wheel 只对同一个小版本生效：

```
pip download --only-binary=:all: --python-version 314 --abi cp314 \
    --platform win_amd64 -d modules/<id>/wheels <包名>
```

宿主逐个判断 ABI，不符的跳过并在日志点名（不会让整包自带依赖作废）。但没有可靠的
联网兜底：镜像不通、证书过期、目标机离线都会导致依赖安装失败。**发布前**由
`build_exe.py` 检查所有模块 `wheels/` 的 ABI（不符直接拒绝构建，
`--allow-stale-wheels` 可强行跳过）。宿主**只扫 `wheels/`**，因此不要放只给子进程
使用的 wheel（如 `onnxruntime` 在冻结主进程 import 即段错误）；这类附属环境另起
目录（vision_link 的 `ocr_wheels/`），由模块自己的安装逻辑取用。

---

## 2. ModuleContext API

模块只应通过 `ctx` 访问引擎。全部公开成员如下。

### 2.1 基础与设备状态

| 成员 | 说明 |
|---|---|
| `ctx.engine` | 引擎实例（仅用于传给需要的对象，日常用下列封装） |
| `ctx.events` | 事件总线（§5） |
| `ctx.module_id` | 本模块 id |
| `ctx.log(msg)` | 写应用日志（自动带 `[模块id]` 前缀），进日志页；开启文件日志时也写 `dgstudio.log` |
| `ctx.submit(coro)` | 协程提交到引擎事件循环，返回 Future |
| `ctx.settings` | 模块私有设置字典（写穿持久化，§4.1） |
| `ctx.get_state()` | 当前 `EngineState`（含全部 `Slot`） |
| `ctx.devices()` | 已接入设备列表 `[{slot_id, name, type, family}]` |
| `ctx.resolve_slot(slot_id=None, family=None, output_only=False)` | 解析目标设备：显式 id 优先 → 按 family → 默认第一台（`output_only` 排除纯传感器灵猫） |

设备家族：`COYOTE`（郊狼，电刺激）、`OVC`（负鼠，振动）、`BMTR`（灵猫，气压
传感器）；`dglab.state.family_of(type)` 从设备型号得家族。

### 2.2 强度与波形（只读）

```python
params = ctx.intensity_params()            # 默认输出设备；也可传 slot_id
```

| 字段 | 含义 |
|---|---|
| `slot_id` / `connected` | 解析到的设备（无设备为 None）/ 是否在线 |
| `strength` / `strength_limit` | `{"A", "B"}` 当前强度 / 硬件上限 |
| `channel_status` | 探活：0/2 正常，1 异常 |
| `max_strength` | 最大强度上限（设备独立值，缺省全局 100） |
| `strength_step` | 步长（已按设备量化，OVC 至少 10） |
| `fire_strength` | 旧版双通道共用开火强度（遗留键；0 = 跟随上限） |
| `fire_strength_a` / `fire_strength_b` | A/B 通道独立开火强度（0 = 跟随该设备上限） |
| `fire_duration_s` | 开火时长（秒） |
| `wave_duration_s` | Socket V3 波形循环时长（秒） |
| `wave` | `{"A", "B"}` 当前选定波形名 |

逐项便捷读取：

| 方法 | 返回 |
|---|---|
| `ctx.strength(slot_id, "A")` | 当前强度 |
| `ctx.strength_limit(slot_id, "A")` | 硬件上限 |
| `ctx.device_setting(slot_id, key)` | 设备级设置（回退全局），任意键 |
| `ctx.device_step(slot_id)` | 量化后的步长 |
| `ctx.wave_selection()` | `{"A": 名, "B": 名}` |
| `ctx.wave_order("COYOTE")` | 该家族波形名序列（静默 / 持续在前） |

**模块是纯输入设备，不能直写设备。** 为兼容旧模块，`set_strength` /
`add_strength` / `reset_strength` / `set_wave` / `set_intensity_param` /
`push_pulse_stream` / `fire*` / `zap` 仍然存在，但调用一律被拦截：返回 `None`，
并写一条日志提示改用事件流写入卡。唯一直通的是安全闸
`ctx.emergency_stop()`（清零全部输出、取消开火保持）。

要驱动设备，就把数据登记成变量，由用户在「事件流」画布上用**写入卡**接线
（§4.2）：强度 / 波形 / 开火 / `in_pulse_a/b` 脉冲流等核心写入参数都在卡片面板的
「核心变量」分类里。同一份外部数据因此可以接不同设备、加运算与分支，而不必每个
模块各写一套下发逻辑。

### 2.3 游戏模组携带与安装（通用接口）

携带游戏端模组的模块在 META 里声明释放目标与定位标记：

```python
META = {"id": "...", ...,
        "mods": {"dest": "BepInEx/plugins/<模组名>",   # 相对游戏根
                 "marker": "Game.exe"}}                # 游戏主程序名（自动扫描）
```

载荷放在模块目录（随模块一起下载分发）：

| 路径 | 内容 |
|---|---|
| `mods/` | 编译好的模组文件（释放到 dest 的内容） |
| `mods/BepInEx/`（可选） | 需随模组合并安装的 BepInEx 文件 |
| `vendor/BepInEx_win_*.zip`（可选） | BepInEx 5 官方发行包，目标缺 BepInEx 时自动安装 |

| 方法 | 说明 |
|---|---|
| `ctx.game_mods_dir()` | 模块携带的 `mods/` 目录（无载荷返回 `None`） |
| `ctx.scan_game_roots(roots=None, max_depth=3)` | 按 marker 在盘符根浅层扫描游戏根目录（可传 `roots` 收敛范围） |
| `ctx.install_game_mod(game_root)` | 释放模组；缺 BepInEx 时自动安装（`mods/BepInEx/` → `vendor/` zip）；目标不含游戏主程序抛 `ValueError` |

alice_cradle 模块即示范实现：模组源码 `AliceInCradleLink/` +
`dotnet build -t:Deploy` 产出 `mods/` 载荷 + `vendor/` 携带发行包。

---

## 3. 按键绑定动作（负鼠按键 → 模块功能）

加载时注册动作 → 控制页绑定选择框出现该项；卸载时自动撤下。OSC 模块的
「发送 OSC 参数…」即由此机制提供。

```python
from plugins import ButtonAction

def button_actions(self) -> list:
    return [ButtonAction(
        key="myaction",                  # 绑定值前缀，全局唯一（重复只接受第一个）
        label="我的动作…",                # 选择框显示文本
        argument_placeholder="参数…",     # 非空 → 绑定值带参数 "<key>:<参数>"
        on_press=self._on_press,         # (slot_id, argument | None)，同步调用
        on_release=self._on_release,     # 可选
    )]
```

* 绑定值存于按键映射配置，形如 `"myaction"` 或 `"myaction:参数"`；
* 回调同步调用（可能来自协议接收线程），应快速返回，耗时操作 `ctx.submit()`；
* `META["actions"]` 是静态声明，供模块**未加载**时把配置里的绑定反查到模块。

应用启动与模块卸载时会检查绑定：引用了未加载模块的动作就发出
`binding_modules_missing` 事件并写日志；按键面板同时把对应键位标成告警，加载对应
模块后自动恢复。未识别的动作不会被清除，方便用户先装模块再回来。

---

## 4. 模块设置与联动参数

### 4.1 设置文件与配置声明

* 设置独立于主 `config.json`：每模块一个 `config/<settings_key|id>.json`，宿主
  自动读写；启用状态集中在 `config/modules.json`；旧版主配置里的模块段首次运行
  时自动迁移；
* `ctx.settings` 是**写穿字典**：顶层键写入 / 删除 / 更新立即落盘。**嵌套字典的
  就地修改不落盘**，需要时显式调用 `ctx.settings.save()`；
* `META["default_enabled"]: true` → 从未被显式启停过的模块随应用自启（模块下载后
  仍以显式「启动」为准）。

```python
self.threshold = int(ctx.settings.get("threshold", 50))
ctx.settings["threshold"] = 80        # 即时落盘
```

**配置项声明 `META["config"]`**（纯字面量；实例可覆写 `config_spec()`，优先于
META）。宿主装载时自动补齐缺失项写入设置文件，模块页据此渲染编辑控件：

```python
META = {
    ...,
    "config": {
        "port": {"label": "输出端口", "type": "int", "default": 9000,
                 "min": 1, "max": 65535, "desc": "发送数值的目标端口"},
    },
}
```

| type | 控件 | 附加字段 |
|---|---|---|
| `int` / `float` | 步进框（修改即落盘，按 min/max 钳制） | `min` / `max` / `step`；`unit` 仅 float 显示 |
| `str` | 文本框 | — |
| `bool` | 开关 | — |
| `choice` | 下拉（只能选预设值） | `choices` |
| `map` | 每个子键一行文本框 | — |
| `list` | 列表 / 表格，按 `columns` 渲染 | `columns` / `fixed` |

公共字段：`label`（显示名）、`default`、`desc`（说明文字）。

`list` 的 `columns` 是列定义：
`[{id, label, type(str|choice), hint?, choices?, labels?, readonly?}]`（`labels` 与
`choices` 一一对应，用于显示中文选项；`readonly` 列只显示、不可改）。
`fixed: true` 表示行由模块现算、不落盘（如 OSC 按在连设备生成的参数表），只允许
改名字：宿主读设置时用实例钩子 `derived_rows()` 的返回值覆盖该项：

```python
def derived_rows(self) -> dict[str, list[dict]]:
    return {"device_params": [{"address": "...", "dir": "inout", "type": "Float"}]}
```

这些行只给界面看，不要写进设置文件，否则设备一断、参数一改名就成了过期状态。

### 4.2 变量登记模型（模块 → 事件流变量表）

模块不驱动设备，只**向核心登记变量**；用户在「事件流」页把变量拖成读数卡 / 写入卡，
动作才会发生。登记由实例钩子提供，核心按名字合并（方向取并集、`renamable` 取或）。
同一参数多处登记时一处 `in`、一处 `out` 会合并成「读写」；没写方向按 `in` 处理：

| 钩子 | 返回 | 用途 |
|---|---|---|
| `link_params()` | `[{name, label, dir, type, renamable}]` | 模块产出的参数 / 读数。也接受 `(名, 说明)` 元组，但会丢失方向与 `renamable`，按只读处理 |
| `read_params()` | 同上 | 与 `link_params()` 成对，返回模块**可写**的参数（`dir="out"`）；事件流写入后用 `ctx.get_temp(name)` 取回 |
| `temp_specs()` | `[{key\|name, label, dir, type, desc, renamable}]` | 随运行状态实时算出的行（如 OSC 按当前在连设备生成全部路径变量，没连上就返回空）。宿主也据此在卸载时清理共享值残值 |
| `rename_var(old, new)` | 空串 = 成功，中文 = 失败原因 | 可选。用户改这一行名字时调用：模块改自己的收发地址，返回空串后核心自动改接画布上引用旧名的卡片 |
| `META["temps"]` | `[{name, label, dir, ...}]` | 静态兜底；实例未提供 `temp_specs()`（或返回空）时使用 |

`dir` 三取一：`in` = 宿主可读（模块产出的读数，**不写时的默认值**）、`out` = 宿主
可写（用户能把数值写回模块）、`inout` = 双向。方向按**参数语义**判定，不要按变量名
路径判定：能被驱动下去的量（强度、波形、开火、脉冲频率…）标可写，只读得出的量
（电量、连接状态、通道探活、气压…）标可读，既下发又回读的行标读写。
`renamable: True` 的行落在变量表的「可改名参数」栏（名称格是输入框），否则落在
「系统参数 · 不可改名」栏。

值的来与去：模块写自己的信号表（`ctx.set_temp(key, value)` 或运行时对象的
`.signals`），核心的共享值空间据此给变量供实时值；反方向由事件流的写入卡调
`ctx.set_temp` 落回模块，模块在自己的循环里用 `ctx.get_temp` 取用。

**运行时对象的约定名**（不用则实时值静默为空，别改名）：核心按 `instance.bridge`
（或 `instance.server`）→ `.engine` 找到模块的运行时挂接点，读它的 `signals`
（外部读数，事件流现值来源），并调 `attach_temps(共享表)` 与 `pump()`（宿主写入
后的通知）。取不到时核心静默返回空字典，不报错——画布上只会表现为变量一直没有
数据，所以这条链路建议用单例钉住。

用户在画布上的接线手段（模块无需实现）：变量表按住行左侧拖动柄拖到画布即生成
读数卡 / 写入卡；核心写入卡（强度 / 波形 / 开火 / 脉冲流等）与核心读出卡
（`COYOTE.Battery`、`Action` 等）在卡片面板的「核心变量」分类里，不进变量表。
旧版设置里的映射表（`mappings` / `outputs`）与自动迁移产物会在首次读取设置时
自动清除，模块不需要处理。

> 默认头像参数名的生成规则（设备前缀 + 信号模板）在核心 `dglab/naming.py`
> （`default_input_name` / `default_output_name` / `device_osc_names`），改名覆盖表
> 写在模块设置文件的 `param_names` 里，模块与核心共用。

---

## 5. 事件总线（ctx.events）

`cb = ctx.events.on(event, callback)` 注册（返回回调引用），
`ctx.events.off(event, cb)` 取消。回调异常被吞掉并记日志。事件总线不感知模块生命
周期——**on_unload 必须退订自己的全部订阅**，否则卸载后仍会被调用。

| 事件 | 参数 | 触发时机 |
|---|---|---|
| `state` | `EngineState` | 连接 / 配对 / 设备 / 强度等状态变化（高频） |
| `log` | `str` | 应用日志（含其他模块 `ctx.log` 写入的） |
| `action` | `int \| None` | App 物理按键反馈 0-9（None = 清除） |
| `ovc_button` / `ovc_button_up` | `slot_id, bit` | 负鼠物理按键按下 / 抬起（先于绑定动作） |
| `saved_devices` | `list[dict]` | 已保存蓝牙设备列表变化 |
| `intensity_params` | `dict` | 强度参数写入后（字段同 §2.2 快照） |
| `modules_changed` | `module_id` | 任意模块加载 / 卸载后（动作表、页面随之刷新） |
| `profiles_changed` | `module_id` | 模块默认配置档注入 / 移除 / 套用后 |
| `binding_modules_missing` | `{"modules", "bindings"}` | 配置绑定引用未启用模块的动作时（按键面板标记缺失） |

---

## 6. 线程规则

| 上下文 | 规则 |
|---|---|
| `on_load` / `on_unload` | 在提交操作的线程执行（通常引擎线程） |
| `start` / `stop` | 在引擎 asyncio 循环执行，可直接 `await` |
| 事件回调 | 可能在协议接收线程触发：只做轻量处理，发协程用 `ctx.submit()`，**不操作 UI、不长时间阻塞**（会拖慢整个引擎） |

---

## 7. 调试与发布

* **日志**：`ctx.log()` 进日志页（开启文件日志时也写 `dgstudio.log`）；未捕获异常的栈全文落日志；
* **加载失败**：日志里有完整异常栈，界面上表现为模块没有运行。常见原因：
  `META` 非字面量、未定义模块类、`plugin.py` 顶层抛异常、依赖缺失（先点
  「安装依赖」）。手动放入 `modules/` 的模块需重启应用后才会被发现；
* **改代码**：卸载 → 启动（或市场「更新」后启动）即生效，无需重启；只改了设置的
  用「重新加载」（调用可选的 `reload_config()`）；
* **发布**：推送到自己的 `dgstudio-modules-<id>` 仓库，总仓库 Actions 每日重建
  `market.yaml`；需要立即上架可手动 Run「build market」workflow。本地可先用
  `python _tools/build_market.py --local <仓库所在父目录>` 验证解析结果；
* **测试**：单测放在各自模块仓库的 `tests/` 下。测试文件先 `import _bootstrap`
  定位核心源码（核心仓库与模块仓库放同一父目录，或设环境变量 `DGSTUDIO_CORE`），
  然后照常 `from dglab…` / `from modules.<id>…` 导入；在模块仓库根运行
  `python -m unittest discover -s tests`。

---

## 8. 示例

* **strength_logger**（最小完整示例）：订阅 `state`，把每台设备 A/B 通道的强度
  变化写入日志（每设备限速 1 条/秒）。演示鸭子类型模块类、`ctx.log` / `ctx.events`
  与高频事件限速；复制该目录、改 `META.id` 即可起步。
* **vision_link**（动态登记）：不声明静态参数，按用户配置的检测行为动态返回
  `link_params()` / `temp_specs()`，每个检测量登记为只读变量；`realtime_manager`
  让模块页渲染「参数名 ← 检测行为」管理块；检测配置存设置文件的 `detectors`，
  运行时对象挂在 `self.bridge`。其 `requirements.txt` 只列进程内依赖，OCR 栈放在
  `ocr_wheels/` 由子进程使用。
* **sound_link**（只登记、不下发）：采集麦克风与系统声音（WASAPI 回环），登记
  左 / 右响度、左 / 右频率共 8 个只读变量（`META["params"]` + `link_params()`）。
  用户把「响度 / 频率」读数卡接进核心写入卡 `in_pulse_a/b`，通道波形选「外部
  脉冲流（PULSE_STREAM）」即成流；核心对脉冲参数每 0.1 s 生成一帧（0 = 静音帧，
  10-1000 = 逻辑频率），不使用内置波形发生器。
* **osc_bridge**（可改名参数）：`link_params()` 按当前在连设备与自定义地址登记变量，
  `derived_rows()` 给模块页那张只读参数表，`rename_var()` 把改名写进 `param_names`
  并同步收发地址。
