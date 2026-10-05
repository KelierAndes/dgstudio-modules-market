# DGStudio 联动模块开发文档（模块 SDK）

> 本文档维护于模块市场总仓库 **dgstudio-modules-market**。DGStudio 的一切联动
> （VRChat OSC、游戏数据、未来的 MQTT/硬件外设……）都是**联动模块**：每个
> 模块一个独立 GitHub 仓库（`dgstudio-modules-<模块 id>`，与 AstrBot 插件
> 仓库同模式），总仓库经 Actions 聚合各子仓库生成市场清单 `market.yaml`，
> DGStudio「模块」页只读该清单并按需下载、实时装卸、热重载。模块通过
> `ModuleContext`（下文简称 `ctx`）访问引擎的命令层、强度参数 API、设备
> 状态与事件总线；私有设置自动持久化。

---

## 1. 快速开始

### 1.1 目录与文件

**模块仓库（每模块一个，命名 `dgstudio-modules-<id>`）——模块源码：**

```
dgstudio-modules-<id>/
├── modules/<id>/plugin.py      模块入口：META 字典 + 模块类（单文件模块可直放仓库根）
├── modules/<id>/requirements.txt  pip 依赖串（可选；随模块下载、安装时自动补装）
├── modules/<id>/mods/          可选：携带的游戏端模组（一键释放到游戏目录）
├── tests/                      模块单测（需核心源码，见文末）
├── README.md / LICENSE
```

**总仓库（dgstudio-modules-market，本仓库）——市场聚合：**

```
dgstudio-modules-market/
├── market.yaml                 市场清单（Actions 聚合各子仓库自动生成）
├── sources.txt                 API 发现失败时的手工兜底清单
├── _tools/build_market.py      聚合解析工具（CI / 本地双模式）
└── .github/workflows/market.yml  定时/手动重建 market.yaml
```

**应用目录（DGStudio 运行时）——宿主与产物：**

```
DGStudio/
├── plugins.py                  模块宿主（ModuleBase / ModuleContext / PluginManager）
├── module_store.py             仓库客户端（清单获取 / 下载 / 依赖安装）
├── modules/<id>/               已下载的模块（含模块私有依赖 _deps/）
├── config.json                 主配置
└── config/
    ├── modules.json            各模块启用（自启动）状态
    └── <settings_key|id>.json  各模块私有设置
```

每个模块一个仓库、一个文件夹，**最少只需一个 `plugin.py`**。包形式
（`__init__.py` + 任意多文件，推荐拆文件时用，放在 `modules/<id>/` 下）与
仓库根直放的散文件形式都能被市场解析、被宿主加载；打包版 exe 运行时放入
新模块同样生效。模块需要的第三方依赖**不进核心、不随软件分发**，写入模块
仓库的 `requirements.txt`（§1.4），安装时自动补装。

### 1.2 最小模块

`modules/hello/plugin.py`：

```python
META = {
    "id": "hello",                # 全局唯一，与文件夹同名
    "name": "示例模块",
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

    def on_unload(self):          # 卸载时一次：必须退订事件、释放资源
        pass

    async def start(self):        # 启动（引擎 asyncio 循环上）
        pass

    async def stop(self):         # 停止（卸载前宿主先调用）
        pass

    def is_running(self):         # 模块页状态胶囊据此显示
        return False
```

要点：

* `META` 由模块页**不执行代码**读取（AST 解析字面量），必须是纯字面量字典；
* 宿主取 `plugin.py` 中**第一个**符合协议的类：继承 `ModuleBase`（有默认空实现
  与 IDE 补全）或鸭子类型（提供 `id`/`name`/`on_load`/`on_unload` 即可），
  鸭子类型缺失的 `start`/`stop`/`is_running` 自动补空实现；
* `META` 可选键：`settings_key`、`dependencies`（依赖声明，§1.4）、
  `actions`（按键动作静态声明，§3）、`config`（配置项声明，§4.1）、
  `params` / `reads` / `dynamic_params`（联动参数，§4.2）、`default_enabled`、
  `mods`（游戏模组一键安装：模块内 `mods/` 里的文件释放到
  `<游戏根>/<dest>`，`marker` 可执行文件名用于自动扫描游戏根目录）。

### 1.3 生命周期

