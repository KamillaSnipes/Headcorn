from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import json
import os
import requests as http_requests
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "headcorn-tracker-2026")

DATA_FILE = os.environ.get("DATA_FILE", "decisions.json")

CONTEXT_HUB_URL = os.environ.get("CONTEXT_HUB_URL", "https://tg-headboss-production.up.railway.app")
CONTEXT_HUB_KEY = os.environ.get("CONTEXT_HUB_KEY", "")

STATUS_MAP = {
    "overdue": {"label": "Просрочено", "emoji": "🔴", "color": "#ef4444"},
    "active": {"label": "В работе", "emoji": "🟡", "color": "#eab308"},
    "done": {"label": "Выполнено", "emoji": "🟢", "color": "#22c55e"},
    "deferred": {"label": "Отложено", "emoji": "⏳", "color": "#94a3b8"},
    "no_deadline": {"label": "Без срока", "emoji": "🟠", "color": "#f97316"},
}

BLOCK_MAP = {
    "structure": "Люди и структура ОК",
    "sales": "Продажи и BD",
    "coo": "Роль COO и управление",
    "finance": "Финансы",
    "ops": "Операционка",
    "open": "Открытые вопросы",
}

DOMAIN_TO_BLOCK = {
    "hr": "structure", "operations": "ops", "sales": "sales",
    "management": "coo", "finance": "finance", "china": "ops",
    "logistics": "ops", "marketing": "sales", "general": "open",
}
BLOCK_TO_DOMAIN = {
    "structure": "hr", "sales": "sales", "coo": "management",
    "finance": "finance", "ops": "operations", "open": "general",
}

HUB_STATUS_TO_LOCAL = {
    "active": "active", "archived": "done", "superseded": "done",
}
LOCAL_STATUS_TO_HUB = {
    "active": "active", "overdue": "active", "done": "archived",
    "deferred": "active", "no_deadline": "active",
}


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"decisions": get_initial_decisions(), "history": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def hub_headers():
    return {"Authorization": f"Bearer {CONTEXT_HUB_KEY}", "Content-Type": "application/json"}


