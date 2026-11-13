# 桌面备忘录 DesktopMemo

一个基于 **Python + PySide6** 的原生 Windows 桌面备忘录客户端，采用无边框、圆角玻璃卡片风格，可自由拖拽移动与缩放。任务支持置顶、配色、备注、完成勾选，并内置超时归档、逾期提醒、历史清理等自动化规则。

> 本项目为桌面原生应用，不依赖浏览器或 Web 框架；可直接打包为单文件 EXE 分发。

## 功能特性

- **任务管理**：新建任务、标题、备注、自选颜色、置顶、勾选完成、删除。
- **自动记录时间**：任务创建时间自动记录并显示在卡片上。
- **完成后自动归档**：勾选完成后 5 分钟内无任何操作，任务自动从列表消失，移入历史任务。
- **逾期提醒并置顶**：任务超过 24 小时未完成，弹窗提醒并自动置顶。
- **历史任务**：归档任务存入历史列表；每周日 00:00 自动清空历史并清理相关缓存。
- **外观个性化**：自定义背景色，或指定本地图片作为背景；支持深色模式。
- **窗口行为**：可锁定窗口位置、可设置窗口始终置顶；无边框标题栏拖拽移动，四边与四角自由缩放。
- **矢量图标**：功能按钮使用本地 SVG 矢量图标，随浅色 / 深色主题自动着色。

## 技术栈

| 层 | 选型 |
| --- | --- |
| 语言 | Python 3.13 |
| GUI 框架 | PySide6 6.12（Qt 6） |
| 打包 | PyInstaller 6.22（单文件 EXE，嵌入 DPI 清单与图标资源） |
| 持久化 | 本地 JSON 文件 + 缓存目录 |
| 图标 | QSvgRenderer 渲染本地 SVG，按主题色重着色 |

## 目录结构

```
DesktopMemo/
├── client/
│   ├── main.py            # 客户端完整源码（单文件）
│   ├── memo.manifest      # PerMonitorV2 DPI 感知清单（打包嵌入）
│   ├── logo.ico           # 窗口 / EXE 图标（二进制，见下方说明）
│   └── icons/             # 功能按钮 SVG 矢量图标
│       ├── 锁定.svg
│       ├── 钉住1.svg
│       ├── 深色.svg
│       ├── 编辑.svg
│       ├── 设置.svg
│       ├── 删除.svg
│       └── 历史记录.svg
├── docs/
│   └── 技术文档.md         # 架构、数据模型与实现细节
├── assets/
│   └── logo.png           # Logo 高清原图（二进制，见下方说明）
├── requirements.txt
└── README.md
```

## 快速开始

### 从源码运行

```bash
pip install -r requirements.txt
python client/main.py
```

### 打包为单文件 EXE

```bash
python -m PyInstaller --noconfirm --windowed --onefile --name DesktopMemo ^
  --icon client/logo.ico --add-data "client/logo.ico;." ^
  --add-data "client/icons;icons" ^
  --manifest client/memo.manifest ^
  --distpath dist --workpath build --specpath build ^
  client/main.py
```

打包产物位于 `dist/DesktopMemo.exe`。

## 数据存储

- 任务、历史与设置：`%APPDATA%\DesktopMemo\data.json`
- 运行缓存：`%APPDATA%\DesktopMemo\cache\`

卸载或重置时删除上述目录即可清空全部本地数据。

## 业务规则与定时机制

| 规则 | 阈值 / 时机 | 行为 |
| --- | --- | --- |
| 完成归档 | 勾选完成后 5 分钟（300 秒）无操作 | 任务移入历史列表，从当前列表移除 |
| 逾期提醒 | 创建后超过 24 小时（86400 秒）未完成 | 弹窗提醒，任务自动置顶，仅提醒一次 |
| 历史清理 | 每周日 00:00 | 清空历史任务并清理缓存目录 |
| 空闲计时重置 | 编辑、置顶、改色、改备注等操作 | 刷新任务的最近操作时间，重新计算空闲时长 |

## 关于版本库中的二进制文件

为保持仓库轻量，以下**二进制产物不纳入 Git 版本库**：

- `dist/DesktopMemo.exe`：打包产物，体积较大，可由源码重新生成。
- `client/logo.ico`、`assets/logo.png`：Logo 二进制文件；源码运行时若缺少 `logo.ico`，窗口图标会回退为默认占位，不影响功能。

SVG 矢量图标为文本文件，已全部纳入版本库。

## 许可证

本项目仅作个人学习与演示用途，未指定开源许可证。