```
模块页「安装并启动」             模块页「卸载」
        │ install(id)                  │ uninstall(id)
        ▼                              ▼
   补装缺失依赖（§1.4）            stop()  ←── 若在运行
        │                              │
   on_load(ctx)                   on_unload()
        │                              │
   start()                        实例移除，文件保留
        │
   （运行中）
```

* **安装** = 补装依赖 + 启用状态置真（重启后自动加载）+ 立即加载并启动；
  **卸载** = 停止 + 移除实例 + 启用置假。模块**文件不会被删除**；
  模块页另有「删除」按钮移除磁盘文件（可随时从在线列表重新下载）；
* **热重载**：卸载时宿主清理该模块的全部导入缓存（sys.modules 条目与
  `__pycache__`）并摘除其私有依赖路径——「卸载 → 安装」与「更新」无需
  重启应用即可运行新代码；
* `start`/`stop` 运行在引擎 asyncio 循环上，可直接 `await`；
  非异步上下文用 `ctx.submit(coro)` 提交（返回 Future）；
* 事件回调运行在引擎线程或协议接收线程：只做轻量处理，**不操作 UI、
  不阻塞**，耗时逻辑用 `ctx.submit()` 切回引擎循环。

### 1.4 依赖声明（requirements.txt）

模块的第三方依赖写在模块仓库的 **`requirements.txt`**（放在模块目录内，
随模块一起下载），模块页「安装并启动」时自动读取并 pip 补装缺失项
（模块页也提供「安装依赖」按钮手动触发）：

```
python-osc>=1.9                      # 必装依赖
# 可选依赖以「!」前缀声明：安装时以 --no-deps 尽力安装，失败不阻断
# 手动 pip install -r 时请跳过这些行
!rapidocr-onnxruntime>=1.4.4
```

无 `requirements.txt` 时回退读 `META["dependencies"]`（旧式声明，等价的
pip 依赖串列表），仅作兼容保留。

* **源码运行**（`python main.py`）：装进当前解释器环境（venv）；
* **打包 exe**：**首选模块自带 `wheels/`**（模块目录内；wheel 即 zip，
  安装时逐个解包合并进私有 `modules/<id>/_deps/`，离线、按 dist-info 幂等），
  剩余缺失才经宿主内置的真实 Python 子进程 pip 兜底——目标机无需安装
  Python；`_deps/` 会在模块装载前挂到 `sys.path` 最前；
* 可用性探测按「环境元数据 → `_deps` 目录元数据 → import 名探测」进行，
  pip 包名与 import 名不一致（如 `opencv-python-headless` → `cv2`）自动映射；
* 市场清单 `market.yaml` 由总仓库 Actions 解析各子仓库的 requirements.txt
  生成，模块页下载前即可展示依赖。

---

## 2. ModuleContext API

模块**只应通过 `ctx` 访问引擎**。全部公开成员如下。

### 2.1 基础与设备状态

| 成员 | 说明 |
|---|---|
| `ctx.engine` | 引擎实例（仅用于传给需要的对象，日常用下列封装） |
| `ctx.events` | 事件总线（§5） |
| `ctx.log(msg)` | 写应用日志（自动带 `[模块id]` 前缀），进日志页与日志文件 |
| `ctx.submit(coro)` | 协程提交到引擎事件循环，返回 Future |
| `ctx.settings` | 模块私有设置字典（写穿持久化，§4.1） |
| `ctx.get_state()` | 当前 `EngineState`（含全部 `Slot`） |
| `ctx.devices()` | 已接入设备列表 `[{slot_id, name, type, family}]` |
| `ctx.resolve_slot(slot_id=None, family=None, output_only=False)` | 解析目标设备：显式 id 优先 → 按 family → 默认第一台（`output_only` 排除纯传感器灵猫） |

设备家族：`COYOTE`（郊狼，电刺激）、`OVC`（负鼠，振动）、`BMTR`（灵猫，气压
传感器）。`dglab.state.family_of(type)` 从设备型号得家族。

### 2.2 强度参数

**读取快照：**

```python
params = ctx.intensity_params()            # 默认输出设备；也可传 slot_id
```

