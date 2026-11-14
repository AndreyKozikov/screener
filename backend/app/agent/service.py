"""Оркестратор ИИ-агента: маршрутизация запроса, исполнение инструментов,
финализация ответа и хранение истории сессии.
"""

import json
import logging
from datetime import date
from time import perf_counter
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from uuid import uuid4

from app.agent.dto import (
    AgentChatRequest,
    AgentChatResponse,
    AgentSource,
    AgentTurn,
)
from app.agent.llm_client import AgentLlmClient
from app.agent.contracts import validate_router_decision, validate_tool_args
from app.agent.prompts import (
    ROUTER_JSON_REPAIR_HINT,
    SKILL_SELECTION_JSON_REPAIR_HINT,
    build_finalizer_prompt,
    build_finalizer_system_prompt,
    build_router_user_prompt,
    build_skill_selection_system_prompt,
    build_system_prompt,
)
from app.agent.skill_loader import (
    AgentSkill,
    discover_skills,
    load_skill_instructions,
    skill_metadata,
    validate_skill_selection,
)
from app.agent.session import AgentSessionStore, new_session_id
from app.agent.chat_repository import repository as chat_repository
from app.agent.session_logger import get_session_logger
from app.agent.tools import TOOL_HANDLERS, ToolOutput

logger = logging.getLogger(__name__)


