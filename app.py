from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from auxiliary import login_required, apology, currency

# Configure application
app = Flask(__name__)

# Ensure templates are auto reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# custom filter
app.jinja_env.filters["currency"] = currency

# Configure session to use filesystem
app.config["SESSION_PERMENANT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure SQL database
db = SQL("sqlite:///project.db")

# Create table for in database
# for user
db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, username TEXT NOT NULL, hash TEXT NOT NULL)")

# for account
db.execute("CREATE TABLE IF NOT EXISTS account (id INTEGER PRIMARY KEY NOT NULL, user_id INTEGER NOT NULL, account_name TEXT NOT NULL, category TEXT NOT NULL, initial_amount NUMERIC NOT NULL, balance NUMERIC, FOREIGN KEY (user_id) REFERENCES users(id))")

# for borrower and lender
db.execute("CREATE TABLE IF NOT EXISTS person (id INTEGER PRIMARY KEY NOT NULL, user_id INTEGER, pic TEXT, person_name TEXT NOT NULL, amount NUMERIC DEFAULT 0.00, FOREIGN KEY (user_id) REFERENCES users(id))")

# for expense and income cashflow
db.execute("CREATE TABLE IF NOT EXISTS cashflow (id INTEGER PRIMARY KEY NOT NULL, user_id INTEGER NOT NULL, category TEXT NOT NULL, amount NUMERIC, timestamp INTEGER, FOREIGN KEY (user_id) REFERENCES users(id))")


@app.route("/", methods=["GET", "POST"])
def index():
    """ landing page """
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")
        passcheck = request.form.get("passcheck")

        if not username:
            return apology("must provide username")

        else:

            # need to fetch the queries result
            # https://stackoverflow.com/questions/67551898/missing-len-within-sqlite-query
            rows = db.execute("SELECT * FROM users WHERE username = ?", username)

            if len(rows) != 0:
                flash("Username is taken.")
                return apology("username is taken")

            else:
                if not password:
                    return apology("must provide password")

                elif not passcheck:
                    return apology("must confirm password")

                else:

                    if password != passcheck:
                        return apology("password does not match")

                    else:

                        hash = generate_password_hash(password)

                        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash)

        login = db.execute("SELECT * FROM users WHERE username = ?", username)

        session["user_id"] = login[0]["id"]

        flash("You were registered!")

        return redirect("/dashboard")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()

    if request.method == "POST":
        if not request.form.get("username"):
            return apology("must provide username")

        elif not request.form.get("password"):
            return apology("must provide password")

        rows = db.execute("SELECT * FROM users WHERE username= ?", request.form.get("username"))

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password")

        session["user_id"] = rows[0]["id"]

        flash("Logged In Successfully")

        return redirect("/dashboard")


@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()

    return redirect("/")


@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    """Allow user to change password"""
    if request.method == "POST":

        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        passcheck = request.form.get("passcheck")

        # check whether the user key in the old password
        if not old_password:
            return apology("please key in your old password")

        else:

            # check whether the old password is correct
            rows = db.execute("SELECT hash FROM users WHERE id = ?", session["user_id"])

            if not check_password_hash(rows[0]["hash"], old_password):
                return apology("invalid password")

            else:

                # check whether the user key in the new password and confirm it
                if not new_password:
                    return apology("please key in your new password")

                elif not passcheck:
                    return apology("must confirm password")

                else:

                    # confirm the password are matches
                    if new_password != passcheck:
                        return apology("password does not match")

                    else:

                        # hash the new password
                        hash = generate_password_hash(new_password)

                        # update the users table
                        db.execute("UPDATE users SET hash = ? WHERE id = ?", hash, session["user_id"])

                        # pop up message
                        flash("Password changed!")

                        session.clear()

                        return render_template("index.html")

    else:
        return render_template("change_password.html")