| 字段 | 含义 |
|---|---|
| `slot_id` / `connected` | 解析到的设备（无设备时为 None）/ 是否在线 |
| `strength` / `strength_limit` | `{"A", "B"}` 当前强度 / 硬件上限 |
| `channel_status` | 探活：0/2 正常，1 异常 |
| `max_strength` | 最大强度上限（设备独立值，缺省全局 100） |
| `strength_step` | 步长（已按设备量化，OVC 至少 10） |
| `fire_strength` | 旧版双通道共用开火强度（遗留键，兼容保留；0=跟随上限） |
| `fire_strength_a` / `fire_strength_b` | A/B 通道独立开火强度（0=跟随该设备上限） |
| `fire_duration_s` | 开火时长（秒） |
| `wave_duration_s` | Socket V3 波形循环时长（秒） |
| `wave` | `{"A", "B"}` 当前选定波形名 |

**写入参数**（无效键抛 `ValueError`，越界自动钳制，写入后发 `intensity_params` 事件）：

```python
ctx.set_intensity_param("max_strength", 150)               # 全局
ctx.set_intensity_param("fire_strength", 80, slot_id=sid)  # 设备级覆盖（旧键）
ctx.set_intensity_param("fire_strength_a", 40, slot_id=sid)  # A 通道独立开火强度
ctx.set_intensity_param("fire_strength_b", 60, slot_id=sid)  # B 通道独立开火强度
```

| 键 | 范围 | 说明 |
|---|---|---|
| `max_strength` | 0–200 | 最大强度上限（钳制一切强度设定，含开火） |
| `strength_step` | 1–50 | 加减步长（OVC 量化到 10 的倍数） |
| `fire_strength` | 0–200 | 旧版双通道共用键（兼容保留），0 = 跟随 max_strength |
| `fire_strength_a` / `fire_strength_b` | 0–200 | 通道开火强度；设备级显式 0 = 跟随该设备上限，全局 0 视为未设定（回退旧键） |
| `fire_duration_s` | 0.1–60 | 定时开火时长 |
| `wave_duration_s` | 1–120 | 仅全局，无设备级覆盖 |

**逐项便捷读取：**

| 方法 | 返回 |
|---|---|
| `ctx.strength(slot_id, "A")` | 当前强度 |
| `ctx.strength_limit(slot_id, "A")` | 硬件上限 |
| `ctx.device_setting(slot_id, key)` | 设备级设置（回退全局），任意键 |
| `ctx.device_step(slot_id)` | 量化后的步长 |
| `ctx.wave_selection()` | `{"A": 名, "B": 名}` |
| `ctx.wave_order("COYOTE")` | 该家族波形名序列（静默/持续在前） |

**控制命令**（引擎公开方法，返回协程——异步上下文直接 `await`，否则 `ctx.submit`）：

| 方法 | 说明 |
|---|---|
| `ctx.set_strength(channel, value, slot_id=None)` | 直接设置（自动钳制与量化） |
| `ctx.add_strength(channel, delta, slot_id=None)` | 增减（步长/量化/上限保护） |
| `ctx.reset_strength(channel, slot_id=None)` | 归零：强度清零 + 波形切回静默 |
| `ctx.set_wave(channel, name, slot_id=None)` | 切波形（不中断强度会话） |
| `ctx.push_pulse_stream(frequency, channel="A", level=100, slot_id=None)` | **外部脉冲流直推 API**：每 0.1s 推入一次频率数据（逻辑频率 10-1000，电平 0-100，0=该帧静音），核心把每次推送作为**最新帧**刷新播放（实时跟随；追加历史会因播放循环积压导致频率严重滞后）——波形由模块数据生成，不使用内置波形发生器。仅当该通道波形选中「外部脉冲流 (PULSE_STREAM)」时落地，其余情况静默丢弃（可常推不息）。返回协程：异步上下文直接 `await`，否则 `ctx.submit`。蓝牙实时逐帧跟随；V4 随补批节奏（≤1s）跟随；V3 为尽力而为（整段窗口重发）。**常规路径是事件流周期卡**：把变量推入核心输入参数 `in_pulse_a/b`（数值推入，见 §4.2），经同一落地链路且自带 0.1s 节流 |
| `ctx.fire(slot_id=None, duration_s=None, channel=None)` | 一键开火（定时，到时自动恢复强度/波形）；`channel`="A"/"B" 只开火该通道，缺省双通道。需 Socket V4 / 蓝牙连接 |
| `ctx.fire_start(slot_id=None, channel=None)` / `fire_stop(slot_id=None, channel=None)` | 按住持续开火（60 秒安全超时，结束恢复原强度/波形）；`channel`="A"/"B" 只动该通道，缺省双通道。开火保持按 (设备, 通道) 独立记账 |
| `ctx.zap(channel, seconds, slot_id=None)` | 定时爆发：**仅对指定通道**开火（通道分离语义；需双通道齐射请分别调 A/B 或用 `ctx.fire` 不带 channel） |
| `ctx.emergency_stop()` | 急停：全部输出设备清零 + 波形重置（取消全部通道的开火保持） |

