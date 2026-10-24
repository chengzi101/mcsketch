"""Real CLIP inference. Never replace inference with fixture predictions."""
import base64
import io
import os
import threading
from PIL import Image, ImageChops, UnidentifiedImageError
from backend.errors import AppError
from backend.matching import CATEGORIES

def read_png(value):
    if not isinstance(value, str) or not value.startswith("data:image/png;base64,") or len(value) > 4_000_000:
        raise AppError("需要不超过 3 MB 的 PNG 图片")
    try:
        data = base64.b64decode(value.split(",", 1)[1], validate=True)
        img = Image.open(io.BytesIO(data))
        if img.format != "PNG" or not 16 <= img.width <= 2048 or not 16 <= img.height <= 2048:
            raise AppError("PNG 尺寸须在 16–2048 像素之间")
        img.load()
        rgba = img.convert("RGBA")
        white = Image.new("RGBA", img.size, "white")
        white.alpha_composite(rgba)
        img = white.convert("RGB")
        if ImageChops.difference(img, Image.new("RGB", img.size, "white")).getbbox() is None:
            raise AppError("画板还是空的，先画点想吃的吧")
        return img
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise AppError("图片无法读取，请重新导出 PNG") from None

class Vision:
    def __init__(self):
        self.model = self.processor = None
        self.lock = threading.Lock()
        self.state = "not_loaded"

    def predict(self, image):
        with self.lock:
            try:
                import torch
                from transformers import CLIPModel, CLIPProcessor
                if self.model is None:
                    self.state = "loading"
                    model_id = os.getenv("VISION_MODEL", "openai/clip-vit-base-patch32")
                    revision = os.getenv("VISION_REVISION") or ("3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268" if model_id == "openai/clip-vit-base-patch32" else "main")
                    self.processor = CLIPProcessor.from_pretrained(model_id, revision=revision, use_fast=False)
                    self.model = CLIPModel.from_pretrained(model_id, revision=revision, use_safetensors=False).eval()
                    torch.set_num_threads(min(4, os.cpu_count() or 1))
                words = ["hamburger", "french fries", "ice cream cone", "soda drink in a cup with a straw", "chicken nuggets", "coffee cup"]
                prompts = [f"a simple hand drawn doodle of {w} on white paper" for w in words]
                # Extra classes reduce forced guesses on unrelated sketches.
                prompts += ["a drawing of a house", "a drawing of a cat", "random scribbles", "a blank sheet of paper"]
                inputs = self.processor(text=prompts, images=image, return_tensors="pt", padding=True)
                with torch.inference_mode():
                    scores = self.model(**inputs).logits_per_image[0].softmax(dim=0).tolist()
                top = sorted(range(6), key=lambda i: -scores[i])[:3]
                candidates = [dict(category=list(CATEGORIES)[i], label=list(CATEGORIES.values())[i], score=round(scores[i], 5)) for i in top]
                uncertain = scores[top[0]] < .45 or scores[top[0]] - scores[top[1]] < .12 or max(scores[6:]) > scores[top[0]]
                self.state = "ready"
                return dict(status="ok", model=os.getenv("VISION_MODEL", "openai/clip-vit-base-patch32"), candidates=candidates, uncertain=uncertain, message="模型评分不是准确率，请确认类别后匹配餐品。" if not uncertain else "这张画有点难猜，请手动确认或纠正类别。")
            except Exception:
                self.state = "unavailable"
                return dict(status="manual", candidates=[], uncertain=True, message="视觉模型暂不可用。可手动选择类别继续；安装视觉依赖并下载权重后重试。")
