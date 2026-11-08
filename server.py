import os
import sys
import io
import gc
import glob
import uuid
import json
import shutil
import socket
import struct
import re
import tempfile
import datetime
import threading
import time
import webbrowser
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
from PIL import Image, ImageDraw, ImageFont, ImageOps
# numpy 独立导入（M4）：不依赖 pytoshop try 块顺带导入
import numpy as np

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
ASSETS_DIR = STATIC_DIR / "assets"
UPLOADS_DIR = STATIC_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
MODELS_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- P1-2 data/*.json 原子写与全局读写锁 ---
# 单把全局可重入锁：串行化所有 JSON 配置库的读/写文件操作
_json_db_lock = threading.RLock()

def atomic_save(path: Path, obj: Any):
    """原子写 JSON：先写 .tmp 再 os.replace，避免写一半留下损坏文件。持全局锁。"""
    path = Path(path)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with _json_db_lock:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)

def safe_load_json(path: Path, default):
    """持锁读取 JSON；解析失败视为损坏，把坏文件改名 .bak 保留后返回默认值。"""
    path = Path(path)
    with _json_db_lock:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            # 文件损坏：备份为 .bak，防止后续反复读到坏文件
            try:
                bak = path.with_suffix(path.suffix + ".bak")
                shutil.copy2(path, bak)
                print(f"[JSON-DB] 文件损坏已备份为 {bak.name}: {path.name} ({e})")
            except Exception:
                pass
            return default() if callable(default) else default
        except FileNotFoundError:
            return default() if callable(default) else default
        except Exception as e:
            print(f"[JSON-DB] 读取失败 {path.name}: {e}")
            return default() if callable(default) else default

def sanitize_name(s: Any) -> str:
    """清洗用户输入，保证可安全用于文件名（M1）"""
    return re.sub(r'[^\w一-鿿.\-]', '_', str(s))

PRODUCTS_FILE = DATA_DIR / "products.json"
if not PRODUCTS_FILE.exists():
    atomic_save(PRODUCTS_FILE, [])

GROUPS_FILE = DATA_DIR / "groups.json"
if not GROUPS_FILE.exists():
    today = datetime.datetime.now().strftime("%Y.%m.%d")
    initial_groups = [
        {
            "id": "group_1",
            "name": "11.06 送审批次 (默认)",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tasks": [
                {
                    "id": f"task_{uuid.uuid4().hex[:8]}",
                    "name": "款式 206209",
                    "sku": "206209",
                    "material_code": today,
                    "size": "36",
                    "category": "单鞋",
                    "season": "四季鞋",
                    "craft": "冷粘",
                    "fabrics": "牛反绒+沙丁布",
                    "soles": "橡胶大底",
                    "shoes": []
                }
            ]
        }
    ]
    atomic_save(GROUPS_FILE, initial_groups)

LOGOS_FILE = DATA_DIR / "logos.json"
DEFAULT_LOGOS = [
    {
        "id": "logo_square_boat",
        "name": "小帆船方形白底镂空LOGO",
        "role": "鞋舌口主标（基本固定）",
        "file": "logos/logo_square_boat.png",
        "default_type": "tongue",
        "default_rel_x": 0.38,
        "default_rel_y": 0.08,
        "default_scale": 1.0,
        "is_builtin": True
    },
    {
        "id": "logo_nvg_cursive",
        "name": "nvg草书LOGO",
        "role": "鞋面/侧身标",
        "file": "logos/logo_nvg_cursive.png",
        "default_type": "side",
        "default_rel_x": 0.44,
        "default_rel_y": 0.48,
        "default_scale": 1.0,
        "is_builtin": True
    },
    {
        "id": "logo_nvg_young",
        "name": "NVG-YOUNG白底镂空",
        "role": "后跟/侧后大标",
        "file": "logos/logo_nvg_young.png",
        "default_type": "heel",
        "default_rel_x": 0.12,
        "default_rel_y": 0.35,
        "default_scale": 0.65,
        "is_builtin": True
    },
    {
        "id": "logo_navigare_letters",
        "name": "纯英文字母LOGO",
        "role": "织带/侧边副标",
        "file": "logos/logo_navigare_letters.png",
        "default_type": "strap",
        "default_rel_x": 0.62,
        "default_rel_y": 0.28,
        "default_scale": 0.85,
        "is_builtin": True
    }
]
if not LOGOS_FILE.exists():
    atomic_save(LOGOS_FILE, DEFAULT_LOGOS)

def load_logos_db() -> List[Dict[str, Any]]:
    if not LOGOS_FILE.exists():
        return list(DEFAULT_LOGOS)
    # 空 list 是合法状态（用户清空标贴库）；只有 JSON 解析异常才算损坏（safe_load_json 内部备份 .bak）
    data = safe_load_json(LOGOS_FILE, lambda: list(DEFAULT_LOGOS))
    return data if isinstance(data, list) else list(DEFAULT_LOGOS)

def save_logos_db(logos: List[Dict[str, Any]]):
    atomic_save(LOGOS_FILE, logos)

# --- Logo Categories DB ---
LOGO_CATEGORIES_FILE = DATA_DIR / "logo_categories.json"
DEFAULT_CATEGORIES = ["常用核心标", "22SS官方库", "鞋身标", "鞋舌标", "大底图案", "自定义"]

def load_categories() -> List[str]:
    if not LOGO_CATEGORIES_FILE.exists():
        atomic_save(LOGO_CATEGORIES_FILE, DEFAULT_CATEGORIES)
        return list(DEFAULT_CATEGORIES)
    data = safe_load_json(LOGO_CATEGORIES_FILE, lambda: list(DEFAULT_CATEGORIES))
    return data if isinstance(data, list) else list(DEFAULT_CATEGORIES)

def save_categories(cats: List[str]):
    atomic_save(LOGO_CATEGORIES_FILE, cats)

# --- Custom Layout Templates DB ---
LAYOUT_TEMPLATES_FILE = DATA_DIR / "layout_templates.json"
DEFAULT_LAYOUT_TEMPLATES = [
    {
        "id": "tmpl_grid_4",
        "name": "四宫格标准 (3~4色推荐)",
        "desc": "标准 2×2 四宫格，3 色填左上、右上、左下，4 色填满四格",
        "slots_map": {
            "2": [{"cx": 1510, "cy": 1060}, {"cx": 1510, "cy": 1830}],
            "3": [{"cx": 1510, "cy": 1060}, {"cx": 2720, "cy": 1060}, {"cx": 1510, "cy": 1830}],
            "4": [{"cx": 1510, "cy": 1060}, {"cx": 2720, "cy": 1060}, {"cx": 1510, "cy": 1830}, {"cx": 2720, "cy": 1830}]
        }
    },
    {
        "id": "tmpl_vertical_2",
        "name": "双色左列纵向 (2色标准)",
        "desc": "左列上下排布，右侧留白展示工艺或备用",
        "slots_map": {
            "2": [{"cx": 1510, "cy": 1060}, {"cx": 1510, "cy": 1830}]
        }
    },
    {
        "id": "tmpl_tri_center_3",
        "name": "品字形居中 (3色对称)",
        "desc": "上方左右 2 款，下方居中 1 款",
        "slots_map": {
            "3": [{"cx": 1550, "cy": 1150}, {"cx": 2750, "cy": 1150}, {"cx": 2150, "cy": 1850}]
        }
    }
]

def load_layout_templates() -> List[Dict[str, Any]]:
    if not LAYOUT_TEMPLATES_FILE.exists():
        atomic_save(LAYOUT_TEMPLATES_FILE, DEFAULT_LAYOUT_TEMPLATES)
        return list(DEFAULT_LAYOUT_TEMPLATES)
    data = safe_load_json(LAYOUT_TEMPLATES_FILE, lambda: list(DEFAULT_LAYOUT_TEMPLATES))
    return data if isinstance(data, list) else list(DEFAULT_LAYOUT_TEMPLATES)

def save_layout_templates(tmpls: List[Dict[str, Any]]):
    atomic_save(LAYOUT_TEMPLATES_FILE, tmpls)

TEMPLATE_CONFIG_FILE = DATA_DIR / "template_config.json"
DEFAULT_TEMPLATE_CONFIG = {
    "title": "臻兴科技开发样品单",
    "category_title": "成人女鞋",
    "reviewer": "审核:",
    "re_reviewer": "复核:",
    "logo_url": "/static/assets/logos/logo_navigare_horizontal.png",
    "logo_filename": "logos/logo_navigare_horizontal.png",
    "fonts": {
        "title_font": "Microsoft YaHei",
        "title_size": 76,
        "title_weight": "bold",
        "title_color": "#000000",
        "category_font": "Microsoft YaHei",
        "category_size": 72,
        "category_weight": "bold",
        "category_color": "#000000",
        "table_font": "Microsoft YaHei",
        "table_size": 52,
        "table_weight": "bold",
        "table_color": "#000000",
        "labels_font": "Microsoft YaHei",
        "labels_size": 48,
        "labels_weight": "normal",
        "labels_color": "#000000",
        "color_label_font": "Microsoft YaHei",
        "color_label_size": 56,
        "color_label_weight": "bold",
        "color_label_color": "#000000"
    },
    "lines": {
        "border_width": 4,
        "border_color": "#000000",
        "inner_width": 2,
        "inner_color": "#000000",
        "divider_x": 840,
        "left_table_label_w": 285
    },
    "labels": {
        "sku": "货号:",
        "season": "季节:",
        "craft": "工艺:",
        "category": "类别:",
        "last": "楦型:",
        "size": "尺码",
        "designer": "设计:",
        "patternmaker": "版师:",
        "order": "打单:",
        "print": "印花:",
        "material_code": "素材编号:",
        "fabrics": "面料:",
        "soles": "鞋底:"
    },
    "is_custom": False
}
if not TEMPLATE_CONFIG_FILE.exists():
    atomic_save(TEMPLATE_CONFIG_FILE, DEFAULT_TEMPLATE_CONFIG)

def load_template_config() -> Dict[str, Any]:
    if not TEMPLATE_CONFIG_FILE.exists():
        return json.loads(json.dumps(DEFAULT_TEMPLATE_CONFIG))
    cfg = safe_load_json(TEMPLATE_CONFIG_FILE, lambda: json.loads(json.dumps(DEFAULT_TEMPLATE_CONFIG)))
    if not isinstance(cfg, dict):
        return json.loads(json.dumps(DEFAULT_TEMPLATE_CONFIG))
    merged = json.loads(json.dumps(DEFAULT_TEMPLATE_CONFIG))
    for k, v in cfg.items():
        if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
            merged[k].update(v)
        else:
            merged[k] = v
    return merged

def save_template_config(cfg: Dict[str, Any]):
    atomic_save(TEMPLATE_CONFIG_FILE, cfg)

FONT_NAME_MAP = {
    "Microsoft YaHei": ("msyh.ttc", "msyhbd.ttc", "MicrosoftYaHei"),
    "SimHei": ("simhei.ttf", "simhei.ttf", "SimHei"),
    "SimSun": ("simsun.ttc", "simsun.ttc", "SimSun"),
    "KaiTi": ("simkai.ttf", "simkai.ttf", "KaiTi"),
    "FangSong": ("simfang.ttf", "simfang.ttf", "FangSong"),
    "Arial": ("arial.ttf", "arialbd.ttf", "ArialMT"),
    "Times New Roman": ("times.ttf", "timesbd.ttf", "TimesNewRomanPSMT")
}

def resolve_pil_font(font_name: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    font_tuple = FONT_NAME_MAP.get(font_name, ("msyh.ttc", "msyhbd.ttc", "MicrosoftYaHei"))
    font_file = font_tuple[1] if bold else font_tuple[0]
    font_path = Path("C:/Windows/Fonts") / font_file
    if not font_path.exists():
        font_path = Path("C:/Windows/Fonts/msyh.ttc")
    try:
        return ImageFont.truetype(str(font_path), size)
    except Exception:
        return ImageFont.load_default()

def create_table_lines_image(lines_cfg: Dict[str, Any], width=3508, height=2480) -> Image.Image:
    border_w = int(lines_cfg.get("border_width", 4))
    inner_w = int(lines_cfg.get("inner_width", 2))
    border_color = lines_cfg.get("border_color", "#000000")
    inner_color = lines_cfg.get("inner_color", "#000000")
    divider_x = int(lines_cfg.get("divider_x", 840))
    label_w = int(lines_cfg.get("left_table_label_w", 285))
    
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([(28, 107), (3422, 2405)], outline=border_color, width=border_w)
    d.line([(28, 258), (3422, 258)], fill=border_color, width=border_w)
    d.line([(2650, 107), (2650, 258)], fill=inner_color, width=inner_w)
    d.line([(3040, 107), (3040, 258)], fill=inner_color, width=inner_w)
    d.line([(divider_x, 258), (divider_x, 2405)], fill=border_color, width=border_w)
    d.line([(label_w, 258), (label_w, 1422)], fill=inner_color, width=inner_w)
    h_rows = [374, 491, 608, 724, 840, 955, 1070, 1185, 1300, 1422]
    for y in h_rows:
        d.line([(28, y), (divider_x, y)], fill=inner_color, width=inner_w)
    d.line([(470, 724), (470, 840)], fill=inner_color, width=inner_w)
    return img

# ============================================================
# 表格文字排版事实源（JPG 导出 / PSD 导出 / 前端预览 三方共用）
# 坐标对齐前端 static/app.js renderTableTexts() 与 static/style.css：
#   表头标题(960,130) 品类(880,300) 审核(2680,145 间隔320) 面料(2480,395) 鞋底(2480,520)
#   左表 10 行：标签列 padding-left 32、数值列 padding-left 40、行内垂直居中
# ============================================================
TABLE_ROW_RECTS = [  # 左表 10 行 (top, height)，与 app.js rowsDef 及 SVG 横线一致
    (258, 116), (374, 117), (491, 117), (608, 116), (724, 116),
    (840, 115), (955, 115), (1070, 115), (1185, 115), (1300, 122)
]
HEADER_TITLE_POS = (960, 130)
HEADER_CATEGORY_POS = (880, 300)
HEADER_REVIEWER_POS = (2680, 145)
HEADER_REVIEWER_GAP = 320      # .reviewer-text flex gap
FABRICS_TEXT_POS = (2480, 395)
SOLES_TEXT_POS = (2480, 520)
TABLE_LEFT_X = 28              # 左表格外框 x（与 SVG rect x=28 一致）
LEFT_LABEL_PAD_X = 32          # .left-row-lbl padding-left
LEFT_VALUE_PAD_X = 40          # .left-row-val padding-left
SIZE_SUBLABEL_W = 185          # .left-row-sublbl width
SIZE_SUBLABEL_PAD_X = 20       # .left-row-sublbl padding-left
PS_PT_PER_PX = 72.0 / 300.0    # 300DPI 画布 像素→点 换算

LABEL_DEFAULTS = {
    "sku": "货号:", "season": "季节:", "craft": "工艺:", "category": "类别:",
    "last": "楦型:", "size": "尺码", "designer": "设计:", "patternmaker": "版师:",
    "order": "打单:", "print": "印花:", "material_code": "素材编号:",
    "fabrics": "面料:", "soles": "鞋底:"
}

def compute_table_text_layout(tmpl_cfg: Dict[str, Any], task) -> List[Dict[str, Any]]:
    """表格文字坐标统一计算（JPG/PSD 共用，避免双轨）。
    每个条目: name/text/x/y_top(PIL 用)/y_baseline(JSX 用)/size_px/size_pt/font_key/font_name/weight/color
    """
    fonts_cfg = tmpl_cfg.get("fonts", {})
    lines_cfg = tmpl_cfg.get("lines", {})
    lbls = tmpl_cfg.get("labels", {})
    label_w = int(lines_cfg.get("left_table_label_w", 285))

    def _pil_font(key):
        return resolve_pil_font(
            fonts_cfg.get(f"{key}_font", "Microsoft YaHei"),
            int(fonts_cfg.get(f"{key}_size", 52)),
            fonts_cfg.get(f"{key}_weight") == "bold")

    def _entry(name, text, x, y_top, key):
        f = _pil_font(key)
        ascent, descent = f.getmetrics()
        size_px = int(fonts_cfg.get(f"{key}_size", 52))
        return {
            "name": name, "text": str(text), "x": int(x), "y_top": int(y_top),
            "y_baseline": int(y_top + ascent),
            "size_px": size_px, "size_pt": round(size_px * PS_PT_PER_PX, 2),
            "font_key": key,
            "font_name": fonts_cfg.get(f"{key}_font", "Microsoft YaHei"),
            "weight": fonts_cfg.get(f"{key}_weight", "normal"),
            "color": fonts_cfg.get(f"{key}_color", "#000000"),
        }

    def _header_y(css_top, key):
        # CSS 盒顶 → PIL 字形顶：按 normal line-height(≈1.3em) 内的居中偏移估算
        f = _pil_font(key)
        ascent, descent = f.getmetrics()
        size_px = int(fonts_cfg.get(f"{key}_size", 52))
        delta = (int(size_px * 1.3) - (ascent + descent)) // 2
        return css_top + max(0, delta)

    def _row_center_y(y0, h, key):
        # 前端 .left-grid-row 为 flex 垂直居中：字形顶 = 行顶 + (行高 - 字形高)/2
        f = _pil_font(key)
        ascent, descent = f.getmetrics()
        return y0 + max(0, (h - (ascent + descent)) // 2)

    entries = []
    # --- 表头 ---
    title = (tmpl_cfg.get("title") or "臻兴科技开发样品单").strip() or "臻兴科技开发样品单"
    entries.append(_entry("表头标题", title, HEADER_TITLE_POS[0], _header_y(HEADER_TITLE_POS[1], "title"), "title"))
    cat = (tmpl_cfg.get("category_title") or "成人女鞋").strip() or "成人女鞋"
    entries.append(_entry("品类名称", cat, HEADER_CATEGORY_POS[0], _header_y(HEADER_CATEGORY_POS[1], "category"), "category"))
    rev_l = tmpl_cfg.get("reviewer", "审核:")
    rev_r = tmpl_cfg.get("re_reviewer", "复核:")
    rev_y = _header_y(HEADER_REVIEWER_POS[1], "labels")
    entries.append(_entry("审核", rev_l, HEADER_REVIEWER_POS[0], rev_y, "labels"))
    rev_w = _pil_font("labels").getlength(rev_l)
    entries.append(_entry("复核", rev_r, HEADER_REVIEWER_POS[0] + rev_w + HEADER_REVIEWER_GAP, rev_y, "labels"))
    # --- 面料 / 鞋底（标签文字取自配置，不再硬编码） ---
    entries.append(_entry("面料", f"{lbls.get('fabrics', '面料:')} {task.fabrics}",
                          FABRICS_TEXT_POS[0], _header_y(FABRICS_TEXT_POS[1], "table"), "table"))
    entries.append(_entry("鞋底", f"{lbls.get('soles', '鞋底:')} {task.soles}",
                          SOLES_TEXT_POS[0], _header_y(SOLES_TEXT_POS[1], "table"), "table"))
    # --- 左表 10 行 ---
    row_defs = [
        ("sku", "sku", task.sku), ("season", "season", task.season),
        ("craft", "craft", task.craft), ("category", "category", task.category),
        ("size", "last", task.size),
        ("designer", "designer", ""), ("patternmaker", "patternmaker", ""),
        ("order", "order", ""), ("print", "print", ""),
        ("material_code", "material_code", task.material_code),
    ]
    label_col_x = TABLE_LEFT_X + LEFT_LABEL_PAD_X                       # 60
    value_col_x = TABLE_LEFT_X + (label_w - TABLE_LEFT_X) + LEFT_VALUE_PAD_X   # label_w + 40
    sublabel_col_x = TABLE_LEFT_X + (label_w - TABLE_LEFT_X) + SIZE_SUBLABEL_PAD_X
    size_value_x = sublabel_col_x + SIZE_SUBLABEL_W + LEFT_VALUE_PAD_X
    for i, (field, label_key, val) in enumerate(row_defs):
        y0, rh = TABLE_ROW_RECTS[i]
        label_txt = lbls.get(label_key, LABEL_DEFAULTS[label_key])
        entries.append(_entry(label_txt, label_txt, label_col_x, _row_center_y(y0, rh, "labels"), "labels"))
        if field == "size":
            # 尺码行结构：楦型: | 尺码 | 36（子标签与数值分列）
            sub_txt = lbls.get("size", LABEL_DEFAULTS["size"])
            entries.append(_entry(sub_txt, sub_txt, sublabel_col_x, _row_center_y(y0, rh, "labels"), "labels"))
            if val:
                entries.append(_entry(f"尺码数值 {val}", val, size_value_x, _row_center_y(y0, rh, "table"), "table"))
        elif val:
            entries.append(_entry(f"{label_txt} {val}", val, value_col_x, _row_center_y(y0, rh, "table"), "table"))
    return entries


# 100% Self-contained: Enforce U2NET_HOME to point directly to project models directory
os.environ["U2NET_HOME"] = str(MODELS_DIR)

from pydantic import BaseModel
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from PIL import Image, ImageDraw, ImageFont, ImageOps
import uvicorn

try:
    from rembg import new_session, remove
    rembg_session = new_session("u2net")
    print("[Server] 通用 rembg u2net 引擎备用就绪。")
except Exception as e:
    rembg_session = None
    remove = None

try:
    from shoe_cutout_engine import ShoeCutoutEngine
    shoe_engine = ShoeCutoutEngine(threads=4)
    print("[Server] 工业级高精鞋样抠图引擎 (ISNet 1024 + 白底救援 + 反解去白边) 已就绪。")
except Exception as e:
    print(f"[Server] 调优抠图引擎载入异常: {e}")
    shoe_engine = None

# P0-3 抠图并发安全：切模型与推理必须在同一把锁内原子执行，
# 否则并发请求会在推理中途被 switch_model 换掉 session 导致张量错位/崩溃
cutout_lock = threading.Lock()

try:
    import packbits
    import pytoshop
    import pytoshop.codecs
    pytoshop.codecs.packbits = packbits
    from pytoshop import enums
    from pytoshop.user import nested_layers
    HAS_PYTOSHOP = True
    print("[Server] Photoshop 可编辑分层 PSD 导出引擎已就绪。")
except Exception as e:
    HAS_PYTOSHOP = False
    print(f"[Server] pytoshop 引擎载入提示: {e}")

def pil_to_psd_layer(img: Image.Image, name: str, left: int, top: int, max_w=3508, max_h=2480):
    if not HAS_PYTOSHOP:
        return None
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    arr = np.array(img, dtype=np.uint8)
    h, w = arr.shape[:2]
    top = max(0, min(top, max_h - 1))
    left = max(0, min(left, max_w - 1))
    bottom = min(max_h, top + h)
    right = min(max_w, left + w)
    if bottom <= top or right <= left:
        arr = np.zeros((1, 1, 4), dtype=np.uint8)
        bottom = top + 1
        right = left + 1
    
    sliced = arr[:(bottom - top), :(right - left)]
    channels = {
        0: sliced[:, :, 0],
        1: sliced[:, :, 1],
        2: sliced[:, :, 2],
        -1: sliced[:, :, 3]
    }
    return nested_layers.Image(
        name=name,
        top=top,
        left=left,
        bottom=bottom,
        right=right,
        channels=channels
    )

def _build_resolution_info_block():
    """构造 300DPI 的 ResolutionInfo 图像资源块（Resource ID 1005）。
    数据布局：hRes(16.16定点) + hResUnit + widthUnit + vRes(16.16定点) + vResUnit + heightUnit，共16字节大端。"""
    if not HAS_PYTOSHOP:
        return None
    import pytoshop.image_resources as pir
    fixed300 = 300 << 16  # 16.16 定点数表示 300.0
    data = struct.pack(">IhhIhh", fixed300, 1, 1, fixed300, 1, 1)  # 单位 1 = Pixels/Inch
    return pir.GenericImageResourceBlock(name="", resource_id=1005, data=data)

def _attach_psd_metadata(psd_doc, composite_rgb: Image.Image):
    """P0-1：给 pytoshop 生成的 PsdFile 补写 300DPI ResolutionInfo 与 merged composite 合成预览图。"""
    try:
        import pytoshop.image_data as pida
        # 1) 合并合成预览图（merged composite）：Photoshop 第三方查看器无需逐层合成即可预览
        comp = np.array(composite_rgb.convert("RGB"), dtype=np.uint8)
        channels = np.stack([comp[:, :, 0], comp[:, :, 1], comp[:, :, 2]], axis=0)
        psd_doc.image_data = pida.ImageData(channels=channels, compression=enums.Compression.rle)
        # 2) 300DPI ResolutionInfo 资源块
        block = _build_resolution_info_block()
        if block is not None and psd_doc.image_resources is not None:
            psd_doc.image_resources.blocks.append(block)
        return True
    except Exception as e:
        print(f"[Render] PSD 元信息补写失败（不影响分层内容）: {e}")
        return False

def verify_psd_dpi(psd_path: Path, expect_dpi: float = 300.0) -> bool:
    """P0-1：导出后用 psd-tools 重开文件断言 DPI==300；失败打 warning，不阻断流程。"""
    try:
        from psd_tools import PSDImage
        from psd_tools.constants import Resource
        psd = PSDImage.open(str(psd_path))
        info = psd.image_resources.get_data(Resource.RESOLUTION_INFO)
        if info is None:
            print(f"[Render][Warning] PSD 未包含 ResolutionInfo: {psd_path.name}")
            return False
        # psd-tools ResoulutionInfo.horizontal 为 16.16 定点整数
        h_res = float(getattr(info, "horizontal", 0)) / 65536.0
        if abs(h_res - expect_dpi) > 1.0:
            print(f"[Render][Warning] PSD DPI 校验失败: 期望 {expect_dpi}, 实际 {h_res}: {psd_path.name}")
            return False
        return True
    except ImportError:
        # TODO: 环境无 psd-tools 时无法回读校验 DPI，保留此 TODO 以便将来接入其它校验方式
        print("[Render][Warning] 未安装 psd-tools，跳过 PSD DPI 回读校验")
        return False
    except Exception as e:
        print(f"[Render][Warning] PSD DPI 回读校验异常: {e}")
        return False

def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

LAN_IP = get_lan_ip()

app = FastAPI(
    title="PSDweb - 鞋样送审图稿制作与款式库工作台",
    description="支持局域网多端共享、多任务标签组管理、产品库一键复用、AI自然语言提取、离线高精抠图与300DPI排版",
    version="2.1.0"
)

# P1-3 安全收紧：仅允许本机前端来源，禁止携带凭据
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8765", "http://localhost:8765"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 静态资源禁缓存：本地工具需要改完即生效，避免浏览器拿旧 CSS/JS（no-cache 每次回源校验，本地零成本）
@app.middleware("http")
async def disable_static_cache(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".css", ".js", ".html")):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response

# Models
class PlacedLogo(BaseModel):
    logo_id: str
    file: Optional[str] = None
    rel_x: float
    rel_y: float
    scale: float = 1.0
    rotation: float = 0.0

class ShoeItem(BaseModel):
    id: str
    color_name: str = ""
    raw_filename: str = ""
    cutout_filename: Optional[str] = None
    is_cutout: bool = False
    offset_x: float = 0.0
    offset_y: float = 0.0
    scale_multiplier: float = 1.0
    logos: List[PlacedLogo] = []

class CanvasLogo(BaseModel):
    id: str
    logo_id: str
    file: Optional[str] = None
    abs_x: float = 1200.0
    abs_y: float = 1200.0
    scale: float = 1.0
    rotation: float = 0.0

class TaskItem(BaseModel):
    id: str
    name: str = "款式任务"
    sku: str = ""
    material_code: str = ""
    season: str = "四季鞋"
    craft: str = "冷粘"
    category: str = "单鞋"
    size: str = "36"
    fabrics: str = "牛反绒"
    soles: str = "橡胶大底"
    shoes: List[ShoeItem] = []
    canvas_logos: List[CanvasLogo] = []

class TaskGroupItem(BaseModel):
    id: str
    name: str
    created_at: Optional[str] = None
    tasks: List[TaskItem] = []

class ProductColorItem(BaseModel):
    id: Optional[str] = None
    color_name: str = ""
    image_url: Optional[str] = None
    raw_filename: Optional[str] = None
    cutout_filename: Optional[str] = None
    is_cutout: bool = False

class ProductItem(BaseModel):
    id: Optional[str] = None
    sku: str
    name: str
    category: str = "单鞋"
    season: str = "四季鞋"
    craft: str = "冷粘"
    fabrics: str = "牛反绒"
    soles: str = "橡胶大底"
    size: str = "36"
    default_colors: List[str] = []
    colors: List[ProductColorItem] = []
    cover_image: Optional[str] = None
    layout_history: List[Dict[str, Any]] = []
    notes: str = ""
    updated_at: Optional[str] = None

class SnapshotRequest(BaseModel):
    name: str = "默认排版快照"
    shoes: List[ShoeItem]

class BatchCutoutRequest(BaseModel):
    filenames: Optional[List[str]] = None
    raw_filenames: Optional[List[str]] = None
    force: bool = False
    model_id: Optional[str] = None

class SelectModelRequest(BaseModel):
    model_id: str

class BatchRenderRequest(BaseModel):
    tasks: List[TaskItem]

class AiParseRequest(BaseModel):
    prompt: str

@app.get("/")
def read_root():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/initial-data")
def get_initial_data():
    today = datetime.datetime.now().strftime("%Y.%m.%d")
    return {
        "material_code": today,
        "size": "36",
        "category": "单鞋",
        "season": "四季鞋",
        "craft": "冷粘",
        "fabrics": "牛反绒",
        "soles": "橡胶大底",
        "lan_ip": LAN_IP,
        "lan_url": f"http://{LAN_IP}:8765",
        "season_options": ["四季鞋", "春单", "秋单", "棉鞋", "凉鞋"],
        "craft_options": ["冷粘", "硫化", "注塑"],
        "category_options": ["单鞋", "老爹鞋", "板鞋", "休闲鞋", "德训鞋", "马丁靴"],
        "fabric_presets": ["牛反绒", "猪巴+沙丁布", "反绒皮+网布", "牛皮+反绒", "超纤皮", "网布+飞织"],
        "sole_presets": ["橡胶大底", "MD大底", "橡胶+EVA", "发泡大底", "聚氨酯底", "生胶大底"],
        "logos": load_logos_db(),
        "template_config": load_template_config(),
        "categories": load_categories(),
        "layout_templates": load_layout_templates()
    }

# --- Logos Management CRUD (标贴模版管理：增删改换) ---

@app.get("/api/logos")
def list_logos(category: Optional[str] = None, q: Optional[str] = None):
    db = load_logos_db()
    res = []
    q_lower = q.lower().strip() if q else None
    for item in db:
        if category and category != "all":
            item_cat = item.get("category", "")
            if category == "core" and "常用" not in item_cat:
                continue
            elif category == "pdf" and "22SS" not in item_cat:
                continue
            elif category == "custom" and item.get("is_builtin", False):
                continue
        if q_lower:
            match = (
                q_lower in item.get("name", "").lower() or
                q_lower in item.get("id", "").lower() or
                q_lower in item.get("role", "").lower() or
                q_lower in item.get("code", "").lower()
            )
            if not match:
                continue
        res.append(item)
    return {"status": "success", "logos": res}

@app.post("/api/logos/upload")
async def upload_logo_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    role: str = Form(""),
    default_type: str = Form("side")
):
    try:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in [".png", ".jpg", ".jpeg", ".webp"]:
            suffix = ".png"
        new_id = f"logo_{uuid.uuid4().hex[:8]}"
        saved_filename = f"{new_id}{suffix}"
        dest_path = ASSETS_DIR / "logos" / saved_filename
        
        contents = await file.read()
        pil_img = Image.open(io.BytesIO(contents)).convert("RGBA")
        pil_img.save(dest_path, format="PNG")
        
        rel_pos_map = {
            "tongue": {"x": 0.38, "y": 0.08, "scale": 1.0},
            "side": {"x": 0.44, "y": 0.48, "scale": 1.0},
            "heel": {"x": 0.12, "y": 0.35, "scale": 0.65},
            "strap": {"x": 0.62, "y": 0.28, "scale": 0.85},
            "toe": {"x": 0.68, "y": 0.58, "scale": 0.75}
        }
        pos = rel_pos_map.get(default_type, {"x": 0.44, "y": 0.48, "scale": 1.0})
        
        new_item = {
            "id": new_id,
            "name": name.strip(),
            "role": role.strip() or "自定义标贴",
            "file": f"logos/{saved_filename}",
            "default_type": default_type,
            "default_rel_x": pos["x"],
            "default_rel_y": pos["y"],
            "default_scale": pos["scale"],
            "is_builtin": False
        }
        
        db = load_logos_db()
        db.append(new_item)
        save_logos_db(db)
        return {"status": "success", "logo": new_item}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/logos/{logo_id}/replace")
async def replace_logo_image(logo_id: str, file: UploadFile = File(...)):
    db = load_logos_db()
    target_idx = None
    for i, item in enumerate(db):
        if item["id"] == logo_id:
            target_idx = i
            break
    if target_idx is None:
        raise HTTPException(status_code=404, detail="标贴不存在")
        
    try:
        item = db[target_idx]
        current_file = item.get("file", f"logos/{logo_id}.png")
        dest_path = STATIC_DIR / "assets" / current_file
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        contents = await file.read()
        pil_img = Image.open(io.BytesIO(contents)).convert("RGBA")
        pil_img.save(dest_path, format="PNG")
        
        return {"status": "success", "logo": item}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UpdateLogoRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    default_type: Optional[str] = None

@app.put("/api/logos/{logo_id}")
def update_logo_info(logo_id: str, req: UpdateLogoRequest):
    db = load_logos_db()
    for item in db:
        if item["id"] == logo_id:
            if req.name is not None:
                item["name"] = req.name.strip()
            if req.role is not None:
                item["role"] = req.role.strip()
            if req.default_type is not None:
                item["default_type"] = req.default_type
            save_logos_db(db)
            return {"status": "success", "logo": item}
    raise HTTPException(status_code=404, detail="标贴不存在")


def remove_logo_background(img: Image.Image) -> Image.Image:
    img_rgba = img.convert("RGBA")
    try:
        # 持锁访问共享 session，避免推理中途被 switch_model 替换
        with cutout_lock:
            if shoe_engine and shoe_engine.session:
                import rembg
                out_img = rembg.remove(img_rgba, session=shoe_engine.session)
                alpha = out_img.split()[-1]
                if alpha.getbbox():
                    return out_img
    except Exception as e:
        # 抠图引擎失败不再静默：记录堆栈，便于定位"边缘一团糟"类问题
        import traceback
        print(f"[Logo Cutout] AI 抠图失败，降级为四角亮度启发式: {e}")
        traceback.print_exc()

    try:
        import numpy as np
        data = np.array(img_rgba)
        r, g, b, a = data[:, :, 0], data[:, :, 1], data[:, :, 2], data[:, :, 3]
        h, w = r.shape
        corners = [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]
        corner_bright = [int(r[y, x]) > 210 and int(g[y, x]) > 210 and int(b[y, x]) > 210 for y, x in corners]
        if sum(corner_bright) >= 2:
            dist_white = np.maximum(np.maximum(255 - r, 255 - g), 255 - b)
            new_a = np.clip((dist_white.astype(np.float32) - 15.0) / 25.0 * 255.0, 0, 255).astype(np.uint8)
            data[:, :, 3] = np.minimum(a, new_a)
            return Image.fromarray(data, "RGBA")
    except Exception as e:
        print(f"[Logo Cutout] NumPy fallback error: {e}")
    return img_rgba

@app.post("/api/logos/{logo_id}/cutout")
def cutout_existing_logo(logo_id: str):
    db = load_logos_db()
    target_item = None
    for item in db:
        if item["id"] == logo_id:
            target_item = item
            break
    if not target_item:
        raise HTTPException(status_code=404, detail="标贴不存在")

    rel_file = target_item.get("file", "")
    src_path = ASSETS_DIR / rel_file if not rel_file.startswith("uploads/") else UPLOADS_DIR / rel_file.replace("uploads/", "")
    if not src_path.exists():
        src_path = ASSETS_DIR / "logos" / Path(rel_file).name
    if not src_path.exists():
        raise HTTPException(status_code=404, detail="标贴原图文件不存在")

    try:
        orig = Image.open(src_path)
        cutout = remove_logo_background(orig)
        out_name = f"cutout_{Path(src_path).stem}_{uuid.uuid4().hex[:6]}.png"
        out_path = ASSETS_DIR / "logos" / out_name
        cutout.save(out_path, format="PNG")
        
        target_item["file"] = f"logos/{out_name}"
        save_logos_db(db)
        return {"status": "success", "logo": target_item}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"标贴抠图失败: {e}")

@app.post("/api/logos/upload-and-cutout")
async def upload_and_cutout_logo(file: UploadFile = File(...), auto_cutout: bool = False):
    try:
        contents = await file.read()
        pil_img = Image.open(io.BytesIO(contents))
        if auto_cutout:
            pil_img = remove_logo_background(pil_img)
        else:
            pil_img = pil_img.convert("RGBA")
        
        stem = Path(file.filename or "pasted_logo").stem
        clean_stem = re.sub(r'[^A-Za-z0-9_一-龥]', '_', stem)
        out_name = f"logo_{clean_stem}_{uuid.uuid4().hex[:6]}.png"
        out_path = ASSETS_DIR / "logos" / out_name
        pil_img.save(out_path, format="PNG")

        db = load_logos_db()
        new_item = {
            "id": f"logo_custom_{uuid.uuid4().hex[:8]}",
            "name": stem or "自定义图案",
            "file": f"logos/{out_name}",
            "role": "自定义图案",
            "default_type": "side",
            "is_system": False,
            "width": pil_img.width,
            "height": pil_img.height,
            "default_rel_x": 0.24,
            "default_rel_y": 0.45
        }
        db.append(new_item)
        save_logos_db(db)
        return {"status": "success", "logo": new_item}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传标贴失败: {e}")

@app.delete("/api/logos/{logo_id}")
def delete_logo(logo_id: str):
    db = load_logos_db()
    new_db = [item for item in db if item["id"] != logo_id]
    if len(new_db) == len(db):
        raise HTTPException(status_code=404, detail="标贴不存在")
    save_logos_db(new_db)
    return {"status": "success", "deleted_id": logo_id}

# --- Category Management Endpoints ---

@app.get("/api/logos/categories")
def get_logo_categories_api():
    cats = load_categories()
    logos = load_logos_db()
    cat_counts = {}
    for l in logos:
        c = l.get("category") or "未分类"
        cat_counts[c] = cat_counts.get(c, 0) + 1
    res = []
    for c in cats:
        res.append({"name": c, "count": cat_counts.get(c, 0)})
    return {"status": "success", "categories": res}

@app.post("/api/logos/categories")
def add_logo_category_api(req: Dict[str, str]):
    name = req.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="分类名称不能为空")
    cats = load_categories()
    if name not in cats:
        cats.append(name)
        save_categories(cats)
    return {"status": "success", "categories": cats}

@app.put("/api/logos/categories")
def rename_logo_category_api(req: Dict[str, str]):
    old_name = req.get("old_name", "").strip()
    new_name = req.get("new_name", "").strip()
    if not old_name or not new_name:
        raise HTTPException(status_code=400, detail="分类名称不能为空")
    cats = load_categories()
    if old_name in cats:
        idx = cats.index(old_name)
        cats[idx] = new_name
        save_categories(cats)
    logos = load_logos_db()
    for l in logos:
        if l.get("category") == old_name:
            l["category"] = new_name
    save_logos_db(logos)
    return {"status": "success", "categories": cats}

@app.delete("/api/logos/categories")
def delete_logo_category_api(name: str):
    name = name.strip()
    cats = load_categories()
    if name in cats:
        cats.remove(name)
        save_categories(cats)
    logos = load_logos_db()
    for l in logos:
        if l.get("category") == name:
            l["category"] = "未分类"
    save_logos_db(logos)
    return {"status": "success", "categories": cats}

@app.post("/api/logos/batch-delete")
def batch_delete_logos_api(req: Dict[str, Any]):
    ids = set(req.get("ids", []))
    if not ids:
        return {"status": "success", "deleted_count": 0}
    logos = load_logos_db()
    new_logos = [l for l in logos if l["id"] not in ids]
    deleted_cnt = len(logos) - len(new_logos)
    save_logos_db(new_logos)
    return {"status": "success", "deleted_count": deleted_cnt}

@app.post("/api/logos/batch-move")
def batch_move_logos_api(req: Dict[str, Any]):
    ids = set(req.get("ids", []))
    target_cat = req.get("category", "未分类").strip()
    if not ids:
        return {"status": "success", "moved_count": 0}
    cats = load_categories()
    if target_cat not in cats and target_cat != "未分类":
        cats.append(target_cat)
        save_categories(cats)
    logos = load_logos_db()
    moved_cnt = 0
    for l in logos:
        if l["id"] in ids:
            l["category"] = target_cat
            moved_cnt += 1
    save_logos_db(logos)
    return {"status": "success", "moved_count": moved_cnt}

@app.put("/api/logos/{logo_id}/rename")
def rename_single_logo_api(logo_id: str, req: Dict[str, str]):
    new_name = req.get("name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="素材名称不能为空")
    logos = load_logos_db()
    found = False
    for l in logos:
        if l["id"] == logo_id:
            l["name"] = new_name
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="未找到素材")
    save_logos_db(logos)
    return {"status": "success", "logo_id": logo_id, "name": new_name}

@app.post("/api/logos/upload-multiple")
async def upload_multiple_materials_api(
    files: List[UploadFile] = File(...),
    category: Optional[str] = Form("自定义")
):
    db = load_logos_db()
    added_items = []
    cat_name = category or "自定义"
    cats = load_categories()
    if cat_name not in cats:
        cats.append(cat_name)
        save_categories(cats)

    for file in files:
        fname = file.filename or "upload_material"
        ext = Path(fname).suffix.lower()
        contents = await file.read()

        if ext == ".pdf":
            try:
                import fitz
                doc = fitz.open(stream=contents, filetype="pdf")
                for p_idx in range(len(doc)):
                    page = doc[p_idx]
                    pix = page.get_pixmap(dpi=150)
                    p_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples).convert("RGBA")
                    arr = np.array(p_img)
                    gray = np.mean(arr[:, :, :3], axis=2)
                    mask = (gray < 240)
                    if np.mean(mask) < 0.008:
                        continue
                    ys, xs = np.where(mask)
                    x0 = max(0, int(xs.min()) - 6)
                    y0 = max(0, int(ys.min()) - 6)
                    x1 = min(p_img.width, int(xs.max()) + 6)
                    y1 = min(p_img.height, int(ys.max()) + 6)
                    cropped = p_img.crop((x0, y0, x1, y1))
                    
                    c_arr = np.array(cropped)
                    wh_mask = (c_arr[:, :, 0] > 240) & (c_arr[:, :, 1] > 240) & (c_arr[:, :, 2] > 240)
                    c_arr[wh_mask, 3] = 0
                    final_crop = Image.fromarray(c_arr, "RGBA")

                    uid = uuid.uuid4().hex[:8]
                    out_name = f"logo_pdf_p{p_idx+1}_{uid}.png"
                    out_path = ASSETS_DIR / "logos" / out_name
                    final_crop.save(out_path, format="PNG")
                    item = {
                        "id": f"logo_{uid}",
                        "name": f"{Path(fname).stem}-P{p_idx+1}",
                        "file": f"logos/{out_name}",
                        "category": cat_name,
                        "role": "矢量标贴",
                        "default_type": "side",
                        "is_builtin": False,
                        "width": final_crop.width,
                        "height": final_crop.height
                    }
                    db.append(item)
                    added_items.append(item)
            except Exception as ex:
                print(f"[Upload-Multi] PDF extract error: {ex}")
            continue

        try:
            # 按需抠图：入库保留原图（含白底与完整构图），不再自动去背/裁剪；
            # 需要透明底时由用户点击卡片上的「抠图」按钮，走 /api/logos/{id}/cutout
            pil_img = Image.open(io.BytesIO(contents))
            if pil_img.mode != "RGBA":
                pil_img = pil_img.convert("RGBA")

            stem = Path(fname).stem
            clean_stem = re.sub(r'[^A-Za-z0-9_一-龥\-]', '_', stem)
            uid = uuid.uuid4().hex[:8]
            out_name = f"logo_{clean_stem}_{uid}.png"
            out_path = ASSETS_DIR / "logos" / out_name
            pil_img.save(out_path, format="PNG")

            item = {
                "id": f"logo_{uid}",
                "name": stem or "自定义素材",
                "file": f"logos/{out_name}",
                "category": cat_name,
                "role": "通用素材",
                "default_type": "side",
                "is_builtin": False,
                "width": pil_img.width,
                "height": pil_img.height
            }
            db.append(item)
            added_items.append(item)
        except Exception as ex:
            print(f"[Upload-Multi] Image error for {fname}: {ex}")

    save_logos_db(db)
    return {"status": "success", "added_count": len(added_items), "added_items": added_items}

# --- Layout Templates Endpoints ---

@app.get("/api/layout-templates")
def get_layout_templates_api():
    return {"status": "success", "templates": load_layout_templates()}

@app.post("/api/layout-templates")
def save_layout_template_api(req: Dict[str, Any]):
    name = req.get("name", "").strip() or f"自定义模版 {len(load_layout_templates())+1}"
    slots_map = req.get("slots_map", {})
    tmpls = load_layout_templates()
    uid = f"tmpl_user_{uuid.uuid4().hex[:6]}"
    new_tmpl = {
        "id": uid,
        "name": name,
        "desc": req.get("desc", "用户自定义排版模版"),
        "is_user": True,
        "slots_map": slots_map
    }
    tmpls.append(new_tmpl)
    save_layout_templates(tmpls)
    return {"status": "success", "template": new_tmpl}

@app.delete("/api/layout-templates/{template_id}")
def delete_layout_template_api(template_id: str):
    tmpls = load_layout_templates()
    new_tmpls = [t for t in tmpls if t["id"] != template_id]
    save_layout_templates(new_tmpls)
    return {"status": "success", "deleted_id": template_id}


# --- Template Config API (底表模版编辑：换文字、字体、线条与主Logo) ---

@app.get("/api/template-config")
def get_template_config_api():
    return {"status": "success", "config": load_template_config()}

@app.post("/api/template-config")
async def update_template_config_api(req: Dict[str, Any]):
    cfg = load_template_config()
    for k, v in req.items():
        if isinstance(v, dict) and k in cfg and isinstance(cfg[k], dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    cfg["is_custom"] = True
    save_template_config(cfg)
    return {"status": "success", "config": cfg}

@app.post("/api/template-config/upload-logo")
async def upload_template_header_logo(file: UploadFile = File(...)):
    try:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in [".png", ".jpg", ".jpeg", ".webp"]:
            suffix = ".png"
        saved_name = f"custom_brand_logo{suffix}"
        dest_path = UPLOADS_DIR / saved_name
        
        contents = await file.read()
        pil_img = Image.open(io.BytesIO(contents)).convert("RGBA")
        pil_img.save(dest_path, format="PNG")
        
        cfg = load_template_config()
        cfg["logo_url"] = f"/static/uploads/{saved_name}"
        cfg["logo_filename"] = f"uploads/{saved_name}"
        cfg["is_custom"] = True
        save_template_config(cfg)
        
        return {"status": "success", "config": cfg}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/template-config/reset")
def reset_template_config_api():
    cfg = json.loads(json.dumps(DEFAULT_TEMPLATE_CONFIG))
    save_template_config(cfg)
    return {"status": "success", "config": cfg}

class ImportPdfLogosRequest(BaseModel):
    pdf_path: Optional[str] = None

@app.post("/api/logos/import-pdf")
async def import_pdf_logos_endpoint(req: ImportPdfLogosRequest):
    pdf_p = req.pdf_path
    if not pdf_p:
        # Default downloads folder
        dl_p = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Downloads" / "新建文件夹 (2)" / "22FW图案编号基础版02.12 (1).pdf"
        if dl_p.exists():
            pdf_p = str(dl_p)
        else:
            raise HTTPException(status_code=400, detail="未找到默认 PDF 文件路径，请指定有效路径")
    if not os.path.exists(pdf_p):
        raise HTTPException(status_code=404, detail=f"文件不存在: {pdf_p}")
        
    try:
        import fitz
        doc = fitz.open(pdf_p)
        out_dir = STATIC_DIR / "assets" / "logos" / "library"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        col_ranges = [(30, 452), (454, 876), (878, 1300), (1302, 1724)]
        row_ranges = [(23, 335), (428, 740), (837, 1149)]
        
        db = load_logos_db()
        existing_ids = set(item["id"] for item in db)
        added_count = 0
        
        for p_idx in range(len(doc)):
            page = doc[p_idx]
            pix = page.get_pixmap(dpi=150)
            page_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            words = page.get_text("words")
            codes = [w for w in words if re.match(r"^22[A-Z0-9\-]+$", w[4])]
            codes.sort(key=lambda w: (round(w[1] / 150.0), w[0]))
            
            c_idx_counter = 0
            for r_idx, (y0, y1) in enumerate(row_ranges):
                for c_idx, (x0, x1) in enumerate(col_ranges):
                    if c_idx_counter < len(codes):
                        code_name = codes[c_idx_counter][4]
                    else:
                        code_name = f"22SS_P{p_idx+1}_{r_idx+1}_{c_idx+1}"
                    c_idx_counter += 1
                    
                    cell = page_img.crop((x0, y0, x1, y1))
                    rgba = cell.convert("RGBA")
                    arr = np.array(rgba)
                    is_white = (arr[:, :, 0] > 238) & (arr[:, :, 1] > 238) & (arr[:, :, 2] > 238)
                    arr[is_white, 3] = 0
                    
                    non_trans = arr[:, :, 3] > 0
                    rows = np.any(non_trans, axis=1)
                    cols = np.any(non_trans, axis=0)
                    if np.any(rows) and np.any(cols):
                        rmin, rmax = np.where(rows)[0][[0, -1]]
                        cmin, cmax = np.where(cols)[0][[0, -1]]
                        rmin = max(0, rmin - 2)
                        rmax = min(arr.shape[0] - 1, rmax + 2)
                        cmin = max(0, cmin - 2)
                        cmax = min(arr.shape[1] - 1, cmax + 2)
                        tight_img = Image.fromarray(arr[rmin:rmax+1, cmin:cmax+1])
                        filename = f"logo_{code_name}.png"
                        tight_img.save(out_dir / filename, format="PNG")
                        
                        logo_id = f"logo_{code_name}"
                        if logo_id not in existing_ids:
                            db.append({
                                "id": logo_id,
                                "name": f"小帆船 {code_name}",
                                "code": code_name,
                                "role": "鞋身/鞋舌标贴",
                                "category": "22SS系列官方图案库",
                                "file": f"logos/library/{filename}",
                                "default_type": "side" if "NVG" in code_name or "NG" in code_name else "tongue",
                                "default_rel_x": 0.45,
                                "default_rel_y": 0.45,
                                "default_scale": 0.85,
                                "is_builtin": True
                            })
                            existing_ids.add(logo_id)
                            added_count += 1
                            
        save_logos_db(db)
        return {"status": "success", "added_count": added_count, "total_logos": len(db)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Task Groups (任务标签 / 批次分组 CRUD) ---

def load_groups_db() -> List[Dict[str, Any]]:
    if not GROUPS_FILE.exists():
        return []
    data = safe_load_json(GROUPS_FILE, list)
    return data if isinstance(data, list) else []

def save_groups_db(groups: List[Dict[str, Any]]):
    atomic_save(GROUPS_FILE, groups)

@app.get("/api/groups")
def list_groups():
    return {"status": "success", "groups": load_groups_db()}

@app.post("/api/groups")
def create_group(req: TaskGroupItem):
    db = load_groups_db()
    gid = req.id or f"group_{uuid.uuid4().hex[:8]}"
    item = req.model_dump()
    item["id"] = gid
    item["created_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.append(item)
    save_groups_db(db)
    return {"status": "success", "group": item}

@app.put("/api/groups/{group_id}")
def update_group(group_id: str, req: TaskGroupItem):
    db = load_groups_db()
    found = False
    for i, g in enumerate(db):
        if g["id"] == group_id:
            db[i]["name"] = req.name
            if req.tasks:
                db[i]["tasks"] = [t.model_dump() for t in req.tasks]
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="任务标签不存在")
    save_groups_db(db)
    return {"status": "success", "group": db[i]}

@app.delete("/api/groups/{group_id}")
def delete_group(group_id: str):
    db = load_groups_db()
    if len(db) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个任务标签！")
    new_db = [g for g in db if g["id"] != group_id]
    if len(new_db) == len(db):
        raise HTTPException(status_code=404, detail="任务标签不存在")
    save_groups_db(new_db)
    return {"status": "success", "deleted_id": group_id}

@app.post("/api/groups/save-all")
def save_all_groups(groups: List[TaskGroupItem]):
    save_groups_db([g.model_dump() for g in groups])
    return {"status": "success"}

# --- Product Library (款式资料库 CRUD) ---

def load_products_db() -> List[Dict[str, Any]]:
    if not PRODUCTS_FILE.exists():
        return []
    data = safe_load_json(PRODUCTS_FILE, list)
    return data if isinstance(data, list) else []

def save_products_db(items: List[Dict[str, Any]]):
    atomic_save(PRODUCTS_FILE, items)

@app.get("/api/products")
def list_products():
    return {"status": "success", "products": load_products_db()}

@app.post("/api/products")
def create_product(prod: ProductItem):
    db = load_products_db()
    pid = prod.id or f"prod_{uuid.uuid4().hex[:8]}"
    item = prod.model_dump()
    item["id"] = pid
    item["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    existing = next((i for i, p in enumerate(db) if p["sku"] == prod.sku), None)
    if existing is not None:
        db[existing] = item
    else:
        db.insert(0, item)
        
    save_products_db(db)
    return {"status": "success", "product": item}

@app.put("/api/products/{product_id}")
def update_product(product_id: str, prod: ProductItem):
    db = load_products_db()
    found = False
    for i, p in enumerate(db):
        if p["id"] == product_id:
            item = prod.model_dump()
            item["id"] = product_id
            item["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db[i] = item
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="款式不存在")
    save_products_db(db)
    return {"status": "success", "product": db[i]}

@app.delete("/api/products/{product_id}")
def delete_product(product_id: str):
    db = load_products_db()
    new_db = [p for p in db if p["id"] != product_id]
    if len(new_db) == len(db):
        raise HTTPException(status_code=404, detail="款式不存在")
    save_products_db(new_db)
    return {"status": "success", "deleted_id": product_id}

@app.post("/api/products/{product_id}/snapshot")
def save_product_snapshot(product_id: str, req: SnapshotRequest):
    db = load_products_db()
    for i, p in enumerate(db):
        if p["id"] == product_id or p["sku"] == product_id:
            if "layout_history" not in db[i] or not isinstance(db[i]["layout_history"], list):
                db[i]["layout_history"] = []
            snap_item = {
                "id": f"snap_{uuid.uuid4().hex[:8]}",
                "name": req.name or f"排版快照 {len(db[i]['layout_history']) + 1}",
                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "shoes_count": len(req.shoes),
                "shoes": [s.model_dump() for s in req.shoes]
            }
            db[i]["layout_history"].insert(0, snap_item)
            # If product has no cover image yet and there's a shoe with image, set cover automatically
            if not db[i].get("cover_image") and req.shoes:
                for s in req.shoes:
                    if s.cutout_filename:
                        db[i]["cover_image"] = f"/static/uploads/{s.cutout_filename}"
                        break
                    elif s.raw_filename:
                        db[i]["cover_image"] = f"/static/uploads/{s.raw_filename}"
                        break
            db[i]["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_products_db(db)
            return {"status": "success", "snapshot": snap_item, "product": db[i]}
    raise HTTPException(status_code=404, detail="款式不存在")

@app.post("/api/products/upload-cover")
async def upload_product_cover(file: UploadFile = File(...)):
    try:
        raw_ext = Path(file.filename or "").suffix.lower()
        # P1-3：扩展名白名单，且用 PIL 打开重编码后再保存，杜绝伪装图片/脚本文件
        if raw_ext not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise HTTPException(status_code=400, detail="仅支持 png/jpg/jpeg/webp 封面图片")
        unique_id = uuid.uuid4().hex[:8]
        cover_filename = f"prod_cover_{unique_id}{raw_ext}"
        cover_path = UPLOADS_DIR / cover_filename
        content = await file.read()
        try:
            with Image.open(io.BytesIO(content)) as im:
                im.load()
                if raw_ext in (".jpg", ".jpeg"):
                    im.convert("RGB").save(cover_path, format="JPEG", quality=95)
                elif raw_ext == ".webp":
                    im.convert("RGB").save(cover_path, format="WEBP", quality=95)
                else:
                    im.convert("RGBA").save(cover_path, format="PNG")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="文件内容不是有效图片")
        return {
            "status": "success",
            "cover_url": f"/static/uploads/{cover_filename}",
            "filename": cover_filename
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- AI Parsing Assistant (自然语言智能提取) ---


def extract_spec_fields(text: str) -> Dict[str, Any]:
    result = {
        "sku": "",
        "name": "",
        "category": "单鞋",
        "season": "四季鞋",
        "craft": "冷粘",
        "fabrics": "牛反绒",
        "soles": "橡胶大底",
        "size": "36",
        "colors": []
    }
    sku_match = re.search(r'(?:款号|货号|型号|编号|款)\s*[:：]?\s*([A-Za-z0-9\-]+)', text)
    if not sku_match:
        sku_match = re.search(r'\b(20\d{4}|\d{6,8})\b', text)
    if sku_match:
        result["sku"] = sku_match.group(1)
        result["name"] = f"款式 {result['sku']}"

    for cat in ["老爹鞋", "德训鞋", "马丁靴", "休闲鞋", "板鞋", "单鞋", "凉鞋", "短靴", "女鞋", "运动鞋"]:
        if cat in text:
            result["category"] = "单鞋" if cat in ["女鞋", "单鞋"] else cat
            break

    for s in ["春单", "秋单", "四季鞋", "棉鞋", "凉鞋", "春夏", "秋冬", "四季"]:
        if s in text:
            result["season"] = "四季鞋" if s in ["四季", "春夏"] else s
            break

    for c in ["冷粘", "硫化", "注塑"]:
        if c in text:
            result["craft"] = c
            break

    fabric_keywords = [
        "牛反绒", "猪巴", "沙丁布", "植绒", "超纤皮", "牛皮", "反绒皮", "网布", "飞织", 
        "羊皮", "磨砂皮", "帆布", "PU皮", "真皮", "反绒"
    ]
    found_fabrics = [k for k in fabric_keywords if k in text]
    if found_fabrics:
        result["fabrics"] = "+".join(found_fabrics)
    else:
        m_fab = re.search(r'面料\s*[:：]?\s*([^\s,，；;]+)', text)
        if m_fab:
            result["fabrics"] = m_fab.group(1)

    sole_keywords = [
        "橡胶大底", "MD大底", "橡胶+EVA", "发泡大底", "聚氨酯底", "生胶大底", 
        "橡胶底", "MD底", "EVA底", "防滑底", "厚底"
    ]
    found_soles = [s for s in sole_keywords if s in text]
    if found_soles:
        result["soles"] = found_soles[0]
    else:
        m_sole = re.search(r'(?:鞋底|大底|底)\s*[:：]?\s*([^\s,，；;]+)', text)
        if m_sole:
            result["soles"] = m_sole.group(1)

    color_candidates = [
        "黑色", "酒红", "粉色", "米白", "卡其", "深蓝", "深灰", "浅灰", "墨绿", "棕色", 
        "奶茶", "焦糖", "大红", "藏青", "银白", "白色", "咖色", "米黄", "红色", "蓝色", "浅粉", "灰白"
    ]
    found_colors = []
    for c in color_candidates:
        if c in text and c not in found_colors:
            found_colors.append(c)
    if found_colors:
        result["colors"] = found_colors
    return result

@app.post("/api/ai/parse-spec-image")
async def parse_spec_from_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        suffix = Path(file.filename or "temp.png").suffix or ".png"
        tmp_img = UPLOADS_DIR / f"ocr_tmp_{uuid.uuid4().hex[:8]}{suffix}"
        with open(tmp_img, "wb") as f:
            f.write(contents)

        ps_script = BASE_DIR / "windows_ocr.ps1"
        extracted_text = ""
        if ps_script.exists():
            cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps_script), "-ImagePath", str(tmp_img)]
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
            if p.returncode == 0:
                extracted_text = p.stdout.strip()

        try:
            tmp_img.unlink(missing_ok=True)
        except Exception:
            pass

        if not extracted_text:
            return {"status": "warning", "message": "未能从图片中识别到清晰文字", "parsed": extract_spec_fields("")}

        parsed = extract_spec_fields(extracted_text)
        return {"status": "success", "raw_text": extracted_text, "parsed": parsed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片OCR解析失败: {e}")

@app.post("/api/ai/parse-spec")
def parse_spec_with_ai(req: AiParseRequest):
    text = req.prompt.strip()
    if not text:
        raise HTTPException(status_code=400, detail="内容不能为空")
    result = extract_spec_fields(text)
    return {"status": "success", "parsed": result}

# --- Raw Upload & Cutout ---

# 最大允许尺寸 (超出则等比例缩放，2048px 为 1024 抠图模型的 2 倍采样，既保留极致微细节与车线，又杜绝卡顿与爆内存)
MAX_UPLOAD_DIM = int(os.environ.get("CUT_MAX_DIM", "2048"))

@app.post("/api/upload-raw")
async def upload_raw_photo(file: UploadFile = File(...)):
    try:
        raw_ext = Path(file.filename).suffix.lower() or ".jpg"
        unique_id = uuid.uuid4().hex[:8]
        raw_filename = f"raw_{unique_id}{raw_ext}"
        raw_path = UPLOADS_DIR / raw_filename
        
        contents = await file.read()
        
        # 使用 PIL 读取并自动校正手机/相机 EXIF 拍摄方向
        with Image.open(io.BytesIO(contents)) as im:
            im = ImageOps.exif_transpose(im)
            orig_w, orig_h = im.size
            
            was_downscaled = False
            # 若超过抠图模型与送审图纸最佳尺寸，自动等比例缩小
            if max(orig_w, orig_h) > MAX_UPLOAD_DIM:
                scale = MAX_UPLOAD_DIM / float(max(orig_w, orig_h))
                new_w = int(round(orig_w * scale))
                new_h = int(round(orig_h * scale))
                # 采用专业级 Lanczos 抗锯齿重采样，锁住鞋面织纹、皮纹与细微车缝线，不损失画质
                im = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
                was_downscaled = True
            
            # 高质量存储：JPEG 采用 95 极高画质 + 0 色度抽样(4:4:4)，PNG 采用轻压缩
            if raw_ext in ['.jpg', '.jpeg']:
                if im.mode in ('RGBA', 'P'):
                    im = im.convert('RGB')
                im.save(raw_path, format="JPEG", quality=95, subsampling=0)
            else:
                im.save(raw_path, format="PNG", compress_level=3)
                
            final_w, final_h = im.size
            
        return {
            "status": "success",
            "raw_filename": raw_filename,
            "raw_url": f"/static/uploads/{raw_filename}",
            "width": final_w,
            "height": final_h,
            "was_downscaled": was_downscaled,
            "orig_width": orig_w,
            "orig_height": orig_h
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def do_single_cutout(raw_filename: str, force: bool = False, model_id: Optional[str] = None) -> Dict[str, Any]:
    raw_path = UPLOADS_DIR / raw_filename
    if not raw_path.exists():
        raise FileNotFoundError(f"原图不存在: {raw_filename}")
        
    stem = Path(raw_filename).stem
    cutout_filename = f"cutout_{stem.replace('raw_', '')}.png"
    cutout_path = UPLOADS_DIR / cutout_filename
    
    if not force and cutout_path.exists() and not model_id:
        with Image.open(cutout_path) as im:
            return {
                "cutout_filename": cutout_filename,
                "cutout_url": f"/static/uploads/{cutout_filename}",
                "width": im.width,
                "height": im.height,
                "model_used": shoe_engine.active_model_id if shoe_engine else "rembg"
            }
            
    if shoe_engine:
        # P0-3：按需切模型 + 推理为原子操作，整段持锁
        with cutout_lock:
            if model_id and model_id != shoe_engine.active_model_id:
                shoe_engine.switch_model(model_id)
            res = shoe_engine.process_shoe(str(raw_path), str(cutout_path), crop=True, pad=8)
        return {
            "cutout_filename": cutout_filename,
            "cutout_url": f"/static/uploads/{cutout_filename}",
            "width": res["width"],
            "height": res["height"],
            "model_used": res.get("model_id", shoe_engine.active_model_id)
        }
    elif rembg_session:
        pil_raw = Image.open(raw_path).convert("RGB")
        res_img = remove(pil_raw, session=rembg_session)
        bbox = res_img.getbbox()
        if bbox:
            res_img = res_img.crop(bbox)
        res_img.save(cutout_path, format="PNG")
        return {
            "cutout_filename": cutout_filename,
            "cutout_url": f"/static/uploads/{cutout_filename}",
            "width": res_img.width,
            "height": res_img.height
        }
    else:
        raise RuntimeError("未找到可用的抠图引擎！")

@app.get("/api/cutout/models")
def get_cutout_models():
    if not shoe_engine:
        return {"status": "warning", "models": [], "active_model": None}
    return {
        "status": "success",
        "models": shoe_engine.get_available_models(),
        "active_model": shoe_engine.get_active_model()
    }

@app.post("/api/cutout/models/select")
def select_cutout_model(req: SelectModelRequest):
    if not shoe_engine:
        raise HTTPException(status_code=500, detail="鞋靴抠图引擎未初始化")
    try:
        # P0-3：手动切模型也走同一把锁，避免与进行中的推理并发
        with cutout_lock:
            res = shoe_engine.switch_model(req.model_id)
        return {"status": "success", "result": res, "active_model": shoe_engine.get_active_model()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"切换模型失败: {e}")

@app.post("/api/cutout-batch")
def process_batch_cutout(req: BatchCutoutRequest):
    target_names = req.filenames or req.raw_filenames or []
    # P0-3：不在锁外预切模型；逐张由 do_single_cutout 在锁内完成『切模型+推理』原子操作
    results = []
    for rname in target_names:
        try:
            info = do_single_cutout(rname, force=req.force, model_id=req.model_id)
            results.append({"raw_filename": rname, "status": "success", **info})
        except Exception as e:
            results.append({"raw_filename": rname, "status": "error", "error": str(e)})
    return {"status": "success", "results": results}

@app.post("/api/load-sample")
def load_sample_assets():
    sample_candidates = [
        BASE_DIR.parent / "素材",
        STATIC_DIR / "samples",
        BASE_DIR / "samples"
    ]
    sample_dir = None
    for cand in sample_candidates:
        if cand.exists():
            sample_dir = cand
            break
            
    if not sample_dir:
        raise HTTPException(status_code=404, detail="示例素材目录不存在，请将素材放置在项目素材目录中")
        
    sample_files = [p for p in sample_dir.iterdir() if p.suffix.lower() in ['.jpg', '.jpeg', '.png']]
    if not sample_files:
        raise HTTPException(status_code=404, detail="未找到示例素材")
        
    results = []
    default_colors = ["黑色", "酒红", "粉色", "米白", "卡其", "深蓝"]
    
    for idx, p in enumerate(sample_files):
        unique_id = uuid.uuid4().hex[:8]
        raw_filename = f"raw_sample_{unique_id}{p.suffix.lower()}"
        cutout_filename = f"cutout_sample_{unique_id}.png"
        raw_path = UPLOADS_DIR / raw_filename
        cutout_path = UPLOADS_DIR / cutout_filename
        
        pil_raw = Image.open(p).convert("RGB")
        pil_raw.save(raw_path)
        
        # rembg 不可用时降级到鞋靴抠图引擎，仍不可用则明确报错而非 500
        if remove is not None and rembg_session is not None:
            res_img = remove(pil_raw, session=rembg_session)
        elif shoe_engine is not None:
            res_img = remove_logo_background(pil_raw)
        else:
            raise HTTPException(status_code=503, detail="抠图引擎不可用（rembg 与鞋靴引擎均未就绪）")
        bbox = res_img.getbbox()
        if bbox:
            res_img = res_img.crop(bbox)
        res_img.save(cutout_path, format="PNG")
        
        color = default_colors[idx % len(default_colors)]
        
        logos = [
            PlacedLogo(logo_id="logo_square_boat", rel_x=0.35, rel_y=0.06, scale=1.0),
            PlacedLogo(logo_id="logo_nvg_cursive", rel_x=0.28, rel_y=0.44, scale=1.0)
        ]
        
        results.append({
            "id": f"shoe_{idx+1}",
            "color_name": color,
            "raw_filename": raw_filename,
            "raw_url": f"/static/uploads/{raw_filename}",
            "cutout_filename": cutout_filename,
            "cutout_url": f"/static/uploads/{cutout_filename}",
            "is_cutout": True,
            "width": res_img.width,
            "height": res_img.height,
            "offset_x": 0.0,
            "offset_y": 0.0,
            "scale_multiplier": 1.0,
            "logos": [logo.model_dump() for logo in logos]
        })
        
    return {"status": "success", "shoes": results}

def calculate_ai_slots(num_shoes: int) -> List[Dict[str, Any]]:
    if num_shoes <= 0:
        return []

    # 硬编码默认值仅作为尺寸/对齐兜底；槽位坐标的唯一事实源是 data/layout_templates.json
    DEFAULT_SIZES = {
        1: {"max_w": 1400, "max_h": 800, "align": "center"},
        2: {"max_w": 1050, "max_h": 600, "align": "left"},
        3: {"max_w": 1000, "max_h": 530, "align": "left"},
        4: {"max_w": 1000, "max_h": 530, "align": "left"},
    }
    if num_shoes <= 4:
        # 优先取「四宫格标准」模版，其次任意含该色数槽位的模版
        try:
            templates = load_layout_templates()
            preferred = next((t for t in templates if t.get("id") == "tmpl_grid_4"), None) or \
                          next((t for t in templates if str(num_shoes) in (t.get("slots_map") or {})), None)
            slots = (preferred or {}).get("slots_map", {}).get(str(num_shoes))
            if slots:
                merged = []
                for s in slots[:num_shoes]:
                    entry = dict(DEFAULT_SIZES[num_shoes])
                    entry.update({k: s[k] for k in ("cx", "cy", "max_w", "max_h", "align") if k in s})
                    merged.append(entry)
                if len(merged) == num_shoes:
                    return merged
        except Exception as e:
            print(f"[Layout] 读取排版模版失败，回退内置坐标: {e}")
        # JSON 缺失时的兜底（与默认模版一致）
        fallback = {
            1: [{"cx": 2000, "cy": 1480}],
            2: [{"cx": 1340, "cy": 1080}, {"cx": 1340, "cy": 1840}],
            3: [{"cx": 1340, "cy": 1060}, {"cx": 2550, "cy": 1060}, {"cx": 1340, "cy": 1830}],
            4: [{"cx": 1340, "cy": 1060}, {"cx": 2550, "cy": 1060}, {"cx": 1340, "cy": 1830}, {"cx": 2550, "cy": 1830}],
        }[num_shoes]
        return [dict(DEFAULT_SIZES[num_shoes], **s) for s in fallback]

    area_x1 = 860
    area_x2 = 3360
    area_y1 = 760
    area_y2 = 2360
    total_w = area_x2 - area_x1
    total_h = area_y2 - area_y1
    if num_shoes <= 6:
        rows, cols = 2, 3
    elif num_shoes <= 8:
        rows, cols = 2, 4
    elif num_shoes <= 9:
        rows, cols = 3, 3
    elif num_shoes <= 12:
        rows, cols = 3, 4
    else:
        rows, cols = 3, 5

    col_width = total_w / cols
    row_height = total_h / rows
    max_w = int(col_width * 0.90)
    max_h = int(row_height * 0.72)

    slots = []
    for i in range(num_shoes):
        r = i // cols
        c = i % cols
        cx = int(area_x1 + c * col_width + col_width / 2)
        cy = int(area_y1 + r * row_height + row_height / 2 - 20)
        slots.append({
            "cx": cx,
            "cy": cy,
            "max_w": max_w,
            "max_h": max_h,
            "align": "center"
        })
    return slots

def to_unicode_esc(s: str) -> str:
    return "".join(f"\\u{ord(c):04x}" for c in str(s))

def export_photoshop_native_psd(
    out_psd_filepath: Path,
    task: TaskItem,
    tmpl_cfg: Dict[str, Any],
    lines_png_path: Path,
    head_logo_path: Optional[Path],
    head_logo_info: Dict[str, Any],
    shoes_render_info: List[Dict[str, Any]],
    num_shoes: int
) -> bool:
    """Photoshop COM/JSX 原生 PSD 导出（有 PS 环境时的主路径）。
    图层结构自上而下（对齐参考模版 小帆船审核206209.psd）：
      颜色名文字层(最顶,平铺) → 标贴层(平铺) → 鞋体 pixel 层(平铺)
      → 「表格」组(全部 TypeTool 文字层 + 线框层 + 表头主LOGO) → 底格白底(最底)
    文字全部为可编辑 TypeTool 文字层；坐标与 JPG/前端预览共用 compute_table_text_layout。
    """
    psApp = None
    co_inited = False
    try:
        import win32com.client
        import pythoncom
        try:
            pythoncom.CoInitialize()
            co_inited = True
        except Exception:
            pass
        # 连接/启动 Photoshop：去掉 sleep(8) 硬等，改为轮询 COM 直至就绪（最长 60s）
        ps_candidates = sorted(glob.glob(r"C:/Program Files/Adobe/Adobe Photoshop */Photoshop.exe"))
        launched = False
        deadline = time.time() + 60
        while psApp is None and time.time() < deadline:
            try:
                psApp = win32com.client.Dispatch("Photoshop.Application")
            except Exception as ex_disp:
                if not launched and ps_candidates:
                    subprocess.Popen([ps_candidates[-1], "/Automation"])
                    launched = True
                    print(f"[Render-Native] 正在启动 Photoshop: {ps_candidates[-1]}")
                else:
                    print(f"[Render-Native] 等待 Photoshop COM 就绪... ({ex_disp})")
                time.sleep(1.5)
        if not psApp:
            print("[Render-Native] 无法连接到 Photoshop.Application COM 实例")
            return False
        psApp.DisplayDialogs = 3

        psd_target = str(out_psd_filepath).replace("\\", "/")
        lines_file_esc = str(lines_png_path).replace("\\", "/")

        # 与 JPG 渲染共用同一套文字坐标（单轨）
        entries = compute_table_text_layout(tmpl_cfg, task)

        def _ps_font(ent):
            return FONT_NAME_MAP.get(ent["font_name"], ("msyh.ttc", "msyhbd.ttc", "MicrosoftYaHei"))[2]

        # 颜色名文字层参数（per-shoe，置于最顶层）
        fonts_cfg = tmpl_cfg.get("fonts", {})
        cl_font_name = fonts_cfg.get("color_label_font", "Microsoft YaHei")
        cl_font_ps = FONT_NAME_MAP.get(cl_font_name, ("msyh.ttc", "msyhbd.ttc", "MicrosoftYaHei"))[2]
        cl_size_px = int(fonts_cfg.get("color_label_size", 56))
        cl_size_pt = round(cl_size_px * PS_PT_PER_PX, 2)
        cl_color = fonts_cfg.get("color_label_color", "#000000")
        cl_bold = "true" if fonts_cfg.get("color_label_weight") == "bold" else "false"
        cl_ascent, _ = resolve_pil_font(cl_font_name, cl_size_px, cl_bold == "true").getmetrics()

        jsx_parts = [
            "try {",
            "app.displayDialogs = DialogModes.NO;",
            "app.preferences.rulerUnits = Units.PIXELS;",
            "app.preferences.typeUnits = TypeUnits.POINTS;",
            'var doc = app.documents.add(3508, 2480, 300, "MasterPSD", NewDocumentMode.RGB, DocumentFill.WHITE);',
            # 底格：白底背景层改名为「底格」并置于最底
            'try { var bg = doc.layers[doc.layers.length - 1]; bg.isBackgroundLayer = false; bg.name = "\\u5e95\\u683c"; } catch(eb) {}',
            """
            function addText(grp, nameEsc, contentEsc, x, baselineY, sizePt, fontPsName, hexColor, isBold) {
                var layer = grp.artLayers.add();
                layer.kind = LayerKind.TEXT;
                var ti = layer.textItem;
                ti.content = contentEsc;
                ti.size = sizePt;
                ti.position = [x, baselineY];
                if (fontPsName && fontPsName.length > 0) {
                    if (isBold) { try { ti.font = fontPsName + "-Bold"; } catch(fb) { try { ti.font = fontPsName; ti.fauxBold = true; } catch(fb2) {} } }
                    else { try { ti.font = fontPsName; } catch(fe) {} }
                }
                if (hexColor && hexColor.length === 7) {
                    try {
                        var sc = new SolidColor();
                        sc.rgb.red = parseInt(hexColor.substring(1, 3), 16);
                        sc.rgb.green = parseInt(hexColor.substring(3, 5), 16);
                        sc.rgb.blue = parseInt(hexColor.substring(5, 7), 16);
                        ti.color = sc;
                    } catch(ce) {}
                }
                layer.name = nameEsc;
                return layer;
            }
            function importPNGToGroupBottom(grp, filePath, targetX, targetY, layerName) {
                // 导入 PNG 到组内最底（线框/主LOGO 在「表格」组内沉底，文字层在上）
                var fileRef = new File(filePath);
                if (!fileRef.exists) return null;
                var srcDoc = app.open(fileRef);
                var dup = srcDoc.activeLayer.duplicate(grp, ElementPlacement.PLACEATEND);
                srcDoc.close(SaveOptions.DONOTSAVECHANGES);
                dup.name = layerName;
                var curX = dup.bounds[0].value;
                var curY = dup.bounds[1].value;
                dup.translate(targetX - curX, targetY - curY);
                return dup;
            }
            function importPNGToDocTop(filePath, targetX, targetY, layerName) {
                // 导入 PNG 到文档最顶（鞋体/标贴 平铺不分组）
                var fileRef = new File(filePath);
                if (!fileRef.exists) return null;
                var srcDoc = app.open(fileRef);
                var dup = srcDoc.activeLayer.duplicate(doc, ElementPlacement.PLACEATBEGINNING);
                srcDoc.close(SaveOptions.DONOTSAVECHANGES);
                dup.name = layerName;
                var curX = dup.bounds[0].value;
                var curY = dup.bounds[1].value;
                dup.translate(targetX - curX, targetY - curY);
                return dup;
            }
            """,
            # 「表格」组：先建组，先放线框与主LOGO（沉底），再加全部文字层（在组内上部）
            f'var grpTable = doc.layerSets.add(); grpTable.name = "\\u8868\\u683c";',
        ]
        if head_logo_path and head_logo_path.exists():
            hl_esc = str(head_logo_path).replace("\\", "/")
            jsx_parts.append(f'importPNGToGroupBottom(grpTable, "{hl_esc}", {head_logo_info["x"]}, {head_logo_info["y"]}, "\\u8868\\u5934\\u4e3bLOGO");')
        jsx_parts.append(f'importPNGToGroupBottom(grpTable, "{lines_file_esc}", 0, 0, "\\u7ebf\\u6846");')

        for ent in entries:
            layer_name = ent["text"].strip()[:40] or ent["name"]
            jsx_parts.append(
                f'addText(grpTable, "{to_unicode_esc(layer_name)}", "{to_unicode_esc(ent["text"])}", '
                f'{ent["x"]}, {ent["y_baseline"]}, {ent["size_pt"]}, '
                f'"{_ps_font(ent)}", "{ent["color"]}", {"true" if ent["weight"] == "bold" else "false"});'
            )

        # 鞋体 pixel 层（平铺不分组，位于「表格」组之上）
        for s_info in shoes_render_info:
            shoe_png_esc = str(s_info["cutout_path"]).replace("\\", "/")
            jsx_parts.append(f'importPNGToDocTop("{shoe_png_esc}", {s_info["x"]}, {s_info["y"]}, "{to_unicode_esc("鞋体-" + s_info["color"])}");')
        # 标贴层（平铺不分组，位于鞋体之上）
        for s_info in shoes_render_info:
            for l_item in s_info["logos"]:
                l_png_esc = str(l_item["path"]).replace("\\", "/")
                jsx_parts.append(f'importPNGToDocTop("{l_png_esc}", {l_item["x"]}, {l_item["y"]}, "{to_unicode_esc(l_item["name"])}");')
        # 颜色名文字层（最顶层）
        for s_info in shoes_render_info:
            jsx_parts.append(
                f'addText(doc, "{to_unicode_esc(s_info["color"])}", "{to_unicode_esc(s_info["color"])}", '
                f'{s_info["lbl_x"]}, {s_info["lbl_y"] + cl_ascent}, {cl_size_pt}, "{cl_font_ps}", "{cl_color}", {cl_bold});'
            )

        jsx_parts.extend([
            f'var saveFile = new File("{psd_target}");',
            'var opt = new PhotoshopSaveOptions();',
            'opt.layers = true;',
            'opt.maximizeCompatibility = true;',
            # 显式 save + close 后再返回，Python 端随后轮询文件存在性
            'doc.saveAs(saveFile, opt, true, Extension.LOWERCASE);',
            'doc.close(SaveOptions.DONOTSAVECHANGES);',
            '"SUCCESS";',
            '} catch(e) {',
            '"ERROR: " + e.message + " line: " + e.line;',
            '}'
        ])

        full_jsx = "\n".join(jsx_parts)
        res = psApp.DoJavaScript(full_jsx)
        print(f"[Render-Native] ExtendScript Result: {res}")
        # JSX 已显式 save/close；此处轮询文件落盘（超时 120s），不再使用 sleep 硬等
        poll_deadline = time.time() + 120
        while time.time() < poll_deadline:
            if os.path.exists(out_psd_filepath) and os.path.getsize(out_psd_filepath) > 1000:
                return True
            time.sleep(0.5)
        print(f"[Render-Native] 等待 PSD 落盘超时(120s): {out_psd_filepath}")
        return False
    except Exception as e:
        print(f"[Render-Native] Photoshop COM 异常: {e}")
        return False
    finally:
        if psApp:
            try:
                del psApp
            except Exception:
                pass
        if co_inited:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass

