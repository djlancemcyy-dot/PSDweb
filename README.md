# 鞋样送审图稿制作系统 (PSDweb v2.4.0 Pro)

> 专为鞋类研发、外贸工厂与设计中心打造的高效送审单制作工作台。  
> **纯净工业级 UI** · **本地离线 AI 抠图** · **300DPI 印刷大图 + Photoshop 100% 原生可编辑文字分层 PSD 双模输出** · **全底表文字/线条/LOGO深度可编辑** · **112款官方矢量标贴素材库** · **局域网多机协同**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Format: 300DPI JPG & Live Text PSD](https://img.shields.io/badge/Output-300DPI%20JPG%20%7C%20Live%20Text%20PSD-orange.svg)]()
[![Platform: Windows 10/11](https://img.shields.io/badge/Platform-Windows%2010%2F11-lightgrey.svg)]()

---

## 🌟 核心特性 (v2.4.0 升级版)

1. **Photoshop 100% 原生可编辑文字图层 (Live TypeTool PSD)**：
   - 导出的 PSD 分层工程中，文字彻底告别光栅化死贴图，全部为 Adobe Photoshop TypeTool 原生文字图层（`kind = LayerKind.TEXT`）；
   - 在 Photoshop 中可直接按快捷键 `T`（文字工具）双击编辑任意文本、随意切换字体与修改字号；
   - 包含独立图层组：`【底表文字与规格信息】`、`【底表线框与底板】` 及各鞋款独立配色的分组。
2. **底表模版全面可视化深度编辑**：
   - 不仅是表头大标题与品牌主LOGO，底表内的全部文字（表头标题、品类大字、审核复核、面料材质、鞋底材质、左侧10行工单标签名与数值）以及线条（外边框粗细、内网格粗细、颜色、左侧分割线位置）均可可视化点击编辑、换字体、改大小、调粗细与颜色；
   - 支持微软正黑、黑体、宋体、楷体、仿宋、Arial、Times New Roman 等经典字体族快速切换。
3. **品牌标贴与图案素材库 (Brand Assets & Logo Hub)**：
   - 官方矢量手册 PDF 全量提取 108 款编号图案透明底 PNG 标贴，合并至素材库，总计达 112 款；
   - 支持分类筛选（全部 / 常用核心标 / 22SS官方库 / 自定义）；
   - 支持实时模糊搜索（输入编号如 001、草书、NVG 等秒搜）；
   - 支持随时扫描导入本地 PDF 自动提取入库并自动加入标贴箱。
4. **离线调优 AI 抠图引擎**：
   - 载入调优 `IS-Net 1024` 工业级权重；
   - 融合 **白底救援 (Rescue White)** 保护浅色鞋底，**白布补实 (Solidify)**，**边缘引导滤波** 及 **RGB 反解去白边**，无缝应对高难鞋面摄影。
5. **CAD / Figma 级动态磁吸对齐参考线**：
   - 拖拽鞋款或标贴时，实时探测相邻元素中心 X/Y 轴与上下左右边缘，$\le 15\text{px}$ 自动物理吸附并绘制绿色虚线提示。
6. **零依赖免安装绿色便携架构**：
   - 随包内置独立 Python 3.12 绿色运行时 (`runtime/`)，客户与朋友解压即用，对方电脑无需预装任何环境。
7. **版本管理与历史备份规范**：
   - 严格遵循版本号规范（当前 `v2.4.0`）；
   - 每次打包自动检测旧版本并在独立备份文件夹中建立快照归档。

---

## 🤖 AI 智能体一键安装 (推荐使用)

如果你正在使用 **Google Antigravity**、**Cursor**、**Claude Code**、**Windsurf** 或任意 AI 编程助手，**只需将下面这段 Prompt 发送给 AI 即可全自动完成配置与启动**：

```text
请阅读当前项目代码，帮我完成环境配置并启动服务：
1. 检查 Python 3.10+ 运行环境；
2. 运行 `python setup_env.py` 自动校验并安装 requirements.txt 中的依赖项；
3. 检查 models/ 目录下的 ONNX 抠图模型权重（缺失将自动安全引导）；
4. 运行 `python server.py` 启动本地 8765 端口服务，并自动在浏览器中打开 http://127.0.0.1:8765。
```

---

## 📦 开发者常规安装方法

### 1. 克隆代码仓库
```bash
git clone https://github.com/djlancemcyy-dot/PSDweb.git
cd PSDweb
```

### 2. 创建并激活虚拟环境 (可选推荐)
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 3. 一键校验并安装依赖
```bash
python setup_env.py
```

### 4. 启动服务
```bash
python server.py
```
终端将输出局域网与本机访问地址，默认浏览器将自动弹出：`http://127.0.0.1:8765`。

---

## 🚀 免安装绿色便携版使用方法 (给客户/朋友交付)

1. 双击运行根目录下的 `一键启动.bat`；
2. 脚本将自动检测随包内置的 `runtime/` 独立引擎并启动服务；
3. 浏览器将自动打开送审系统；
4. 如需打包新版本交付朋友，直接双击 `打包给朋友.bat`，系统将自动归档旧版并在独立文件夹生成最新的免安装绿色发布压缩包。

---

## 📁 目录结构说明

```
PSDweb/
├── server.py               # FastAPI 高性能主服务（支持 300DPI 渲染与 Photoshop COM 原生 TypeLayer 导出）
├── shoe_cutout_engine.py   # 工业级调优鞋样抠图引擎 (ISNet 1024 + 白底救援 + RGB 反解去白边)
├── setup_env.py            # AI 智能体与环境一键配置自检脚本
├── package_tool.py         # 自动化版本备份与独立绿色打包工具
├── 一键启动.bat            # 终端用户一键免安装启动脚本
├── 打包给朋友.bat          # 一键归档旧版并输出分发包脚本
├── VERSION                 # 语义化版本号标识 (当前 v2.4.0)
├── requirements.txt        # 生产依赖清单 (全脱敏)
├── SDD.md                  # 软件设计与架构规约文档 (全脱敏)
├── data/
│   ├── logos.json          # 112 款品牌标贴与图案元数据
│   ├── template_config.json# 底表模版文字、线条、字体、LOGO持久化配置
│   ├── groups.json         # 送审批次工单历史记录
│   └── products.json       # 样品库档案记录
├── models/
│   └── isnet_fine_tuned.onnx # AI 抠图深度学习模型（可离线运行）
├── static/
│   ├── index.html          # 前端交互主页面（支持模版深度编辑与矢量SVG网格）
│   ├── style.css           # 纯净工业级 UI/UX 样式（含深浅色双模）
│   ├── app.js              # 前端交互核心（含对齐参考线、文字浮动调节、素材库）
│   └── assets/             # 预置底表底板、官方品牌标贴库 (108款22SS透明PNG)
└── output/                 # 成果导出目录 (300DPI JPG 与 原生分层 PSD)
```

---

## 🔒 脱敏与安全承诺

本项目代码已全面经过专业脱敏处理：
- 零硬编码私有物理绝对路径（全部使用 `Path(__file__).resolve().parent` 动态计算）；
- 零个人隐私信息与敏感认证 Token；
- 完全支持在任何全新的 Windows 计算机或云端容器上克隆并运行。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源发布。