---

### 2.3 游戏模组携带与安装（通用接口）

携带游戏端模组的模块在 META 里声明释放目标与定位标记：

```python
META = {"id": "...", ...,
        "mods": {"dest": "BepInEx/plugins/<模组名>",   # 释放目标（相对游戏根）
                 "marker": "Game.exe"}}                # 游戏主程序名（自动扫描定位）
```

并把载荷放进模块目录（随模块一起下载分发）：

| 路径 | 内容 |
|---|---|
| `mods/` | 编译好的模组文件（释放到 dest 的内容） |
| `mods/BepInEx/`（可选） | 需随模组合并安装的 BepInEx 文件 |
| `vendor/BepInEx_win_*.zip`（可选） | BepInEx 5 官方发行包，目标缺 BepInEx 时自动安装用 |

`ModuleContext` 通用接口（模块页「安装游戏模组」按钮走同一链路）：

| 方法 | 说明 |
|---|---|
| `ctx.game_mods_dir()` | 模块携带的 `mods/` 目录（无载荷返回 `None`） |
| `ctx.scan_game_roots(roots=None, max_depth=3)` | 按 marker 在盘符根浅层扫描游戏根目录（可传 `roots` 收敛范围） |
| `ctx.install_game_mod(game_root)` | 释放模组到游戏根目录；缺 BepInEx 时自动安装（`mods/BepInEx/` → `vendor/` zip），目标不含游戏主程序抛 `ValueError` |

alice_cradle 模块即示范实现：模组源码 `AliceInCradleLink/` +
`dotnet build -t:Deploy` 产出 `mods/` 载荷 + `vendor/` 携带发行包。

---

## 3. 按键绑定动作（负鼠按键 → 模块功能）

加载时注册动作 → 控制页绑定选择框出现该项；卸载时自动撤下。
OSC 模块的「发送 OSC 参数…」即由此机制提供。

```python
from plugins import ButtonAction

def button_actions(self) -> list:
    return [ButtonAction(
        key="myaction",                  # 绑定值前缀，全局唯一（重复只接受第一个）
        label="我的动作…",                # 选择框显示文本
        argument_placeholder="参数…",     # 非空 → 绑定值带参数 "<key>:<参数>"
        on_press=self._on_press,         # (slot_id, argument | None)，引擎线程调用
        on_release=self._on_release,     # 可选
    )]
```

* 绑定值存于按键映射配置，形如 `"myaction"` 或 `"myaction:参数"`；
* 回调在引擎线程同步调用，应快速返回，耗时操作 `ctx.submit()`；
* `META["actions"]: ["myaction"]` 是静态声明，供模块**未加载**时把配置中的
  绑定反查到模块。

**配置检查（自动）**：应用启动、切换按键映射配置、卸载模块时，若配置绑定
引用了未加载模块的动作，弹窗提示——「启用并加载」自动安装对应模块并保留
映射；「拒绝加载」则相关绑定重置为「无动作」。装卸经 `modules_changed`
事件即时刷新全部页面。

---

## 4. 模块设置与联动参数

### 4.1 设置文件与配置声明

* 设置独立于主 config.json：每模块一个文件 `config/<settings_key|id>.json`，
  宿主自动读写；启用状态集中在 `config/modules.json`；旧版主配置里的模块段
  首次运行时自动迁移；
* `ctx.settings` 是**写穿字典**：顶层键写入/删除/更新立即落盘，无需保存方法。
  **嵌套字典的就地修改不落盘**，需要时显式调用 `ctx.settings.save()`。

```python
self.threshold = int(ctx.settings.get("threshold", 50))
ctx.settings["threshold"] = 80        # 即时落盘
```

* `META["default_enabled"]: true` → 从未被显式装卸过的模块随应用自启
  （模块按需下载后仍以显式「安装」为准，示例模块默认不自启）。

**配置项声明 `META["config"]`**（纯字面量；动态声明可覆写 `config_spec()`，
优先于 META）。宿主装载时**自动补齐缺失项**写进设置文件，联动/模块页据此
自动渲染编辑控件，模块无需写界面代码：