def render_task_to_file(task: TaskItem, image_format: str = "png", include_image: bool = True, include_psd: bool = True) -> Dict[str, Any]:
    tmpl_cfg = load_template_config()
    fonts_cfg = tmpl_cfg.get("fonts", {})
    lines_cfg = tmpl_cfg.get("lines", {})
    
    # 1. 纯白 3508 x 2480 画布
    base_img = Image.new("RGBA", (3508, 2480), (255, 255, 255, 255))
    draw = ImageDraw.Draw(base_img)
    
    # 2. 绘制矢量表格线条
    lines_layer = create_table_lines_image(lines_cfg)
    base_img.paste(lines_layer, (0, 0), lines_layer)
    # M1：每次渲染使用独立临时目录，避免固定名 temp_lines.png 被并发渲染互相覆盖
    render_tmpdir = Path(tempfile.mkdtemp(prefix="render_tmp_", dir=str(OUTPUT_DIR)))
    temp_lines_path = render_tmpdir / "temp_lines.png"
    lines_layer.save(temp_lines_path, format="PNG")
    
    # 3. 动态字体解析
    font_title = resolve_pil_font(fonts_cfg.get("title_font", "Microsoft YaHei"), int(fonts_cfg.get("title_size", 76)), fonts_cfg.get("title_weight") == "bold")
    font_cat = resolve_pil_font(fonts_cfg.get("category_font", "Microsoft YaHei"), int(fonts_cfg.get("category_size", 72)), fonts_cfg.get("category_weight") == "bold")
    font_table = resolve_pil_font(fonts_cfg.get("table_font", "Microsoft YaHei"), int(fonts_cfg.get("table_size", 52)), fonts_cfg.get("table_weight") == "bold")
    font_labels = resolve_pil_font(fonts_cfg.get("labels_font", "Microsoft YaHei"), int(fonts_cfg.get("labels_size", 48)), fonts_cfg.get("labels_weight") == "bold")
    
    # 4. 绘制表头与规格文本（坐标与前端预览/PSD 导出共用 compute_table_text_layout，单轨不分叉）
    FONT_PIL_MAP = {"title": font_title, "category": font_cat, "table": font_table, "labels": font_labels}
    table_text_entries = compute_table_text_layout(tmpl_cfg, task)
    for ent in table_text_entries:
        draw.text((ent["x"], ent["y_top"]), ent["text"], fill=ent["color"], font=FONT_PIL_MAP[ent["font_key"]])

    
    # 5. 绘制主表头 LOGO
    l_fname = tmpl_cfg.get("logo_filename", "logos/logo_square_boat.png")
    custom_logo_path = None
    for p_cand in [STATIC_DIR / l_fname, ASSETS_DIR / l_fname, UPLOADS_DIR / Path(l_fname).name, ASSETS_DIR / "logos" / Path(l_fname).name, ASSETS_DIR / "logos" / "library" / Path(l_fname).name]:
        if p_cand.exists():
            custom_logo_path = p_cand
            break
            
    head_logo_info = {"x": 112, "y": 42, "w": 620, "h": 160}
    if custom_logo_path and custom_logo_path.exists():
        try:
            head_logo_img = Image.open(custom_logo_path).convert("RGBA")
            target_lh = 160
            target_lw = max(10, int(head_logo_img.width * (target_lh / head_logo_img.height)))
            if target_lw > 720:
                target_lw = 720
                target_lh = max(10, int(head_logo_img.height * (target_lw / head_logo_img.width)))
            head_logo_resized = head_logo_img.resize((target_lw, target_lh), Image.Resampling.LANCZOS)
            paste_x = 24 + (816 - target_lw) // 2
            paste_y = 28 + (200 - target_lh) // 2
            base_img.paste(head_logo_resized, (paste_x, paste_y), head_logo_resized)
            head_logo_info = {"x": paste_x, "y": paste_y, "w": target_lw, "h": target_lh}
        except Exception as e:
            print(f"[Render] 主LOGO绘制异常: {e}")
    base_sheet_layer = base_img.copy()
    pytoshop_base_layer = pil_to_psd_layer(base_sheet_layer, "送审单模板与底格", 0, 0)

            
    # 6. 计算鞋位网格与标贴缓存
    num_shoes = len(task.shoes)
    slots = calculate_ai_slots(num_shoes)
    font_color_label = resolve_pil_font(fonts_cfg.get("color_label_font", "Microsoft YaHei"), int(fonts_cfg.get("color_label_size", 56)), fonts_cfg.get("color_label_weight") == "bold")
    
    logo_imgs = {}
    for p in (ASSETS_DIR / "logos").rglob("*.png"):
        if p.stem not in logo_imgs:
            try:
                logo_imgs[p.stem] = Image.open(p).convert("RGBA")
            except Exception:
                pass
                
    shoes_render_info = []
    pytoshop_groups = []
    
    for idx, shoe in enumerate(task.shoes[:len(slots)]):
        slot = slots[idx]
        cx, cy, max_w, max_h = slot["cx"], slot["cy"], slot["max_w"], slot["max_h"]
        cutout_filename = shoe.cutout_filename
        if not cutout_filename or not (UPLOADS_DIR / cutout_filename).exists():
            if shoe.raw_filename and (UPLOADS_DIR / shoe.raw_filename).exists():
                c_info = do_single_cutout(shoe.raw_filename)
                cutout_filename = c_info["cutout_filename"]
            else:
                continue
        cutout_path = UPLOADS_DIR / cutout_filename
        if not cutout_path.exists():
            continue
            
        shoe_img = Image.open(cutout_path).convert("RGBA")
        base_scale = min(max_w / shoe_img.width, max_h / shoe_img.height)
        final_scale = base_scale * getattr(shoe, "scale_multiplier", 1.0)
        shoe_w = max(10, int(shoe_img.width * final_scale))
        shoe_h = max(10, int(shoe_img.height * final_scale))
        shoe_x = int(cx - shoe_w // 2 + getattr(shoe, "offset_x", 0.0))
        shoe_y = int(cy - shoe_h // 2 + getattr(shoe, "offset_y", 0.0))
        
        shoe_scaled = shoe_img.resize((shoe_w, shoe_h), Image.Resampling.LANCZOS)
        base_img.paste(shoe_scaled, (shoe_x, shoe_y), shoe_scaled)
        
        # M1：临时文件进本次渲染专属临时目录，用户输入统一清洗
        temp_shoe_path = render_tmpdir / f"temp_shoe_{idx+1}_{sanitize_name(shoe.color_name)}.png"
        shoe_scaled.save(temp_shoe_path, format="PNG")
        
        color_name = shoe.color_name or f"配色{idx+1}"
        label_pos_y = int(shoe_y + shoe_h + (18 if num_shoes > 6 else 30))
        bbox = font_color_label.getbbox(color_name)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        lbl_x = shoe_x + shoe_w // 2 - text_w // 2
        draw.text((lbl_x, label_pos_y), color_name, fill=fonts_cfg.get("color_label_color", "#000000"), font=font_color_label)
        
        s_logos = []
        pytoshop_layers = []
        
        lbl_img = Image.new("RGBA", (text_w + 24, text_h + 24), (0, 0, 0, 0))
        ImageDraw.Draw(lbl_img).text((12, 12), color_name, fill=(0, 0, 0, 255), font=font_color_label)
        plbl = pil_to_psd_layer(lbl_img, f"颜色标注-{color_name}", lbl_x - 12, label_pos_y - 12)
        if plbl: pytoshop_layers.append(plbl)
        
        pshoe = pil_to_psd_layer(shoe_scaled, f"鞋体-{color_name}", shoe_x, shoe_y)
        if pshoe: pytoshop_layers.append(pshoe)
        
        for l_idx, logo in enumerate(shoe.logos):
            l_img = logo_imgs.get(logo.logo_id)
            if not l_img:
                continue
            lw = max(4, int(l_img.width * logo.scale * (final_scale / 0.5)))
            lh = max(4, int(l_img.height * logo.scale * (final_scale / 0.5)))
            scaled_logo = l_img.resize((lw, lh), Image.Resampling.LANCZOS)
            if logo.rotation != 0:
                scaled_logo = scaled_logo.rotate(logo.rotation, expand=True, resample=Image.Resampling.BICUBIC)
            abs_lx = int(shoe_x + logo.rel_x * shoe_w)
            abs_ly = int(shoe_y + logo.rel_y * shoe_h)
            base_img.paste(scaled_logo, (abs_lx, abs_ly), scaled_logo)
            
            temp_l_path = render_tmpdir / f"temp_logo_{idx+1}_{l_idx+1}_{sanitize_name(logo.logo_id)}.png"
            scaled_logo.save(temp_l_path, format="PNG")
            
            s_logos.append({
                "name": f"标贴-{logo.logo_id}_{l_idx+1}",
                "path": temp_l_path,
                "x": abs_lx,
                "y": abs_ly,
                "w": lw,
                "h": lh
            })
            plogo = pil_to_psd_layer(scaled_logo, f"标贴-{logo.logo_id}_{l_idx+1}", abs_lx, abs_ly)
            if plogo: pytoshop_layers.append(plogo)
            
        shoes_render_info.append({
            "idx": idx,
            "color": color_name,
            "cutout_path": temp_shoe_path,
            "x": shoe_x,
            "y": shoe_y,
            "lbl_x": lbl_x,
            "lbl_y": label_pos_y,
            "logos": s_logos
        })
        if HAS_PYTOSHOP and pytoshop_layers:
            grp_name = f"款式 {idx+1} ({color_name})"
            pytoshop_groups.append(nested_layers.Group(name=grp_name, layers=pytoshop_layers))
            
    # Render Canvas Logos (模版公共素材/画布独立标贴)
    for c_idx, clogo in enumerate(getattr(task, "canvas_logos", []) or []):
        try:
            cl_def = next((l for l in load_logos_db() if l["id"] == clogo.logo_id), None)
            cl_file = clogo.file or (cl_def["file"] if cl_def else "logos/logo_square_boat.png")
            cl_path = (STATIC_DIR / cl_file) if not cl_file.startswith("/") else (Path(cl_file.lstrip("/")))
            if not cl_path.exists():
                cl_path = ASSETS_DIR / cl_file.replace("logos/", "")
            if cl_path.exists():
                c_img = Image.open(cl_path).convert("RGBA")
                cw = max(4, int(c_img.width * (clogo.scale or 1.0)))
                ch = max(4, int(c_img.height * (clogo.scale or 1.0)))
                c_scaled = c_img.resize((cw, ch), Image.Resampling.LANCZOS)
                if clogo.rotation:
                    c_scaled = c_scaled.rotate(clogo.rotation, expand=True, resample=Image.Resampling.BICUBIC)
                base_img.paste(c_scaled, (int(clogo.abs_x), int(clogo.abs_y)), c_scaled)
                pclogo = pil_to_psd_layer(c_scaled, f"画布公共素材-{c_idx+1}", int(clogo.abs_x), int(clogo.abs_y))
                if pclogo and HAS_PYTOSHOP: pytoshop_groups.append(nested_layers.Group(name=f"画布素材 {c_idx+1}", layers=[pclogo]))
        except Exception as e:
            print(f"[Render] canvas_logo error: {e}")

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # 输出文件名中的用户输入统一清洗，避免路径注入与 /api/download 白名单拦截
    sku_part = sanitize_name(task.sku.strip() or task.name.strip() or "鞋样审核")
    date_part = sanitize_name(task.material_code.replace(".", ""))
    # 7. 导出 300DPI 送审大图：默认 PNG（无损），可选 JPEG；include_image=False 时只出 PSD
    image_format = "jpg" if str(image_format).lower() in ("jpg", "jpeg") else "png"
    out_filename = f"{sku_part}_{date_part}_{timestamp}.{image_format}"
    out_filepath = OUTPUT_DIR / out_filename
    rgb_img = base_img.convert("RGB")
    if include_image:
        if image_format == "jpg":
            rgb_img.save(out_filepath, "JPEG", quality=95, dpi=(300, 300))
        else:
            base_img.save(out_filepath, "PNG", dpi=(300, 300))

    # 8. 导出 PSD：有 Photoshop 时 COM/JSX 原生可编辑文字路径为主；pytoshop 仅作无 PS 环境的降级
    out_psd_filename = f"{sku_part}_{date_part}_{timestamp}.psd"
    out_psd_filepath = OUTPUT_DIR / out_psd_filename
    has_psd = False
    editable_text = False   # pytoshop 降级路径保持 False；COM 主路径为 True
    dpi_verified = False

    ps_exe_candidates = sorted(glob.glob(r"C:/Program Files/Adobe/Adobe Photoshop */Photoshop.exe")) if include_psd else []
    if ps_exe_candidates:
        try:
            has_psd = export_photoshop_native_psd(
                out_psd_filepath,
                task,
                tmpl_cfg,
                temp_lines_path,
                custom_logo_path,
                head_logo_info,
                shoes_render_info,
                num_shoes
            )
            if has_psd:
                editable_text = True
                print(f"[Render] Photoshop COM 原生 PSD 生成成功（文字图层可编辑）: {out_psd_filepath}")
                dpi_verified = verify_psd_dpi(out_psd_filepath)
        except Exception as ex_com:
            print(f"[Render] Photoshop COM 导出失败，降级 pytoshop: {ex_com}")
            has_psd = False

    # 降级路径：无 Photoshop 或 COM 失败 → pytoshop 直出（文字栅格化，editable_text=False）
    if include_psd and not has_psd and HAS_PYTOSHOP:
        try:
            t_psd0 = time.time()
            all_psd_layers = []
            if pytoshop_base_layer:
                all_psd_layers.append(pytoshop_base_layer)
            if pytoshop_groups:
                all_psd_layers.extend(pytoshop_groups)

            if all_psd_layers:
                psd_doc = nested_layers.nested_layers_to_psd(
                    all_psd_layers,
                    color_mode=enums.ColorMode.rgb,
                    compression=enums.Compression.rle
                )
                _attach_psd_metadata(psd_doc, rgb_img)
                with open(out_psd_filepath, "wb") as f_psd:
                    psd_doc.write(f_psd)
                has_psd = True
                editable_text = False
                print(f"[Render] Pytoshop 降级生成分层 PSD (耗时: {time.time()-t_psd0:.3f}s；文字为栅格化图层，不可编辑): {out_psd_filepath}")
                dpi_verified = verify_psd_dpi(out_psd_filepath)
        except Exception as ex_psd:
            print(f"[Render] Pytoshop 生成 PSD 失败: {ex_psd}")
            has_psd = False

    # M1：渲染临时目录用完即清理（COM 路径的 importPNG 已在上方同步读完）
    try:
        shutil.rmtree(render_tmpdir, ignore_errors=True)
    except Exception:
        pass

    return {
        "status": "success",
        "task_id": task.id,
        "filename": out_filename if include_image else None,
        "filepath": str(out_filepath) if include_image else None,
        "download_url": f"/api/download/{out_filename}" if include_image else None,
        "has_psd": has_psd,
        "psd_filename": out_psd_filename if has_psd else None,
        "psd_filepath": str(out_psd_filepath) if has_psd else None,
        "psd_download_url": f"/api/download/{out_psd_filename}" if has_psd else None,
        "editable_text": editable_text if has_psd else None,
        "dpi_verified": dpi_verified if has_psd else None,
        "width": rgb_img.width,
        "height": rgb_img.height
    }

@app.post("/api/render")
def render_sheet(task: TaskItem, image_format: str = "png", include_image: bool = True, include_psd: bool = True):
    try:
        return render_task_to_file(task, image_format=image_format, include_image=include_image, include_psd=include_psd)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/batch-render-all")
def batch_render_all_tasks(req: BatchRenderRequest):
    results = []
    for task in req.tasks:
        try:
            res = render_task_to_file(task)
            results.append(res)
        except Exception as e:
            results.append({"status": "error", "task_id": task.id, "name": task.name, "error": str(e)})
    return {"status": "success", "results": results}

@app.get("/api/download/{filename}")
def download_output(filename: str):
    # P1-3：文件名白名单（中英文/数字/._-）+ 解析后必须位于输出目录内，杜绝路径穿越
    if not re.fullmatch(r'[\w一-鿿.\-]+', filename):
        raise HTTPException(status_code=400, detail="非法文件名")
    out_root = Path(OUTPUT_DIR).resolve()
    target = (out_root / filename).resolve()
    if not target.is_relative_to(out_root):
        raise HTTPException(status_code=403, detail="禁止访问输出目录之外的文件")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    media_type = "application/octet-stream"
    if target.suffix.lower() in (".jpg", ".jpeg"):
        media_type = "image/jpeg"
    elif target.suffix.lower() == ".png":
        media_type = "image/png"
    return FileResponse(target, filename=filename, media_type=media_type)

@app.get("/api/download-zip")
def download_zip_bundle(files: str):
    """将多个成品文件打成单个 ZIP 下载，避免浏览器『下载多个文件』确认弹窗"""
    import zipfile
    names = [n.strip() for n in files.split(",") if n.strip()]
    if not names:
        raise HTTPException(status_code=400, detail="未指定文件")
    out_root = Path(OUTPUT_DIR).resolve()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in names:
            if not re.fullmatch(r'[\w一-鿿.\-]+', name):
                raise HTTPException(status_code=400, detail="非法文件名")
            target = (out_root / name).resolve()
            if not target.is_relative_to(out_root) or not target.exists() or not target.is_file():
                raise HTTPException(status_code=404, detail=f"文件不存在: {name}")
            zf.write(target, arcname=name)
    buf.seek(0)
    zip_name = Path(names[0]).stem + "_送审图稿.zip"
    from fastapi.responses import StreamingResponse
    from urllib.parse import quote
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(zip_name)}"})


@app.get("/api/settings")
def get_system_settings():
    return {
        "status": "success",
        "output_dir": str(OUTPUT_DIR.resolve()),
        "version": "2.4.2"
    }

@app.post("/api/settings")
def save_system_settings(req: Dict[str, Any]):
    global OUTPUT_DIR
    new_path = req.get("output_dir", "").strip()
    if new_path:
        p = Path(new_path)
        # P1-3：输出目录必须位于用户主目录之下，防止写到系统目录
        try:
            if not p.resolve().is_relative_to(Path.home().resolve()):
                raise HTTPException(status_code=400, detail="输出目录必须位于用户主目录之下")
        except ValueError:
            raise HTTPException(status_code=400, detail="输出目录必须位于用户主目录之下")
        try:
            p.mkdir(parents=True, exist_ok=True)
            OUTPUT_DIR = p
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"目录无效或无权创建: {e}")
    return {"status": "success", "output_dir": str(OUTPUT_DIR.resolve())}

