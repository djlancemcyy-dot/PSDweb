# -*- coding: utf-8 -*-
"""
shoe_cutout_engine.py — 小帆船专用工业级离线鞋样抠图引擎
基于调优 ISNet 1024 + 白底救援 (rescue_white) + 白布补实 (solidify) + 边缘引导滤波 + RGB反解去白边 (decontaminate)
"""

import os
import sys
import time
from pathlib import Path
import numpy as np
import cv2
import onnxruntime as ort
from PIL import Image

_HERE = Path(__file__).resolve().parent
MODELS_DIR = _HERE / "models"

# 优先选用的调优模型路径
MODEL_CANDIDATES = [
    MODELS_DIR / "isnet_fine_tuned.onnx",
    MODELS_DIR / "isnet.onnx",
    MODELS_DIR / "isnet-general-use.onnx",
    MODELS_DIR / "birefnet_lite.onnx",
    MODELS_DIR / "u2net.onnx"
]

class ShoeCutoutEngine:
    def __init__(self, threads: int = 4):
        self.threads = threads
        self.session = None
        self.input_name = None
        self.input_h = 1024
        self.input_w = 1024
        self.model_path = None
        self.init_engine()

    def init_engine(self):
        for candidate in MODEL_CANDIDATES:
            if candidate.exists():
                self.model_path = candidate
                break

        if not self.model_path:
            raise FileNotFoundError(f"未找到可用的 ONNX 抠图模型，搜索目录：{MODELS_DIR}")

        print(f"[ShoeCutoutEngine] 正在加载工业级鞋样抠图模型: {self.model_path.name}...")
        so = ort.SessionOptions()
        so.intra_op_num_threads = self.threads
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        so.enable_cpu_mem_arena = False
        so.enable_mem_pattern = False

        self.session = ort.InferenceSession(str(self.model_path), so, providers=["CPUExecutionProvider"])
        inp = self.session.get_inputs()[0]
        self.input_name = inp.name
        self.input_h = inp.shape[2] if (len(inp.shape) > 2 and isinstance(inp.shape[2], int)) else 1024
        self.input_w = inp.shape[3] if (len(inp.shape) > 3 and isinstance(inp.shape[3], int)) else 1024
        print(f"[ShoeCutoutEngine] 模型载入完成 (输入尺寸: {self.input_w}x{self.input_h}, 线程: {self.threads})")

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
        x = (x - 0.5)  # ISNet 标准预处理
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
        """白底救援：防止白色鞋面、鞋舌、白色EVA大底被当成背景吃空"""
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
        """RGB 反解去白边：F=(I-(1-a)*255)/a，不动 alpha，彻底消除白晕"""
        I = rgb.astype(np.float32)
        a3 = a[..., None]
        F = (I - (1.0 - a3) * 255.0) / np.maximum(a3, 0.05)
        F = np.clip(F, 0, 255)
        w = np.clip((a - 0.01) / 0.25, 0, 1)[..., None]
        return np.clip(I * (1 - w) + F * w, 0, 255).astype(np.uint8)

    def process_shoe(self, in_path: str, out_path: str, crop: bool = True, pad: int = 8, max_dimension: int = 2048) -> dict:
        t0 = time.time()
        rgb = self.load_rgb(in_path)
        
        # 0. 自动等比例缩小超大分辨率照片 (超过 2048px 时采用 INTER_AREA 无摩尔纹重采样，防止爆内存与卡顿，兼顾极高画质)
        orig_h, orig_w = rgb.shape[:2]
        was_downscaled = False
        if max(orig_h, orig_w) > max_dimension:
            scale = max_dimension / float(max(orig_h, orig_w))
            target_w = int(round(orig_w * scale))
            target_h = int(round(orig_h * scale))
            rgb = cv2.resize(rgb, (target_w, target_h), interpolation=cv2.INTER_AREA)
            was_downscaled = True
        
        # 1. 深度推理 (ISNet 1024)
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
            # 找到鞋子最大连通块，只清除小于 1500px 的漂浮阴影/噪点
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
            "elapsed_seconds": round(elapsed, 2)
        }