```python
META = {
    ...,
    "config": {
        "port": {"label": "输出端口", "type": "int", "default": 9000,
                 "min": 1, "max": 65535, "group": "bridge",
                 "desc": "发送数值的目标端口"},
    },
}
```

| type | 控件 | 附加字段 |
|---|---|---|
| `int` / `float` | 滑块（量程 ≤1000）或数字框，修改即落盘 | `min` / `max` / `step` / `unit` |
| `str` | 文本框 | — |
| `bool` | 开关 | — |
| `choice` | 下拉（只能选预设值） | `choices` |
| `map` | 每个子键一行文本框 | — |
| `list` + `rows: "in"/"out"` | 输入/输出映射表（§4.2） | — |

公共字段：`label`（显示名）、`default`、`desc`（说明列）、`group`
（联动页落位：`map` 组渲染成映射表，其余组进「模块设置」）。

### 4.2 联动参数模型（核心参数 + 双向映射表）

统一模型：**核心参数**（固定定义于 `dglab/params.py`，名称不可改）+
**模块侧参数**（模块自行声明）+ **两张映射表**连接两者。联动页每张模块
卡片都按「输出映射表 → 输入映射表 → 模块设置」渲染，全部家族/模块共用。

| 侧向 | 声明方式 | 运行期覆写 | 说明 |
|---|---|---|---|
| 核心输入（模块→设备） | 固定 | `core_inputs()` 列全部条目 | id 为 `in_*`（郊狼）/ `in_ovc_*`（负鼠）+ 全局 `in_emergency`；含 key/label/type/range。开火按通道独立：`in_fire` / `in_ovc_fire`（双通道）与 `in_fire_a/b`、`in_ovc_fire_a/b`（仅本通道，Bool）。**脉冲流数值推入**：`in_pulse_a/b`、`in_ovc_pulse_a/b`（Int 0-1000）——0=静音帧、10-1000=脉冲频率（逻辑频率），事件流「周期更新」卡片每拍把变量值推入该参数即逐帧成流（核心 0.1s 节流防积压；通道波形需选「外部脉冲流」） |
| 核心输出（设备→模块） | 固定 | `output_specs(family, index)` | id 为 `家族.信号`（多台 `家族.序号.信号`，如 `COYOTE.2.Battery`）+ 全局 `Action` |
| 模块可写（喂给核心） | `META["params"]` | `link_params()` → `[(名, 说明)]` | 输入表表达式中以 `{名}` 引用 |
| 模块可读（从核心读走） | `META["reads"]`（核心信号名 → {label, name, type}） | `read_params()` → `[(信号名, 说明)]` | 装载时空输出表按声明自动落地默认行，联动页据此做字段名联想 |
| OSC 动态参数 | `META["dynamic_params"]: true` | — | 头像参数双向自定义：行带 `name`，默认名/直传表达式自动生成，可自由改 |

**两张映射表（配置文件只保存这两张）**：

* `mappings` 输入表，行 `{param: 核心输入id, expr: 表达式}`——表达式以
  `{变量}` 引用模块可写参数与核心输出参数，自由四则运算，结果**取整钳制**
  到该参数 `range` 后派发设备动作；`expr` 留空 = 同名直传。
  **核心参数名固定，下拉选择不可改。**
* `outputs` 输出表，行 `{param: 核心输出id, name: 模块侧字段名, expr, type}`
  ——求值后回传模块（OSC 写 `/avatar/parameters/<name>`，游戏模块进
  `GET /data`）。**来源参数固定，`name` 可由用户自由改名。**

联动页对两张表提供增删行与「实时值」预览；「保存设置」后宿主对暴露
`reload_config()` 的运行中模块调用它，映射改动**热生效**；桥接地址/端口等
改动仍需重开模块。联动页卡片**只显示已安装（启用）的模块**——装卸即时增删
卡片，未安装模块的配置仍持久化、安装后即出现；`config_init` 模块不出卡片，
专责配置装载/保存/导出。已启用且声明了 `META["config"]` 的模块在模块页自动
出现「联动设置」跳转链接。

> 默认头像参数名的生成规则（设备前缀 + 信号模板）在核心 `dglab/naming.py`
> （`default_input_name` / `default_output_name` / `device_osc_names`），
> 模块与联动页共用。

---

## 5. 事件总线（ctx.events）

