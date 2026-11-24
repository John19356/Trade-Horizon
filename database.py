import json
import os


DATA_FOLDER = "data"
DATABASE_FILE = os.path.join(DATA_FOLDER, "database.json")


def ensure_database():
    os.makedirs(DATA_FOLDER, exist_ok=True)

    if not os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, "w", encoding="utf-8") as file:
            json.dump({}, file, indent=4)


def save_database(data):
    ensure_database()

    with open(DATABASE_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def load_database():
    ensure_database()

    try:
        with open(DATABASE_FILE, "r", encoding="utf-8") as file:
            content = file.read().strip()

            if not content:
                return {}

            data = json.loads(content)

            if not isinstance(data, dict):
                raise ValueError("Database must contain a JSON object.")

            changed = False

            for server_data in data.values():
                if isinstance(server_data, dict):
                    if "transactions" in server_data:
                        del server_data["transactions"]
                        changed = True

            if changed:
                save_database(data)

            return data

    except json.JSONDecodeError as error:
        raise ValueError(
            f"Your database.json contains invalid JSON: {error}"
        ) from error


def create_default_leaderboard_data():
    return {
        "active": False,
        "settings": {
            "display_limit": None,
            "leaderstat": "balance",
            "duration": None,
            "color": "#90EE90",
            "title": None,
            "subtitle": None,
            "description": None
        },
        "channel_id": None,
        "message_id": None,
        "ends_at": None,
        "participants": {},
        "history": []
    }


def create_default_server_data():
    return {
        "config": {
            "currency_name": "Coins",
            "currency_emoji": "🪙",
            "starting_balance": 100,
            "admin_role": None,
            "log_channel": None
        },
        "players": {},
        "leaderboard": create_default_leaderboard_data()
    }


def ensure_server_data(data, guild_id):
    guild_id = str(guild_id)
    defaults = create_default_server_data()

    if guild_id not in data:
        data[guild_id] = defaults

    server_data = data[guild_id]
    server_data.pop("transactions", None)

    if not isinstance(server_data.get("config"), dict):
        server_data["config"] = defaults["config"]

    if not isinstance(server_data.get("players"), dict):
        server_data["players"] = {}

    if not isinstance(server_data.get("leaderboard"), dict):
        server_data["leaderboard"] = defaults["leaderboard"]

    for key, value in defaults["config"].items():
        server_data["config"].setdefault(key, value)

    default_leaderboard = defaults["leaderboard"]
    leaderboard = server_data["leaderboard"]

    for key, value in default_leaderboard.items():
        leaderboard.setdefault(key, value)

    for key, value in default_leaderboard["settings"].items():
        leaderboard["settings"].setdefault(key, value)

    return server_data


def get_server_data(guild_id):
    data = load_database()
    server_data = ensure_server_data(data, guild_id)
    save_database(data)
    return server_data


def get_player_data(guild_id, user_id, username=None):
    data = load_database()

    guild_id = str(guild_id)
    user_id = str(user_id)

    server_data = ensure_server_data(data, guild_id)
    changed = False

    if user_id not in server_data["players"]:
        starting_balance = server_data["config"]["starting_balance"]
        server_data["players"][user_id] = {
            "balance": starting_balance,
            "username": username
        }
        changed = True
    else:
        server_data["players"][user_id].setdefault("username", None)
        if username and server_data["players"][user_id].get("username") != username:
            server_data["players"][user_id]["username"] = username
            changed = True

    if changed:
        save_database(data)

    return server_data["players"][user_id]


def set_player_username(guild_id, user_id, username):
    if not username:
        return

    data = load_database()

    guild_id = str(guild_id)
    user_id = str(user_id)

    server_data = ensure_server_data(data, guild_id)

    if user_id not in server_data["players"]:
        starting_balance = server_data["config"]["starting_balance"]
        server_data["players"][user_id] = {
            "balance": starting_balance,
            "username": username
        }
        save_database(data)
    elif server_data["players"][user_id].get("username") != username:
        server_data["players"][user_id]["username"] = username
        save_database(data)


def update_balance(guild_id, user_id, amount, username=None):
    data = load_database()

    guild_id = str(guild_id)
    user_id = str(user_id)

    server_data = ensure_server_data(data, guild_id)

    if user_id not in server_data["players"]:
        starting_balance = server_data["config"]["starting_balance"]
        server_data["players"][user_id] = {
            "balance": starting_balance,
            "username": username
        }
    else:
        server_data["players"][user_id].setdefault("username", None)
        if username and server_data["players"][user_id].get("username") != username:
            server_data["players"][user_id]["username"] = username

    server_data["players"][user_id]["balance"] += amount

    save_database(data)

    return server_data["players"][user_id]["balance"]


def get_leaderboard_data(guild_id):
    server_data = get_server_data(guild_id)
    return server_data["leaderboard"]


def update_leaderboard_data(guild_id, key, value):
    data = load_database()
    server_data = ensure_server_data(data, guild_id)
    server_data["leaderboard"][key] = value
    save_database(data)
    return server_data["leaderboard"]