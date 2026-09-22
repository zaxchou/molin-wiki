# app/llm — LLM 统一网关（v2.0 §2.4）

全项目所有 Chat Completions 调用的唯一出口。

## 用法

```python
from app.llm import chat_completion, chat_completion_async, LLMError, parse_json_loose

# 异步（FastAPI 路由内）
data = await chat_completion_async(messages=[{"role": "user", "content": "..."}],
                                   max_tokens=1000)
# 指定供应商/模型
data = await chat_completion_async(messages=..., provider="qwen", model="qwen3.5-plus")

# LLM 输出 JSON 的宽松解析（容忍 ```json 围栏与前后缀文本）
result = parse_json_loose(data["choices"][0]["message"]["content"])
```

失败语义：**抛 `LLMError`**（重试 2 次耗尽 / 不可重试错误），不再返回 `{"error": ...}` 字典。

## 内置能力

| 能力 | 说明 |
|---|---|
| 供应商解析 | providers.py 配置驱动：调用方显式指定 > site_settings 运行时覆盖（管理后台「AI 接口」开关，键 llm_default_provider / llm_default_model，TTL 缓存 5s）> auto（custom→deepseek→qwen→zhipu，按密钥可用性）；body_defaults 处理各家思考模式差异 |
| 连接复用 | 模块级 httpx 客户端单例（旧实现每次调用新建连接） |
| 重试 | 429/5xx/网络错误指数退避 + 抖动，默认 2 次重试 |
| 计量 | usage.py：每次调用记录 provider/model/延迟/tokens/成败（结构化日志 + 进程内计数器），管理后台可见 |
| JSON 修复 | parse_json_loose |

## 接入新供应商（MiMo / DeepSeek / Kimi / GLM…）

OpenAI 兼容的新模型无需改代码：

1. 服务器 env 设置 `AI_BASE_URL`、`AI_API_KEY`、`AI_MODEL`
2. 管理后台 → 系统设置 → AI 接口，选择「自定义 OpenAI 兼容」并保存

切换 ≤5 秒全站生效，管辖范围是走网关的文本类 LLM（翻译、题跋解读、知识问答、情感校正等）；
视觉专用链路（题跋 VL 分类、构图讲评、书法识别）与 embedding 有各自配置，不受此开关影响
（embedding 换模型会导致向量空间不一致，永远不要跟着切）。

## 存量服务迁移路线（分批进行）

| 批次 | 文件 | 状态 |
|---|---|---|
| 1（样板） | `services/qwen_llm_client.py` → 网关薄封装 | ✅ 已完成 |
| 2 | `services/deepseek_service.py` | ✅ 2026-09-22 零引用已删除（B4） |
| 3 | `services/siliconflow_service.py` / `siliconflow_recognition_service.py` | 待做 |
| 4 | `services/inscription_*` 系列（各自拼 prompt+调 LLM） | 待做（inscription_summary_generator 已随 B4 删除） |
| 5 | `services/baidu_ocr_service.py`（零引用） | ✅ 2026-09-22 已删除（B4） |
| 6 | emotion_lexicon v1/v2 并存收敛（v3 为主） | 进行中（v2 已删，写路径已收口 v3） |

迁移规则：旧模块改为网关薄封装（保留旧函数签名，内部调 app.llm）；禁止在服务层直接 new httpx/requests。
