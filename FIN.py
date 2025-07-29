import sqlite3
import datetime
from collections import Counter
import csv
import matplotlib.pyplot as plt
import os

DB = "finbot.db"
current_user_id = None
assistant_personality = "friendly"
current_username = None

# ---------- DATABASE SETUP ----------
def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS finbot_users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            personality TEXT,
            monthly_budget REAL,
            daily_limit REAL
        )
    ''')
    # Add daily_limit column if missing (safe migration)
    try:
        c.execute("ALTER TABLE finbot_users ADD COLUMN daily_limit REAL")
    except sqlite3.OperationalError:
        pass

    c.execute('''
        CREATE TABLE IF NOT EXISTS finbot_transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            description TEXT,
            amount REAL,
            category TEXT,
            FOREIGN KEY(user_id) REFERENCES finbot_users(id)
        )
    ''')
    conn.commit()
    conn.close()

# ---------- PERSONALITIES ----------
PERSONALITIES = {
    "serious": {
        "budget_warn": "Caution: You are overspending. Please slow down.",
        "praise": "Good job staying disciplined with your finances.",
        "top_cat": "Your main expense category is: {cat}."
    },
    "friendly": {
        "budget_warn": "Careful! You're getting close to your budget limit. Let's slow down a bit 😊",
        "praise": "Nice work! You're handling your money like a pro! 🎉",
        "top_cat": "Heads up! You seem to be spending most on {cat} 😉"
    },
    "funny": {
        "budget_warn": "Bro... do you think money grows on trees? 🌳💸",
        "praise": "Dang! Are you secretly a billionaire? Keep it up! 🤑",
        "top_cat": "Bruh, your wallet is crying because of all that {cat} spending 🤣"
    }
}

# ---------- USER SYSTEM ----------
def register_user():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    username = input("Enter a username: ")
    while True:
        personality = input("Choose AI personality (serious/friendly/funny): ").strip().lower()
        if personality in PERSONALITIES:
            break
        else:
            print("Invalid choice. Try again.")
    while True:
        try:
            budget = float(input("Set your monthly budget (in ₹): "))
            break
        except:
            print("Enter a number.")

    while True:
        try:
            daily_limit = float(input("Set your daily spending limit (in ₹): "))
            break
        except:
            print("Enter a number.")

    try:
        c.execute(
            "INSERT INTO finbot_users(username, personality, monthly_budget, daily_limit) VALUES (?, ?, ?, ?)",
            (username, personality, budget, daily_limit)
        )
        conn.commit()
        print(f"User '{username}' registered.")
    except sqlite3.IntegrityError:
        print("Username already exists.")
        conn.close()
        return None
    conn.close()
    return username

def login_user(username):
    global current_user_id, assistant_personality, current_username
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT id, personality FROM finbot_users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    if user:
        current_user_id = user[0]
        assistant_personality = user[1]
        current_username = username
        personalized_greeting()
        return True
    else:
        print("User not found.")
        return False

def get_user_budget():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT monthly_budget FROM finbot_users WHERE id=?", (current_user_id,))
    val = c.fetchone()
    conn.close()
    return val[0] if val else 5000

def get_user_daily_limit():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT daily_limit FROM finbot_users WHERE id=?", (current_user_id,))
    val = c.fetchone()
    conn.close()
    return val[0] if val else None

def authenticate():
    global current_user_id
    while True:
        print("1. Register\n2. Login")
        choice = input("Choose: ")
        if choice == "1":
            username = register_user()
            if username:
                if login_user(username):
                    break
        elif choice == "2":
            username = input("Enter username: ")
            if login_user(username):
                break
        else:
            print("Invalid choice.")

# ---------- GREETING ----------
def personalized_greeting():
    hour = datetime.datetime.now().hour
    if hour < 12:
        tod = "Good Morning"
    elif hour < 18:
        tod = "Good Afternoon"
    else:
        tod = "Good Evening"

    if assistant_personality == "friendly":
        flair = "😊 Ready to manage those finances?"
    elif assistant_personality == "funny":
        flair = "🤣 Let's see if you're still rich!"
    else:
        flair = ". Let's focus on your financial health."

    print(f"\n{tod}, {current_username}! {flair}")

# ---------- CATEGORIZATION ----------
KEYWORDS = {
    "food": ["restaurant", "cafe", "burger", "pizza", "coffee"],
    "entertainment": ["movie", "netflix", "game", "concert"],
    "transport": ["uber", "taxi", "bus", "train", "fuel"],
    "shopping": ["amazon", "mall", "shopping"],
}

def categorize(description):
    desc = description.lower()
    for cat, words in KEYWORDS.items():
        if any(word in desc for word in words):
            return cat
    return "other"

# ---------- ADD TRANSACTION ----------
def add_transaction(desc, amount):
    if current_user_id is None:
        print("Please log in first.")
        return
    cat = categorize(desc)
    date = datetime.date.today().isoformat()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO finbot_transactions(user_id, date, description, amount, category) VALUES (?, ?, ?, ?, ?)",
        (current_user_id, date, desc, amount, cat),
    )
    conn.commit()
    conn.close()
    ai_assistant()

# ---------- FETCH DATA ----------
def fetch_all():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "SELECT date, description, amount, category FROM finbot_transactions WHERE user_id=? ORDER BY date DESC",
        (current_user_id,),
    )
    rows = c.fetchall()
    conn.close()
    return rows

# ---------- SUMMARY ----------
def show_summary():
    rows = fetch_all()
    if not rows:
        print("No transactions yet.")
        return
    today = datetime.date.today()
    month_rows = [r for r in rows if r[0][:7] == today.isoformat()[:7]]
    total_spent = sum(float(r[2]) for r in month_rows)
    monthly_budget = get_user_budget()
    remaining = monthly_budget - total_spent
    categories = Counter(r[3] for r in month_rows)

    print("\n--- Monthly Summary ---")
    print(f"Total spent this month: ₹{total_spent:.2f}")
    print(f"Remaining budget: ₹{remaining:.2f}")
    if categories:
        print("Top 3 categories:")
        for cat, _ in categories.most_common(3):
            amt = sum(float(r[2]) for r in month_rows if r[3] == cat)
            print(f"  {cat}: ₹{amt:.2f}")
    print("-----------------------")

# ---------- CSV EXPORT ----------
def export_to_csv():
    rows = fetch_all()
    if not rows:
        print("No transactions to export.")
        return
    filename = f"{current_username}_transactions.csv"
    with open(filename, "w", newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Date", "Description", "Amount", "Category"])
        writer.writerows(rows)
    print(f"Transactions exported to {filename}")

# ---------- PIE CHART ----------
def show_pie_chart():
    rows = fetch_all()
    if not rows:
        print("No data to show.")
        return
    today = datetime.date.today()
    month_rows = [r for r in rows if r[0][:7] == today.isoformat()[:7]]
    categories = Counter(r[3] for r in month_rows)
    if not categories:
        print("No spending this month to show chart.")
        return

    plt.figure(figsize=(5, 5))
    plt.pie(categories.values(), labels=categories.keys(), autopct='%1.1f%%')
    plt.title('Spending by Category')
    plt.show()

# ---------- AI SUGGESTION ----------
def smart_suggestion(top_cat):
    suggestions = {
        "food": "Try cooking at home a bit more to save money!",
        "entertainment": "Consider swapping a movie out for a walk outside.",
        "transport": "Maybe carpool or use public transport more often?",
        "shopping": "Do you really need that next item? 🛍",
        "other": "Review miscellaneous expenses – small leaks sink big ships."
    }
    return suggestions.get(top_cat, "Consider balancing your expenses.")

# ---------- STREAK LOGIC (IMPROVED) ----------
def get_streak():
    rows = fetch_all()
    today = datetime.date.today()
    daily_limit = get_user_daily_limit()
    if not daily_limit:
        daily_limit = get_user_budget() / 30

    # Sum all spending for each day
    day_totals = {}
    for r in rows:
        day_totals.setdefault(r[0], 0)
        day_totals[r[0]] += float(r[2])

    streak = 0
    current_day = today
    while current_day.isoformat() in day_totals and day_totals[current_day.isoformat()] <= daily_limit:
        streak += 1
        current_day -= datetime.timedelta(days=1)
    return streak

# ---------- AI ASSISTANT ----------
def ai_assistant():
    rows = fetch_all()
    if not rows:
        print("\n🤖 AI Assistant says:")
        print("Welcome! Start by adding your first transaction to see insights.")
        print("----\n")
        return

    today = datetime.date.today()
    month_rows = [r for r in rows if r[0][:7] == today.isoformat()[:7]]

    total_spent = sum(float(r[2]) for r in month_rows)
    categories = Counter(r[3] for r in month_rows)
    monthly_budget = get_user_budget()

    style = PERSONALITIES.get(assistant_personality, PERSONALITIES["friendly"])
    print("\n🤖 AI Assistant says:")

    percent = (total_spent / monthly_budget * 100) if monthly_budget else 0

    if percent < 50:
        if assistant_personality == "funny":
            print("LOL, you’re cruising with lots of budget left! 💸 Chill vibes only 😎")
        elif assistant_personality == "friendly":
            print("Awesome! You're well within your budget. Keep it going! 😊")
        elif assistant_personality == "serious":
            print("Good. Your spending is currently well under control.")
        print("----\n")
        return

    if percent < 80:
        if assistant_personality == "funny":
            print("Careful there! Don't turn into a broke meme just yet 😂")
        elif assistant_personality == "friendly":
            print("You're spending steadily, but still safe. Keep tracking! 😊")
        elif assistant_personality == "serious":
            print("Your expenses are moderate. Continue to be cautious.")
    elif percent < 100:
        if assistant_personality == "funny":
            print("Bro... do you think money grows on trees? 🌳💸")
        elif assistant_personality == "friendly":
            print("Careful! You're getting close to your budget limit. Let's slow down a bit 😊")
        elif assistant_personality == "serious":
            print("Caution: Your spending is nearing your budget limit.")
    else:
        if assistant_personality == "funny":
            print(f"Budget exploded! You're at {percent:.0f}% – broke speedrun unlocked 😂")
        elif assistant_personality == "friendly":
            print("You've crossed your budget 😅 Let's try to pause expenses for now.")
        elif assistant_personality == "serious":
            print("You have exceeded your budget. Immediate expense control is advised.")

    if categories:
        top_cat = categories.most_common(1)[0][0]
        print(style["top_cat"].format(cat=top_cat))
        print("Suggestion:", smart_suggestion(top_cat))

    streak = get_streak()
    if streak >= 7:
        print("🏆 Badge Unlocked: 7-day Spending Discipline!")
        print("AI Suggestion: You’ve earned a small reward – enjoy a treat within ₹100 guilt-free!")
    elif streak >= 3:
        print("⭐ Badge Unlocked: 3-day Controlled Spending Streak!")

    print("----\n")

# ---------- SETTINGS ----------
def change_personality():
    global assistant_personality
    print("Available personalities: serious / friendly / funny")
    while True:
        new_p = input("Enter new personality: ").strip().lower()
        if new_p in PERSONALITIES:
            conn = sqlite3.connect(DB)
            c = conn.cursor()
            c.execute("UPDATE finbot_users SET personality=? WHERE id=?", (new_p, current_user_id))
            conn.commit()
            conn.close()
            assistant_personality = new_p
            print(f"Personality changed to {new_p}.")
            break
        else:
            print("Invalid choice. Try again.")

def change_budget():
    while True:
        try:
            new_budget = float(input("Enter new monthly budget (₹): "))
            conn = sqlite3.connect(DB)
            c = conn.cursor()
            c.execute("UPDATE finbot_users SET monthly_budget=? WHERE id=?", (new_budget, current_user_id))
            conn.commit()
            conn.close()
            print(f"Monthly budget updated to ₹{new_budget}")
            break
        except:
            print("Invalid number. Try again.")

def change_daily_limit():
    while True:
        try:
            new_limit = float(input("Enter new daily spending limit (₹): "))
            conn = sqlite3.connect(DB)
            c = conn.cursor()
            c.execute("UPDATE finbot_users SET daily_limit=? WHERE id=?", (new_limit, current_user_id))
            conn.commit()
            conn.close()
            print(f"Daily limit updated to ₹{new_limit}")
            break
        except:
            print("Invalid number. Try again.")

def settings_menu():
    global current_user_id, assistant_personality
    while True:
        print("\nSettings:")
        print("1. Change AI personality")
        print("2. Change monthly budget")
        print("3. Change daily limit")
        print("4. Switch user")
        print("5. Back to main menu")
        choice = input("Choose: ")

        if choice == "1":
            change_personality()
        elif choice == "2":
            change_budget()
        elif choice == "3":
            change_daily_limit()
        elif choice == "4":
            authenticate()
            return
        elif choice == "5":
            return
        else:
            print("Invalid choice.")

# ---------- MAIN ----------
def main():
    init_db()
    authenticate()
    print("Welcome to FinBot – Smart Finance Tracker")
    while True:
        print("\nMenu:")
        print("1. Add transaction")
        print("2. View all")
        print("3. Summary")
        print("4. Show Pie Chart")
        print("5. Export to CSV")
        print("6. Settings")
        print("7. Exit")
        choice = input("Choose: ")
        if choice == "1":
            desc = input("Description: ")
            amount = float(input("Amount: "))
            add_transaction(desc, amount)
        elif choice == "2":
            for r in fetch_all():
                print(f"{r[0]} | {r[1]} | ₹{float(r[2])} | {r[3]}")
        elif choice == "3":
            show_summary()
        elif choice == "4":
            show_pie_chart()
        elif choice == "5":
            export_to_csv()
        elif choice == "6":
            settings_menu()
        elif choice == "7":
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()