def hub_get(path, params=None):
    try:
        r = http_requests.get(f"{CONTEXT_HUB_URL}{path}", headers=hub_headers(), params=params, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[Context Hub GET {path}] Error: {e}")
        return None


def hub_post(path, payload):
    try:
        r = http_requests.post(f"{CONTEXT_HUB_URL}{path}", headers=hub_headers(), json=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[Context Hub POST {path}] Error: {e}")
        return None


def hub_decision_to_local(hub_dec):
    domain = hub_dec.get("domain", "general")
    block = DOMAIN_TO_BLOCK.get(domain, "open")
    hub_status = hub_dec.get("status", "active")
    local_status = HUB_STATUS_TO_LOCAL.get(hub_status, "active")

    deadline_raw = hub_dec.get("deadline")
    deadline = ""
    if deadline_raw:
        try:
            deadline = deadline_raw[:10]
        except Exception:
            pass

    return {
        "id": hub_dec.get("id", ""),
        "hub_id": hub_dec.get("id", ""),
        "block": block,
        "decision": hub_dec.get("title", ""),
        "responsible": hub_dec.get("responsible") or "",
        "deadline": deadline,
        "check_date": hub_dec.get("verification", {}).get("date", "") if isinstance(hub_dec.get("verification"), dict) else "",
        "status": local_status,
        "comment": hub_dec.get("content", ""),
        "date_created": (hub_dec.get("createdAt") or "")[:10],
        "source": "Context Hub",
        "tags": hub_dec.get("tags", []),
    }


def local_to_hub_text(dec):
    parts = [dec.get("decision", "")]
    if dec.get("responsible"):
        parts.append(f"Ответственный: {dec['responsible']}")
    if dec.get("deadline"):
        parts.append(f"Срок: {dec['deadline']}")
    if dec.get("comment"):
        parts.append(dec["comment"])
    return ". ".join(parts)


def sync_pull():
    """Pull decisions from Context Hub into local tracker."""
    if not CONTEXT_HUB_KEY:
        return 0, "API ключ не настроен"

    result = hub_get("/api/decisions", {"limit": 200})
    if not result:
        return 0, "Не удалось подключиться к Context Hub"

    hub_decisions = result if isinstance(result, list) else result.get("decisions", result.get("data", []))
    if not isinstance(hub_decisions, list):
        return 0, f"Неожиданный формат ответа"

    data = load_data()
    existing_hub_ids = {d.get("hub_id") for d in data["decisions"] if d.get("hub_id")}
    existing_titles = {d.get("decision", "").lower().strip() for d in data["decisions"]}

    added = 0
    for hub_dec in hub_decisions:
        hub_id = hub_dec.get("id", "")
        title = (hub_dec.get("title") or "").lower().strip()
        if hub_id in existing_hub_ids or title in existing_titles:
            continue
        local = hub_decision_to_local(hub_dec)
        block = local["block"]
        prefix = {"structure": "S", "sales": "P", "coo": "C", "finance": "F", "ops": "O", "open": "Q"}
        count = sum(1 for d in data["decisions"] if d["block"] == block) + 1
        local["id"] = f"{prefix.get(block, 'X')}-{count:02d}"
        data["decisions"].append(local)
        added += 1

    if added > 0:
        data["history"].append({
            "action": "sync_pull",
            "count": added,
            "timestamp": datetime.now().isoformat(),
        })
        save_data(data)

    return added, f"Загружено {added} новых решений из Context Hub"


def sync_push():
    """Push local decisions to Context Hub."""
    if not CONTEXT_HUB_KEY:
        return 0, "API ключ не настроен"

    data = load_data()
    pushed = 0
    for dec in data["decisions"]:
        if dec.get("hub_id") or dec.get("source") == "Context Hub":
            continue

        raw_text = local_to_hub_text(dec)
        extract_result = hub_post("/api/decisions/extract", {"text": raw_text})
        if not extract_result or "extracted" not in extract_result:
            continue

        extracted = extract_result["extracted"]
        extracted["responsible"] = dec.get("responsible") or extracted.get("responsible")
        extracted["deadline"] = dec.get("deadline") or extracted.get("deadline")
        extracted["domain"] = BLOCK_TO_DOMAIN.get(dec.get("block", "open"), "general")

        draft_result = hub_post("/api/decisions/draft", {
            "chatId": "cursor-tracker",
            "userId": "kamilla",
            "rawText": raw_text,
            "extracted": extracted,
            "missingFields": extract_result.get("missingFields", []),
        })
        if not draft_result or "draftId" not in draft_result:
            continue

        draft_id = draft_result["draftId"]
        confirm_result = hub_post(f"/api/decisions/draft/{draft_id}/confirm", {
            "userId": "kamilla",
            "userName": "Камилла",
        })
        if confirm_result and confirm_result.get("id"):
            dec["hub_id"] = confirm_result["id"]
            pushed += 1

    if pushed > 0:
        data["history"].append({
            "action": "sync_push",
            "count": pushed,
            "timestamp": datetime.now().isoformat(),
        })
        save_data(data)

    return pushed, f"Отправлено {pushed} решений в Context Hub"


def get_initial_decisions():
    return [
        {"id": "S-01", "block": "structure", "decision": "Структура МК-1/2/3 запущена", "responsible": "Рэшад → РГ", "deadline": "2026-03-24", "check_date": "2026-03-24", "status": "active", "comment": "1 мес адаптация", "date_created": "2026-02-24", "source": "Встреча 24.02"},
        {"id": "S-02", "block": "structure", "decision": "РГ: фильтрация проектов", "responsible": "Женя, Саша", "deadline": "", "check_date": "2026-03-03", "status": "active", "comment": "Есть ли отказы от нереальных?", "date_created": "2026-02-24", "source": "Встреча 24.02"},
        {"id": "S-03", "block": "structure", "decision": "РГ: стратегия в каждый проект", "responsible": "Женя, Саша", "deadline": "", "check_date": "2026-03-03", "status": "active", "comment": "Появились ли стратегии?", "date_created": "2026-02-24", "source": "Встреча 24.02"},
        {"id": "S-04", "block": "structure", "decision": "РГ: еженедельные 1-2-1 с МК", "responsible": "Женя, Саша", "deadline": "", "check_date": "2026-03-03", "status": "active", "comment": "Были ли 1-2-1 на первой неделе?", "date_created": "2026-02-24", "source": "Встреча 24.02"},
        {"id": "S-05", "block": "structure", "decision": "РГ: доведение проектов до результата", "responsible": "Женя, Саша", "deadline": "2026-03-24", "check_date": "2026-03-24", "status": "active", "comment": "Оценить в ревью", "date_created": "2026-02-24", "source": "Встреча 24.02"},
        {"id": "S-06", "block": "structure", "decision": "План Б: МП как ракеры", "responsible": "Рэшад", "deadline": "2026-03-24", "check_date": "2026-03-24", "status": "deferred", "comment": "Активируется если ОК не справится", "date_created": "2026-02-24", "source": "Встреча 24.02"},
        {"id": "S-07", "block": "structure", "decision": "Прощание с Катей", "responsible": "Камилла + собственники", "deadline": "2026-02-25", "check_date": "2026-02-25", "status": "overdue", "comment": "Сегодня", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "S-08", "block": "structure", "decision": "Артём — под наблюдением", "responsible": "Камилла", "deadline": "2026-03-24", "check_date": "2026-03-24", "status": "active", "comment": "Собирать факты для оценки", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "P-01", "block": "sales", "decision": "Костя (Диор) → BD-менеджер", "responsible": "Костя, Вика поддержка", "deadline": "", "check_date": "2026-03-31", "status": "active", "comment": "Нетворкинг, доля текущих клиентов", "date_created": "2026-02-25", "source": "Встреча 25.02"},
        {"id": "P-02", "block": "sales", "decision": "4 артефакта маркетинга для BD", "responsible": "Костя (маркетинг)", "deadline": "", "check_date": "", "status": "no_deadline", "comment": "Нужно зафиксировать дедлайн", "date_created": "2026-02-25", "source": "Встреча 25.02"},
        {"id": "P-03", "block": "sales", "decision": "Календарь мероприятий/выставок", "responsible": "Костя + Вика", "deadline": "", "check_date": "", "status": "no_deadline", "comment": "Нужно зафиксировать дедлайн", "date_created": "2026-02-25", "source": "Встреча 25.02"},
        {"id": "P-04", "block": "sales", "decision": "Фильтрация: бюджет до просчёта", "responsible": "РГ", "deadline": "", "check_date": "2026-03-03", "status": "active", "comment": "Были ли случаи отказа?", "date_created": "2026-02-25", "source": "Встреча 25.02"},
        {"id": "C-01", "block": "coo", "decision": "Два блока COO: тактика + контроль", "responsible": "Камилла", "deadline": "2026-03-31", "check_date": "2026-03-31", "status": "active", "comment": "Первый ревью с собственниками", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "C-02", "block": "coo", "decision": "Не строить параллельно с Рэшадом", "responsible": "Камилла + Рэшад", "deadline": "", "check_date": "", "status": "no_deadline", "comment": "Блокер: нет формата синхрона", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "C-03", "block": "coo", "decision": "Протокол эскалации", "responsible": "Камилла", "deadline": "", "check_date": "", "status": "active", "comment": "Фиксация → шанс → эскалация", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "C-04", "block": "coo", "decision": "Закрыть техдолг по внедрению", "responsible": "Камилла", "deadline": "2026-03-31", "check_date": "2026-03-31", "status": "active", "comment": "Калькулятор, мокапщик, документы", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "F-01", "block": "finance", "decision": "Табличка расходов РФ", "responsible": "Наташа + Настя", "deadline": "2026-03-06", "check_date": "2026-03-09", "status": "active", "comment": "7 блоков статей", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "F-02", "block": "finance", "decision": "Платёжный календарь (ручной)", "responsible": "Женя Якубин", "deadline": "", "check_date": "2026-03-03", "status": "active", "comment": "Костыль через ПФ", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "F-03", "block": "finance", "decision": "Синхрон расходов Тони (юани)", "responsible": "Камилла → Тони", "deadline": "", "check_date": "2026-03-10", "status": "deferred", "comment": "После завершения РФ", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "F-04", "block": "finance", "decision": "Синхрон расходов Дубай", "responsible": "Камилла → Никита", "deadline": "", "check_date": "", "status": "deferred", "comment": "После Тони", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "O-01", "block": "ops", "decision": "Паша: сроки по перевозчикам", "responsible": "Паша", "deadline": "", "check_date": "", "status": "overdue", "comment": "Пинг: предоставил или нет?", "date_created": "2026-02-16", "source": "Встреча 16.02"},
        {"id": "O-02", "block": "ops", "decision": "Замена фотосервиса для образцов", "responsible": "Не назначен", "deadline": "", "check_date": "", "status": "overdue", "comment": "Нужен ответственный", "date_created": "2026-02-16", "source": "Встреча 16.02"},
        {"id": "Q-01", "block": "open", "decision": "Формат синхронизации Камилла ↔ Рэшад", "responsible": "Камилла + Рэшад", "deadline": "", "check_date": "", "status": "overdue", "comment": "Блокирует C-02 и весь Блок 2", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "Q-02", "block": "open", "decision": "Инструмент трекинга решений", "responsible": "Камилла", "deadline": "", "check_date": "", "status": "overdue", "comment": "Без этого Блок 2 не работает", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "Q-03", "block": "open", "decision": "Порог эскалации стратегических заказов", "responsible": "Камилла + собственники", "deadline": "", "check_date": "", "status": "no_deadline", "comment": "От какой суммы? Какой регламент?", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "Q-04", "block": "open", "decision": "KPI Камиллы — доведение инициатив", "responsible": "Собственники", "deadline": "", "check_date": "", "status": "no_deadline", "comment": "Мотивация и измеримость роли", "date_created": "2026-02-18", "source": "Встреча 18.02"},
        {"id": "Q-05", "block": "open", "decision": "Подотчётность образцов РФ", "responsible": "Камилла + РГ", "deadline": "", "check_date": "", "status": "no_deadline", "comment": "Реализован проект или нет?", "date_created": "2026-02-18", "source": "Встреча 18.02"},
    ]


@app.route("/")
def index():
    data = load_data()
    decisions = data["decisions"]

    stats = {
        "total": len(decisions),
        "overdue": sum(1 for d in decisions if d["status"] == "overdue"),
        "active": sum(1 for d in decisions if d["status"] == "active"),
        "done": sum(1 for d in decisions if d["status"] == "done"),
        "no_deadline": sum(1 for d in decisions if d["status"] == "no_deadline"),
        "deferred": sum(1 for d in decisions if d["status"] == "deferred"),
    }

    filter_block = request.args.get("block", "all")
    filter_status = request.args.get("status", "all")

    filtered = decisions
    if filter_block != "all":
        filtered = [d for d in filtered if d["block"] == filter_block]
    if filter_status != "all":
        filtered = [d for d in filtered if d["status"] == filter_status]

    blocks = {}
    for d in filtered:
        b = d["block"]
        if b not in blocks:
            blocks[b] = []
        blocks[b].append(d)

    return render_template(
        "index.html",
        blocks=blocks,
        block_map=BLOCK_MAP,
        status_map=STATUS_MAP,
        stats=stats,
        filter_block=filter_block,
        filter_status=filter_status,
    )


@app.route("/add", methods=["GET", "POST"])
def add():
    if request.method == "POST":
        data = load_data()
        new_id = request.form.get("id", "").strip()
        if not new_id:
            block_prefix = {"structure": "S", "sales": "P", "coo": "C", "finance": "F", "ops": "O", "open": "Q"}
            b = request.form.get("block", "ops")
            existing = [d for d in data["decisions"] if d["block"] == b]
            new_id = f"{block_prefix.get(b, 'X')}-{len(existing)+1:02d}"

        new_decision = {
            "id": new_id,
            "block": request.form.get("block", "ops"),
            "decision": request.form.get("decision", ""),
            "responsible": request.form.get("responsible", ""),
            "deadline": request.form.get("deadline", ""),
            "check_date": request.form.get("check_date", ""),
            "status": request.form.get("status", "active"),
            "comment": request.form.get("comment", ""),
            "date_created": datetime.now().strftime("%Y-%m-%d"),
            "source": request.form.get("source", ""),
        }
        data["decisions"].append(new_decision)
        data["history"].append({
            "action": "add",
            "id": new_id,
            "timestamp": datetime.now().isoformat(),
        })
        save_data(data)
        return redirect(url_for("index"))

    return render_template(
        "add.html",
        block_map=BLOCK_MAP,
        status_map=STATUS_MAP,
    )


@app.route("/update/<decision_id>", methods=["POST"])
def update(decision_id):
    data = load_data()
    for d in data["decisions"]:
        if d["id"] == decision_id:
            old_status = d["status"]
            new_status = request.form.get("status", d["status"])
            d["status"] = new_status
            d["comment"] = request.form.get("comment", d["comment"])
            d["deadline"] = request.form.get("deadline", d["deadline"])
            d["responsible"] = request.form.get("responsible", d["responsible"])
            if old_status != new_status:
                data["history"].append({
                    "action": "status_change",
                    "id": decision_id,
                    "from": old_status,
                    "to": new_status,
                    "timestamp": datetime.now().isoformat(),
                })
            break
    save_data(data)
    return redirect(url_for("index"))


@app.route("/sync", methods=["GET", "POST"])
def sync():
    hub_ok = False
    hub_stats = None
    sync_result = None

    if CONTEXT_HUB_KEY:
        health = hub_get("/api/health")
        hub_ok = health and health.get("status") == "ok"
        if hub_ok:
            hub_stats = hub_get("/api/decisions/stats")

    if request.method == "POST":
        action = request.form.get("action")
        if action == "pull":
            count, msg = sync_pull()
            flash(msg, "success" if count > 0 else "info")
        elif action == "push":
            count, msg = sync_push()
            flash(msg, "success" if count > 0 else "info")
        elif action == "full":
            pull_count, pull_msg = sync_pull()
            push_count, push_msg = sync_push()
            flash(f"{pull_msg}. {push_msg}", "success")
        return redirect(url_for("sync"))

    data = load_data()
    local_count = len(data["decisions"])
    local_with_hub = sum(1 for d in data["decisions"] if d.get("hub_id"))
    local_only = local_count - local_with_hub
    last_sync = None
    for h in reversed(data.get("history", [])):
        if h.get("action", "").startswith("sync_"):
            last_sync = h
            break

    return render_template("sync.html",
        hub_ok=hub_ok,
        hub_url=CONTEXT_HUB_URL,
        hub_stats=hub_stats,
        local_count=local_count,
        local_with_hub=local_with_hub,
        local_only=local_only,
        last_sync=last_sync,
        has_key=bool(CONTEXT_HUB_KEY),
    )


@app.route("/api/decisions")
def api_decisions():
    data = load_data()
    return jsonify(data)


@app.route("/api/sync/pull", methods=["POST"])
def api_sync_pull():
    count, msg = sync_pull()
    return jsonify({"count": count, "message": msg})


@app.route("/api/sync/push", methods=["POST"])
def api_sync_push():
    count, msg = sync_push()
    return jsonify({"count": count, "message": msg})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
