from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os


app = Flask(__name__)

app.secret_key = "expenseflow-college-project-secret-key"

DATABASE = os.path.join(app.root_path, "database.db")


# --------------------------------------------------
# DATABASE CONNECTION
# --------------------------------------------------

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


# --------------------------------------------------
# INITIALIZE DATABASE
# --------------------------------------------------

def init_db():

    connection = get_db()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense')),
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            transaction_date TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    connection.commit()
    connection.close()


# --------------------------------------------------
# LOGIN REQUIRED DECORATOR
# --------------------------------------------------

def login_required(function):

    @wraps(function)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please login to continue.",
                "error"
            )

            return redirect(url_for("login"))

        return function(*args, **kwargs)

    return decorated_function


# --------------------------------------------------
# GET CURRENT USER
# --------------------------------------------------

def get_current_user():

    if "user_id" not in session:
        return None

    connection = get_db()

    user = connection.execute(
        """
        SELECT id, name, email, created_at
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    connection.close()

    return user


# --------------------------------------------------
# HOME / ROOT
# --------------------------------------------------

@app.route("/")
def index():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# --------------------------------------------------
# REGISTER
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        name = request.form.get(
            "name",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # Required fields
        if not name or not email or not password:

            flash(
                "Please fill in all required fields.",
                "error"
            )

            return render_template("register.html")

        # Name validation
        if len(name) < 2:

            flash(
                "Name must contain at least 2 characters.",
                "error"
            )

            return render_template("register.html")

        # Email validation
        if "@" not in email or "." not in email:

            flash(
                "Please enter a valid email address.",
                "error"
            )

            return render_template("register.html")

        # Password validation
        if len(password) < 6:

            flash(
                "Password must contain at least 6 characters.",
                "error"
            )

            return render_template("register.html")

        # Confirm password
        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return render_template("register.html")

        connection = get_db()

        # Check existing user
        existing_user = connection.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        if existing_user:

            connection.close()

            flash(
                "An account with this email already exists.",
                "error"
            )

            return render_template("register.html")

        # Hash password
        hashed_password = generate_password_hash(password)

        created_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        connection.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                email,
                hashed_password,
                created_at
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Account created successfully. Please login.",
            "success"
        )

        return redirect(url_for("login"))

    return render_template("register.html")


# --------------------------------------------------
# LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        if not email or not password:

            flash(
                "Please enter your email and password.",
                "error"
            )

            return render_template("login.html")

        connection = get_db()

        user = connection.execute(
            """
            SELECT *
            FROM users
            WHERE email = ?
            """,
            (email,)
        ).fetchone()

        connection.close()

        if user and check_password_hash(
            user["password"],
            password
        ):

            session.clear()

            session["user_id"] = user["id"]

            flash(
                "Welcome back!",
                "success"
            )

            return redirect(url_for("dashboard"))

        flash(
            "Invalid email or password.",
            "error"
        )

        return render_template("login.html")

    return render_template("login.html")


# --------------------------------------------------
# LOGOUT
# --------------------------------------------------

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(url_for("login"))


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():

    user = get_current_user()

    connection = get_db()

    # Total income
    income_result = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        AS total_income
        FROM transactions
        WHERE user_id = ?
        AND type = 'income'
        """,
        (session["user_id"],)
    ).fetchone()

    total_income = income_result["total_income"]

    # Total expenses
    expense_result = connection.execute(
        """
        SELECT COALESCE(SUM(amount), 0)
        AS total_expenses
        FROM transactions
        WHERE user_id = ?
        AND type = 'expense'
        """,
        (session["user_id"],)
    ).fetchone()

    total_expenses = expense_result["total_expenses"]

    # Balance
    balance = total_income - total_expenses

    # Recent transactions
    recent_transactions = connection.execute(
        """
        SELECT *
        FROM transactions
        WHERE user_id = ?
        ORDER BY transaction_date DESC, id DESC
        LIMIT 5
        """,
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template(
        "dashboard.html",
        user=user,
        total_income=total_income,
        total_expenses=total_expenses,
        balance=balance,
        recent_transactions=recent_transactions
    )


# --------------------------------------------------
# ADD TRANSACTION
# --------------------------------------------------

@app.route(
    "/add-transaction",
    methods=["GET", "POST"]
)
@login_required
def add_transaction():

    if request.method == "POST":

        transaction_type = request.form.get(
            "type",
            ""
        ).strip().lower()

        title = request.form.get(
            "title",
            ""
        ).strip()

        amount_text = request.form.get(
            "amount",
            ""
        ).strip()

        category = request.form.get(
            "category",
            ""
        ).strip()

        transaction_date = request.form.get(
            "transaction_date",
            ""
        ).strip()

        description = request.form.get(
            "description",
            ""
        ).strip()

        # Validate type
        if transaction_type not in [
            "income",
            "expense"
        ]:

            flash(
                "Please select a valid transaction type.",
                "error"
            )

            return redirect(
                url_for("add_transaction")
            )

        # Validate title
        if not title:

            flash(
                "Please enter a transaction title.",
                "error"
            )

            return redirect(
                url_for("add_transaction")
            )

        # Validate amount
        if not amount_text:

            flash(
                "Please enter an amount.",
                "error"
            )

            return redirect(
                url_for("add_transaction")
            )

        try:

            amount = float(amount_text)

        except ValueError:

            flash(
                "Please enter a valid amount.",
                "error"
            )

            return redirect(
                url_for("add_transaction")
            )

        if amount <= 0:

            flash(
                "Amount must be greater than zero.",
                "error"
            )

            return redirect(
                url_for("add_transaction")
            )

        # Validate category
        if not category:

            flash(
                "Please select a category.",
                "error"
            )

            return redirect(
                url_for("add_transaction")
            )

        # Validate date
        if not transaction_date:

            flash(
                "Please select a date.",
                "error"
            )

            return redirect(
                url_for("add_transaction")
            )

        created_at = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        connection = get_db()

        connection.execute(
            """
            INSERT INTO transactions
            (
                user_id,
                type,
                title,
                amount,
                category,
                transaction_date,
                description,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"],
                transaction_type,
                title,
                amount,
                category,
                transaction_date,
                description,
                created_at
            )
        )

        connection.commit()
        connection.close()

        flash(
            "Transaction added successfully.",
            "success"
        )

        return redirect(
            url_for("dashboard")
        )

    return render_template(
        "add_transaction.html"
    )


# --------------------------------------------------
# TRANSACTION HISTORY
# --------------------------------------------------

@app.route("/history")
@login_required
def history():

    search = request.args.get(
        "search",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    ).strip()

    transaction_type = request.args.get(
        "type",
        ""
    ).strip().lower()

    connection = get_db()

    query = """
        SELECT *
        FROM transactions
        WHERE user_id = ?
    """

    parameters = [
        session["user_id"]
    ]

    # Search
    if search:

        query += """
            AND (
                title LIKE ?
                OR description LIKE ?
                OR category LIKE ?
            )
        """

        search_value = f"%{search}%"

        parameters.extend([
            search_value,
            search_value,
            search_value
        ])

    # Category filter
    if category:

        query += """
            AND category = ?
        """

        parameters.append(category)

    # Type filter
    if transaction_type in [
        "income",
        "expense"
    ]:

        query += """
            AND type = ?
        """

        parameters.append(transaction_type)

    query += """
        ORDER BY transaction_date DESC, id DESC
    """

    transactions = connection.execute(
        query,
        parameters
    ).fetchall()

    connection.close()

    return render_template(
        "history.html",
        transactions=transactions
    )


# --------------------------------------------------
# DELETE TRANSACTION
# --------------------------------------------------

@app.route(
    "/delete-transaction/<int:transaction_id>",
    methods=["POST"]
)
@login_required
def delete_transaction(transaction_id):

    connection = get_db()

    transaction = connection.execute(
        """
        SELECT id
        FROM transactions
        WHERE id = ?
        AND user_id = ?
        """,
        (
            transaction_id,
            session["user_id"]
        )
    ).fetchone()

    if not transaction:

        connection.close()

        flash(
            "Transaction not found.",
            "error"
        )

        return redirect(
            url_for("history")
        )

    connection.execute(
        """
        DELETE FROM transactions
        WHERE id = ?
        AND user_id = ?
        """,
        (
            transaction_id,
            session["user_id"]
        )
    )

    connection.commit()
    connection.close()

    flash(
        "Transaction deleted successfully.",
        "success"
    )

    return redirect(
        url_for("history")
    )


# --------------------------------------------------
# PROFILE
# --------------------------------------------------

@app.route("/profile")
@login_required
def profile():

    user = get_current_user()

    return render_template(
        "profile.html",
        user=user
    )


# --------------------------------------------------
# ERROR HANDLERS
# --------------------------------------------------

@app.errorhandler(404)
def page_not_found(error):

    return """
        <h1>404</h1>
        <p>Page not found.</p>
    """, 404


@app.errorhandler(500)
def internal_server_error(error):

    return """
        <h1>500</h1>
        <p>Something went wrong on the server.</p>
    """, 500


# --------------------------------------------------
# START APPLICATION
# --------------------------------------------------

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True,
        host="127.0.0.1",
        port=5000
    )