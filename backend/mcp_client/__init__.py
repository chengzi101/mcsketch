"""Read-only official MCP SDK transport; schema discovered rather than invented."""
import asyncio
import json
import os
import copy
from time import monotonic
from pathlib import Path
import httpx
from jsonschema import validate, ValidationError
from backend.errors import AppError

ALLOWED = {"query-nearby-stores", "query-meals", "query-meal-detail", "list-nutrition-foods", "calculate-price"}
OPERATION_TO_TOOL = {"stores":"query-nearby-stores", "menu":"query-meals", "detail":"query-meal-detail", "nutrition":"list-nutrition-foods", "quote":"calculate-price"}

def unpack(result):
    if result.isError:
        raise AppError("官方工具返回业务错误，请检查门店、商品规格和参数", "mcp_tool_error", 502)
    if result.structuredContent is not None:
        return result.structuredContent
    texts = [b.text for b in result.content if getattr(b, "type", "") == "text"]
    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except ValueError:
            pass
    return {"text": "\n".join(texts)}

def error_kind(exc):
    if isinstance(exc, BaseExceptionGroup):
        for child in exc.exceptions:
            result = error_kind(child)
            if result != "connection":
                return result
    if isinstance(exc, httpx.HTTPStatusError):
        return str(exc.response.status_code)
    if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
        return "timeout"
    return "connection"

class OfficialClient:
    async def _session(self, operation):
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
        token = os.getenv("MCD_MCP_TOKEN", "").strip()
        if not token:
            raise AppError("请在后端 .env 配置 MCD_MCP_TOKEN，然后重启服务", "missing_token", 503)
        for attempt in range(2):
            try:
                async with asyncio.timeout(35):
                    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}, timeout=25) as http:
                        async with streamable_http_client("https://mcp.mcd.cn", http_client=http) as streams:
                            async with ClientSession(streams[0], streams[1]) as session:
                                await session.initialize()
                                return await operation(session)
            except AppError:
                raise
            except Exception as exc:
                kind = error_kind(exc)
                if attempt == 0 and kind in {"429", "timeout", "connection", "502", "503"}:
                    await asyncio.sleep(.8)
                    continue
                messages = {"401": "MCP Token 无效或已过期", "403":"官方服务拒绝访问，请检查 Token 权限和网络环境", "429": "官方服务限流，请稍后重试", "timeout": "MCP 请求超时，请稍后重试"}
                raise AppError(messages.get(kind, "无法连接官方 MCP 服务，请检查网络和配置"), "mcp_" + kind, 502) from None

    def tools(self):
        async def action(s):
            items, cursor = [], None
            for _ in range(10):
                r = await s.list_tools(cursor=cursor)
                items.extend(t.model_dump(by_alias=True) for t in r.tools if t.name in ALLOWED)
                cursor = r.nextCursor
                if not cursor:
                    break
            if cursor:
                raise AppError("工具列表分页超过限制，未使用不完整 schema", "schema_pagination", 502)
            return items
        return asyncio.run(self._session(action))

    def call(self, name, arguments):
        if not isinstance(name, str) or name not in ALLOWED:
            raise AppError("仅允许菜单查询、营养查询和核价工具")
        async def action(s):
            cursor, tool = None, None
            for _ in range(10):
                listing = await s.list_tools(cursor=cursor)
                tool = next((t for t in listing.tools if t.name == name), None)
                cursor = listing.nextCursor
                if tool or not cursor:
                    break
            if tool is None:
                raise AppError("当前服务未提供该工具", "missing_tool", 502)
            try:
                validate(arguments, tool.inputSchema)
            except ValidationError:
                raise AppError("调用参数不符合官方 tools/list schema") from None
            return unpack(await s.call_tool(name, arguments))
        return asyncio.run(self._session(action))

def path_get(data, path):
    for part in path.split(".") if path else []:
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data

def render(value, context):
    if isinstance(value, str) and value.startswith("$"):
        return path_get(context, value[1:])
    if isinstance(value, dict):
        if "$map" in value:
            if set(value) != {"$map", "template"} or not isinstance(value["$map"], str):
                raise AppError("本地数组映射配置须包含 $map 和 template", "bindings_invalid", 503)
            rows = path_get(context, value["$map"])
            if not isinstance(rows,list):
                raise AppError("本地数组映射的数据源不是数组", "bindings_invalid", 503)
            return [render(value["template"], {**context, "item":row}) for row in rows]
        return {k: render(v, context) for k,v in value.items()}
    if isinstance(value, list):
        return [render(v, context) for v in value]
    return value

class LiveGateway:
    """Bindings are local configuration, filled only from observed official schemas."""
    def __init__(self):
        self.client = OfficialClient()
        self.bindings = None
        self.cache = {}

    def uses_official_defaults(self):
        return self.bindings is None and not Path(os.getenv("MCD_BINDINGS_FILE", "live-bindings.json")).is_file()

    def config(self):
        if self.bindings is not None:
            return self.bindings
        p = Path(os.getenv("MCD_BINDINGS_FILE", "live-bindings.json"))
        if not p.is_file():
            from backend.mcp_client.official import DEFAULT_BINDINGS
            return copy.deepcopy(DEFAULT_BINDINGS)
        try:
            config = json.loads(p.read_text(encoding="utf-8"))
            schema = json.loads((Path(__file__).resolve().parents[2]/"docs"/"live-bindings.schema.json").read_text(encoding="utf-8"))
            validate(config, schema)
            return config
        except (ValueError, OSError, ValidationError):
            raise AppError("Live 映射配置无法读取", "bindings_invalid", 503) from None

    def execute(self, operation, context):
        try:
            official=self.uses_official_defaults()
            cache_key=(operation,context.get('store_id'),context.get('product_id'))
            if official and operation in {'detail','nutrition'}:
                cached=self.cache.get(cache_key)
                if cached and monotonic()-cached[0]<60:return copy.deepcopy(cached[1])
            spec = self.config()[operation]
            if spec["tool"] != OPERATION_TO_TOOL[operation]:
                raise AppError("本地映射工具与业务操作不一致", "bindings_invalid", 503)
            if official and operation=='stores':
                from backend.mcp_client.official import search_context
                context=search_context(context)
            args=render(spec.get("arguments", {}), context)
            if official and operation=='quote':
                from backend.mcp_client.official import default_quote_item
                args['items']=[default_quote_item(self.execute('detail',{'store_id':context['store_id'],'product_id':item['id']})[0]['data'],item['qty']) for item in context['items']]
            data = self.client.call(spec["tool"], args)
            if "success_path" in spec and path_get(data,spec["success_path"]) != spec["success_value"]:
                raise AppError("官方响应未满足已配置的业务成功条件，未使用其中价格或菜单", "mcp_business_error", 502)
            if official and operation=='menu':
                from backend.mcp_client.official import normalize_menu
                data=normalize_menu(data)
            if official and operation=='nutrition':
                from backend.mcp_client.official import decode_nutrition_table
                data=copy.deepcopy(data);data['data']=decode_nutrition_table(data['data'])
            if official and operation in {'detail','nutrition'}:self.cache[cache_key]=(monotonic(),copy.deepcopy((data,spec)))
            return data, spec
        except (KeyError, IndexError, TypeError, ValueError, AttributeError):
            raise AppError("官方数据结构与本地映射不一致，请重新核对 schema", "schema_drift", 502) from None
