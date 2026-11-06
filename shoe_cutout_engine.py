# -*- coding: utf-8 -*-
"""
shoe_cutout_engine.py — 小帆船专用工业级离线鞋样抠图引擎
支持多模型热切换与中文场景标注 (ISNet 工业鞋模微调版 / BiRefNet 反绒毛面专精 / ISNet 通用大图版 / U2Net 极速平衡版)
结合白底救援 (rescue_white) + 白布补实 (solidify) + 边缘引导滤波 + RGB反解去白边 (decontaminate)
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
import cv2
import onnxruntime as ort
from PIL import Image

_HERE = Path(__file__).resolve().parent
MODELS_DIR = _HERE / "models"
SETTINGS_FILE = _HERE / "data" / "cutout_settings.json"

MODEL_SPECS = [
    {
        "id": "isnet_fine_tuned.onnx",
        "name": "ISNet 1024 工业鞋模微调版 (默认推荐)",
        "badge": "鞋靴送审专精",
        "scenario": "推荐场景：鞋样高精送审、鞋舌织唛、大底齿纹、车线细节。白底防穿透与边缘平滑优化。",
        "resolution": "1024×1024",
        "speed": "均衡 (约 0.6s)",
        "memory": "轻量 (~176MB)",
        "is_default": True
    },
    {
        "id": "birefnet_lite.onnx",
        "name": "BiRefNet Lite 双向高保真版",
        "badge": "反绒毛面专精",
        "scenario": "推荐场景：反绒皮/翻毛皮、网眼织物、半透明鞋材及高反差深色鞋款。边缘发丝级过渡自然。",
        "resolution": "1024×1024",
        "speed": "高精 (约 0.9s)",
        "memory": "标准 (~224MB)",
        "is_default": False
    },
    {
        "id": "isnet-general-use.onnx",
        "name": "ISNet 通用大图版",
        "badge": "多品类通用",
        "scenario": "推荐场景：大尺寸鞋靴、靴子、包袋、皮具及多配件组合样板。轮廓饱满、抗噪点能力强。",
        "resolution": "1024×1024",
        "speed": "均衡 (约 0.7s)",
        "memory": "轻量 (~178MB)",
        "is_default": False
    },
    {
        "id": "u2net.onnx",
        "name": "U2Net 极速平衡版",
        "badge": "极速低耗",
        "scenario": "推荐场景：低配电脑、无独立显卡机型，或大批量几十款快速粗筛预览。显存与CPU占用极低。",
        "resolution": "320×320",
        "speed": "极速 (约 0.2s)",
        "memory": "微型 (~175MB)",
        "is_default": False
    }
]

class ShoeCutoutEngine:
    def __init__(self, threads: int = 4):
        self.threads = threads
        self.session = None
        self.input_name = None
        self.input_h = 1024
        self.input_w = 1024
        self.model_path = None
        self.active_model_id = None
        
        # Determine initial model from settings or default
        init_model_id = self._load_saved_model_id() or "isnet_fine_tuned.onnx"
        self.switch_model(init_model_id)

    def _load_saved_model_id(self) -> Optional[str]:
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("active_model_id")
            except Exception:
                pass
        return None

    def _save_model_id(self, model_id: str):
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump({"active_model_id": model_id}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ShoeCutoutEngine] 保存模型设置失败: {e}")

    def switch_model(self, model_id: str) -> Dict[str, Any]:
        """动态热切换抠图模型，无需重启服务"""
        target_path = MODELS_DIR / model_id
        if not target_path.exists():
            # Fallback search
            for m in MODEL_SPECS:
                cand = MODELS_DIR / m["id"]
                if cand.exists():
                    target_path = cand
                    model_id = m["id"]
                    break

        if not target_path.exists():
            raise FileNotFoundError(f"未找到可用的 ONNX 抠图模型: {model_id}，搜索目录：{MODELS_DIR}")

        print(f"[ShoeCutoutEngine] 正在载入 AI 抠图模型: {target_path.name}...")
        so = ort.SessionOptions()
        so.intra_op_num_threads = self.threads
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        so.enable_cpu_mem_arena = False
        so.enable_mem_pattern = False

        new_session = ort.InferenceSession(str(target_path), so, providers=["CPUExecutionProvider"])
        inp = new_session.get_inputs()[0]
        
        self.session = new_session
        self.input_name = inp.name
        self.input_h = inp.shape[2] if (len(inp.shape) > 2 and isinstance(inp.shape[2], int)) else 1024
        self.input_w = inp.shape[3] if (len(inp.shape) > 3 and isinstance(inp.shape[3], int)) else 1024
        self.model_path = target_path
        self.active_model_id = model_id
        self._save_model_id(model_id)

        spec = next((m for m in MODEL_SPECS if m["id"] == model_id), None)
        badge = spec["badge"] if spec else "通用"
        name = spec["name"] if spec else target_path.name
        print(f"[ShoeCutoutEngine] 模型加载成功: 【{badge}】{name} (输入: {self.input_w}x{self.input_h})")

        return {
            "status": "success",
            "active_model_id": model_id,
            "name": name,
            "badge": badge,
            "resolution": f"{self.input_w}x{self.input_h}"
        }

    def get_available_models(self) -> List[Dict[str, Any]]:
        """返回所有存在的模型及其场景说明与当前激活状态"""
        results = []
        for spec in MODEL_SPECS:
            item = dict(spec)
            p = MODELS_DIR / spec["id"]
            item["exists"] = p.exists()
            item["file_size_mb"] = round(p.stat().st_size / (1024 * 1024), 1) if p.exists() else 0
            item["is_active"] = (spec["id"] == self.active_model_id)
            results.append(item)
        return results

    def get_active_model(self) -> Dict[str, Any]:
        spec = next((m for m in MODEL_SPECS if m["id"] == self.active_model_id), None)
        if spec:
            res = dict(spec)
            res["is_active"] = True
            return res
        return {
            "id": self.active_model_id or "isnet_fine_tuned.onnx",
            "name": self.model_path.name if self.model_path else "默认模型",
            "badge": "鞋靴送审专精",
            "scenario": "推荐场景：鞋样高精送审、鞋舌织唛、大底齿纹、车线细节。",
            "is_active": True
        }

    @staticmethod
    def load_rgb(path: str) -> np.ndarray:
        with open(path, "rb") as f:
            buf = np.frombuffer(f.read(), np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise RuntimeError(f"无法解码图像: {path}")
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    def infer(self, rgb: np.ndarray) -> np.ndarray:
        h, w = rgb.shape[:2]
        x = cv2.resize(rgb, (self.input_w, self.input_h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        
        m_id = (self.active_model_id or "").lower()
        if "birefnet" in m_id or "u2net" in m_id:
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            x = (x - mean) / std
        else:
            # ISNet 标准归一化
            x = (x - 0.5)

        x = np.transpose(x, (2, 0, 1))[None]
        out = self.session.run(None, {self.input_name: x})[0]
        a = out[0, 0] if out.ndim == 4 else out
        if a.min() < 0 or a.max() > 1:
            a = 1.0 / (1.0 + np.exp(-a))
        return cv2.resize(a.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)

    @staticmethod
    def guided(I: np.ndarray, p: np.ndarray, r: int = 4, eps: float = 1e-4) -> np.ndarray:
        k = (2 * r + 1, 2 * r + 1)
        mI = cv2.boxFilter(I, -1, k)
        mp = cv2.boxFilter(p, -1, k)
        mIp = cv2.boxFilter(I * p, -1, k)
        mII = cv2.boxFilter(I * I, -1, k)
        a = (mIp - mI * mp) / (mII - mI * mI + eps)
        b = mp - a * mI
        return cv2.boxFilter(a, -1, k) * I + cv2.boxFilter(b, -1, k)

    @staticmethod
    def rescue_white(rgb: np.ndarray, a: np.ndarray, thr: float = 6.0, reach: int = 60, min_area: int = 600):
        """白底救援：防止白色鞋面、鞋舌、白色EVA大底被当成背景吃穿"""
        dev = (255 - np.min(rgb.astype(np.int16), axis=2)).astype(np.float32)
        cand = (dev > thr).astype(np.uint8)
        cand = cv2.morphologyEx(cand, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        hard = (a > 0.5).astype(np.uint8)
        near = cv2.dilate(hard, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (reach, reach)))
        cand &= near
        n, lab, st, _ = cv2.connectedComponentsWithStats(cand, 8)
        keep = np.zeros_like(hard)
        for i in range(1, n):
            comp = (lab == i).astype(np.uint8)
            if st[i, cv2.CC_STAT_AREA] < min_area:
                continue
            if (comp & cv2.dilate(hard, np.ones((5, 5), np.uint8))).sum() > 200:
                keep |= comp
        m = hard | keep
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
        soft = np.clip(ShoeCutoutEngine.guided(g, m.astype(np.float32), 3, 1e-4), 0, 1)
        return np.maximum(a, np.where(keep > 0, np.maximum(soft, 0.6), 0.0))

    @staticmethod
    def solidify_shoes(rgb: np.ndarray, a: np.ndarray, dev_thr: float = 10.0, std_thr: float = 1.5):
        """鞋体补实：纯白背景方差=0.0，白色橡胶底/车线方差>1.5，精确补回被吃掉的大底与内衬"""
        hard = (a > 0.5).astype(np.uint8)
        dev = 255.0 - rgb.min(axis=2).astype(np.float32)
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
        mu = cv2.blur(g, (9, 9))
        mu2 = cv2.blur(g * g, (9, 9))
        std = np.sqrt(np.maximum(mu2 - mu * mu, 0))
        nb = ((dev > dev_thr) | (std > std_thr)).astype(np.uint8)
        nb = cv2.morphologyEx(nb, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        nb = cv2.morphologyEx(nb, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))

        n, lab, st, _ = cv2.connectedComponentsWithStats(nb, 8)
        touch = cv2.dilate(hard, np.ones((9, 9), np.uint8))
        keep = np.zeros_like(nb)
        for i in range(1, n):
            comp = (lab == i).astype(np.uint8)
            if (comp & touch).sum() > 200:
                keep |= comp
        merged = hard | keep
        merged = cv2.morphologyEx(merged, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))

        # 洞填充
        inv = (1 - merged).astype(np.uint8)
        ni, labi, sti, _ = cv2.connectedComponentsWithStats(inv, 8)
        h, w = merged.shape
        for i in range(1, ni):
            x, y, ww, hh, ar = sti[i]
            if x > 1 and y > 1 and x + ww < w - 1 and y + hh < h - 1 and ar <= 20000:
                merged[labi == i] = 1

        soft_new = np.clip(ShoeCutoutEngine.guided(g / 255.0, merged.astype(np.float32), 4, 1e-4), 0, 1)
        return np.maximum(a, np.where((merged > 0) & (a < 0.5), np.maximum(soft_new, 0.55), 0.0))

    @staticmethod
    def refine(rgb: np.ndarray, a: np.ndarray, crisp: float = 1.35) -> np.ndarray:
        """引导滤波边缘细化与轻度硬化，保证 1px 亚像素平滑"""
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
        a = np.clip(ShoeCutoutEngine.guided(g, a, 6, 8e-5), 0, 1)
        a = np.clip((a - 0.5) * crisp + 0.5, 0, 1)
        return a

    @staticmethod
    def decontaminate(rgb: np.ndarray, a: np.ndarray) -> np.ndarray:
        """RGB反解去白边：对半透明过渡边缘反解去除原图背景混杂的白光"""
        rgb_f = rgb.astype(np.float32)
        bg = np.array([255.0, 255.0, 255.0], dtype=np.float32)
        a_3d = a[:, :, None]
        fg = (rgb_f - (1.0 - a_3d) * bg) / np.maximum(a_3d, 0.12)
        fg = np.clip(fg, 0, 255)
        blend = np.where(a_3d >= 0.98, rgb_f, np.where(a_3d <= 0.05, rgb_f, fg))
        return blend.astype(np.uint8)

    def process_shoe(self, in_path: str, out_path: str, crop: bool = True, pad: int = 8, max_dim: int = 2048) -> dict:
        t0 = time.time()
        rgb = self.load_rgb(in_path)
        orig_h, orig_w = rgb.shape[:2]
        was_downscaled = False
        
        # 工业等比采样限制
        if max(orig_h, orig_w) > max_dim:
            scale = max_dim / max(orig_h, orig_w)
            rgb = cv2.resize(rgb, (int(orig_w * scale), int(orig_h * scale)), interpolation=cv2.INTER_AREA)
            was_downscaled = True
        
        # 1. 深度推理
        a = self.infer(rgb)
        
        # 2. 白底救援 (白色部件回捞)
        a = self.rescue_white(rgb, a)
        
        # 3. 鞋体补实 (基于局部纹理方差)
        a = self.solidify_shoes(rgb, a)
        
        # 4. 引导滤波细化
        a = self.refine(rgb, a, crisp=1.35)
        
        # 5. 反解去白边
        rgb = self.decontaminate(rgb, a)
        
        # 6. 主体提取与孤岛杂点清理
        hard = (a > 0.5).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(hard, 8)
        if n > 2:
            areas = st[1:, cv2.CC_STAT_AREA]
            main_idx = 1 + int(np.argmax(areas))
            for i in range(1, n):
                if i != main_idx and st[i, cv2.CC_STAT_AREA] < 1500:
                    hard[lab == i] = 0

        soft = np.where(hard > 0, a, 0.0)
        soft = np.clip(soft * 1.02, 0, 1)
        a8 = (soft * 255).astype(np.uint8)
        rgba = np.dstack([rgb, a8])

        # 7. 紧凑外接框裁剪
        if crop:
            ys, xs = np.where(a8 > 8)
            if len(ys) > 0 and len(xs) > 0:
                y0, y1 = max(0, ys.min() - pad), min(rgba.shape[0], ys.max() + pad + 1)
                x0, x1 = max(0, xs.min() - pad), min(rgba.shape[1], xs.max() + pad + 1)
                rgba = rgba[y0:y1, x0:x1]

        # 8. Windows 安全写盘
        out_path_obj = Path(out_path)
        out_path_obj.parent.mkdir(parents=True, exist_ok=True)
        ok, buf = cv2.imencode(".png", cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA))
        if ok:
            with open(out_path, "wb") as f:
                f.write(buf.tobytes())

        elapsed = time.time() - t0
        return {
            "status": "success",
            "out_path": str(out_path),
            "width": rgba.shape[1],
            "height": rgba.shape[0],
            "was_downscaled": was_downscaled,
            "orig_width": orig_w,
            "orig_height": orig_h,
            "elapsed_seconds": round(elapsed, 2),
            "model_id": self.active_model_id
        }
