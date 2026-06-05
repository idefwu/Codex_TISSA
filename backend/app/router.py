from __future__ import annotations

import json
import re
from typing import Literal

from openai import OpenAIError
from pydantic import BaseModel, Field, ValidationError

from app.llm import get_openai_client


RouteName = Literal["general_chat", "db_query", "db_write", "rag", "image_skill"]

ROUTE_NAMES = ("general_chat", "db_query", "db_write", "rag", "image_skill")


class RouterDecision(BaseModel):
    route: RouteName
    confidence: float = Field(ge=0, le=1)
    reason: str
    required_capability: str
    suggested_followup_question: str | None = None


ROUTER_SYSTEM_PROMPT = """
你是 DB Agent Chat 的 Context Router。請根據使用者最新訊息，判斷任務路由。

只能輸出合法 JSON，不要 markdown，不要解釋 JSON 以外的文字。

可用 route：
1. general_chat：一般聊天、問候、情緒、非資料查詢。
2. db_query：查詢資料庫，例如員工、部門、費用、發票、廠商、資訊部名單。
3. db_write：新增、修改、刪除或寫入資料庫，例如新增費用、寫入發票。
4. rag：查公司 SOP、MIS 常見問題、VPN、帳號、設備、內部流程。
5. image_skill：圖片辨識，例如發票、收據、文件截圖、照片 OCR。

JSON schema：
{
  "route": "general_chat | db_query | db_write | rag | image_skill",
  "confidence": 0.0,
  "reason": "簡短原因",
  "required_capability": "llm | db_query | db_write | rag | image_skill",
  "suggested_followup_question": null
}
""".strip()


def router_decision_to_dict(decision: RouterDecision) -> dict:
    return decision.model_dump()


def extract_json_object(text: str) -> dict:
    stripped = text.strip()
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    if fenced_match:
        stripped = fenced_match.group(1)

    if not stripped.startswith("{"):
        object_match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if object_match:
            stripped = object_match.group(0)

    return json.loads(stripped)


def fallback_route(message: str, reason: str = "LLM router fallback") -> RouterDecision:
    text = message.lower()
    compact = message.replace(" ", "")

    image_terms = ("圖片", "照片", "截圖", "辨識", "ocr", "這張", "收據")
    write_terms = ("新增", "建立", "寫入", "修改", "更新", "刪除", "記一筆", "加一筆")
    db_terms = ("員工", "部門", "資訊部", "費用", "餐費", "發票", "廠商", "vendor", "invoice", "expense")
    rag_terms = ("vpn", "sop", "mis", "常見問題", "連不上", "網路", "印表機", "帳號", "密碼")

    if any(term in text or term in compact for term in image_terms) and any(
        term in text or term in compact for term in ("發票", "收據", "文件", "截圖", "圖片", "照片", "辨識")
    ):
        return RouterDecision(
            route="image_skill",
            confidence=0.78,
            reason=f"{reason}: 訊息提到圖片或文件辨識。",
            required_capability="image_skill",
        )

    if any(term in text or term in compact for term in write_terms) and any(
        term in text or term in compact for term in db_terms
    ):
        return RouterDecision(
            route="db_write",
            confidence=0.78,
            reason=f"{reason}: 訊息看起來要新增或修改資料庫資料。",
            required_capability="db_write",
        )

    if any(term in text or term in compact for term in rag_terms):
        return RouterDecision(
            route="rag",
            confidence=0.74,
            reason=f"{reason}: 訊息看起來是公司 SOP 或 MIS 常見問題。",
            required_capability="rag",
        )

    if any(term in text or term in compact for term in db_terms):
        return RouterDecision(
            route="db_query",
            confidence=0.74,
            reason=f"{reason}: 訊息看起來要查詢公司營運資料。",
            required_capability="db_query",
        )

    return RouterDecision(
        route="general_chat",
        confidence=0.62,
        reason=f"{reason}: 訊息看起來是一般聊天。",
        required_capability="llm",
    )


def classify_context_route(*, message: str, model: str) -> tuple[RouterDecision, bool]:
    try:
        client = get_openai_client()
        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": ROUTER_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": message,
                },
            ],
            temperature=0,
        )
        raw_text = (getattr(response, "output_text", "") or "").strip()
        parsed = extract_json_object(raw_text)
        decision = RouterDecision.model_validate(parsed)
        return decision, False
    except (OpenAIError, ValidationError, json.JSONDecodeError, ValueError, TypeError) as exc:
        return fallback_route(message, reason=f"Router fallback ({exc.__class__.__name__})"), True
