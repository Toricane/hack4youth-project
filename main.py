import os
from collections import defaultdict
from datetime import datetime, timedelta

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# Google OAuth 2.0 Client Config
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
REDIRECT_URI = "http://localhost:5000/oauth2callback"

# OAuth Flow
flow = Flow.from_client_secrets_file(
    CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
)


# Utility functions for date manipulation
def get_week_start(date=None):
    if not date:
        date = datetime.now()
    start_of_week = date - timedelta(days=date.weekday())
    return start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)


def get_current_date():
    return session.get("current_date", datetime.now().strftime("%Y-%m-%d"))


def format_date_for_api(date_str):
    return datetime.fromisoformat(date_str).isoformat() + "Z"


def get_date_range(current_date_str, days_to_add=0):
    current_date = datetime.fromisoformat(current_date_str)
    start_date = current_date + timedelta(days=days_to_add)
    end_date = start_date + timedelta(days=4)
    return start_date, end_date


# Routes
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/authorize")
def authorize():
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )
    session["state"] = state
    return redirect(authorization_url)


@app.route("/oauth2callback")
def oauth2callback():
    if "state" not in session or session["state"] != request.args["state"]:
        return "Error: State mismatch", 400

    flow.fetch_token(authorization_response=request.url)
    credentials = flow.credentials
    session["credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
    }
    session["current_date"] = datetime.now().strftime("%Y-%m-%d")
    return redirect(url_for("list_calendar_events"))


@app.route("/list-calendar-events", methods=["GET"])
def list_calendar_events():
    if "credentials" not in session:
        return redirect("authorize")

    credentials_dict = session["credentials"]
    credentials = Credentials(**credentials_dict)

    if not credentials.valid and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        session["credentials"] = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }

    service = build("calendar", "v3", credentials=credentials)

    current_date_str = get_current_date()

    if request.args.get("direction") == "next":
        current_date = datetime.fromisoformat(current_date_str)
        next_date = current_date + timedelta(days=4)
        session["current_date"] = next_date.strftime("%Y-%m-%d")
        current_date_str = session["current_date"]
    elif request.args.get("direction") == "prev":
        current_date = datetime.fromisoformat(current_date_str)
        prev_date = current_date - timedelta(days=4)
        session["current_date"] = prev_date.strftime("%Y-%m-%d")
        current_date_str = session["current_date"]

    start_date, end_date = get_date_range(current_date_str)

    now = format_date_for_api(start_date.isoformat())
    end = format_date_for_api(end_date.isoformat())

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            maxResults=100,
            singleEvents=True,
            orderBy="startTime",
            timeMin=now,
            timeMax=end,
        )
        .execute()
    )
    events = events_result.get("items", [])

    formatted_events = []
    for event in events:
        start_time = event["start"].get("dateTime", event["start"].get("date"))
        end_time = event["end"].get("dateTime", event["end"].get("date"))
        summary = event.get("summary", "No Title")
        formatted_events.append(
            {"start": start_time, "end": end_time, "summary": summary}
        )

    header_height = 40  # Height of your header in pixels
    hour_height = 60  # Height of each hour slot in pixels

    days_events = defaultdict(list)
    for event in formatted_events:
        start_dt = datetime.fromisoformat(event["start"])
        end_dt = datetime.fromisoformat(event["end"])
        event_day = start_dt.strftime("%Y-%m-%d")
        days_events[event_day].append(
            {
                "summary": event["summary"],
                "start_time": start_dt.strftime("%H:%M"),
                "end_time": end_dt.strftime("%H:%M"),
                "start_pixel": (start_dt.hour * 60 + start_dt.minute - 6.5 * 60)
                + (header_height / hour_height * 60),  # Corrected calculation
                "duration": (end_dt.hour * 60 + end_dt.minute)
                - (start_dt.hour * 60 + start_dt.minute),
            }
        )

    date_range = [start_date + timedelta(days=i) for i in range(4)]

    return render_template(
        "list_events.html",
        days_events=days_events,
        date_range=date_range,
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    message = data.get("message")
    chat_log = data.get("chat_log")

    print(f"Message: {message}")
    print(f"Chat Log: {chat_log}")

    # Process chat_log and message here (e.g., with your Groq API)
    # ...

    bot_response = "I am a placeholder response. I will use Groq API soon!"  # Replace with actual bot response

    return jsonify({"bot_response": bot_response})


if __name__ == "__main__":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    app.run("localhost", 5000, debug=True)
