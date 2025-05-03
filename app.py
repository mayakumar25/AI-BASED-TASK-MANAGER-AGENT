from flask import Flask, render_template, request, redirect
from datetime import datetime
import sqlite3
import os
import spacy
from dateparser.search import search_dates
import re

app = Flask(__name__)
nlp = spacy.load("en_core_web_sm")

DB_FILE = "tasks.db"

def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task TEXT,
                        datetime TEXT,
                        category TEXT
                    )''')
        conn.commit()
        conn.close()
    else:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("PRAGMA table_info(tasks)")
        columns = [column[1] for column in c.fetchall()]
        if 'category' not in columns:
            c.execute("ALTER TABLE tasks ADD COLUMN category TEXT")
            conn.commit()
        conn.close()

def normalize_task(task):
    task = re.sub(r'\b(upcoming|next)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)', r'\2', task, flags=re.IGNORECASE)
    
    # Make sure standalone weekdays are capitalized
    weekdays = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
    for day in weekdays:
        task = re.sub(rf'\b{day}\b', day.capitalize(), task, flags=re.IGNORECASE)
    return task

def parse_datetime(task):
    task = normalize_task(task)
    results = search_dates(
        task,
        settings={
            'PREFER_DATES_FROM': 'future',
            'RELATIVE_BASE': datetime.now(),  # Uses current date as reference
            'RETURN_AS_TIMEZONE_AWARE': False
        }
    )
    if results:
        parsed_date = results[0][1]
        if parsed_date.time() == datetime.min.time():
            parsed_date = parsed_date.replace(hour=9, minute=0)
        return parsed_date
    return None

def categorize_task(task):
    work_keywords = ['meeting', 'report', 'boss', 'deadline', 'work']
    personal_keywords = ['dinner', 'grocery', 'shopping', 'errand', 'home']
    reminder_keywords = ['call', 'reminder', 'pick up', 'buy']
    social_keywords = ['meet', 'friends', 'party', 'event', 'concert']

    if any(keyword in task.lower() for keyword in work_keywords):
        return 'Work'
    elif any(keyword in task.lower() for keyword in personal_keywords):
        return 'Personal'
    elif any(keyword in task.lower() for keyword in reminder_keywords):
        return 'Reminder'
    elif any(keyword in task.lower() for keyword in social_keywords):
        return 'Social'
    else:
        return 'Uncategorized'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        task_input = request.form['task']
        task_datetime = parse_datetime(task_input)
        category = categorize_task(task_input)

        if task_datetime:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO tasks (task, datetime, category) VALUES (?, ?, ?)",
                      (task_input, task_datetime.strftime('%Y-%m-%d %H:%M:%S'), category))
            conn.commit()
            conn.close()
        else:
            print("❌ Could not parse date from input:", task_input)
        return redirect('/')

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, task, datetime, category FROM tasks ORDER BY datetime ASC")
    tasks = c.fetchall()
    conn.close()

    tasks_formatted = [
        (id_, i + 1, task, datetime.strptime(dt, "%Y-%m-%d %H:%M:%S").strftime('%A %I:%M %p %d-%m-%Y'), category)
        for i, (id_, task, dt, category) in enumerate(tasks)
    ]

    return render_template('index.html', tasks=tasks_formatted)

@app.route('/delete/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return redirect('/')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
