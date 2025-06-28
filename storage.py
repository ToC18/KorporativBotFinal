import json
import os

DATA_FILE = "polls.json"


def load_polls():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_poll(poll):
    """Добавляет опрос в файл"""
    polls = load_polls()
    polls.append(poll)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(polls, f, ensure_ascii=False, indent=4)


def update_last_poll_votes(votes):
    """Обновляет голоса последнего опроса"""
    polls = load_polls()
    if polls:
        polls[-1]["votes"] = votes
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(polls, f, ensure_ascii=False, indent=4)
