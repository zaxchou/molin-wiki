import logging
import httpx
import base64
import json
import time
from typing import List, Dict, Optional, Tuple
import io
from PIL import Image

from app.core.config import get_settings
from app.llm import parse_json_loose

# logger = logging.getLogger(__name__)  # 彻底禁用，避免 name 'logger' is not defined 问题！！
settings = get_settings()
_SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
MAX_RETRIES = 4
RETRY_DELAY = 3


def encode_image_to_base64(image_path: str, max_side: int = 2048, quality: int = 85) -> str:
    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        width, height = img.size
        longest = max(width, height)
        if longest > max_side:
            scale = max_side / float(longest)
            new_w = max(1, int(width * scale))
            new_h = max(1, int(height * scale))
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        data = buf.getvalue()
        return base64.b64encode(data).decode("utf-8")


def _extract_complete_json_array(content: str, array_key: str) -> Optional[list]:
    """
    从截断的 content 中提取完整的数组（如 inscription_regions）。
    用括号计数找到正确的闭合 ]，非正则非贪婪匹配。
    返回完整解析的数组或 None。
    """
    import re
    print(f"DEBUG: _extract_complete_json_array for {array_key}")
    key_pattern = rf'"{array_key}"\s*:'
    key_match = re.search(key_pattern, content)
    if not key_match:
        print("DEBUG: _extract_complete_json_array: key not found")
        return None

    # 找 [ 开始
    ptr = key_match.end()
    while ptr < len(content) and content[ptr] in ' \t\n\r':
        ptr += 1
    if ptr >= len(content) or content[ptr] != '[':
        print("DEBUG: _extract_complete_json_array: no [ found")
        return None

    # 括号计数找 ] 结束
    bracket_count = 1
    ptr += 1
    start = ptr - 1
    while ptr < len(content) and bracket_count > 0:
        c = content[ptr]
        if c == '[':
            bracket_count += 1
        elif c == ']':
            bracket_count -= 1
        ptr += 1

    array_str = content[start:ptr]
    try:
        result = json.loads(array_str)
        print(f"DEBUG: _extract_complete_json_array: {array_key} parsed, {len(result) if result else 0} items")
        return result
    except json.JSONDecodeError as e:
        print(f"DEBUG: _extract_complete_json_array: {array_key} parse failed: {e}")
        return None




def _parse_llm_json_response(content: str) -> Dict:
    """
    解析 LLM 返回的 JSON 内容（B10 收敛为两层）：
    1. parse_json_loose：容忍 ```json 围栏与前后缀文本
    2. 截断兜底：响应被 max_tokens 截断时，用括号计数提取完整的 regions 数组
    都失败返回 success=False 的最小结构（调用方会重试或报错）。
    """
    try:
        parsed = parse_json_loose(content)
        parsed["success"] = True
        return parsed
    except (ValueError, json.JSONDecodeError):
        pass

    try:
        insc_extracted = _extract_complete_json_array(content, "inscription_regions")
        paint_extracted = _extract_complete_json_array(content, "painting_regions")
        if insc_extracted is not None or paint_extracted is not None:
            print("INFO: JSON截断但括号计数提取 regions 成功")
            return {
                "inscription_regions": insc_extracted if insc_extracted is not None else [],
                "painting_regions": paint_extracted if paint_extracted is not None else [],
                "blank_regions": [],
                "analysis_note": "JSON截断但成功提取区域",
                "success": True,
            }
    except Exception as e_ext:
        print(f"WARNING: regions 截断提取兜底失败: {e_ext}")

    print("ERROR: 所有JSON解析方式均失败，返回空结构")
    print(f"ERROR: 原始响应前500字符: {content[:500]}")
    return {
        "success": False,
        "inscription_regions": [],
        "painting_regions": [],
        "blank_regions": [],
        "analysis_note": "JSON解析失败，原始内容前200字符: " + content[:200]
    }




