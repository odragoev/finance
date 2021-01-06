import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached


@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    """Add cash to account"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure field is not blank
        if not request.form.get("amount"):
            return apology("must provide amount of cash to add", 400)
        try:
            amount = float(request.form.get("amount"))
        # Ensure numeric value for amount
        except:
            return apology("must provide valid amount of cash to add", 400)
        # Ensure amount is not negative or fractional
        if not (isinstance(amount, float)) or amount <= 0:
            return apology("must provide valid amount of cash to add", 400)
        # Update user's cash value
        db.execute("UPDATE users SET cash = cash + :amount WHERE id = :id", amount=amount, id=session["user_id"])
        # Redirect user to home page
        return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("cash.html")


class Portfolio():
    def __init__(self, symbol, company, shares, price, total):
        self.symbol = symbol
        self.company = company
        self.shares = shares
        self.price = price
        self.total = total


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # Get all stocks owned by user
    rows = db.execute("SELECT symbol, SUM(shares) from transactions WHERE userkey = :id GROUP BY symbol", id=session["user_id"])
    cashDict = db.execute("SELECT cash from users WHERE id = :id", id=session["user_id"])
    cash = cashDict[0]["cash"]
    portfolios = []
    grandTotal = cash
    # Display stock if user owns at least one stock
    for row in rows:
        if row["SUM(shares)"] != 0:
            symbol = row["symbol"]
            shares = row["SUM(shares)"]
            dict = lookup(symbol)
            total = round(shares * dict["price"], 2)
            grandTotal += total
            portfolio = Portfolio(symbol, dict["name"], shares, '${:,.2f}'.format(dict["price"]), '${:,.2f}'.format(total))
            portfolios.append(portfolio)
    return render_template("index.html", portfolios=portfolios, cash='${:,.2f}'.format(cash), grandTotal='${:,.2f}'.format(grandTotal))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure stock symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide stock symbol", 400)

        # Ensure number of shares was submitted
        if not request.form.get("shares"):
            return apology("must provide number of shares to purchase", 400)

        # Ensure stock symbol is valid
        symbol = request.form.get("symbol")
        if lookup(symbol) == None:
            return apology("must provide valid stock symbol", 400)

        # Ensure number of shares is valid
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("must provide valid number of shares", 400)
        if not isinstance(shares, int) or shares < 0:
            return apology("must provide valid number of shares", 400)

        userkey = session["user_id"]
        cashDict = db.execute("SELECT cash FROM users WHERE id = :id", id=userkey)
        cash = cashDict[0]["cash"]

        dict = lookup(symbol)
        currentPrice = round(dict["price"], 2)
        total = round(currentPrice * shares, 2)

        # Check if user has enough funds for transaciton
        if cash >= total:
            # Insert transaction into table and update cash
            db.execute("INSERT INTO transactions (userkey, symbol, price, shares, date, time) VALUES(:userkey, :symbol, :price, :shares, CURRENT_DATE, CURRENT_TIME)",
                       userkey=userkey, symbol=symbol, price=currentPrice, shares=shares)
            db.execute("UPDATE users SET cash = cash - :total WHERE id = :id", total=total, id=userkey)
            return redirect("/")
        else:
            return apology("not enough funds for transaction", 400)
    else:
        return render_template("buy.html")


class Transaction():
    def __init__(self, symbol, shares, price, date, time):
        self.symbol = symbol
        self.shares = shares
        self.price = price
        self.date = date
        self.time = time


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows = db.execute("SELECT symbol, shares, price, date, time from transactions WHERE userkey = :userkey",
                    userkey=session["user_id"])
    transactions = []
    for row in rows:
        symbol = row["symbol"]
        shares = row["shares"]
        price = row["price"]
        date = row["date"]
        time = row["time"]
        transaction = Transaction(symbol, shares, '${:,.2f}'.format(price), date, time)
        transactions.append(transaction)
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide stock symbol", 400)

        # Ensure stock symbol is valid
        symbol = request.form.get("symbol")
        if lookup(symbol) == None:
            return apology("must provide valid stock symbol", 400)

        dict = lookup(symbol)
        price = round(dict["price"], 2)

        # Ensure stock symbol is valid
        if not dict == None:
            return render_template("quoted.html", name=dict["name"], price='${:,.2f}'.format(price), symbol=dict["symbol"])
        else:
            return apology("must provide valid stock symbol", 400)
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username does not already exist
        if not len(rows) == 0:
            return apology("username already exists", 400)

        # Ensure confirmation and password match
        if not request.form.get("password") == request.form.get("confirmation"):
            return apology("password and confirmation do not match", 400)

        hash = generate_password_hash(request.form.get("password"))

        # Insert the user into the database
        primaryKey = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                                username=request.form.get("username"), hash=hash)

        # Log user in put a registered banner
        session["user_id"] = primaryKey
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure number of shares was submitted
        if not request.form.get("shares"):
            return apology("must provide number of shares to purchase", 400)

        # Ensure number of shares is valid
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("must provide valid number of shares", 400)
        if not isinstance(shares, int) or shares < 0:
            return apology("must provide valid number of shares", 400)

        # Ensure symbol is valid
        symbol = request.form.get("symbol")
        if symbol == None:
            return apology("must provide valid stock symbol", 400)

        userTransaction = db.execute(
            "SELECT symbol, SUM(shares) from transactions WHERE userkey = :userkey AND symbol=:symbol GROUP BY symbol", userkey=session["user_id"], symbol=symbol)

        # Ensure user owns enough shares
        if (int(userTransaction[0]["SUM(shares)"]) - shares) < 0:
            return apology("must provide valid number of owned shares", 400)

        userkey = session["user_id"]
        cashDict = db.execute("SELECT cash from users WHERE id = :id", id=userkey)
        cash = cashDict[0]["cash"]

        dict = lookup(symbol)
        currentPrice = round(dict["price"], 2)
        total = round(currentPrice * shares, 2)
        # Insert transaction into table and update cash
        db.execute("INSERT INTO transactions (userkey, symbol, price, shares, date, time) VALUES(:userkey, :symbol, :price, :shares, CURRENT_DATE, CURRENT_TIME)",
                   userkey=userkey, symbol=symbol, price=currentPrice, shares=-shares)
        db.execute("UPDATE users SET cash = cash + :total WHERE id = :id", total=total, id=userkey)
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        # Get all stocks that user owns to display to sell
        rows = db.execute("SELECT symbol, SUM(shares) from transactions WHERE userkey = :userkey GROUP BY symbol",
                          userkey=session["user_id"])
        symbols = []
        for row in rows:
            if row["SUM(shares)"] != 0:
                symbol = row["symbol"]
                symbols.append(symbol)
        return render_template("sell.html", symbols=symbols)


def errorhandler(e):
    """Handle error"""
    return apology(e.name, e.code)


# listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
