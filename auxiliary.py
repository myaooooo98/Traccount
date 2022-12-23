from flask import redirect, render_template, request, session
from functools import wraps

def apology(message):
    """Render message as an apology to user"""
    message = message.upper()
    return render_template("apology.html", message=message)

def login_required(f):
    """Decorate routes to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

def currency(value):
    """Format value as currency"""
    return f"${value:,.2f}"