def ask_directory_dialog(initial_dir=None):
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        folder = filedialog.askdirectory(
            parent=root,
            initialdir=initial_dir or str(OUTPUT_DIR),
            title="选择成品大图与 PSD 输出存储目录"
        )
        root.destroy()
        return folder
    except Exception as e:
        print(f"[Settings] ask_directory error: {e}")
        return ""

# tkinter 非线程安全：对话框统一投递到唯一的专属守护线程执行，避免在临时线程池里反复创建 Tk 实例
import queue as _queue
_tk_dialog_lock = threading.Lock()
_tk_dialog_queue = _queue.Queue()

def _tk_dialog_worker():
    """专属 tk 线程：从队列取任务执行并把结果放回，进程生命周期内常驻"""
    while True:
        initial_dir, result_box = _tk_dialog_queue.get()
        try:
            result_box.append(ask_directory_dialog(initial_dir))
        except Exception as e:
            print(f"[Settings] tk dialog worker error: {e}")
            result_box.append("")

def _run_dialog_on_tk_thread(initial_dir, timeout=180):
    """同步等待专属线程弹窗结果；超时返回空串，避免线程悬挂"""
    result_box = []
    _tk_dialog_queue.put((initial_dir, result_box))
    deadline = time.time() + timeout
    while time.time() < deadline:
        if result_box:
            return result_box[0]
        time.sleep(0.3)
    print("[Settings] 目录选择对话框超时(180s)，已放弃等待")
    return ""