@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    """main page"""
    equity = db.execute("SELECT sum(initial_amount) AS total FROM account WHERE user_id = ?", session["user_id"])
    equity_amount = equity[0]["total"]
    if equity_amount == None:
        equity_amount = 0.00

    accounts = db.execute("SELECT category, sum(balance) AS balance FROM account WHERE user_id = ? GROUP BY category", session["user_id"])

    account_total = 0.00
    for account in accounts:
        account_total += float(account['balance'])

    cashflows = db.execute("SELECT category, sum(amount) AS amount FROM cashflow WHERE user_id = ? GROUP BY category", session["user_id"])

    income_amount = 0
    expenses_amount = 0

    for cashflow in cashflows:
        if cashflow["category"] == "Income":
            income_amount = float(cashflow["amount"])

        else:
            expenses_amount += abs(float(cashflow["amount"]))

    persons = db.execute("SELECT id, amount FROM person WHERE user_id = ?", session["user_id"])

    borrower_amount = 0
    lender_amount = 0

    for person in persons:
        # if it is positive, means I lend them money
        if person['amount'] > 0:
            borrower_amount += float(person['amount'])

        # if it is negative, means I own them money
        elif person['amount'] < 0:
            lender_amount += abs(float(person['amount']))

    debit_total = account_total + expenses_amount + borrower_amount

    credit_total = equity_amount + income_amount + lender_amount

    return render_template("dashboard.html", equity_amount=equity_amount, accounts=accounts, income_amount=income_amount, expenses_amount=expenses_amount, borrower_amount=borrower_amount, lender_amount=lender_amount, debit_total=debit_total, credit_total=credit_total)


@app.route("/account")
@login_required
def account():
    """show all account and its balance"""
    # define the category for account
    CATEGORY = [
        "Cash",
        "Bank",
        "eWallet",
        "Investment",
        "Other"
    ]

    # create a list of dictinaries that hold all the account details
    accounts = db.execute("SELECT * FROM account WHERE user_id = ?", session["user_id"])

    # loop through the list to get total balance of all account
    total = 0
    for account in accounts:
        if account["balance"] == None:
            account["balance"] = float(account["initial_amount"])
            total += float(account["balance"])

        else:
            total += float(account["balance"])

    return render_template("account.html", accounts=accounts, total=total, CATEGORY=CATEGORY)


@app.route("/add_account", methods=["GET","POST"])
@login_required
def add_account():
    """Add account of payment type"""
    # define the category for account
    CATEGORY = [
        "Cash",
        "Bank",
        "eWallet",
        "Investment",
        "Other"
    ]

    if request.method == "POST":

        initial_amount = request.form.get("initial_amount")
        account_name = request.form.get("account_name")
        category = request.form.get("category")

        # check whether the account name and amount is key in
        if not account_name:
            return apology("must provide account name")

        elif not initial_amount:
            return apology("please input a value")

        elif not category or category not in CATEGORY:
            return apology("invalid category")

        else:
            # check whether the account name is repectative
            rows = db.execute("SELECT account_name FROM account WHERE user_id = ?", session["user_id"])

            for row in rows:
                if account_name == row["account_name"]:
                    return apology("account already exist")

            # avoid user changing the input type in developer's tool
            try:
                initial_amount = float(initial_amount)

                # add the data into the database
                db.execute("INSERT INTO account (user_id, account_name, category, initial_amount, balance) VALUES (?, ?, ?, ?, ?)", session["user_id"], account_name, category, initial_amount, initial_amount)

                # inform user account added
                flash("Account added successfully!")

                return redirect("/account")

            except ValueError:
                return apology("invalid numeric number")


