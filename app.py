from flask import Flask, render_template, request, redirect, url_for, flash
import requests
from crontab import CronTab
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = 'secret_key_here'  # Потрібен для флеш-повідомлень

PHONE_NUMBER = "+380689053869"
BASE_URL = "http://localhost:8080"
JSON_FILE = 'scheduled_messages.json'

def get_signal_groups():
    try:
        response = requests.get(f"{BASE_URL}/v1/groups/{PHONE_NUMBER}")
        if response.status_code == 200:
            groups_data = response.json()
            groups = {group['id']: group['name'] for group in groups_data}
            return groups
        else:
            flash('Помилка під час отримання груп')
            return {}
    except requests.RequestException as e:
        print("Error fetching groups:", e)
        return {}

def save_message_to_json(group_id, message, scheduled_time):
    groups = get_signal_groups()
    group_name = groups.get(group_id, 'Unknown Group')
    try:
        with open(JSON_FILE, 'r') as file:
            data = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        data = []

    data.append({
        'group_name': group_name,
        'group_id': group_id,
        'message': message,
        'scheduled_time': scheduled_time
    })

    with open(JSON_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def get_scheduled_messages():
    try:
        with open(JSON_FILE, 'r') as file:
            data = json.load(file)

        # Видалення прострочених повідомлень
        now = datetime.now()
        valid_messages = [msg for msg in data if datetime.fromisoformat(msg['scheduled_time']) > now]

        # Зберігаємо тільки актуальні повідомлення
        with open(JSON_FILE, 'w') as file:
            json.dump(valid_messages, file, indent=4)

        return valid_messages
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def schedule_message(group_id, message, scheduled_time):
    cron = CronTab(user=True)
    scheduled_dt = datetime.fromisoformat(scheduled_time)

    # Оновлена команда для групових повідомлень
    job = cron.new(
        command=f"curl -X POST {BASE_URL}/v2/send -H 'Content-Type: application/json' -d '{{\"number\": \"{PHONE_NUMBER}\", \"recipients\": [\"{group_id}\"], \"message\": \"{message}\"}}'",
        comment=f"Signal message to {group_id}"
    )

    # Налаштування часу для cron: хвилина, година, день, місяць
    job.minute.on(scheduled_dt.minute)
    job.hour.on(scheduled_dt.hour)
    job.day.on(scheduled_dt.day)
    job.month.on(scheduled_dt.month)

    cron.write()
    save_message_to_json(group_id, message, scheduled_time)


def delete_scheduled_message(group_id, scheduled_time):
    cron = CronTab(user=True)
    # Видаляємо cron завдання
    for job in cron:
        if job.comment == f"Signal message to {group_id}" and job.scheduled_at().isoformat() == scheduled_time:
            cron.remove(job)
            cron.write()
            break

    # Видаляємо з JSON
    messages = get_scheduled_messages()
    messages = [msg for msg in messages if not (msg['group_id'] == group_id and msg['scheduled_time'] == scheduled_time)]

    with open(JSON_FILE, 'w') as file:
        json.dump(messages, file, indent=4)

@app.route('/delete/<group_id>/<scheduled_time>', methods=['POST'])
def delete_message(group_id, scheduled_time):
    delete_scheduled_message(group_id, scheduled_time)
    flash('Повідомлення видалено!')
    return redirect(url_for('index'))

@app.route('/', methods=['GET', 'POST'])
def index():
    groups = get_signal_groups()
    scheduled_messages = get_scheduled_messages()
    if request.method == 'POST':
        group_name = request.form.get('group')
        message = request.form.get('message')
        scheduled_time = request.form.get('datetime')
        group_id = next((id for id, name in groups.items() if name == group_name), None)

        if not group_id or not message or not scheduled_time:
            flash('Заповніть всі поля!')
            return redirect(url_for('index'))

        schedule_message(group_id, message, scheduled_time)
        flash('Повідомлення заплановано!')
        return redirect(url_for('index'))
    
    return render_template('index.html', groups=groups.values(), scheduled_messages=scheduled_messages)

if __name__ == "__main__":
    app.run(debug=True)
