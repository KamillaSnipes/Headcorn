from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os
from datetime import datetime, date

app = Flask(__name__)

DATA_FILE = os.environ.get("DATA_FILE", "decisions.json")

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


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"decisions": get_initial_decisions(), "history": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


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


@app.route("/api/decisions")
def api_decisions():
    data = load_data()
    return jsonify(data)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
