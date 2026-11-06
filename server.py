import os
import sys
import io
import uuid
import json
import socket
import re
import datetime
import threading
import time
import webbrowser
from pathlib import Path
from typing import List, Optional, Dict, Any
from PIL import Image, ImageDraw, ImageFont, ImageOps

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

PRODUCTS_FILE = DATA_DIR / "products.json"
if not PRODUCTS_FILE.exists():
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

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
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(initial_groups, f, ensure_ascii=False, indent=2)

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
    with open(LOGOS_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_LOGOS, f, ensure_ascii=False, indent=2)

def load_logos_db() -> List[Dict[str, Any]]:
    if not LOGOS_FILE.exists():
        return list(DEFAULT_LOGOS)
    try:
        with open(LOGOS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list) or len(data) == 0:
                return list(DEFAULT_LOGOS)
            return data
    except Exception:
        return list(DEFAULT_LOGOS)

def save_logos_db(logos: List[Dict[str, Any]]):
    with open(LOGOS_FILE, "w", encoding="utf-8") as f:
        json.dump(logos, f, ensure_ascii=False, indent=2)

TEMPLATE_CONFIG_FILE = DATA_DIR / "template_config.json"
DEFAULT_TEMPLATE_CONFIG = {
    "title": "臻兴科技开发样品单",
    "category_title": "成人女鞋",
    "reviewer": "审核:",
    "re_reviewer": "复核:",
    "logo_url": "/static/assets/logos/logo_square_boat.png",
    "logo_filename": "logos/logo_square_boat.png",
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
    with open(TEMPLATE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_TEMPLATE_CONFIG, f, ensure_ascii=False, indent=2)

def load_template_config() -> Dict[str, Any]:
    if not TEMPLATE_CONFIG_FILE.exists():
        return json.loads(json.dumps(DEFAULT_TEMPLATE_CONFIG))
    try:
        with open(TEMPLATE_CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            if not isinstance(cfg, dict):
                return json.loads(json.dumps(DEFAULT_TEMPLATE_CONFIG))
            merged = json.loads(json.dumps(DEFAULT_TEMPLATE_CONFIG))
            for k, v in cfg.items():
                if isinstance(v, dict) and k in merged and isinstance(merged[k], dict):
                    merged[k].update(v)
                else:
                    merged[k] = v
            return merged
    except Exception:
        return json.loads(json.dumps(DEFAULT_TEMPLATE_CONFIG))

def save_template_config(cfg: Dict[str, Any]):
    with open(TEMPLATE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

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

try:
    import numpy as np
    import pytoshop
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

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
    filenames: List[str]

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
        "template_config": load_template_config()
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

@app.delete("/api/logos/{logo_id}")
def delete_logo(logo_id: str):
    db = load_logos_db()
    new_db = [item for item in db if item["id"] != logo_id]
    if len(new_db) == len(db):
        raise HTTPException(status_code=404, detail="标贴不存在")
    save_logos_db(new_db)
    return {"status": "success", "deleted_id": logo_id}

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
    try:
        with open(GROUPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_groups_db(groups: List[Dict[str, Any]]):
    with open(GROUPS_FILE, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)

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
    try:
        with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_products_db(items: List[Dict[str, Any]]):
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

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
        raw_ext = Path(file.filename).suffix.lower() or ".jpg"
        unique_id = uuid.uuid4().hex[:8]
        cover_filename = f"prod_cover_{unique_id}{raw_ext}"
        cover_path = UPLOADS_DIR / cover_filename
        contents = await file.read()
        with open(cover_path, "wb") as f:
            f.write(contents)
        return {
            "status": "success",
            "cover_url": f"/static/uploads/{cover_filename}",
            "filename": cover_filename
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- AI Parsing Assistant (自然语言智能提取) ---

@app.post("/api/ai/parse-spec")
def parse_spec_with_ai(req: AiParseRequest):
    text = req.prompt.strip()
    if not text:
        raise HTTPException(status_code=400, detail="内容不能为空")

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
        m_fab = re.search(r'面料\s*[:：]?\s*([^\s,，;；]+)', text)
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
        m_sole = re.search(r'(?:鞋底|大底|底)\s*[:：]?\s*([^\s,，;；]+)', text)
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

def do_single_cutout(raw_filename: str) -> Dict[str, Any]:
    raw_path = UPLOADS_DIR / raw_filename
    if not raw_path.exists():
        raise FileNotFoundError(f"原图不存在: {raw_filename}")
        
    stem = Path(raw_filename).stem
    cutout_filename = f"cutout_{stem.replace('raw_', '')}.png"
    cutout_path = UPLOADS_DIR / cutout_filename
    
    if cutout_path.exists():
        with Image.open(cutout_path) as im:
            return {
                "cutout_filename": cutout_filename,
                "cutout_url": f"/static/uploads/{cutout_filename}",
                "width": im.width,
                "height": im.height
            }
            
    if shoe_engine:
        res = shoe_engine.process_shoe(str(raw_path), str(cutout_path), crop=True, pad=8)
        return {
            "cutout_filename": cutout_filename,
            "cutout_url": f"/static/uploads/{cutout_filename}",
            "width": res["width"],
            "height": res["height"]
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

@app.post("/api/cutout-batch")
def process_batch_cutout(req: BatchCutoutRequest):
    results = []
    for rname in req.filenames:
        try:
            info = do_single_cutout(rname)
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
        
        res_img = remove(pil_raw, session=rembg_session)
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
        
    area_x1 = 950
    area_x2 = 3360
    area_y1 = 760
    area_y2 = 2360
    total_w = area_x2 - area_x1
    total_h = area_y2 - area_y1

    if num_shoes == 1:
        return [{ "cx": 2150, "cy": 1480, "max_w": 1400, "max_h": 800, "align": "center" }]
    elif num_shoes == 2:
        return [
            { "cx": 1550, "cy": 1480, "max_w": 1050, "max_h": 650, "align": "center" },
            { "cx": 2750, "cy": 1480, "max_w": 1050, "max_h": 650, "align": "center" }
        ]
    elif num_shoes == 3:
        return [
            { "cx": 1550, "cy": 1150, "max_w": 1000, "max_h": 560, "align": "center" },
            { "cx": 2750, "cy": 1150, "max_w": 1000, "max_h": 560, "align": "center" },
            { "cx": 2150, "cy": 1850, "max_w": 1000, "max_h": 560, "align": "center" }
        ]
    elif num_shoes == 4:
        return [
            { "cx": 1510, "cy": 1060, "max_w": 1000, "max_h": 530, "align": "left" },
            { "cx": 2720, "cy": 1060, "max_w": 1000, "max_h": 530, "align": "left" },
            { "cx": 1510, "cy": 1830, "max_w": 1000, "max_h": 530, "align": "left" },
            { "cx": 2720, "cy": 1830, "max_w": 1000, "max_h": 530, "align": "left" }
        ]
        
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
    try:
        import win32com.client
        psApp = win32com.client.Dispatch("Photoshop.Application")
        psApp.DisplayDialogs = 3
        
        psd_target = str(out_psd_filepath).replace("\\", "/")
        lines_file_esc = str(lines_png_path).replace("\\", "/")
        
        title_str = tmpl_cfg.get("title", "臻兴科技开发样品单").strip() or "臻兴科技开发样品单"
        category_title = tmpl_cfg.get("category_title", "成人女鞋").strip() or "成人女鞋"
        rev_l = tmpl_cfg.get("reviewer", "审核:")
        rev_r = tmpl_cfg.get("re_reviewer", "复核:")
        reviewer_str = f"{rev_l}               {rev_r}"
        fabrics_str = f"面料: {task.fabrics}"
        soles_str = f"鞋底: {task.soles}"
        
        lbl_sku = tmpl_cfg.get("labels", {}).get("sku", "货号:")
        lbl_season = tmpl_cfg.get("labels", {}).get("season", "季节:")
        lbl_craft = tmpl_cfg.get("labels", {}).get("craft", "工艺:")
        lbl_cat = tmpl_cfg.get("labels", {}).get("category", "类别:")
        lbl_last = tmpl_cfg.get("labels", {}).get("last", "楦型:")
        lbl_mat = tmpl_cfg.get("labels", {}).get("material_code", "素材编号:")
        
        title_esc = to_unicode_esc(title_str)
        category_esc = to_unicode_esc(category_title)
        reviewer_esc = to_unicode_esc(reviewer_str)
        fabrics_esc = to_unicode_esc(fabrics_str)
        soles_esc = to_unicode_esc(soles_str)
        
        sku_esc = to_unicode_esc(task.sku)
        season_esc = to_unicode_esc(task.season)
        craft_esc = to_unicode_esc(task.craft)
        cat_val_esc = to_unicode_esc(task.category)
        size_val_esc = to_unicode_esc(f"尺码 {task.size}")
        mat_esc = to_unicode_esc(task.material_code)
        
        left_labels_esc = to_unicode_esc(f"{lbl_sku}\n\n{lbl_season}\n\n{lbl_craft}\n\n{lbl_cat}\n\n{lbl_last}\n\n设计:\n\n版师:\n\n打单:\n\n印花:\n\n{lbl_mat}")
        
        fonts_cfg = tmpl_cfg.get("fonts", {})
        title_font_name = fonts_cfg.get("title_font", "Microsoft YaHei")
        title_font_ps = FONT_NAME_MAP.get(title_font_name, ("msyh.ttc", "msyhbd.ttc", "MicrosoftYaHei"))[2]
        title_color = fonts_cfg.get("title_color", "#000000")
        
        category_font_name = fonts_cfg.get("category_font", "Microsoft YaHei")
        category_font_ps = FONT_NAME_MAP.get(category_font_name, ("msyh.ttc", "msyhbd.ttc", "MicrosoftYaHei"))[2]
        category_color = fonts_cfg.get("category_color", "#000000")
        
        table_font_name = fonts_cfg.get("table_font", "Microsoft YaHei")
        table_font_ps = FONT_NAME_MAP.get(table_font_name, ("msyh.ttc", "msyhbd.ttc", "MicrosoftYaHei"))[2]
        table_color = fonts_cfg.get("table_color", "#000000")

        labels_font_name = fonts_cfg.get("labels_font", "Microsoft YaHei")
        labels_font_ps = FONT_NAME_MAP.get(labels_font_name, ("msyh.ttc", "msyhbd.ttc", "MicrosoftYaHei"))[2]
        labels_color = fonts_cfg.get("labels_color", "#000000")

        color_label_font_name = fonts_cfg.get("color_label_font", "Microsoft YaHei")
        color_label_font_ps = FONT_NAME_MAP.get(color_label_font_name, ("msyh.ttc", "msyhbd.ttc", "MicrosoftYaHei"))[2]
        color_label_color = fonts_cfg.get("color_label_color", "#000000")
        
        grp1_name = to_unicode_esc("【底表文字与规格信息】")
        grp_lines_name = to_unicode_esc("【底表线框与底板】")
        
        jsx_parts = [
            "try {",
            "app.displayDialogs = DialogModes.NO;",
            "app.preferences.rulerUnits = Units.PIXELS;",
            "app.preferences.typeUnits = TypeUnits.POINTS;",
            'var doc = app.documents.add(3508, 2480, 300, "MasterPSD", NewDocumentMode.RGB, DocumentFill.WHITE);',
            f'var grpText = doc.layerSets.add(); grpText.name = "{grp1_name}";',
            """
            function addText(grp, nameEsc, contentEsc, x, y, size, fontPsName, hexColor) {
                var layer = grp.artLayers.add();
                layer.kind = LayerKind.TEXT;
                layer.name = nameEsc;
                var ti = layer.textItem;
                ti.contents = contentEsc;
                ti.size = size;
                ti.position = [x, y];
                if (fontPsName && fontPsName.length > 0) {
                    try { ti.font = fontPsName; } catch(fe) {}
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
                return layer;
            }
            function importPNG(grp, filePath, targetX, targetY, layerName) {
                var fileRef = new File(filePath);
                if (!fileRef.exists) return null;
                var srcDoc = app.open(fileRef);
                var dup = srcDoc.activeLayer.duplicate(doc);
                srcDoc.close(SaveOptions.DONOTSAVECHANGES);
                dup.name = layerName;
                dup.move(grp, ElementPlacement.PLACEATEND);
                var curX = dup.bounds[0].value;
                var curY = dup.bounds[1].value;
                dup.translate(targetX - curX, targetY - curY);
                return dup;
            }
            """,
            f'addText(grpText, "{to_unicode_esc("表头标题")}", "{title_esc}", 960, 180, 26, "{title_font_ps}", "{title_color}");',
            f'addText(grpText, "{to_unicode_esc("品类名称")}", "{category_esc}", 880, 330, 24, "{category_font_ps}", "{category_color}");',
            f'addText(grpText, "{to_unicode_esc("审核复核")}", "{reviewer_esc}", 2680, 180, 18, "{table_font_ps}", "{table_color}");',
            f'addText(grpText, "{to_unicode_esc("面料材质")}", "{fabrics_esc}", 2480, 420, 18, "{table_font_ps}", "{table_color}");',
            f'addText(grpText, "{to_unicode_esc("鞋底材质")}", "{soles_esc}", 2480, 540, 18, "{table_font_ps}", "{table_color}");',
            f'addText(grpText, "{to_unicode_esc("左侧字段标签")}", "{left_labels_esc}", 80, 330, 16, "{labels_font_ps}", "{labels_color}");',
            f'addText(grpText, "{to_unicode_esc("货号数值")}", "{sku_esc}", 472, 330, 18, "{table_font_ps}", "{table_color}");',
            f'addText(grpText, "{to_unicode_esc("季节数值")}", "{season_esc}", 472, 445, 18, "{table_font_ps}", "{table_color}");',
            f'addText(grpText, "{to_unicode_esc("工艺数值")}", "{craft_esc}", 472, 560, 18, "{table_font_ps}", "{table_color}");',
            f'addText(grpText, "{to_unicode_esc("类别数值")}", "{cat_val_esc}", 472, 675, 18, "{table_font_ps}", "{table_color}");',
            f'addText(grpText, "{to_unicode_esc("楦型尺码")}", "{size_val_esc}", 472, 790, 18, "{table_font_ps}", "{table_color}");',
            f'addText(grpText, "{to_unicode_esc("素材编号")}", "{mat_esc}", 395, 1370, 16, "{table_font_ps}", "{table_color}");',
            f'var grpLines = doc.layerSets.add(); grpLines.name = "{grp_lines_name}";',
            f'importPNG(grpLines, "{lines_file_esc}", 0, 0, "{to_unicode_esc("表格线框线条")}");'
        ]
        
        if head_logo_path and head_logo_path.exists():
            hl_esc = str(head_logo_path).replace("\\", "/")
            jsx_parts.append(f'importPNG(grpLines, "{hl_esc}", {head_logo_info["x"]}, {head_logo_info["y"]}, "{to_unicode_esc("表头主LOGO")}");')
            
        for s_info in shoes_render_info:
            s_grp_name = to_unicode_esc(f"【款式{s_info['idx']+1}-{s_info['color']}】")
            jsx_parts.append(f"var sGrp = doc.layerSets.add(); sGrp.name = '{s_grp_name}';")
            c_label_esc = to_unicode_esc(s_info['color'])
            jsx_parts.append(f'addText(sGrp, "{to_unicode_esc("颜色标注-" + s_info["color"])}", "{c_label_esc}", {s_info["lbl_x"]}, {s_info["lbl_y"]}, 20);')
            
            shoe_png_esc = str(s_info["cutout_path"]).replace("\\", "/")
            jsx_parts.append(f'importPNG(sGrp, "{shoe_png_esc}", {s_info["x"]}, {s_info["y"]}, "{to_unicode_esc("鞋体-" + s_info["color"])}");')
            
            for l_item in s_info["logos"]:
                l_png_esc = str(l_item["path"]).replace("\\", "/")
                jsx_parts.append(f'importPNG(sGrp, "{l_png_esc}", {l_item["x"]}, {l_item["y"]}, "{to_unicode_esc(l_item["name"])}");')
                
        jsx_parts.extend([
            f'var saveFile = new File("{psd_target}");',
            'var opt = new PhotoshopSaveOptions();',
            'opt.layers = true;',
            'opt.maximizeCompatibility = true;',
            'doc.saveAs(saveFile, opt, false, Extension.LOWERCASE);',
            'doc.close(SaveOptions.DONOTSAVECHANGES);',
            '"SUCCESS";',
            '} catch(e) {',
            '"ERROR: " + e.message + " line: " + e.line;',
            '}'
        ])
        
        full_jsx = "\n".join(jsx_parts)
        res = psApp.DoJavaScript(full_jsx)
        print(f"[Render-Native] ExtendScript Result: {res}")
        return os.path.exists(out_psd_filepath) and os.path.getsize(out_psd_filepath) > 1000
    except Exception as e:
        print(f"[Render-Native] Photoshop COM 异常: {e}")
        return False

def render_task_to_file(task: TaskItem) -> Dict[str, Any]:
    tmpl_cfg = load_template_config()
    fonts_cfg = tmpl_cfg.get("fonts", {})
    lines_cfg = tmpl_cfg.get("lines", {})
    
    # 1. 纯白 3508 x 2480 画布
    base_img = Image.new("RGBA", (3508, 2480), (255, 255, 255, 255))
    draw = ImageDraw.Draw(base_img)
    
    # 2. 绘制矢量表格线条
    lines_layer = create_table_lines_image(lines_cfg)
    base_img.paste(lines_layer, (0, 0), lines_layer)
    temp_lines_path = OUTPUT_DIR / "temp_lines.png"
    lines_layer.save(temp_lines_path, format="PNG")
    
    # 3. 动态字体解析
    font_title = resolve_pil_font(fonts_cfg.get("title_font", "Microsoft YaHei"), int(fonts_cfg.get("title_size", 76)), fonts_cfg.get("title_weight") == "bold")
    font_cat = resolve_pil_font(fonts_cfg.get("category_font", "Microsoft YaHei"), int(fonts_cfg.get("category_size", 72)), fonts_cfg.get("category_weight") == "bold")
    font_table = resolve_pil_font(fonts_cfg.get("table_font", "Microsoft YaHei"), int(fonts_cfg.get("table_size", 52)), fonts_cfg.get("table_weight") == "bold")
    font_labels = resolve_pil_font(fonts_cfg.get("labels_font", "Microsoft YaHei"), int(fonts_cfg.get("labels_size", 48)), fonts_cfg.get("labels_weight") == "bold")
    
    # 4. 绘制表头与规格文本
    title_str = tmpl_cfg.get("title", "臻兴科技开发样品单").strip() or "臻兴科技开发样品单"
    draw.text((960, 140), title_str, fill=fonts_cfg.get("title_color", "#000000"), font=font_title)
    
    cat_str = tmpl_cfg.get("category_title", "成人女鞋").strip() or "成人女鞋"
    draw.text((880, 310), cat_str, fill=fonts_cfg.get("category_color", "#000000"), font=font_cat)
    
    # 审核复核
    rev_l = tmpl_cfg.get("reviewer", "审核:")
    rev_r = tmpl_cfg.get("re_reviewer", "复核:")
    draw.text((2680, 155), rev_l, fill=fonts_cfg.get("labels_color", "#000000"), font=font_labels)
    draw.text((3070, 155), rev_r, fill=fonts_cfg.get("labels_color", "#000000"), font=font_labels)
    
    # 左侧标签列与数值列
    lbls = tmpl_cfg.get("labels", {})
    divider_x = int(lines_cfg.get("divider_x", 840))
    label_w = int(lines_cfg.get("left_table_label_w", 285))
    
    left_fields = [
        (lbls.get("sku", "货号:"), task.sku, 315),
        (lbls.get("season", "季节:"), task.season, 432),
        (lbls.get("craft", "工艺:"), task.craft, 550),
        (lbls.get("category", "类别:"), task.category, 666),
        (lbls.get("last", "楦型:"), f"{lbls.get('size', '尺码')} {task.size}", 782),
        (lbls.get("designer", "设计:"), "", 897),
        (lbls.get("patternmaker", "版师:"), "", 1012),
        (lbls.get("order", "打单:"), "", 1127),
        (lbls.get("print", "印花:"), "", 1242),
        (lbls.get("material_code", "素材编号:"), task.material_code, 1361)
    ]
    for lbl_txt, val_txt, y_pos in left_fields:
        draw.text((60, y_pos), lbl_txt, fill=fonts_cfg.get("labels_color", "#000000"), font=font_labels)
        if val_txt:
            draw.text((350, y_pos), val_txt, fill=fonts_cfg.get("table_color", "#000000"), font=font_table)
            
    # 面料与鞋底
    draw.text((2480, 405), f"面料: {task.fabrics}", fill=fonts_cfg.get("table_color", "#000000"), font=font_table)
    draw.text((2480, 530), f"鞋底: {task.soles}", fill=fonts_cfg.get("table_color", "#000000"), font=font_table)
    
    # 5. 绘制主表头 LOGO
    l_fname = tmpl_cfg.get("logo_filename", "logos/logo_square_boat.png")
    custom_logo_path = None
    for p_cand in [STATIC_DIR / l_fname, ASSETS_DIR / l_fname, UPLOADS_DIR / Path(l_fname).name, ASSETS_DIR / "logos" / Path(l_fname).name, ASSETS_DIR / "logos" / "library" / Path(l_fname).name]:
        if p_cand.exists():
            custom_logo_path = p_cand
            break
            
    head_logo_info = {"x": 190, "y": 100, "w": 120, "h": 120}
    if custom_logo_path and custom_logo_path.exists():
        try:
            head_logo_img = Image.open(custom_logo_path).convert("RGBA")
            target_lh = 120
            target_lw = max(10, int(head_logo_img.width * (target_lh / head_logo_img.height)))
            if target_lw > 650:
                target_lw = 650
                target_lh = max(10, int(head_logo_img.height * (target_lw / head_logo_img.width)))
            head_logo_resized = head_logo_img.resize((target_lw, target_lh), Image.Resampling.LANCZOS)
            paste_y = 157 - target_lh // 2
            base_img.paste(head_logo_resized, (190, paste_y), head_logo_resized)
            head_logo_info = {"x": 190, "y": paste_y, "w": target_lw, "h": target_lh}
        except Exception as e:
            print(f"[Render] 主LOGO绘制异常: {e}")
            
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
        
        temp_shoe_path = OUTPUT_DIR / f"temp_shoe_{idx+1}_{shoe.color_name}.png"
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
            
            temp_l_path = OUTPUT_DIR / f"temp_logo_{idx+1}_{l_idx+1}.png"
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
            
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    sku_part = task.sku.strip() or task.name.strip() or "鞋样审核"
    date_part = task.material_code.replace(".", "")
    out_filename = f"{sku_part}_{date_part}_{timestamp}.jpg"
    out_filepath = OUTPUT_DIR / out_filename
    
    # 7. 导出 300DPI JPEG 印刷送审大图
    rgb_img = base_img.convert("RGB")
    rgb_img.save(out_filepath, "JPEG", quality=95, dpi=(300, 300))
    
    # 8. 导出 Photoshop 100% 原生可编辑文字图层 PSD (或 Pytoshop 独立图层降级)
    out_psd_filename = f"{sku_part}_{date_part}_{timestamp}.psd"
    out_psd_filepath = OUTPUT_DIR / out_psd_filename
    has_psd = False
    
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
    
    if not has_psd and HAS_PYTOSHOP:
        try:
            base_bg = Image.new("RGBA", (3508, 2480), (255, 255, 255, 255))
            p_bg = pil_to_psd_layer(base_bg, "底色背景", 0, 0)
            p_lines = pil_to_psd_layer(lines_layer, "表格线框线条", 0, 0)
            all_layers = [p_bg, p_lines] + pytoshop_groups
            psd_doc = nested_layers.nested_layers_to_psd(
                all_layers,
                color_mode=enums.ColorMode.rgb,
                size=(3508, 2480),
                compression=enums.Compression.raw
            )
            with open(out_psd_filepath, "wb") as f_psd:
                psd_doc.write(f_psd)
            has_psd = True
            print(f"[Render] pytoshop 独立图层分层 PSD 导出成功: {out_psd_filename}")
        except Exception as e_psd:
            print(f"[Render] pytoshop 降级导出失败: {e_psd}")
            
    return {
        "status": "success",
        "task_id": task.id,
        "filename": out_filename,
        "filepath": str(out_filepath),
        "download_url": f"/api/download/{out_filename}",
        "has_psd": has_psd,
        "psd_filename": out_psd_filename if has_psd else None,
        "psd_filepath": str(out_psd_filepath) if has_psd else None,
        "psd_download_url": f"/api/download/{out_psd_filename}" if has_psd else None,
        "width": rgb_img.width,
        "height": rgb_img.height
    }

@app.post("/api/render")
def render_sheet(task: TaskItem):
    try:
        return render_task_to_file(task)
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
    target = OUTPUT_DIR / filename
    if not target.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(target, filename=filename, media_type="image/jpeg")

@app.get("/api/open-folder")
def open_output_folder():
    try:
        os.startfile(OUTPUT_DIR)
        return {"status": "success", "path": str(OUTPUT_DIR)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
