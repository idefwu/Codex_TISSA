from decimal import Decimal
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import desc, func, inspect, select
from sqlalchemy.exc import SQLAlchemyError

from app.db import check_database_connection, create_session, get_engine
from app.db_write_agent import DBWriteAgentError, DBWriteExecutionError, execute_confirmed_db_write, prepare_db_write_request
from app.llm import (
    LLMConfigurationError,
    LLMRequestError,
    check_llm_connection,
    clamp_temperature,
    generate_llm_reply,
    normalize_memory_rounds,
    normalize_model,
    normalize_system_prompt,
)
from app.models import ChatMessage, ChatRoom, Department, Employee, ExpenseReport, Invoice, Vendor
from app.router import ROUTE_NAMES, RouterDecision, classify_context_route, router_decision_to_dict
from app.sql_agent import SQLAgentError, run_sql_agent


def decimal_to_float(value):
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return float(value)
    return value


def serialize_chat_message(message):
    return {
        "id": message.id,
        "room_id": message.room_id,
        "role": message.role,
        "content": message.content,
        "metadata_json": message.metadata_json,
        "model": message.model,
        "created_at": message.created_at.isoformat(),
    }


def serialize_chat_room(room):
    return {
        "id": room.id,
        "title": room.title,
        "created_at": room.created_at.isoformat(),
        "updated_at": room.updated_at.isoformat(),
        "message_count": len(room.messages),
    }


def load_recent_chat_history(session, room_id: int, memory_rounds: int) -> list[dict]:
    rows = (
        session.query(ChatMessage)
        .filter(ChatMessage.room_id == room_id)
        .filter(ChatMessage.role.in_(("user", "assistant")))
        .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
        .limit(memory_rounds * 2)
        .all()
    )

    return [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in reversed(rows)
    ]


def load_recent_chat_history_before_message(session, room_id: int, memory_rounds: int, message: ChatMessage) -> list[dict]:
    rows = (
        session.query(ChatMessage)
        .filter(ChatMessage.room_id == room_id)
        .filter(ChatMessage.role.in_(("user", "assistant")))
        .filter(
            (ChatMessage.created_at < message.created_at)
            | ((ChatMessage.created_at == message.created_at) & (ChatMessage.id < message.id))
        )
        .order_by(desc(ChatMessage.created_at), desc(ChatMessage.id))
        .limit(memory_rounds * 2)
        .all()
    )

    return [
        {
            "role": row.role,
            "content": row.content,
        }
        for row in reversed(rows)
    ]


def required_capability_for_route(route: str) -> str:
    return {
        "general_chat": "llm",
        "db_query": "db_query",
        "db_write": "db_write",
        "rag": "rag",
        "image_skill": "image_skill",
    }.get(route, "llm")


def build_controls(payload: dict, model: str, temperature: float, system_prompt: str, memory_rounds: int) -> dict:
    tools = payload.get("tools", {}) if isinstance(payload.get("tools", {}), dict) else {}
    return {
        "model": model,
        "temperature": temperature,
        "system_prompt": system_prompt,
        "memory_rounds": memory_rounds,
        "auto_route": bool(payload.get("autoRoute", True)),
        "tools": tools,
    }


def get_route_disabled_message(route: str, tools: dict) -> str | None:
    if route == "db_query" and not tools.get("dbQuery"):
        return "DB Query 尚未啟用，請先在右側開啟。"
    if route == "db_write" and tools.get("dbWrite") is False:
        return "DB Write 尚未啟用，請先在右側開啟。"
    if route == "rag" and not tools.get("rag"):
        return "RAG 尚未啟用，請先在右側開啟。"
    if route == "image_skill" and not tools.get("imageSkill"):
        return "Image Skill 尚未啟用，請先在右側開啟。"
    return None