@app.get("/api/settings/browse-dir")
def browse_directory(path: Optional[str] = None):
    """目录浏览 API：替代原生弹窗，前端树形选择器使用（仅允许主目录之下）"""
    base = Path(path).resolve() if path else Path.home().resolve()
    home = Path.home().resolve()
    try:
        if not base.is_relative_to(home):
            raise HTTPException(status_code=400, detail="仅允许浏览用户主目录之下的文件夹")
    except ValueError:
        raise HTTPException(status_code=400, detail="仅允许浏览用户主目录之下的文件夹")
    if not base.exists() or not base.is_dir():
        raise HTTPException(status_code=404, detail="目录不存在")
    try:
        dirs = [{"name": p.name, "path": str(p)} for p in sorted(base.iterdir(), key=lambda x: x.name.lower()) if p.is_dir()]
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权限访问该目录")
    parent = str(base.parent) if base != base.parent else None
    return {"status": "success", "current": str(base), "parent": parent, "dirs": dirs}

import asyncio as _asyncio
_choose_folder_async_lock = _asyncio.Lock()  # 串行化弹窗请求（3.10+ 懒绑定事件循环，可模块级创建）

# 启动专属 tk 对话框守护线程
threading.Thread(target=_tk_dialog_worker, daemon=True).start()

