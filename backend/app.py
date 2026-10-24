import os
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException
from backend.errors import AppError
from backend.service import MealService
from backend.matching import CATEGORIES, match
from backend.optimizer import repair
from backend.vision import Vision, read_png

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "30")

def create_app(service=None, vision=None):
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 4_200_000
    service, vision = service or MealService(), vision or Vision()

    @app.before_request
    def same_origin():
        if request.method == "POST" and request.headers.get("Origin") and request.headers["Origin"] != request.host_url.rstrip("/"):
            raise AppError("不允许跨站调用本地服务", "origin",403)

    @app.after_request
    def headers(r):
        r.headers["X-Content-Type-Options"]="nosniff"
        r.headers["Referrer-Policy"]="no-referrer"
        if request.path.startswith("/api/"):
            r.headers["Cache-Control"]="no-store"
        return r

    @app.errorhandler(AppError)
    def known(e):
        return jsonify(error=str(e),code=e.code),e.status

    @app.errorhandler(Exception)
    def unknown(e):
        if isinstance(e,HTTPException):
            return jsonify(error=e.description,code="http_error"),e.code
        return jsonify(error="服务处理失败，请检查后端配置或重试",code="server_error"),500

    def body():
        b=request.get_json()
        if not isinstance(b,dict):
            raise AppError("请求须为 JSON 对象")
        return b

    def context(b):
        mode=b.get("mode","demo")
        store=b.get("store_id","demo-studio")
        if not isinstance(mode,str) or mode not in {"demo","live"} or not isinstance(store,str) or len(store)>200:
            raise AppError("模式或门店格式错误")
        return mode,store

    @app.get("/api/status")
    def status():
        return jsonify(mode="demo",token_configured=bool(os.getenv("MCD_MCP_TOKEN", "").strip()),vision=vision.state,categories=CATEGORIES,live_bindings=Path(os.getenv("MCD_BINDINGS_FILE","live-bindings.json")).is_file())

    @app.post("/api/recognize")
    def recognize():
        return jsonify(vision.predict(read_png(body().get("image"))))

    @app.post("/api/stores")
    def stores():
        b=body(); mode,_=context(b)
        address=b.get("address","")
        if not isinstance(address,str) or len(address)>300:
            raise AppError("地址格式错误")
        return jsonify(stores=service.stores(mode,address))

    @app.post("/api/menu")
    def menu():
        mode,store=context(body())
        return jsonify(products=service.menu(mode,store),source=mode)

    @app.post("/api/match")
    def matching():
        b=body(); mode,store=context(b)
        products=match(service.menu(mode,store),b.get("category"))
        return jsonify(products=products,source=mode)

    @app.post("/api/detail")
    def detail():
        b=body(); mode,store=context(b)
        p=next((p for p in service.menu(mode,store) if p["id"]==b.get("id")),None)
        if not p:
            raise AppError("商品不存在")
        return jsonify(product=service.enrich(p,store) if mode=="live" else p)

    @app.post("/api/quote")
    def quote():
        b=body(); mode,store=context(b); menu=service.menu(mode,store)
        cart=service.cart(b.get("items"),menu)
        return jsonify(service.quote(mode,store,cart,menu))

    @app.post("/api/repair")
    def optimize():
        b=body(); mode,store=context(b); menu=service.menu(mode,store)
        if mode=="live" and (b.get("avoid") or b.get("max_kcal") is not None):
            menu=[service.enrich(p,store) for p in menu]
        cart=service.cart(b.get("items"),menu)
        return jsonify(repair(service,mode,store,cart,menu,b))

    @app.get("/api/live/tools")
    def live_tools():
        return jsonify(tools=service.live.client.tools())

    @app.post("/api/live/call")
    def live_call():
        b=body()
        if not isinstance(b.get("arguments"),dict):
            raise AppError("arguments 必须是对象")
        return jsonify(data=service.live.client.call(b.get("tool"),b["arguments"]))

    @app.get("/")
    def index():
        folder=ROOT/"frontend"/"dist"
        if not (folder/"index.html").exists():
            return "请先执行前端构建，参见 README.md",503
        return send_from_directory(folder,"index.html")

    @app.get("/assets/<path:name>")
    def assets(name):
        return send_from_directory(ROOT/"frontend"/"dist"/"assets",name)

    return app

if __name__=="__main__":
    from waitress import serve
    port=int(os.getenv("MCSKETCH_PORT","5173"))
    print(f"McSketch: http://127.0.0.1:{port}",flush=True)
    serve(create_app(),host="127.0.0.1",port=port,threads=8)