def analyze_image_regions(image_path: str, image_width: int, image_height: int, artist: str = None) -> Dict:
    """
    使用 MiniMax-M2.5 模型分析图像中的题跋、绘画、留白区域

    Returns:
        {
            "inscription_regions": [{"x1": 0, "y1": 0, "x2": 100, "y2": 50}, ...],
            "painting_regions": [...],
            "blank_regions": [...],
            "analysis_note": "..."
        }
    """
    print(f"INFO: 开始分析图像: {image_path}")
    print(f"INFO: 图像尺寸: {image_width}x{image_height}")
    
    try:
        # 检查图像文件大小
        import os
        file_size = os.path.getsize(image_path) / (1024 * 1024)  # MB
        print(f"INFO: 图像文件大小: {file_size:.2f} MB")
        
        # 限制文件大小，避免处理过大的图像
        if file_size > 50:  # 限制为50MB
            print("ERROR: 图像文件过大，超过50MB限制")
            return {
                "success": False,
                "error": "图像文件过大，超过50MB限制"
            }
        
        base64_image = encode_image_to_base64(image_path, max_side=2048, quality=85)
        print(f"INFO: Base64编码完成，大小: {len(base64_image) / (1024 * 1024):.2f} MB")

        artist_name = artist if artist else ""
        artist_desc = f"{artist_name}的" if artist_name else ""
        prompt = f"""你是一个专业的中国画艺术分析师。请按照以下三步策略分析这幅{artist_desc}绘画作品：

## 三步划分策略

### 第一步：确定绘画区域（绿色）
- **目标**：标记画作中的绘画主体（山水、花鸟、竹石等）
- **要求**：用15-25个点的多边形沿绘画主体外边缘描绘轮廓，尽量贴合实际边缘，允许少量溢出（5%左右）
- **方法**：沿绘画内容的可见外缘取点，点间距大致均匀，在边缘弯曲或变化大的地方多取点以贴合轮廓

### 第二步：确定题跋区域（红色）
- **目标**：标记所有书法文字、款识、印章
- **要求**：
  - 准确框选文字和印章，可以稍微溢出文字边缘（约5-10%的边距）
  - **绝对不能和绘画区域重叠**
  - 如果有重叠，题跋区域优先，绘画区域需要退让
- **方法**：用多边形精确描绘文字和印章的边界，稍微向外扩展一点点确保完整包含

### 第三步：自动计算留白区域（蓝色）
- **目标**：剩余的所有部分
- **要求**：不需要识别，自动计算为整幅画减去绘画和题跋的部分
- **注意**：你只需要返回绘画区域和题跋区域，留白区域由系统自动计算

## 返回格式（重要：必须使用多边形points格式）

```json
{{
    "inscription_regions": [
        {{
            "points": [{{"x": 0.1, "y": 0.1}}, {{"x": 0.5, "y": 0.1}}, {{"x": 0.5, "y": 0.3}}, {{"x": 0.1, "y": 0.3}}]
        }}
    ],
    "painting_regions": [
        {{
            "points": [
                {{"x": 0.15, "y": 0.05}}, {{"x": 0.30, "y": 0.08}}, {{"x": 0.42, "y": 0.15}},
                {{"x": 0.50, "y": 0.25}}, {{"x": 0.55, "y": 0.38}}, {{"x": 0.52, "y": 0.48}},
                {{"x": 0.58, "y": 0.55}}, {{"x": 0.62, "y": 0.65}}, {{"x": 0.60, "y": 0.75}},
                {{"x": 0.55, "y": 0.82}}, {{"x": 0.50, "y": 0.88}}, {{"x": 0.42, "y": 0.92}},
                {{"x": 0.32, "y": 0.90}}, {{"x": 0.22, "y": 0.85}}, {{"x": 0.15, "y": 0.78}},
                {{"x": 0.10, "y": 0.68}}, {{"x": 0.08, "y": 0.55}}, {{"x": 0.06, "y": 0.42}},
                {{"x": 0.08, "y": 0.28}}, {{"x": 0.10, "y": 0.15}}
            ]
        }}
    ],
    "blank_regions": [],
    "analysis_note": "分析画作内容、艺术特色、题跋内容等，不要包含坐标信息或区域边界描述"
}}```

## 输出格式

```json
{{
    "inscription_regions": [ {{"points": [{{"x":0.05,"y":0.05}},...]}}, ... ],
    "painting_regions": [ {{"points": [{{"x":0.1,"y":0.1}},{{"x":0.3,"y":0.1}},...]}}, ... ],
    "blank_regions": [],
    "analysis_note": "简要描述画作内容"
}}
```

## 关键规则
- **只用 points 多边形格式，禁止 x1/y1/x2/y2 矩形格式**，每个多边形至少3个点
- **绘画区域**：沿外缘取15-25个点，允许约5%溢出
- **题跋区域**：精确框选文字和印章，禁止与绘画重叠
- **留白区域**：留空数组，由系统自动计算
- 坐标为0-1之间的浮点数（相对图像宽高比例）

图像尺寸：{image_width}x{image_height}

请只返回JSON格式数据。"""

        payload = {
            "model": settings.SILICONFLOW_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "stream": False,
            "max_tokens": 16384,
            # 要求供应商返回合法 JSON（实测 zhipu/dashscope 兼容模式均支持）
            "response_format": {"type": "json_object"}
        }

        print("INFO: 开始调用API分析图像...")

        def build_chat_url(base_url: str) -> str:
            base = (base_url or "").rstrip("/")
            if base.endswith("/chat/completions"):
                return base
            return f"{base}/chat/completions"

        def call_provider(provider: str, base_url: str, api_key: str, model: str) -> Dict:
            url = build_chat_url(base_url)
            print(f"INFO: 当前使用AI供应商: {provider}")
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            provider_payload = dict(payload)
            provider_payload["model"] = model

            limits = httpx.Limits(max_keepalive_connections=5, max_connections=5)
            with httpx.Client(limits=limits) as client:
                for retry in range(MAX_RETRIES):
                    attempt_timeout = httpx.Timeout(400.0, connect=10.0, read=360.0, write=60.0)
                    delay = min(60, (2 ** retry) * RETRY_DELAY)
                    jitter = 0.5 + (time.time() % 1.0) * 0.5
                    delay = delay * jitter
                    try:
                        response = client.post(url, headers=headers, json=provider_payload, timeout=attempt_timeout)
                        response.raise_for_status()
                        result = response.json()

                        content = result["choices"][0]["message"]["content"]
                        print("INFO: API调用成功，开始解析返回结果...")

                        # 使用统一的JSON修复函数
                        analysis = _parse_llm_json_response(content)

                        # JSON 解析彻底失败（Level 4 也恢复不了）
                        if not analysis.get("success", True):
                            if retry < MAX_RETRIES - 1:
                                print(f"WARNING: JSON解析失败，将在同一供应商内重试 ({retry+1}/{MAX_RETRIES})")
                                time.sleep(delay)
                                continue
                            print("WARNING: JSON解析失败，所有重试用尽，报告给调用方处理")
                            return {
                                "success": False,
                                "error": analysis.get("analysis_note", "JSON解析失败"),
                                "regions": {},
                                "analysis_note": analysis.get("analysis_note", ""),
                                "raw_response": content[:500]
                            }

                        print("INFO: JSON解析成功")

                        # 【极端容错】区域标准化失败时返回默认空 regions
                        try:
                            normalized_regions = _normalize_regions(analysis, image_width, image_height)
                            print("INFO: 区域标准化完成")
                        except Exception as e_norm:
                            print(f"WARNING: 区域标准化失败，使用默认空regions: {e_norm}")
                            normalized_regions = {
                                "inscription_regions": [],
                                "painting_regions": [],
                                "blank_regions": [{"x1": 0, "y1": 0, "x2": image_width, "y2": image_height, "type": "rectangle"}]
                            }

                        return {
                            "success": True,
                            "provider": provider,
                            "regions": normalized_regions,
                            "analysis_note": analysis.get("analysis_note", ""),
                            "raw_response": content
                        }
                    except httpx.HTTPStatusError as e:
                        status = e.response.status_code
                        # 个别供应商/模型不支持 response_format：去掉后在本供应商内重试
                        if status == 400 and provider_payload.pop("response_format", None) is not None:
                            print("WARNING: 供应商拒绝 response_format，去掉后重试")
                            continue
                        retryable = status in (429, 500, 502, 503, 504)
                        if retryable and retry < MAX_RETRIES - 1:
                            print(f"WARNING: API请求错误 {status} (重试 {retry+1}/{MAX_RETRIES})")
                            time.sleep(delay)
                            continue
                        try:
                            error_detail = e.response.json().get("error", {}).get("message", "Unknown error")
                            return {"success": False, "error": f"API请求错误: {status} - {error_detail}"}
                        except Exception:
                            return {"success": False, "error": f"API请求错误: {status}"}
                    except (httpx.ConnectError, httpx.ReadError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as e:
                        if retry < MAX_RETRIES - 1:
                            print(f"WARNING: 网络/超时错误 (重试 {retry+1}/{MAX_RETRIES}): {e}")
                            time.sleep(delay)
                            continue
                        return {"success": False, "error": "网络/超时错误: " + str(e)}
                    except json.JSONDecodeError as e:
                        if retry < MAX_RETRIES - 1:
                            print(f"WARNING: JSON解析错误 (重试 {retry+1}/{MAX_RETRIES}): {e}")
                            time.sleep(delay)
                            continue
                        return {"success": False, "error": "JSON解析错误: " + str(e)}
                    except Exception as e:
                        return {"success": False, "error": "分析失败: " + str(e)}

        tried = []
        last_error = None

        forced = (getattr(settings, "TIBA_LLM_PROVIDER", "") or "").strip().lower()
        if forced and forced not in ("zhipu", "qwen", "siliconflow"):
            return {"success": False, "error": f"无效TIBA_LLM_PROVIDER: {forced}"}

        def _try(provider: str, base_url: str, api_key: str, model: str) -> Optional[Dict]:
            nonlocal last_error
            tried.append(provider)
            result = call_provider(provider, base_url, api_key, model)
            if result.get("success"):
                return result
            last_error = result.get("error") or last_error
            return None

        if forced == "zhipu":
            if settings.ZHIPU_API_KEY and settings.ZHIPU_BASE_URL:
                r = _try("zhipu", settings.ZHIPU_BASE_URL, settings.ZHIPU_API_KEY, settings.ZHIPU_MODEL)
                if r:
                    return r
            return {"success": False, "error": f"zhipu调用失败或未配置: {last_error or ''}".strip()}

        if forced == "qwen":
            if settings.QWEN_API_KEY and settings.QWEN_BASE_URL:
                r = _try("qwen", settings.QWEN_BASE_URL, settings.QWEN_API_KEY, settings.QWEN_MODEL)
                if r:
                    return r
            return {"success": False, "error": f"qwen调用失败或未配置: {last_error or ''}".strip()}

        if forced == "siliconflow":
            if settings.SILICONFLOW_API_KEY:
                r = _try("siliconflow", _SILICONFLOW_BASE_URL, settings.SILICONFLOW_API_KEY, settings.SILICONFLOW_MODEL)
                if r:
                    return r
            return {"success": False, "error": f"siliconflow调用失败或未配置: {last_error or ''}".strip()}

        if settings.ZHIPU_ENABLED and settings.ZHIPU_API_KEY and settings.ZHIPU_BASE_URL:
            r = _try("zhipu", settings.ZHIPU_BASE_URL, settings.ZHIPU_API_KEY, settings.ZHIPU_MODEL)
            if r:
                return r

        if settings.QWEN_ENABLED and settings.QWEN_API_KEY and settings.QWEN_BASE_URL:
            r = _try("qwen", settings.QWEN_BASE_URL, settings.QWEN_API_KEY, settings.QWEN_MODEL)
            if r:
                return r

        if settings.SILICONFLOW_ENABLED and settings.SILICONFLOW_API_KEY:
            r = _try("siliconflow", _SILICONFLOW_BASE_URL, settings.SILICONFLOW_API_KEY, settings.SILICONFLOW_MODEL)
            if r:
                return r

        tried_text = " -> ".join(tried) if tried else "none"
        suffix = f": {last_error}" if last_error else ""
        return {"success": False, "error": f"无可用AI供应商或调用失败 ({tried_text}){suffix}"}

    except Exception as e:
        print(f"ERROR: 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": "分析失败: " + str(e)
        }


def _normalize_regions(analysis: Dict, image_width: int, image_height: int) -> Dict:
    """
    将比例坐标转换为像素坐标
    支持多边形和矩形两种格式
    所有区域最终都会转换为多边形格式以确保一致性
    """
    def rectangle_to_polygon_points(x1: float, y1: float, x2: float, y2: float, width: int, height: int) -> List[Dict]:
        """将矩形转换为多边形points格式"""
        return [
            {"x": int(max(0, min(1, x1)) * width), "y": int(max(0, min(1, y1)) * height)},
            {"x": int(max(0, min(1, x2)) * width), "y": int(max(0, min(1, y1)) * height)},
            {"x": int(max(0, min(1, x2)) * width), "y": int(max(0, min(1, y2)) * height)},
            {"x": int(max(0, min(1, x1)) * width), "y": int(max(0, min(1, y2)) * height)}
        ]
    
    def convert_regions(regions: List[Dict], width: int, height: int) -> List[Dict]:
        converted = []
        for reg in regions:
            # 检查是否是多边形格式
            if "points" in reg and isinstance(reg["points"], list):
                # 多边形格式
                points = reg["points"]
                if len(points) >= 3:
                    converted_points = []
                    for point in points:
                        x = int(max(0, min(1, point.get("x", 0))) * width)
                        y = int(max(0, min(1, point.get("y", 0))) * height)
                        converted_points.append({"x": x, "y": y})
                    converted.append({
                        "points": converted_points,
                        "type": "polygon"
                    })
            elif "x1" in reg and "y1" in reg and "x2" in reg and "y2" in reg:
                # 矩形格式 - 自动转换为多边形
                x1 = reg.get("x1", 0)
                y1 = reg.get("y1", 0)
                x2 = reg.get("x2", 0)
                y2 = reg.get("y2", 0)
                # 检查坐标是比例值(0-1)还是像素值
                if x1 <= 1 and y1 <= 1 and x2 <= 1 and y2 <= 1:
                    # 比例坐标，需要转换为像素
                    polygon_points = rectangle_to_polygon_points(x1, y1, x2, y2, width, height)
                else:
                    # 已经是像素坐标
                    polygon_points = [
                        {"x": int(x1), "y": int(y1)},
                        {"x": int(x2), "y": int(y1)},
                        {"x": int(x2), "y": int(y2)},
                        {"x": int(x1), "y": int(y2)}
                    ]
                converted.append({
                    "points": polygon_points,
                    "type": "polygon"
                })
        return converted

    # 转换题跋和绘画区域
    inscription_regions = convert_regions(
        analysis.get("inscription_regions", []),
        image_width, image_height
    )
    painting_regions = convert_regions(
        analysis.get("painting_regions", []),
        image_width, image_height
    )
    
    # 如果AI返回了留白区域，使用AI的；否则自动计算
    blank_regions_from_ai = convert_regions(
        analysis.get("blank_regions", []),
        image_width, image_height
    )
    
    if blank_regions_from_ai:
        blank_regions = blank_regions_from_ai
    else:
        # 自动计算留白区域 = 整幅画 - 题跋 - 绘画
        blank_regions = calculate_blank_regions(
            inscription_regions, painting_regions, image_width, image_height
        )
    
    return {
        "inscription_regions": inscription_regions,
        "painting_regions": painting_regions,
        "blank_regions": blank_regions
    }


def calculate_blank_regions(inscription_regions, painting_regions, image_width, image_height):
    """
    自动计算留白区域
    留白 = 整幅画 - 题跋区域 - 绘画区域
    """
    try:
        # 简化处理：返回一个大的矩形留白区域，覆盖整个图像
        # 这样可以避免复杂的计算，减少内存使用和计算时间
        blank_regions = [{
            "x1": 0,
            "y1": 0,
            "x2": image_width,
            "y2": image_height,
            "type": "rectangle"
        }]
        
        return blank_regions
    except Exception as e:
        print(f"ERROR: 计算留白区域时出错: {e}")
        # 出错时返回一个默认的留白区域
        return [{
            "x1": 0,
            "y1": 0,
            "x2": image_width,
            "y2": image_height,
            "type": "rectangle"
        }]


def calculate_area_stats(regions: Dict, image_width: int, image_height: int) -> Dict:
    """
    计算各类区域的面积统计
    使用新的面积计算模块，确保总和为100%
    """
    from .area_calculator import calculate_area_stats_with_overlap_correction
    
    return calculate_area_stats_with_overlap_correction(regions, image_width, image_height)


def _adjust_for_overlap(regions: Dict, image_width: int, image_height: int) -> Dict:
    """
    简化处理：假设区域可能重叠，返回各类区域的估算面积
    已弃用，请使用 calculate_area_stats
    """
    stats = calculate_area_stats(regions, image_width, image_height)
    return {
        "inscription_area": stats["inscription_area"],
        "painting_area": stats["painting_area"],
        "blank_area": stats["blank_area"]
    }


def analyze_text_summary_only(image_path: str, artist: str = None) -> Dict:
    """
    轻量化AI分析：只生成画作点评概述，不进行区域检测和OCR识别

    Returns:
        {
            "success": boolean,
            "analysis_note": str,
            "error": str (if failed)
        }
    """
    print(f"INFO: 开始轻量化AI点评: {image_path}")
    
    try:
        # 检查图像文件大小
        import os
        file_size = os.path.getsize(image_path) / (1024 * 1024)  # MB
        print(f"INFO: 图像文件大小: {file_size:.2f} MB")
        
        # 限制文件大小，避免处理过大的图像
        if file_size > 50:  # 限制为50MB
            print("ERROR: 图像文件过大，超过50MB限制")
            return {
                "success": False,
                "error": "图像文件过大，超过50MB限制"
            }
        
        base64_image = encode_image_to_base64(image_path, max_side=2048, quality=85)
        print(f"INFO: Base64编码完成，大小: {len(base64_image) / (1024 * 1024):.2f} MB")

        artist_name = artist if artist else ""
        artist_desc = f"{artist_name}的" if artist_name else ""
        prompt = f"""你是一个专业的中国画艺术分析师。请对这幅{artist_desc}绘画作品进行简要点评概述。

## 点评内容要求

请从以下几个方面进行点评：
1. 画作内容概述（描绘了什么主题）
2. 艺术特色和风格特点
3. 整体观感和评价

请用简洁明了的语言，不要超过300字。直接返回点评内容，不需要任何JSON格式或其他标记。"""

        payload = {
            "model": settings.SILICONFLOW_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "stream": False,
            "max_tokens": 1000
        }

        print("INFO: 开始调用轻量化AI点评API...")

        def build_chat_url(base_url: str) -> str:
            base = (base_url or "").rstrip("/")
            if base.endswith("/chat/completions"):
                return base
            return f"{base}/chat/completions"

        def call_provider(provider: str, base_url: str, api_key: str, model: str) -> Optional[Dict]:
            url = build_chat_url(base_url)
            print(f"INFO: 当前使用AI供应商: {provider}")
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            provider_payload = dict(payload)
            provider_payload["model"] = model

            limits = httpx.Limits(max_keepalive_connections=5, max_connections=5)
            with httpx.Client(limits=limits) as client:
                for retry in range(MAX_RETRIES):
                    attempt_timeout = httpx.Timeout(120.0, connect=10.0, read=90.0, write=20.0)
                    delay = min(60, (2 ** retry) * RETRY_DELAY)
                    jitter = 0.5 + (time.time() % 1.0) * 0.5
                    delay = delay * jitter
                    try:
                        response = client.post(url, headers=headers, json=provider_payload, timeout=attempt_timeout)
                        response.raise_for_status()
                        result = response.json()

                        content = result["choices"][0]["message"]["content"]
                        print("INFO: 轻量化AI点评API调用成功")
                        
                        return {
                            "success": True,
                            "analysis_note": content.strip(),
                            "provider": provider
                        }
                    except httpx.HTTPStatusError as e:
                        status = e.response.status_code
                        retryable = status in (429, 500, 502, 503, 504)
                        if retryable and retry < MAX_RETRIES - 1:
                            print(f"WARNING: API请求错误 {status} (重试 {retry+1}/{MAX_RETRIES})")
                            time.sleep(delay)
                            continue
                        try:
                            error_detail = e.response.json().get("error", {}).get("message", "Unknown error")
                            return {"success": False, "error": f"API请求错误: {status} - {error_detail}"}
                        except Exception:
                            return {"success": False, "error": f"API请求错误: {status}"}
                    except (httpx.ConnectError, httpx.ReadError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException) as e:
                        if retry < MAX_RETRIES - 1:
                            print(f"WARNING: 网络/超时错误 (重试 {retry+1}/{MAX_RETRIES}): {e}")
                            time.sleep(delay)
                            continue
                        return {"success": False, "error": "网络/超时错误: " + str(e)}
                    except Exception as e:
                        return {"success": False, "error": "分析失败: " + str(e)}

        tried = []
        last_error = None

        forced = (getattr(settings, "TIBA_LLM_PROVIDER", "") or "").strip().lower()
        if forced and forced not in ("zhipu", "qwen", "siliconflow"):
            return {"success": False, "error": f"无效TIBA_LLM_PROVIDER: {forced}"}

        def _try(provider: str, base_url: str, api_key: str, model: str) -> Optional[Dict]:
            nonlocal last_error
            tried.append(provider)
            result = call_provider(provider, base_url, api_key, model)
            if result.get("success"):
                return result
            last_error = result.get("error") or last_error
            return None

        if forced == "zhipu":
            if settings.ZHIPU_API_KEY and settings.ZHIPU_BASE_URL:
                r = _try("zhipu", settings.ZHIPU_BASE_URL, settings.ZHIPU_API_KEY, settings.ZHIPU_MODEL)
                if r:
                    return r
            return {"success": False, "error": f"zhipu调用失败或未配置: {last_error or ''}".strip()}

        if forced == "qwen":
            if settings.QWEN_API_KEY and settings.QWEN_BASE_URL:
                r = _try("qwen", settings.QWEN_BASE_URL, settings.QWEN_API_KEY, settings.QWEN_MODEL)
                if r:
                    return r
            return {"success": False, "error": f"qwen调用失败或未配置: {last_error or ''}".strip()}

        if forced == "siliconflow":
            if settings.SILICONFLOW_API_KEY:
                r = _try("siliconflow", _SILICONFLOW_BASE_URL, settings.SILICONFLOW_API_KEY, settings.SILICONFLOW_MODEL)
                if r:
                    return r
            return {"success": False, "error": f"siliconflow调用失败或未配置: {last_error or ''}".strip()}

        if settings.ZHIPU_ENABLED and settings.ZHIPU_API_KEY and settings.ZHIPU_BASE_URL:
            r = _try("zhipu", settings.ZHIPU_BASE_URL, settings.ZHIPU_API_KEY, settings.ZHIPU_MODEL)
            if r:
                return r

        if settings.QWEN_ENABLED and settings.QWEN_API_KEY and settings.QWEN_BASE_URL:
            r = _try("qwen", settings.QWEN_BASE_URL, settings.QWEN_API_KEY, settings.QWEN_MODEL)
            if r:
                return r

        if settings.SILICONFLOW_ENABLED and settings.SILICONFLOW_API_KEY:
            r = _try("siliconflow", _SILICONFLOW_BASE_URL, settings.SILICONFLOW_API_KEY, settings.SILICONFLOW_MODEL)
            if r:
                return r

        tried_text = " -> ".join(tried) if tried else "none"
        suffix = f": {last_error}" if last_error else ""
        return {"success": False, "error": f"无可用AI供应商或调用失败 ({tried_text}){suffix}"}

    except Exception as e:
        print(f"ERROR: 轻量化AI点评失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": "轻量化AI点评失败: " + str(e)
        }
