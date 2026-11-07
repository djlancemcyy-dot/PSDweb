# PSDweb v2.4.0 技术与体验审计报告

> 审计对象：`C:\Users\lee\Downloads\PSD-m\PSDweb`（server.py 2308 行 / app.js 5134 行 / style.css 3780 行 / index.html 903 行 / data/*.json）
> 审计视角：全栈架构 + 桌面端图形工具交互 + 工业印刷规范
> 结论先行：**功能完成度高，但存在 2 个致命级导出缺陷、1 个随时可复现的并发数据事故，以及一个"每帧全量重建 DOM"的前端性能第一热点。**

---

## 一、总评

| 维度 | 评分 | 简评 |
|---|---|---|
| 业务完成度 | ★★★★☆ | 录入→抠图→排版→同步→导出五环齐全，离线 AI 抠图与双模导出是真实差异化 |
| 后端健壮性 | ★★☆☆☆ | PSD 元信息缺失、抠图引擎并发串模型、JSON 无锁裸写、多个安全洞 |
| 前端渲染架构 | ★★☆☆☆ | 逆缩放思路正确，但被 mousemove 全量 innerHTML 重建拖垮；坐标换算六处手写重复 |
| 数据规范 | ★★★☆☆ | 字体/线宽全数据化是亮点；但坐标双轨、自由文本无校验、已产生脏数据 |
| 交互专业度 | ★★★☆☆ | 深浅主题/令牌体系达准专业；快捷键仅 4 个、无 undo、批量无进度 |

---

## 二、致命级问题（必须优先修）

### P0-1 PSD 导出缺 300DPI 元信息与合成预览图，印刷场景直接踩坑
- **位置**：`server.py:2148-2154`（nested_layers_to_psd 调用）、`362-392`（pil_to_psd_layer）
- **现状**：`pytoshop.nested_layers_to_psd()` 只写图层结构，**不写 ResolutionInfo image resource**。Photoshop 打开后按默认 72dpi 解释，3508×2480px 变成 123.8×87.5cm 的"巨幅画布"，客户送印排版时尺寸字号全部错乱。同时不写 merged composite，旧版 PS 与第三方查看器可能显示空白或弹兼容性警告。`Compression.raw` 使每个满画布 RGBA 图层约 35MB，多鞋款多标贴时单文件数百 MB。
- **修复**：
  1. 导出后用 `psd-tools` 补写 `Resource.RESOLUTION_INFO`（300dpi），或直接改用 psd-tools API 构建；
  2. 写入顶层 composite（等价 maximizeCompatibility）；
  3. compression 改 `enums.Compression.rle`（无损 packbits，体积通常缩 5~10 倍）；
  4. 加回归断言：导出后用 psd-tools 重开，断言 dpi==300 且 composite 非空。

### P0-2 "可编辑文字 PSD"名不副实——pytoshop 路径文字全部栅格化
- **位置**：`server.py:2052-2058`、`1994`（底板整图单图层）；对比 `1800-1893` COM JSX 真文字层
- **现状**：README 与前端宣传"TypeTool 原生可编辑文字层"，但 HAS_PYTOSHOP 优先分支把标题、规格、颜色标注全部 `PIL draw.text` 烧进像素。只有 pytoshop 失败降级到 COM 路径时才是真文字层。**同一接口在有无装 PS 的两台机器上产出结构完全不同**——隐性数据质量事故。另外底板线框+标题+规格+LOGO 全烘进单个图层，客户改货号必须整图重渲。
- **修复（二选一）**：
  - (a) 目标真是"可编辑文字"→ Windows 上强制 COM 路径，pytoshop 仅作降级并在响应中返回 `editable_text:false` 明示；
  - (b) 接受栅格化 → 去掉宣传语，但至少把标题/规格/颜色标注各自拆成独立栅格层，结构对齐 COM 路径。

### P0-3 抠图引擎全局单例 + 就地切模型，并发必串模型
- **位置**：`server.py:340-346`、`1510-1512`、`1547-1561`
- **现状**：`shoe_engine` 是进程级单例，`/api/cutout/models/select` 和 `/api/cutout-batch` 都会 `switch_model()` 直接改全局 `active_model_id`。两个客户端同时操作时，A 的批量任务循环中途被 B 切成另一个模型，同批图用两个模型出图且无任何报错——结果不可复现。此外 `switch_model` 若每次新建 InferenceSession 而不释放旧 session，反复切换持续涨内存直至 OOM。
- **修复**：
```python
cutout_lock = threading.Lock()

def do_single_cutout(...):
    with cutout_lock:  # 批量请求持锁到底，切换+推理原子化
        if model_id and model_id != shoe_engine.active_model_id:
            shoe_engine.switch_model(model_id)
        return shoe_engine.process_shoe(...)
```
  引擎侧做模型 LRU（`del self.sessions[old_id]` + `gc.collect()`，最多驻留 1~2 个），批量接口加内存护栏（psutil 检查 available < 1.5GB 时拒绝）。

### P0-4 拖拽/缩放 mousemove 每帧全量 innerHTML 重建 DOM（前端性能第一热点）
- **位置**：`app.js:3393`（makeShoeDraggable）、`3143`/`3176`/`3248`（三类 Resizable）；`updateStageUI` 本体 `2766-2787`
- **现状**：拖拽的 onMouseMove 每次都调 `updateStageUI()`，后者执行 `stageShoesLayer.innerHTML=""` 并**全量重建**所有鞋样、标贴、工具条、手柄，顺带重绘 SVG 表格线与全部文字层。15 色 × 每色 3~5 标贴的拖动 = 每帧销毁新建数百个 DOM 节点 + 重挂全部事件 + 3508×2480 整版回流。更糟的是：**被拖元素自己被重建销毁**，window 级 mousemove 闭包操作的是已脱离文档的旧节点，mouseup 若发生在窗口外则监听永久泄漏、isDragging 卡死。
- **修复**：
```javascript
// 拖动中只写 style，松手才重建
onMouseMove: shoeEl.style.left = toStagePx(...) + 'px'; // 不调 updateStageUI()
onMouseUp:   updateStageUI(); syncGroupsToServer();
```
  同时统一改用 **Pointer Events + setPointerCapture**，pointermove/pointerup 绑在句柄自身，元素被移除也能安全收尾；window blur 强制收尾。

---

## 三、高危问题

### P1-1 tkinter 目录对话框：线程池里反复建 Tk 实例，多客户端语义错误
- **位置**：`server.py:2239-2273`
- **问题**：tkinter 非线程安全，每次请求在临时 ThreadPoolExecutor 的任意线程 `new Tk()`，多次调用后大概率"main thread is not in main loop"或对话框卡死；用户不点确定线程永久挂起；局域网客户端调用时对话框弹在**服务器屏幕**上无人可点；容器/WSL/服务运行直接失败。
- **修复（推荐）**：彻底去 tkinter，改目录浏览 API + 前端树形选择器：
```python
@app.get('/api/settings/browse-dir')
def browse_dir(path: str = ''):
    base = (Path(path) if path else Path.home()).resolve()
    if not base.is_dir(): raise HTTPException(404, '目录不存在')
    return {'current': str(base), 'parent': str(base.parent),
            'dirs': [{'name': p.name, 'path': str(p)} for p in sorted(base.iterdir()) if p.is_dir()]}
```
  多客户端部署时在 `/api/initial-data` 下发 `server_local` 标志，非本机隐藏该按钮。

### P1-2 data/*.json 无锁裸读-改-写 + 非原子写
- **位置**：`server.py:114-148` 及所有 save_*_db 调用点
- **问题**：并发下 lost update；`json.dump` 中途崩溃留下截断文件后**静默回退默认值**——用户整库配置无声丢失；`load_logos_db` 把"用户清空库"误判为损坏并复活内置数据。
- **修复**：每文件一把 RLock + 原子写：
```python
def atomic_save(path, obj):
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
```
  读取失败保留 .bak 副本；删掉"空 list 回退默认"逻辑。

### P1-3 安全洞一串（绑 0.0.0.0 + CORS 全开的背景下）
- `/api/download`（`2210-2215`）：filename 无校验，路径穿越可读任意文件 → 白名单 `[\w.-]+` + `resolve().is_relative_to(OUTPUT_DIR)`；
- `/api/settings`（`2226-2237`）：output_dir 可改任意路径 → 白名单限定用户目录下；
- `/api/open-folder`（`2275-2291`）：任意路径 explorer 打开，可钓鱼 → 删参数或白名单；
- `upload-cover`（`1309-1325`）：用户扩展名原样写盘，传 .html 即存储型 XSS → 与 upload-raw 一样 PIL 重编码 + 后缀白名单；
- CORS 收窄到 `127.0.0.1:8765` 与 LAN IP，`allow_credentials=False`。

### P1-4 粘贴/同步链路脏数据
- **未选鞋时 Ctrl+V 静默污染首款**（`app.js:4674`：`task.shoes.find(...) || task.shoes[0]` 兜底）→ 改为显式校验并 toast 提示"请先选中鞋款"；
- 内外剪贴板优先级颠倒（系统截图被内部残留 clipboard_logo 吞掉）→ imageFile 优先，粘贴后清空内部剪贴板；
- `switchTask/switchGroup` 不清除 selected_logo/clipboard_logo 等残留引用 → 统一 reset；
- **同步全色按数组下标对齐**（`app.js:3771`）：次款标贴数量/顺序与首款不同时舌标位置套到跟标上 → 按 `logo_id` 匹配，匹配不到按槽位类型回退，toast 报告"N 枚同款对齐 / M 枚槽位回退"。

### P1-5 逆缩放体系五处硬伤
1. **平移层挂 `transition: transform 0.05s`**（`style.css:2736-2739`）：每次位移重新插值，拖拽橡胶拖尾 → mousedown 加 `.panning{transition:none}`；
2. zoom in/out/100% 按钮不复位 pan（`app.js:216-247`），25% 平移后切 100% 画布飞出视口 → 统一调 resetPan()；
3. `--stage-scale` 三处来源（:root 静态 0.25 / documentElement / stage）→ 删静态默认，JS 单源写入；
4. rotate 父级下工具条补偿基准错位 + `style.css:2622` 属性子串选择器 `div[style*="top: -22px"]` 脆弱误命中；
5. 非整数 scale 下 `calc(2px/var)` 边框落亚像素，手柄边缘模糊。

### P1-6 架构建议：静态层 Canvas 化 + 控件 portal 出缩放容器
当前表格线/文字/鞋图/标贴/工具条全在同一棵被 scale(0.2~0.25) 的 DOM 树里，被迫对每个控件逆补偿。建议：
- 表格线/文字等纯静态层 → 单张离屏 Canvas 或 SVG（仅配置变更时重绘），消除每帧 DOM 开销；
- 鞋图/标贴保留 DOM，但**工具条/手柄/选中框渲染到未缩放的 overlay 层**，每帧用 `getBoundingClientRect()` 反算屏幕坐标定位——控件永远 1:1 CSS 像素，彻底删除所有 `calc(1/var)`、overflow 裁剪与亚像素问题；
- 坐标换算统一为 DOMMatrix 工具函数，替换六处手写 `/state.stage_scale` 除法（`app.js:3139/3172/3208/3244/3285/3439`，3285 还缺兜底）：
```javascript
function stagePointFromEvent(e) {
  const m = stage.getScreenCTM().inverse();
  return new DOMPoint(e.clientX, e.clientY).matrixTransform(m);
}
```

---

## 四、中危问题

| # | 位置 | 问题 | 修复 |
|---|---|---|---|
| M1 | `server.py:1921/2038/2073` | temp 文件固定名竞态（temp_lines.png 并发互覆出串图）+ 用户输入入文件名 + 永不清理 | 每次渲染用 `tempfile.TemporaryDirectory`；文件名过 `re.sub(r'[^\w\u4e00-\u9fff.-]','_',s)`；定时清理 mtime>N 天的产物 |
| M2 | `server.py:1557-1569/2190-2208` | 批量抠图/渲染挤占 anyio 默认线程池，并发批量把 40 线程吃光 | 改后台任务：POST 返回 job_id，独立 1~2 线程 worker 串行处理，前端轮询进度 |
| M3 | `server.py:332-338/665-675` | 抠图异常被吞静默降级四角启发式，rembg 缺失时 load-sample 直接 500 | except 至少 logger.exception；结果带 warning 字段；统一对外中文错误提示 |
| M4 | `server.py:291/1729/1412` | 字体目录/PS 路径（只覆盖 2022~2024）/powershell OCR 硬编码 | PS 路径改 glob `Adobe Photoshop *` 取最新；字体用 `%SystemRoot%/Fonts`；HAS_PYTOSHOP=False 时 numpy NameError 需独立 import |
| M5 | `app.js:3826-3843` | Space/H 守卫不覆盖 contenteditable/模态框；Space 未 preventDefault 边滚边拖 | 统一 isEditable 守卫；Space preventDefault；keyup 时若 isPanning 同步收尾 |
| M6 | `app.js:506-520` | 1 秒防抖同步丢尾 + 无 beforeunload 保护，关页面丢最后一次编辑 | state.dirty 标记 + beforeunload 拦截 + pagehide 时 sendBeacon flush；中期改增量同步 |
| M7 | `app.js:1645-1665/3508/2198` | 输入框每次击键触发全画布重建，取色器拖动每秒数十次全量重排 | rAF 合帧 scheduleRender()；局部更新替代整层重建 |
| M8 | `app.js:3053/4637/4677` | 剪贴板浅拷贝（嵌套字段即踩坑）；粘贴的 logo_id 悬空时静默 fallback 默认船标"贴错标" | structuredClone；粘贴前校验 logo_id 存在于素材池 |
| M9 | `server.py` 整体 | 排版坐标双轨：calculate_ai_slots 硬编码 vs layout_templates.json 两份事实源 | slots_map 升级为唯一事实源（含 max_w/max_h/align/safe_area），删除代码内重复坐标 |

---

## 五、工业设计规范问题

| # | 位置 | 问题 | 建议 |
|---|---|---|---|
| D1 | `server.py:1914` | 画布按净尺寸 3508×2480 排版，**无 3mm 出血与裁切角线**，贴边 4px 表线有被裁断风险 | 增加可选"含出血导出"：3578×2510px + 出血参考线 + crop marks，template_config 加 bleed_mm |
| D2 | `server.py:1667-1696` | 5~15 色走数学均分网格 + 0.72/-20px 魔术数字，无文字避让区 | template_config 定义 canvas_safe_area 与 text_reserved_zones，网格生成做避让断言；5/6/8 色补人工精调模板 |
| D3 | `data/logos.json` | 标贴只有相对坐标，无物理 mm 尺寸约束，鞋图缩放后标贴物理尺寸失控 | 增加 print_width_mm/print_height_mm 与按类型的工业位置参数表，300DPI 换算并校验告警 |
| D4 | typo-font-size-input min=16 | 16px@300DPI≈1.36mm，低于印刷可读下限（≥6pt≈25px）无提示 | 下限提 24px，低于 28px 黄色警示 |
| D5 | `data/products.json` | 规格字段自由文本，已存在 color_name='ddddd' 脏数据进入历史快照；同义词无法归一 | 服务端白名单+trim 校验；建受控色卡表；清理历史脏数据脚本 |
| D6 | products vs groups | 两套任务结构冗余双写（material_code vs cover_image 各缺一半），改一处漂移 | groups.tasks 存 product_id 引用 + 覆写差异字段；抽公共 ShoeSpec schema（pydantic 复用到落库层）；rel 坐标 range 校验 |
| D7 | `index.html:149/567-575` | 尺码 36、类别/工艺/季节缺省值硬编码在 HTML value 属性 | 新建 data/field_defaults.json 集中管理，前端从 API 拉取；material_code 加 YYYY.MM.DD 正则 |

---

## 六、交互与 UX 问题

| # | 问题 | 建议 |
|---|---|---|
| U1 | 五步动线 Z 字跳跃（录入左侧→抠图底部→排版/同步顶部→导出右上）；三个自动化按钮并列易点错且无 undo | 顶部加 1-2-3-4-5 步骤指示器；按钮 tooltip 说明差异；实现快照级 undo（至少 10 步） |
| U2 | 快捷键仅 4 个（Space/H/Ctrl+C/Ctrl+V） | 补齐 Delete/Ctrl+S/Ctrl+E/方向键微移/Ctrl+0/1/Esc，加 Ctrl+Shift+/ 快捷键总表；键位抽到单一 keymap 对象 |
| U3 | 批量抠图/导出只有无进度 spinner，15 款导出分钟级等待无反馈；失败 toast 一闪而过 | 进度条 + 当前款名 + 可取消；完成后结果汇总（成功 N/失败 M + 一键重试） |
| U4 | index.html 大量内联样式绕过令牌体系，深色模式下突兀 | 迁入 style.css 用 var(--space-*)，间距收敛 4pt 网格 |
| U5 | 左右 drawer 同开时 1366px 屏幕画布不足 700px，无专注模式 | 加一键 focus mode 收起全部面板，折叠状态存 localStorage |
| U6 | 危险操作防护不一致：删除批次有强确认，但"恢复默认模版""批量抠图覆盖"无确认 | 恢复默认前自动备份 template_config 到 backups/（复用现有机制） |

---

## 七、修复路线图（按性价比排序）

**第一波（1~2 天，止血）**
1. P0-4 拖拽只写 style、松手重建（改动小，体验提升立竿见影）
2. P0-1 PSD 补 300DPI + composite + RLE 压缩
3. P0-3 抠图推理锁 + 模型 LRU
4. P1-2 JSON 原子写 + 锁
5. P1-3 download/settings/open-folder 白名单

**第二波（3~5 天，架构加固）**
6. P1-1 去 tkinter 改目录浏览 API
7. M2 批处理后台任务化（顺带解决 P0-3 残余并发）
8. M6 beforeunload + sendBeacon 防丢稿
9. P1-4 粘贴/同步链路校验
10. D6 数据层 schema 校验 + 清理 'ddddd' 类脏数据

**第三波（1~2 周，专业度跃升）**
11. P1-6 静态层 Canvas 化 + 控件 overlay portal + DOMMatrix 统一坐标
12. D1 出血模式、D3 标贴 mm 尺寸标准库
13. U1 快照 undo + 步骤指示器、U3 批量进度 UI
14. U2 快捷键体系补齐

---

*报告生成：2026-11-07 · 来财*