@app.post("/api/settings/choose-folder")
async def choose_output_folder_dialog():
    global OUTPUT_DIR
    import asyncio
    loop = asyncio.get_event_loop()
    # 串行化 + 专属 tk 线程：防止并发弹窗与 Tk 线程安全问题
    async with _choose_folder_async_lock:
        folder = await loop.run_in_executor(None, _run_dialog_on_tk_thread, str(OUTPUT_DIR))
    if folder:
        p = Path(folder)
        try:
            if not p.resolve().is_relative_to(Path.home().resolve()):
                return {"status": "error", "detail": "输出目录必须位于用户主目录之下", "output_dir": str(OUTPUT_DIR.resolve())}
            p.mkdir(parents=True, exist_ok=True)
            OUTPUT_DIR = p
            return {"status": "success", "output_dir": str(OUTPUT_DIR.resolve())}
        except Exception as e:
            return {"status": "error", "detail": str(e), "output_dir": str(OUTPUT_DIR.resolve())}
    return {"status": "cancelled", "output_dir": str(OUTPUT_DIR.resolve())}

@app.get("/api/open-folder")
@app.post("/api/open-folder")
def open_output_folder(path: Optional[str] = None):
    try:
        target = Path(path) if path else OUTPUT_DIR
        # P1-3：显式指定路径时必须位于用户主目录之下
        if path:
            try:
                if not target.resolve().is_relative_to(Path.home().resolve()):
                    raise HTTPException(status_code=400, detail="仅允许打开用户主目录之下的文件夹")
            except ValueError:
                raise HTTPException(status_code=400, detail="仅允许打开用户主目录之下的文件夹")
        target.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(target))
        except Exception:
            subprocess.Popen(["explorer.exe", str(target)])
        return {"status": "success", "path": str(target)}
    except Exception as e:
        try:
            subprocess.Popen(["explorer.exe", str(OUTPUT_DIR)])
            return {"status": "success", "path": str(OUTPUT_DIR)}
        except Exception as e2:
            raise HTTPException(status_code=500, detail=str(e2))

def open_browser_later():
    time.sleep(1.8)
    try:
        webbrowser.open_new("http://127.0.0.1:8765")
    except Exception as e:
        print(f"[Warning] Failed to open browser automatically: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print(f" [PSDweb 2.1] 服务已就绪！")
    print(f" 本机访问地址: http://127.0.0.1:8765")
    print(f" 局域网共享地址: http://{LAN_IP}:8765")
    print(f" AI & 开放接口文档: http://{LAN_IP}:8765/docs")
    print("=" * 60)
    threading.Thread(target=open_browser_later, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8765)