`cb = ctx.events.on(event, callback)` 注册（返回回调引用），
`ctx.events.off(event, cb)` 取消。回调异常被吞掉（记日志）。事件总线不感知
模块生命周期——**on_unload 必须退订自己的全部订阅**，否则卸载后仍会被调用。

| 事件 | 参数 | 触发时机 |
|---|---|---|
| `state` | `EngineState` | 连接/配对/设备/强度等状态变化（高频） |
| `log` | `str` | 应用日志（含其他模块 `ctx.log` 写入的） |
| `frame_log` | `direction, frame` | 协议数据帧（需开「记录通信数据帧」） |
| `action` | `int \| None` | App 物理按键反馈 0-9（None=清除） |
| `ovc_button` / `ovc_button_up` | `slot_id, bit` | 负鼠物理按键按下/抬起（先于绑定动作） |
| `saved_devices` | `list[dict]` | 已保存蓝牙设备列表变化 |
| `intensity_params` | `dict` | `set_intensity_param` 写入后（字段同 §2.2 快照） |
| `modules_changed` | `module_id` | 任意模块加载/卸载后（动作表、页面随之刷新） |
| `binding_modules_missing` | `{"modules", "bindings"}` | 配置绑定引用未启用模块动作时（界面弹窗） |

---

## 6. 线程规则

| 上下文 | 规则 |
|---|---|
| `on_load` / `on_unload` | 在提交操作的线程执行（通常引擎线程） |
| `start` / `stop` | 在引擎 asyncio 循环执行，可直接 `await` |
| 事件回调 | 可能在协议接收线程触发：只做轻量处理，发协程用 `ctx.submit()`，**不操作 UI、不长时间阻塞**（会拖慢整个引擎） |

---

## 7. 调试与发布

* **日志**：`ctx.log()` 进日志页与 `dgstudio.log`；异常栈全文落日志；
* **加载失败**：模块页「扫描模块目录」后如实显示。常见错误：`META` 非字面量、
  未定义模块类、`plugin.py` 顶层抛异常、依赖缺失（先点「安装依赖」）；
* **热重载**：卸载会清空该模块的导入缓存与 pyc——改完代码「卸载 → 安装」
  或模块页「更新」即运行新代码，无需重启应用；
* **发布**：推送自己的 `dgstudio-modules-*` 仓库，总仓库 Actions 定期
  （每日）重建 `market.yaml`，需要立即上架可到总仓库手动 Run workflow；
  本地验证可直接运行 `python _tools/build_market.py --local <仓库所在目录>`；
* **测试**：模块单测放在**各自模块仓库**的 `tests/` 下。每个测试文件先
  `import _bootstrap` 定位核心源码（核心仓库与模块仓库放同一父目录，或设
  环境变量 `DGSTUDIO_CORE`），随后照常 `from dglab…` / `from modules.<id>…`
  导入；在模块仓库根运行 `python -m unittest discover -s tests`。

---

## 8. 示例

`modules/strength_logger/plugin.py` 是最小完整示例：订阅 `state` 事件，把每台
设备 A/B 通道的强度变化写入日志（每设备限速 1 条/秒）。演示了鸭子类型模块类、
`ctx.log` / `ctx.events` 基本用法、高频事件限速。复制该目录、改 `META.id`、
按 §2 的 API 实现自己的联动逻辑即可。

`modules/vision_link/` 是进阶示例（OpenCV 画面识别）：不声明静态 `META["params"]`，
而是按用户配置的检测参数**动态返回 `link_params()`**；用 `META["realtime_manager"]`
让联动页实时数据区渲染「参数名 ← 检测行为」的自定义管理块（页面按标志渲染，
模块零界面代码），检测配置存设置文件的 `detectors` 列表；运行时对象挂在
`self.bridge` 上（联动页按 `inst.bridge.engine` 查找映射引擎以渲染实时值）；
其 `dependencies` 同时演示了必装依赖与「!」可选依赖（OCR 增强）的写法。

`dgstudio-modules-sound_link`（音频联动）演示**事件流周期推入外部脉冲流**：
采集麦克风/系统声音，维护左/右响度、左/右频率与左/右推流值六个映射变量
（`META["params"]` 静态声明），首次运行播种一张默认事件卡（周期 100ms）把
推流值推入核心 `in_pulse_a/b` 参数——核心对脉冲流参数每拍生成一帧 100ms
脉冲（0=静音帧，10-1000=逻辑频率），通道波形选「外部脉冲流 (PULSE_STREAM)」
即成流，不使用内置波形发生器。