@app.route("/cashflow", methods=["GET", "POST"])
@login_required
def cashflow():
    """records of income and expenses"""
        # define category
    CATEGORY = [
        "Food & Beverage",
        "Entertainment",
        "Housing",
        "Medical",
        "Shopping",
        "Transportation",
        "Telecommunication",
        "Finance",
        "Miscellaneous",
        "Income"
    ]

    # extract account info
    accounts = db.execute("SELECT * FROM account WHERE user_id = ?", session["user_id"])
    ACCOUNT = []
    for account in accounts:
        name = account["account_name"]
        ACCOUNT.append(name)

    # if user apply filter for date
    if request.method == "POST":

        month = request.form.get("month")
        year = request.form.get("year")

        # https://www.programiz.com/python-programming/datetime/strftime
        if not year or not month:
            now = datetime.now()
            year = now.strftime('%Y')
            month = now.strftime('%m')

        # obtain information for expenses
        # https://stackoverflow.com/questions/33688263/sqlite-filter-records-by-month-year
        # https://stackoverflow.com/questions/650480/get-month-from-datetime-in-sqlite
        expenses = db.execute("SELECT category, sum(amount) AS total FROM cashflow WHERE user_id = ? AND strftime('%m', DATETIME(timestamp, 'unixepoch')) = ? AND strftime('%Y', DATETIME(timestamp, 'unixepoch')) = ? GROUP BY category", session["user_id"], month, year)

        # https://stackoverflow.com/questions/1235618/remove-dictionary-from-list
        for i in range(len(expenses)):
            if expenses[i]['category'] == "Income":
                del expenses[i]
                break

        expenses = expenses

        expenses_total = 0
        for expense in expenses:
            expense["total"] = -expense["total"]
            expenses_total += float(expense["total"])

        #obtain information for income
        incomes = db.execute("SELECT category, sum(amount) AS total FROM cashflow WHERE user_id = ? AND category = ? AND strftime('%m', DATETIME(timestamp, 'unixepoch')) = ? AND strftime('%Y', DATETIME(timestamp, 'unixepoch')) = ? GROUP BY category", session["user_id"], "Income", month, year)

        income_total = 0
        for income in incomes:
            income_total += income["total"]

        return render_template("cashflow.html", expenses=expenses, expenses_total=expenses_total,incomes=incomes, income_total=income_total)

    else:

        # obtain information for expenses
        expenses = db.execute("SELECT category, sum(amount) AS total FROM cashflow WHERE user_id = ? GROUP BY category", session["user_id"])

        # https://stackoverflow.com/questions/1235618/remove-dictionary-from-list
        for i in range(len(expenses)):
            if expenses[i]['category'] == "Income":
                del expenses[i]
                break

        expenses = expenses

        expenses_total = 0
        for expense in expenses:
            expense["total"] = -expense["total"]
            expenses_total += float(expense["total"])

        #obtain information for income
        incomes = db.execute("SELECT category, sum(amount) AS total FROM cashflow WHERE user_id = ? AND category = ? GROUP BY category", session["user_id"], "Income")

        income_total = 0
        for income in incomes:
            income_total += income["total"]

        return render_template("cashflow.html", expenses=expenses, expenses_total=expenses_total,incomes=incomes, income_total=income_total, CATEGORY=CATEGORY, ACCOUNT=ACCOUNT)


@app.route("/add_cashflow", methods=["GET", "POST"])
@login_required
def add_cashflow():
    """ add new income or expenses """
    # define category
    CATEGORY = [
        "Food & Beverage",
        "Entertainment",
        "Housing",
        "Medical",
        "Shopping",
        "Transportation",
        "Telecommunication",
        "Finance",
        "Miscellaneous",
        "Income"
    ]

    # extract account info
    accounts = db.execute("SELECT * FROM account WHERE user_id = ?", session["user_id"])
    ACCOUNT = []
    for account in accounts:
        name = account["account_name"]
        ACCOUNT.append(name)

    if request.method == "POST":

        category = request.form.get("category")
        account_name = request.form.get("account")
        amount = request.form.get("amount")

        # ensure user choose a category
        if not category or category not in CATEGORY:
            return apology("invalid category")

        # ensure the user choose an account
        elif not account_name or account_name not in ACCOUNT:
            return apology("invalid account")

        # ensure the user input an amount
        elif not amount:
            return apology("please input a value")

        else:

            # check the validity of amount
            try:
                amount = float(amount)

                # if the category is income
                if category == "Income":
                    amount = amount

                # if category are related to expenses
                else:
                    amount = -amount

                # update account balance
                for account in accounts:
                    if account_name == account["account_name"]:

                        balance = float(account["balance"]) + amount

                        db.execute("UPDATE account SET balance = ? WHERE user_id = ? AND id = ?", balance, session["user_id"], account["id"])

                # insert records into cashflow data
                db.execute("INSERT INTO cashflow (user_id, category, amount, timestamp) VALUES (?, ?, ?, strftime('%s', 'now'))", session["user_id"], category, amount)

                flash("Added Successfully")

                return redirect("/cashflow")

            except ValueError:
                return apology("invalid numeric number")


@app.route("/person", methods=["GET", "POST"])
@login_required
def person():
    """ records of borrowers and lenders """
    persons = db.execute("SELECT * FROM person WHERE user_id = ?", session["user_id"])

    accounts = db.execute("SELECT * FROM account WHERE user_id = ?", session["user_id"])
    ACCOUNT = []
    for account in accounts:
        name = account["account_name"]
        ACCOUNT.append(name)

    return render_template("person.html", persons=persons, ACCOUNT=ACCOUNT)


@app.route("/add_person", methods=["GET", "POST"])
@login_required
def add_person():
    """ add new person """
    if request.method == "POST":
        person_name = request.form.get("person_name")
        pic = request.form.get("pic")

        if not pic:
            return apology("please choose a picture")

        if not person_name:
            return apology("invalid input")

        else:

            # ensure the name us not duplicated
            rows = db.execute("SELECT person_name FROM person WHERE user_id = ?", session["user_id"])

            for row in rows:
                if person_name == row["person_name"]:
                    return apology("this person already exist")

            #add person into database
            db.execute("INSERT INTO person (user_id, pic, person_name) VALUES (?, ?, ?)", session["user_id"], pic, person_name)

            flash("Added Successfully")

            return redirect("/person")