def execute_route_for_user_message(
    *,
    session,
    room: ChatRoom,
    user_message: ChatMessage,
    controls: dict,
    history: list[dict],
    router_decision: RouterDecision | None,
) -> ChatMessage:
    route = router_decision.route if router_decision else "general_chat"
    metadata = {
        "source": "openai" if route == "general_chat" else "route-placeholder",
        "controls": controls,
        "route": router_decision_to_dict(router_decision) if router_decision else None,
        "memory": {
            "rounds_requested": controls["memory_rounds"],
            "history_messages_sent": len(history),
        },
    }

    disabled_message = get_route_disabled_message(route, controls["tools"])
    if disabled_message:
        content = disabled_message
        metadata["source"] = "capability-disabled"
    elif route == "db_query":
        try:
            sql_agent_result = run_sql_agent(
                question=user_message.content,
                model=controls["model"],
                temperature=controls["temperature"],
            )
            content = sql_agent_result["answer"]
            metadata["source"] = "sql-agent"
            metadata["sql_agent"] = {
                "sql": sql_agent_result["sql"],
                "raw_sql": sql_agent_result["raw_sql"],
                "reason": sql_agent_result["reason"],
                "columns": sql_agent_result["columns"],
                "rows": sql_agent_result["rows"],
                "row_count": sql_agent_result["row_count"],
                "max_rows": sql_agent_result["max_rows"],
                "allowed_tables": sql_agent_result["allowed_tables"],
            }
        except SQLAgentError as exc:
            content = f"DB Query 無法完成：{exc}"
            metadata["source"] = "sql-agent-error"
            metadata["sql_agent"] = {
                "error": str(exc),
                "stage": exc.stage,
            }
    elif route == "db_write":
        try:
            db_write_result = prepare_db_write_request(
                session=session,
                message=user_message.content,
                model=controls["model"],
            )
            content = db_write_result["assistant_content"]
            metadata["source"] = db_write_result["source"]
            metadata["db_write"] = db_write_result["metadata"]
        except DBWriteAgentError as exc:
            content = f"DB Write 無法準備寫入：{exc}"
            metadata["source"] = "db-write-error"
            metadata["db_write"] = {
                "status": "error",
                "error": str(exc),
            }
    elif route != "general_chat":
        content = "此能力將在下一階段啟用。"
    else:
        llm_reply = generate_llm_reply(
            history=history,
            message=user_message.content,
            model=controls["model"],
            system_prompt=controls["system_prompt"],
            temperature=controls["temperature"],
        )
        content = llm_reply.content
        controls["model"] = llm_reply.model

    assistant_message = ChatMessage(
        room_id=room.id,
        role="assistant",
        content=content,
        metadata_json=metadata,
        model=controls["model"],
    )
    room.updated_at = datetime.utcnow()
    session.add(assistant_message)
    session.commit()
    session.refresh(room)
    session.refresh(assistant_message)
    return assistant_message


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": [
                    "http://localhost:5173",
                    "http://127.0.0.1:5173",
                ]
            }
        },
    )

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok", "service": "backend"})

    @app.get("/api/db/health")
    def db_health():
        result = check_database_connection()

        if result["ok"]:
            return jsonify(
                {
                    "status": "ok",
                    "database": {
                        "connected": True,
                        "version": result["version"],
                        "url": result["database_url"],
                    },
                }
            )

        return (
            jsonify(
                {
                    "status": "error",
                    "database": {
                        "connected": False,
                        "url": result["database_url"],
                    },
                    "message": result["message"],
                    "error": result["error"],
                }
            ),
            503,
        )

    @app.get("/api/llm/health")
    def llm_health():
        result = check_llm_connection()

        if result["ok"]:
            return jsonify(
                {
                    "status": "ok",
                    "llm": {
                        "configured": True,
                        "reachable": True,
                        "masked_key": result["masked_key"],
                        "sample_model": result.get("sample_model"),
                    },
                    "message": result["message"],
                }
            )

        status_code = 503 if result["status"] == "api_error" else 400
        return (
            jsonify(
                {
                    "status": "error",
                    "llm": {
                        "configured": bool(result.get("masked_key")),
                        "reachable": False,
                        "masked_key": result.get("masked_key", ""),
                    },
                    "message": result["message"],
                    "error": result.get("error", result["message"]),
                }
            ),
            status_code,
        )

    @app.get("/api/db/tables")
    def db_tables():
        try:
            inspector = inspect(get_engine())
            table_names = inspector.get_table_names()

            with get_engine().connect() as connection:
                tables = []
                for table_name in table_names:
                    columns = inspector.get_columns(table_name)
                    row_count = connection.exec_driver_sql(f"SELECT COUNT(*) FROM `{table_name}`").scalar_one()
                    tables.append(
                        {
                            "name": table_name,
                            "row_count": int(row_count),
                            "columns": [column["name"] for column in columns],
                        }
                    )

            return jsonify({"status": "ok", "tables": tables})
        except SQLAlchemyError as exc:
            return jsonify({"status": "error", "message": "Unable to inspect database tables.", "error": str(exc)}), 503

    @app.get("/api/db/summary")
    def db_summary():
        session = create_session()

        try:
            expense_total = session.scalar(select(func.coalesce(func.sum(ExpenseReport.amount), 0)))
            approved_expense_total = session.scalar(
                select(func.coalesce(func.sum(ExpenseReport.amount), 0)).where(ExpenseReport.status == "approved")
            )
            pending_expense_total = session.scalar(
                select(func.coalesce(func.sum(ExpenseReport.amount), 0)).where(ExpenseReport.status == "pending")
            )
            invoice_total = session.scalar(select(func.coalesce(func.sum(Invoice.total_amount), 0)))

            category_rows = session.execute(
                select(ExpenseReport.category, func.count(), func.coalesce(func.sum(ExpenseReport.amount), 0))
                .group_by(ExpenseReport.category)
                .order_by(ExpenseReport.category)
            ).all()

            status_rows = session.execute(
                select(ExpenseReport.status, func.count(), func.coalesce(func.sum(ExpenseReport.amount), 0))
                .group_by(ExpenseReport.status)
                .order_by(ExpenseReport.status)
            ).all()

            return jsonify(
                {
                    "status": "ok",
                    "summary": {
                        "department_count": session.scalar(select(func.count()).select_from(Department)),
                        "employee_count": session.scalar(select(func.count()).select_from(Employee)),
                        "vendor_count": session.scalar(select(func.count()).select_from(Vendor)),
                        "expense_count": session.scalar(select(func.count()).select_from(ExpenseReport)),
                        "invoice_count": session.scalar(select(func.count()).select_from(Invoice)),
                        "expense_total": decimal_to_float(expense_total),
                        "approved_expense_total": decimal_to_float(approved_expense_total),
                        "pending_expense_total": decimal_to_float(pending_expense_total),
                        "invoice_total": decimal_to_float(invoice_total),
                        "currency": "TWD",
                        "expenses_by_category": [
                            {"category": category, "count": count, "total": decimal_to_float(total)}
                            for category, count, total in category_rows
                        ],
                        "expenses_by_status": [
                            {"status": status, "count": count, "total": decimal_to_float(total)}
                            for status, count, total in status_rows
                        ],
                    },
                }
            )
        except SQLAlchemyError as exc:
            return jsonify({"status": "error", "message": "Unable to load database summary.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.get("/api/employees")
    def employees():
        session = create_session()

        try:
            rows = (
                session.query(Employee)
                .join(Employee.department)
                .order_by(Employee.employee_code)
                .all()
            )
            return jsonify(
                {
                    "status": "ok",
                    "employees": [
                        {
                            "id": employee.id,
                            "employee_code": employee.employee_code,
                            "name": employee.name,
                            "department_id": employee.department_id,
                            "department_name": employee.department.name,
                            "title": employee.title,
                            "email": employee.email,
                            "location": employee.location,
                            "hire_date": employee.hire_date.isoformat(),
                        }
                        for employee in rows
                    ],
                }
            )
        finally:
            session.close()

    @app.get("/api/expenses")
    def expenses():
        session = create_session()

        try:
            limit = min(int(request.args.get("limit", 100)), 500)
            rows = (
                session.query(ExpenseReport)
                .join(ExpenseReport.employee)
                .outerjoin(ExpenseReport.vendor)
                .order_by(ExpenseReport.expense_date.desc(), ExpenseReport.id.desc())
                .limit(limit)
                .all()
            )
            return jsonify(
                {
                    "status": "ok",
                    "expenses": [
                        {
                            "id": expense.id,
                            "employee_id": expense.employee_id,
                            "employee_name": expense.employee.name,
                            "employee_code": expense.employee.employee_code,
                            "vendor_id": expense.vendor_id,
                            "vendor_name": expense.vendor.name if expense.vendor else None,
                            "expense_date": expense.expense_date.isoformat(),
                            "category": expense.category,
                            "amount": decimal_to_float(expense.amount),
                            "currency": expense.currency,
                            "status": expense.status,
                            "description": expense.description,
                        }
                        for expense in rows
                    ],
                }
            )
        finally:
            session.close()

    @app.get("/api/invoices")
    def invoices():
        session = create_session()

        try:
            rows = (
                session.query(Invoice)
                .outerjoin(Invoice.vendor)
                .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
                .all()
            )
            return jsonify(
                {
                    "status": "ok",
                    "invoices": [
                        {
                            "id": invoice.id,
                            "vendor_id": invoice.vendor_id,
                            "vendor_name": invoice.vendor.name if invoice.vendor else None,
                            "invoice_number": invoice.invoice_number,
                            "invoice_date": invoice.invoice_date.isoformat(),
                            "buyer_tax_id": invoice.buyer_tax_id,
                            "seller_tax_id": invoice.seller_tax_id,
                            "total_amount": decimal_to_float(invoice.total_amount),
                            "raw_text": invoice.raw_text,
                            "source_image_path": invoice.source_image_path,
                            "created_at": invoice.created_at.isoformat(),
                        }
                        for invoice in rows
                    ],
                }
            )
        finally:
            session.close()

    @app.get("/api/chat/rooms")
    def chat_rooms():
        session = create_session()

        try:
            rooms = session.query(ChatRoom).order_by(ChatRoom.updated_at.desc(), ChatRoom.id.desc()).all()
            return jsonify({"status": "ok", "rooms": [serialize_chat_room(room) for room in rooms]})
        except SQLAlchemyError as exc:
            return jsonify({"status": "error", "message": "Unable to load chat rooms.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.post("/api/chat/rooms")
    def create_chat_room():
        payload = request.get_json(silent=True) or {}
        title = str(payload.get("title", "")).strip() or "新聊天室"
        session = create_session()

        try:
            room = ChatRoom(title=title)
            session.add(room)
            session.commit()
            session.refresh(room)
            return jsonify({"status": "ok", "room": serialize_chat_room(room)}), 201
        except SQLAlchemyError as exc:
            session.rollback()
            return jsonify({"status": "error", "message": "Unable to create chat room.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.patch("/api/chat/rooms/<int:room_id>")
    def update_chat_room(room_id):
        payload = request.get_json(silent=True) or {}
        title = str(payload.get("title", "")).strip()

        if not title:
            return jsonify({"status": "error", "message": "Title is required."}), 400

        session = create_session()

        try:
            room = session.get(ChatRoom, room_id)
            if room is None:
                return jsonify({"status": "error", "message": "Chat room not found."}), 404

            room.title = title
            room.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(room)
            return jsonify({"status": "ok", "room": serialize_chat_room(room)})
        except SQLAlchemyError as exc:
            session.rollback()
            return jsonify({"status": "error", "message": "Unable to update chat room.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.delete("/api/chat/rooms/<int:room_id>")
    def delete_chat_room(room_id):
        session = create_session()

        try:
            room = session.get(ChatRoom, room_id)
            if room is None:
                return jsonify({"status": "error", "message": "Chat room not found."}), 404

            session.delete(room)
            session.commit()
            return jsonify({"status": "ok", "deleted_id": room_id})
        except SQLAlchemyError as exc:
            session.rollback()
            return jsonify({"status": "error", "message": "Unable to delete chat room.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.get("/api/chat/rooms/<int:room_id>/messages")
    def chat_room_messages(room_id):
        session = create_session()

        try:
            room = session.get(ChatRoom, room_id)
            if room is None:
                return jsonify({"status": "error", "message": "Chat room not found."}), 404

            messages = (
                session.query(ChatMessage)
                .filter(ChatMessage.room_id == room_id)
                .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
                .all()
            )
            return jsonify(
                {
                    "status": "ok",
                    "room": serialize_chat_room(room),
                    "messages": [serialize_chat_message(message) for message in messages],
                }
            )
        except SQLAlchemyError as exc:
            return jsonify({"status": "error", "message": "Unable to load chat messages.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.post("/api/chat/rooms/<int:room_id>/messages")
    def create_chat_room_message(room_id):
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()
        model = normalize_model(payload.get("model"))
        temperature = clamp_temperature(payload.get("temperature"))
        system_prompt = normalize_system_prompt(payload.get("systemPrompt"))
        memory_rounds = normalize_memory_rounds(payload.get("memoryRounds"))
        context_router_enabled = bool((payload.get("tools") or {}).get("contextRouter"))

        if not message:
            return jsonify({"status": "error", "message": "Message is required."}), 400

        session = create_session()

        try:
            room = session.get(ChatRoom, room_id)
            if room is None:
                return jsonify({"status": "error", "message": "Chat room not found."}), 404

            controls = build_controls(payload, model, temperature, system_prompt, memory_rounds)
            history = load_recent_chat_history(session, room_id, memory_rounds)
            router_decision = None
            router_fallback = False

            if context_router_enabled:
                router_decision, router_fallback = classify_context_route(message=message, model=model)

            user_message = ChatMessage(
                room_id=room.id,
                role="user",
                content=message,
                metadata_json={
                    "source": "frontend",
                    "controls": controls,
                    "llm_status": "submitted",
                    "route": router_decision_to_dict(router_decision) if router_decision else None,
                    "route_fallback": router_fallback,
                    "memory": {
                        "rounds_requested": memory_rounds,
                        "history_messages_sent": len(history),
                    },
                },
                model=model,
            )

            room.updated_at = datetime.utcnow()
            session.add(user_message)
            session.commit()
            session.refresh(room)
            session.refresh(user_message)

            if context_router_enabled and not controls["auto_route"]:
                return (
                    jsonify(
                        {
                            "status": "needs_route_confirmation",
                            "room": serialize_chat_room(room),
                            "messages": [serialize_chat_message(user_message)],
                            "router_decision": router_decision_to_dict(router_decision),
                            "router_fallback": router_fallback,
                            "pending_user_message_id": user_message.id,
                        }
                    ),
                    202,
                )

            try:
                assistant_message = execute_route_for_user_message(
                    session=session,
                    room=room,
                    user_message=user_message,
                    controls=controls,
                    history=history,
                    router_decision=router_decision,
                )
            except LLMConfigurationError as exc:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "OpenAI API key is not configured.",
                            "error": str(exc),
                            "room": serialize_chat_room(room),
                            "messages": [serialize_chat_message(user_message)],
                        }
                    ),
                    400,
                )
            except LLMRequestError as exc:
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "OpenAI API request failed.",
                            "error": str(exc),
                            "room": serialize_chat_room(room),
                            "messages": [serialize_chat_message(user_message)],
                        }
                    ),
                    502,
                )

            return jsonify(
                {
                    "status": "ok",
                    "room": serialize_chat_room(room),
                    "router_decision": router_decision_to_dict(router_decision) if router_decision else None,
                    "router_fallback": router_fallback,
                    "messages": [
                        serialize_chat_message(user_message),
                        serialize_chat_message(assistant_message),
                    ],
                }
            ), 201
        except SQLAlchemyError as exc:
            session.rollback()
            return jsonify({"status": "error", "message": "Unable to save chat message.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.post("/api/chat/rooms/<int:room_id>/messages/<int:message_id>/execute")
    def execute_chat_room_message(room_id, message_id):
        payload = request.get_json(silent=True) or {}
        selected_route = str(payload.get("route", "")).strip()
        model = normalize_model(payload.get("model"))
        temperature = clamp_temperature(payload.get("temperature"))
        system_prompt = normalize_system_prompt(payload.get("systemPrompt"))
        memory_rounds = normalize_memory_rounds(payload.get("memoryRounds"))

        if selected_route not in ROUTE_NAMES:
            return jsonify({"status": "error", "message": "Invalid route selected."}), 400

        session = create_session()

        try:
            room = session.get(ChatRoom, room_id)
            if room is None:
                return jsonify({"status": "error", "message": "Chat room not found."}), 404

            user_message = session.get(ChatMessage, message_id)
            if user_message is None or user_message.room_id != room_id or user_message.role != "user":
                return jsonify({"status": "error", "message": "Pending user message not found."}), 404

            controls = build_controls(payload, model, temperature, system_prompt, memory_rounds)
            history = load_recent_chat_history_before_message(session, room_id, memory_rounds, user_message)
            router_decision = RouterDecision(
                route=selected_route,
                confidence=float(payload.get("confidence", 1)),
                reason=str(payload.get("reason", "Human selected route.")).strip() or "Human selected route.",
                required_capability=required_capability_for_route(selected_route),
                suggested_followup_question=payload.get("suggested_followup_question"),
            )

            try:
                assistant_message = execute_route_for_user_message(
                    session=session,
                    room=room,
                    user_message=user_message,
                    controls=controls,
                    history=history,
                    router_decision=router_decision,
                )
            except LLMConfigurationError as exc:
                return jsonify({"status": "error", "message": "OpenAI API key is not configured.", "error": str(exc)}), 400
            except LLMRequestError as exc:
                return jsonify({"status": "error", "message": "OpenAI API request failed.", "error": str(exc)}), 502

            return jsonify(
                {
                    "status": "ok",
                    "room": serialize_chat_room(room),
                    "router_decision": router_decision_to_dict(router_decision),
                    "router_fallback": False,
                    "messages": [serialize_chat_message(assistant_message)],
                }
            )
        except SQLAlchemyError as exc:
            session.rollback()
            return jsonify({"status": "error", "message": "Unable to execute selected route.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.post("/api/chat/rooms/<int:room_id>/messages/<int:message_id>/db-write/confirm")
    def confirm_db_write(room_id, message_id):
        session = create_session()

        try:
            room = session.get(ChatRoom, room_id)
            if room is None:
                return jsonify({"status": "error", "message": "Chat room not found."}), 404

            pending_message = session.get(ChatMessage, message_id)
            if pending_message is None or pending_message.room_id != room_id or pending_message.role != "assistant":
                return jsonify({"status": "error", "message": "Pending DB Write message not found."}), 404

            metadata = dict(pending_message.metadata_json or {})
            db_write = dict(metadata.get("db_write") or {})
            if db_write.get("status") != "pending_confirmation":
                return jsonify({"status": "error", "message": "This DB Write request is not pending confirmation."}), 400

            result = execute_confirmed_db_write(
                session=session,
                db_write=db_write,
                source_message_id=pending_message.id,
            )
            db_write["status"] = "confirmed"
            db_write["confirmed_at"] = datetime.utcnow().isoformat()
            db_write["result"] = result
            metadata["source"] = "db-write-confirmed"
            metadata["db_write"] = db_write
            pending_message.metadata_json = metadata

            assistant_message = ChatMessage(
                room_id=room.id,
                role="assistant",
                content=result["summary"],
                metadata_json={
                    "source": "db-write-result",
                    "related_message_id": pending_message.id,
                    "db_write": {
                        "status": "confirmed",
                        "tool": db_write.get("tool"),
                        "result": result,
                    },
                },
                model=pending_message.model,
            )
            room.updated_at = datetime.utcnow()
            session.add(assistant_message)
            session.commit()
            session.refresh(room)
            session.refresh(pending_message)
            session.refresh(assistant_message)

            return jsonify(
                {
                    "status": "ok",
                    "room": serialize_chat_room(room),
                    "updated_message": serialize_chat_message(pending_message),
                    "messages": [serialize_chat_message(assistant_message)],
                    "db_write_result": result,
                }
            )
        except DBWriteExecutionError as exc:
            session.rollback()
            return jsonify({"status": "error", "message": "Unable to complete DB Write.", "error": str(exc)}), 400
        except SQLAlchemyError as exc:
            session.rollback()
            return jsonify({"status": "error", "message": "Unable to confirm DB Write.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.post("/api/chat/rooms/<int:room_id>/messages/<int:message_id>/db-write/cancel")
    def cancel_db_write(room_id, message_id):
        session = create_session()

        try:
            room = session.get(ChatRoom, room_id)
            if room is None:
                return jsonify({"status": "error", "message": "Chat room not found."}), 404

            pending_message = session.get(ChatMessage, message_id)
            if pending_message is None or pending_message.room_id != room_id or pending_message.role != "assistant":
                return jsonify({"status": "error", "message": "Pending DB Write message not found."}), 404

            metadata = dict(pending_message.metadata_json or {})
            db_write = dict(metadata.get("db_write") or {})
            if db_write.get("status") != "pending_confirmation":
                return jsonify({"status": "error", "message": "This DB Write request is not pending confirmation."}), 400

            db_write["status"] = "cancelled"
            db_write["cancelled_at"] = datetime.utcnow().isoformat()
            metadata["source"] = "db-write-cancelled"
            metadata["db_write"] = db_write
            pending_message.metadata_json = metadata

            assistant_message = ChatMessage(
                room_id=room.id,
                role="assistant",
                content="已取消這次待確認寫入，沒有更動資料庫。",
                metadata_json={
                    "source": "db-write-cancelled",
                    "related_message_id": pending_message.id,
                    "db_write": {
                        "status": "cancelled",
                        "tool": db_write.get("tool"),
                    },
                },
                model=pending_message.model,
            )
            room.updated_at = datetime.utcnow()
            session.add(assistant_message)
            session.commit()
            session.refresh(room)
            session.refresh(pending_message)
            session.refresh(assistant_message)

            return jsonify(
                {
                    "status": "ok",
                    "room": serialize_chat_room(room),
                    "updated_message": serialize_chat_message(pending_message),
                    "messages": [serialize_chat_message(assistant_message)],
                }
            )
        except SQLAlchemyError as exc:
            session.rollback()
            return jsonify({"status": "error", "message": "Unable to cancel DB Write.", "error": str(exc)}), 503
        finally:
            session.close()

    @app.post("/api/chat")
    def chat():
        payload = request.get_json(silent=True) or {}
        message = str(payload.get("message", "")).strip()
        model = str(payload.get("model", "gpt-4o")).strip() or "gpt-4o"

        if not message:
            return jsonify({"status": "error", "message": "Message is required."}), 400

        return jsonify(
            {
                "status": "ok",
                "model": model,
                "reply": f"後端已收到你的訊息：{message}。下一階段會由 LLM 回覆。",
            }
        )

    return app