class AgentService:
    """Сервис диалога с ИИ-агентом.

    Поток обработки одного сообщения:
    1. Восстановление/создание сессии по session_id.
    2. Выбор относящихся к запросу скилов из локального каталога (если он не пуст).
    3. LLM-роутер: intent=ask (уточняющий вопрос) | tool (вызов инструмента)
       | answer (прямой ответ).
    4. Для tool — исполнение обёртки над существующим сервисом, усечение данных,
       LLM-финализатор пишет итоговый ответ в Markdown.
    5. Ответ и обновление истории сессии.
    """

    def __init__(self) -> None:
        self._sessions = AgentSessionStore(max_turns=1000)
        self._llm = AgentLlmClient()
        self._llm.set_listener(self._on_llm_event)
        self._finalizer_system_prompt = build_finalizer_system_prompt()

    def _log(self, session_id: str, event: dict) -> None:
        get_session_logger().write_event(session_id, event)

    def _on_llm_event(self, event: dict) -> None:
        session_id = str(event.get("session_id") or "")
        if session_id:
            get_session_logger().write_event(
                session_id,
                {"type": event.get("type") or "llm", **event},
            )

    async def chat(self, request: AgentChatRequest, user_id: str) -> AgentChatResponse:
        session_id = request.session_id or new_session_id()
        is_new = chat_repository.get_chat(user_id, session_id) is None
        if not chat_repository.ensure_chat(user_id, session_id):
            raise ValueError("Чат не найден")
        saved = chat_repository.get_chat(user_id, session_id)
        if saved and not self._sessions.get_history(session_id):
            stored_turns = saved["messages"]
            history = ([AgentTurn(role=m["role"], content=m["content"], intent=m.get("intent"))
                       for m in stored_turns] if stored_turns else request.history)
            request = request.model_copy(update={"session_id": session_id, "history": history})
            for turn in history:
                self._sessions.append_turn(session_id, {"role": turn.role, "content": turn.content, "intent": turn.intent})
            try:
                self._sessions.set_state(session_id, "pending_large", json.loads(saved.get("state_json") or "{}").get("pending_large"))
            except (ValueError, TypeError):
                pass
        else:
            request = request.model_copy(update={"session_id": session_id})
        response = await self._chat(request)
        history = self._sessions.get_history(session_id, limit=10000)
        pending = self._sessions.get_state(session_id, "pending_large")
        chat_repository.save_snapshot(user_id, session_id, history, {"pending_large": pending})
        if is_new:
            title = request.query.strip().replace("\n", " ")[:60]
            try:
                generated = await self._llm.generate_text(
                    "Ты создаёшь короткие темы диалогов на русском. Верни только тему длиной до 8 слов, без кавычек и точки.",
                    f"Первый запрос пользователя: {json.dumps(request.query, ensure_ascii=False)}",
                    session_id=session_id,
                )
                if generated and generated.strip():
                    title = generated.strip().strip('"')[:80]
            except Exception:
                pass
            chat_repository.set_title(user_id, session_id, title or "Новый чат")
        return response

    async def _chat(self, request: AgentChatRequest) -> AgentChatResponse:
        session_id = request.session_id or new_session_id()
        self._sessions.get_or_create(session_id)
        if not self._sessions.get_state(session_id, "meta_written"):
            self._sessions.set_state(session_id, "meta_written", True)
            get_session_logger().write_meta(
                session_id,
                {
                    "session_id": session_id,
                    "first_query": request.query[:500],
                    "with_portfolio": bool(request.portfolio),
                },
            )
        self._seed_history(session_id, request)

        history = self._sessions.get_history(session_id)
        conversation = self._render_conversation(history)
        portfolio_summary = self._render_portfolio(request.portfolio)
        today = date.today().isoformat()
        user_prompt = build_router_user_prompt(
            request.query, conversation, portfolio_summary, today=today
        )

        self._sessions.append_turn(session_id, {"role": "user", "content": request.query})

        self._log(
            session_id,
            {
                "type": "user_query",
                "query": request.query,
                "today": today,
                "portfolio_summary": portfolio_summary,
                "router_prompt": user_prompt,
            },
        )

        if self._is_refine_decline(request.query) and self._sessions.get_state(
            session_id, "pending_large"
        ):
            return await self._handle_refine_decline(session_id, request.query)

        active_skills = await self._load_active_skills(user_prompt, session_id)
        system_prompt = build_system_prompt(active_skills)

        try:
            routed = await self._llm.generate_json(
                system_prompt,
                user_prompt,
                session_id=session_id,
                repair_hint=ROUTER_JSON_REPAIR_HINT,
            )
        except Exception as exc:
            logger.error("[AGENT] Ошибка вызова LLM-роутера: %s", exc, exc_info=True)
            self._log(session_id, {"type": "error", "stage": "router", "message": str(exc)})
            return self._error_response(
                session_id, "Не удалось связаться с языковой моделью. Попробуйте позже."
            )

        if routed is None:
            self._log(session_id, {"type": "router_none", "detail": "JSON не распознан"})
            return self._error_response(
                session_id, "Не удалось распознать запрос. Попробуйте переформулировать."
            )

        try:
            routed = validate_router_decision(routed)
        except (ValueError, TypeError) as exc:
            self._log(session_id, {"type": "router_invalid", "message": str(exc)})
            return self._error_response(session_id, "Ответ модели не прошёл проверку контракта.")
        intent = routed["intent"]
        self._log(
            session_id,
            {"type": "router_decision", "intent": intent, "routed": routed},
        )

        if intent == "ask":
            return await self._handle_ask(session_id, routed)

        if intent == "tool":
            return await self._handle_tool(session_id, routed, request.query)

        if intent == "answer":
            return await self._handle_answer(session_id, routed)

        logger.warning("[AGENT] Неизвестный intent от LLM: %s", routed)
        return self._error_response(
            session_id, "Агент не распознал запрос. Попробуйте ещё раз."
        )

    async def _handle_ask(
        self, session_id: str, routed: Dict[str, Any]
    ) -> AgentChatResponse:
        question = str(routed.get("question") or "").strip()
        if not question:
            question = "Уточните, пожалуйста, условия подбора облигаций."
        missing = routed.get("missing_filters") or []
        self._log(
            session_id,
            {
                "type": "needs_info",
                "question": question,
                "missing_filters": missing,
            },
        )
        self._sessions.append_turn(
            session_id, {"role": "assistant", "content": question, "intent": "ask"}
        )
        return AgentChatResponse(
            session_id=session_id,
            state="needs_info",
            question=question,
        )

    async def _load_active_skills(
        self, user_prompt: str, session_id: str
    ) -> List[tuple[str, str]]:
        """Select relevant skills and load their instructions on demand.

        With no valid skill manifests, this returns immediately and the existing
        router prompt and call flow remain unchanged. If skill selection fails
        or returns no applicable skills, no skill instructions are loaded.
        """
        available: List[AgentSkill] = discover_skills()
        if not available:
            return []

        names = tuple(skill.name for skill in available)
        selection: Optional[Dict[str, Any]] = None
        try:
            selection = await self._llm.generate_json(
                build_skill_selection_system_prompt(skill_metadata(available)),
                user_prompt,
                session_id=session_id,
                repair_hint=SKILL_SELECTION_JSON_REPAIR_HINT,
                validator=lambda payload: validate_skill_selection(payload, names),
                stage="skill_selector_raw",
            )
        except Exception as exc:
            logger.error("[AGENT] Ошибка выбора скилов: %s", exc, exc_info=True)
            self._log(
                session_id,
                {"type": "skill_selection_error", "message": str(exc)},
            )

        if selection is None:
            selected: List[AgentSkill] = []
            selection_status = "invalid_or_failed"
        else:
            selected_names = set(selection["skills"])
            selected = [skill for skill in available if skill.name in selected_names]
            selection_status = "selected" if selected else "no_match"

        loaded: List[tuple[str, str]] = []
        for skill in selected:
            try:
                loaded.append((skill.name, load_skill_instructions(skill)))
            except (OSError, UnicodeError, ValueError) as exc:
                logger.warning("[AGENT] Не удалось загрузить скил %s: %s", skill.name, exc)
                self._log(
                    session_id,
                    {
                        "type": "skill_load_error",
                        "skill": skill.name,
                        "message": str(exc),
                    },
                )

        self._log(
            session_id,
            {
                "type": "skill_selection",
                "available": list(names),
                "selected": [name for name, _ in loaded],
                "status": selection_status,
            },
        )
        return loaded

    async def _handle_tool(
        self, session_id: str, routed: Dict[str, Any], query: str
    ) -> AgentChatResponse:
        tool = str(routed.get("tool") or "").strip()
        try:
            args = validate_tool_args(tool, routed["args"])
        except (KeyError, ValueError, TypeError) as exc:
            self._log(session_id, {"type": "tool_args_invalid", "tool": tool, "message": str(exc)})
            return self._error_response(session_id, "Параметры запроса не прошли проверку. Поиск не выполнялся.")

        handler = TOOL_HANDLERS.get(tool)
        if handler is None:
            self._log(session_id, {"type": "tool_unknown", "tool": tool})
            return self._error_response(
                session_id, f"Инструмент «{tool}» недоступен. Уточните запрос."
            )

        call_id = uuid4().hex
        started = perf_counter()
        self._log(
            session_id,
            {"type": "tool_call", "call_id": call_id, "tool": tool, "args": args},
        )
        self._sessions.clear_state(session_id, "pending_large")
        try:
            output: ToolOutput = await handler(args)
        except Exception as exc:
            logger.error("[AGENT] Ошибка инструмента %s: %s", tool, exc, exc_info=True)
            self._log(session_id, {
                "type": "tool_error",
                "call_id": call_id,
                "tool": tool,
                "message": str(exc),
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            })
            return self._error_response(
                session_id, "Ошибка при обращении к данным. Попробуйте позже."
            )

        if output.is_error:
            question = output.question or "Уточните, пожалуйста, условия запроса."
            self._log(
                session_id,
                {
                    "type": "tool_error_result",
                    "call_id": call_id,
                    "tool": tool,
                    "error": output.error,
                    "question": question,
                    "summary": output.summary,
                    "data": output.data,
                    "filters": output.filters,
                    "sources": [source.model_dump() for source in output.sources],
                    "duration_ms": round((perf_counter() - started) * 1000, 2),
                },
            )
            self._sessions.append_turn(
                session_id, {"role": "assistant", "content": question, "intent": "ask"}
            )
            return AgentChatResponse(
                session_id=session_id,
                state="needs_info",
                question=question,
            )

        self._log(
            session_id,
            {
                "type": "tool_result",
                "call_id": call_id,
                "tool": tool,
                "summary": output.summary,
                "sources": [source.model_dump() for source in output.sources],
                "data": output.data,
                "filters": output.filters,
                "final_answer": output.final_answer,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )

        if output.final_answer:
            answer = self._append_market_link(output.final_answer, output.filters)
            self._log(
                session_id,
                {
                    "type": "final_answer",
                    "call_id": call_id,
                    "tool": tool,
                    "answer": answer,
                    "sources": [s.model_dump() for s in output.sources],
                },
            )
            self._sessions.append_turn(
                session_id, {"role": "assistant", "content": answer, "intent": "tool"}
            )
            return AgentChatResponse(
                session_id=session_id,
                state="done",
                answer=answer,
                sources=output.sources,
                filters=output.filters,
            )

        if output.data.get("too_many"):
            return await self._handle_too_many(session_id, output, query=query, tool=tool, args=args)

        answer = await self._finalize(query, output, session_id, tool=tool, args=args)
        if not answer:
            return self._error_response(
                session_id, "Не удалось сформулировать ответ по найденным данным."
            )
        answer = self._append_market_link(answer, output.filters)

        self._log(
            session_id,
            {
                "type": "final_answer",
                "call_id": call_id,
                "tool": tool,
                "answer": answer,
                "sources": [s.model_dump() for s in output.sources],
            },
        )
        self._sessions.append_turn(
            session_id, {"role": "assistant", "content": answer, "intent": "tool"}
        )
        return AgentChatResponse(
            session_id=session_id,
            state="done",
            answer=answer,
            sources=output.sources,
            filters=output.filters,
        )

    async def _handle_answer(
        self, session_id: str, routed: Dict[str, Any]
    ) -> AgentChatResponse:
        answer = str(routed.get("answer_markdown") or "").strip()
        if not answer:
            return self._error_response(
                session_id, "Агент не смог сформулировать ответ. Попробуйте ещё раз."
            )
        sources: List[AgentSource] = []
        self._log(
            session_id,
            {
                "type": "final_answer",
                "tool": "direct",
                "answer": answer,
                "sources": [s.model_dump() for s in sources],
            },
        )
        self._sessions.append_turn(
            session_id, {"role": "assistant", "content": answer, "intent": "answer"}
        )
        return AgentChatResponse(
            session_id=session_id,
            state="done",
            answer=answer,
            sources=sources,
        )

    async def _handle_too_many(
        self, session_id: str, output: ToolOutput, *, query: str, tool: str, args: Dict[str, Any]
    ) -> AgentChatResponse:
        """Большой список бумаг: предлагает пользователю сузить условия поиска."""
        self._sessions.set_state(
            session_id,
            "pending_large",
            {
                "data": output.data,
                "sources": [s.model_dump() for s in output.sources],
                "summary": output.summary,
                "filters": output.filters,
                "query": query,
                "tool": tool,
                "args": args,
            },
        )
        total = output.data.get("total_found", 0)
        question = (
            f"По вашему запросу найдено {total} подходящих облигаций — это довольно "
            "большой список. Хотите сузить круг поиска? Могу учесть дополнительные "
            "условия: рейтинг, срок до погашения, тип бумаг (ОФЗ / корпоративные / "
            "флоатеры), минимальную доходность, отсутствие амортизации или "
            "встроенных опционов, или конкретного эмитента. "
            "Для просмотра первых 15 бумаг напишите «покажи список»; "
            "полную выборку можно открыть в таблице рынка по ссылке."
        )
        question = self._append_market_link(question, output.filters)
        self._log(
            session_id,
            {"type": "refine_offer", "total_found": total, "question": question},
        )
        self._sessions.append_turn(
            session_id, {"role": "assistant", "content": question, "intent": "ask"}
        )
        return AgentChatResponse(
            session_id=session_id,
            state="needs_info",
            question=question,
        )

    async def _handle_refine_decline(
        self, session_id: str, query: str
    ) -> AgentChatResponse:
        """Пользователь отказался уточнять: выдаём ответ по сохранённому результату."""
        pending = self._sessions.get_state(session_id, "pending_large")
        self._sessions.clear_state(session_id, "pending_large")
        if not isinstance(pending, dict):
            return self._error_response(
                session_id, "Контекст уточнения устарел. Задайте запрос заново."
            )
        output = ToolOutput(
            data=pending.get("data") or {},
            sources=[AgentSource(**s) for s in (pending.get("sources") or [])],
            summary=pending.get("summary") or "",
            filters=pending.get("filters"),
        )
        answer = await self._finalize(
            pending.get("query") or query, output, session_id,
            tool=pending.get("tool") or "search_bonds", args=pending.get("args") or output.filters or {},
        )
        if not answer:
            return self._error_response(
                session_id, "Не удалось сформулировать ответ по найденным данным."
            )
        answer = self._append_market_link(answer, output.filters)
        self._log(
            session_id,
            {
                "type": "final_answer",
                "tool": "search_bonds",
                "refine_declined": True,
                "answer": answer,
                "filters": output.filters,
                "sources": [s.model_dump() for s in output.sources],
            },
        )
        self._sessions.append_turn(
            session_id, {"role": "assistant", "content": answer, "intent": "tool"}
        )
        return AgentChatResponse(
            session_id=session_id,
            state="done",
            answer=answer,
            sources=output.sources,
            filters=output.filters,
        )

    @staticmethod
    def _append_market_link(answer: str, filters: Optional[Dict[str, Any]]) -> str:
        """Добавляет в конец ответа ссылку на таблицу рынка облигаций.

        Ссылка строится детерминированно из реально применённых фильтров —
        модель её не генерирует, чтобы исключить выдуманные параметры.
        Формат URL согласован с фронтендом: /?view=bonds&<query>.
        """
        if not answer or not filters:
            return answer
        query = urlencode(filters, doseq=True)
        return f"{answer}\n\n[Открыть список в таблице рынка →](/?view=bonds&{query})"

    @staticmethod
    def _is_refine_decline(query: str) -> bool:
        """Детектирует отказ пользователя сужать список («покажи все»)."""
        text = " ".join(query.strip().lower().strip(".!? ").split())
        patterns = (
            "покажи все", "покажи всё", "покажи список", "показывай все",
            "показывай всё", "показывай", "не надо", "не нужно", "не буду",
            "не хочу", "не уточняй", "не уточнять", "оставь как есть", "оставь",
            "хватит", "список устраивает", "и так ок", "без уточнений",
            "давай без уточнений",
        )
        return text in patterns

    async def _finalize(
        self, query: str, output: ToolOutput, session_id: str, *, tool: str, args: Dict[str, Any]
    ) -> str:
        """Второй LLM-вызов: по компактным данным инструмента пишет финальный ответ.

        Ошибки финализатора фиксируются в логе сессии (finalizer_error) для
        отладки агента и возвращаются пустой строкой — caller отдаёт пользователю
        ошибку. Никаких запасных форматов ответа не используется.
        """
        data_json = json.dumps(output.data, ensure_ascii=False, default=str)
        context = {
            "tool": tool,
            "args": output.filters if output.filters is not None else args,
            "task": [
                turn["content"] for turn in self._sessions.get_history(session_id)
                if turn.get("role") == "user"
            ],
            "retrieved_on": output.data.get("retrieved_on") or date.today().isoformat(),
        }
        user_prompt = build_finalizer_prompt(query, data_json, context=context)
        try:
            answer = await self._llm.generate_text(
                self._finalizer_system_prompt, user_prompt, session_id=session_id
            )
        except Exception as exc:
            logger.error("[AGENT] Ошибка финализатора: %s", exc, exc_info=True)
            self._log(
                session_id,
                {"type": "finalizer_error", "message": str(exc)},
            )
            return ""
        if not answer:
            self._log(session_id, {"type": "finalizer_empty"})
            return ""
        return answer

    def _seed_history(self, session_id: str, request: AgentChatRequest) -> None:
        """Переносит переданную историю в новую сессию (не дублируя)."""
        if not request.history:
            return
        if len(self._sessions.get_history(session_id)) > 0:
            return
        for turn in request.history:
            if turn.role not in ("user", "assistant"):
                continue
            self._sessions.append_turn(
                session_id,
                {
                    "role": turn.role,
                    "content": turn.content,
                    "intent": turn.intent,
                },
            )

    def _render_conversation(self, history: List[dict]) -> str:
        lines: List[str] = []
        for turn in history:
            role = turn.get("role")
            content = str(turn.get("content") or "").strip()
            if not content:
                continue
            prefix = "Пользователь" if role == "user" else "Ассистент"
            lines.append(f"{prefix}: {content}")
        return "\n".join(lines)

    def _render_portfolio(self, portfolio: List[Dict[str, Any]]) -> str:
        if not portfolio:
            return ""
        lines: List[str] = []
        for item in portfolio[:10]:
            secid = str(item.get("SECID") or item.get("secid") or "")
            name = str(item.get("SHORTNAME") or item.get("shortname") or "")
            qty = item.get("quantity")
            if qty is not None:
                lines.append(f"- {secid} ({name}): количество {qty}")
            else:
                lines.append(f"- {secid} ({name})")
        return "\n".join(lines)

    def _error_response(self, session_id: str, message: str) -> AgentChatResponse:
        self._log(session_id, {"type": "error", "stage": "response", "message": message})
        return AgentChatResponse(
            session_id=session_id,
            state="error",
            answer=message,
        )


_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """Возвращает singleton AgentService (создаётся лениво при первом запросе)."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