@app.route("/add_new", methods=["GET", "POST"])
@login_required
def add_new():
    """ Add borrowers and lenders """
    # define category (without Income)
    CATEGORY = [
        "Food & Beverage",
        "Entertainment",
        "Housing",
        "Medical",
        "Shopping",
        "Transportation",
        "Telecommunication",
        "Finance",
        "Miscellaneous",
    ]

    accounts = db.execute("SELECT * FROM account WHERE user_id = ?", session["user_id"])
    ACCOUNT = []
    for account in accounts:
        name = account["account_name"]
        ACCOUNT.append(name)

    persons = db.execute("SELECT * FROM person WHERE user_id = ?", session["user_id"])

    if request.method == "POST":

        role = request.form.get("role")
        person = request.form.get("person")
        amount = request.form.get("amount")

        # ensure user choose a role
        if not role:
            return apology("please choose one option")

        elif not person:
            return apology("please choose a person")

        elif not amount:
            return apology("please input a value")

        else:

            # check the validity of amount
            try:
                amount = float(amount)

                # if user borrow from other
                if role == "borrower":
                    amount = -amount

                    # ensure user choose a category for expense
                    category = request.form.get("category")
                    if not category or category not in CATEGORY:
                        return apology("please choose a reason for borrowing from others")

                    # insert records into cashflow data
                    db.execute("INSERT INTO cashflow (user_id, category, amount, timestamp) VALUES (?, ?, ?, strftime('%s', 'now'))", session["user_id"], category, amount)

                # if user lend to other
                elif role == "lender":

                    # ensure user choose an account
                    account_name = request.form.get("account")
                    if not account_name or account_name not in ACCOUNT:
                        return apology("please choose the account used")

                    else:

                        # update account balance
                        for account in accounts:
                            if account_name == account["account_name"]:

                                balance = float(account["balance"]) + (-amount)

                                db.execute("UPDATE account SET balance = ? WHERE user_id = ? AND id = ?", balance, session["user_id"], account["id"])

                # update person
                balance = db.execute("SELECT amount FROM person WHERE user_id = ? AND id = ?", session["user_id"], person)
                balance = balance[0]["amount"]

                new_balance = balance + amount

                db.execute("UPDATE person SET amount = ? WHERE user_id = ? AND id = ?", new_balance, session["user_id"], person)

                flash("Added Successfully")

                return redirect("/person")

            except ValueError:
                return apology("invalid numeric number")

    else:
        return render_template("add_new.html", CATEGORY=CATEGORY, ACCOUNT=ACCOUNT, persons=persons)


@app.route("/settle", methods=["GET", "POST"])
@login_required
def settle():
    """ settlement for borrowers and lenders """
    accounts = db.execute("SELECT * FROM account WHERE user_id = ?", session["user_id"])
    ACCOUNT = []
    for account in accounts:
        name = account["account_name"]
        ACCOUNT.append(name)

    if request.method == "POST":

        person_id = request.form.get("id")
        account_name = request.form.get("account")
        amount = request.form.get("amount")

        if not person_id:
            return apology("invalid input")

        # ensure user choose an account
        elif not account_name or account_name not in ACCOUNT:
            return apology("please choose an account")

        elif not amount:
            return apology("please input a value")

        else:

            # check the validity of amount
            try:
                amount = float(amount)

                persons = db.execute("SELECT amount FROM person WHERE user_id = ? AND id = ?", session["user_id"], person_id)
                person_balance = persons[0]["amount"]

                # if amount is negative, means I borrow from others and I pay them
                if person_balance < 0:
                    amount = amount

                # if amount is positive, means I lend to others and I paid by them
                elif person_balance > 0:
                    amount = -amount

                new_balance = person_balance + amount

                # update person
                db.execute("UPDATE person SET amount = ? WHERE user_id = ? AND id = ?", new_balance, session["user_id"], person_id)

                # update account balance
                for account in accounts:
                    if account_name == account["account_name"]:

                        balance = float(account["balance"]) + (-amount)

                        db.execute("UPDATE account SET balance = ? WHERE user_id = ? AND id = ?", balance, session["user_id"], account["id"])

                flash("Settle")

                return redirect("/person")

            except ValueError:
                return apology("invalid numeric number")
