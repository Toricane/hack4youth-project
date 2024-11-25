import json
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from groq import Groq

load_dotenv()

# Flask app setup
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Google OAuth 2.0 Client Config
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.readonly",
]
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


# Updating Google Calendar events
def get_calendar_service():
    """Initialize and return Google Calendar service with current credentials."""
    if "credentials" not in session:
        return None

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

    return build("calendar", "v3", credentials=credentials)


def create_events(
    events: List[Dict[str, str]], timezone: str
) -> List[Dict[str, Union[str, bool]]]:
    """
    Create multiple calendar events.

    Args:
        events: List of event dictionaries containing summary, start, and end times

    Returns:
        List of dictionaries containing success status and event ID or error message
    """
    service = get_calendar_service()
    if not service:
        return [{"success": False, "error": "Not authenticated"}]

    results = []
    for event in events:
        try:
            event_body = {
                "summary": event["summary"],
                "start": {"dateTime": event["start"][:-1], "timeZone": timezone},
                "end": {"dateTime": event["end"][:-1], "timeZone": timezone},
            }

            created_event = (
                service.events().insert(calendarId="primary", body=event_body).execute()
            )

            results.append({"success": True, "eventId": created_event["id"]})
        except Exception as e:
            results.append({"success": False, "error": str(e)})

    return results


def update_events(events: List[Dict[str, str]]) -> List[Dict[str, Union[str, bool]]]:
    """
    Update multiple calendar events.

    Args:
        events: List of event dictionaries containing eventId and optional summary, start, end, and colorId

    Returns:
        List of dictionaries containing success status and updated event ID or error message
    """
    service = get_calendar_service()
    if not service:
        return [{"success": False, "error": "Not authenticated"}]

    results = []
    for event in events:
        try:
            # Get existing event
            existing_event = (
                service.events()
                .get(calendarId="primary", eventId=event["eventId"])
                .execute()
            )

            # Update fields if provided
            if "summary" in event:
                existing_event["summary"] = event["summary"]
            if "start" in event:
                existing_event["start"]["dateTime"] = event["start"]
            if "end" in event:
                existing_event["end"]["dateTime"] = event["end"]
            if "colorId" in event:
                existing_event["colorId"] = event["colorId"]

            updated_event = (
                service.events()
                .update(
                    calendarId="primary", eventId=event["eventId"], body=existing_event
                )
                .execute()
            )

            results.append({"success": True, "eventId": updated_event["id"]})
        except Exception as e:
            results.append({"success": False, "error": str(e)})

    return results


def delete_events(event_ids: List[Dict[str, str]]) -> List[Dict[str, Union[str, bool]]]:
    """
    Delete multiple calendar events.

    Args:
        event_ids: List of dictionaries containing eventId

    Returns:
        List of dictionaries containing success status or error message
    """
    service = get_calendar_service()
    if not service:
        return [{"success": False, "error": "Not authenticated"}]

    results = []
    for event in event_ids:
        try:
            service.events().delete(
                calendarId="primary", eventId=event["eventId"]
            ).execute()

            results.append({"success": True})
        except Exception as e:
            results.append({"success": False, "error": str(e)})

    return results


def list_events(
    timeframe: Optional[Dict[str, str]] = None,
) -> Dict[str, Union[List[Dict], str]]:
    """
    List calendar events within a specified timeframe.

    Args:
        timeframe: Optional dictionary containing start and end times

    Returns:
        Dictionary containing list of events or error message
    """
    service = get_calendar_service()
    if not service:
        return {"success": False, "error": "Not authenticated"}

    try:
        # Default timeframe: 8 hours ago to 56 hours in future
        now = datetime.utcnow() - timedelta(hours=8)
        future = now + timedelta(hours=64)

        time_min = (
            timeframe.get("start", now.isoformat() + "Z")
            if timeframe
            else now.isoformat() + "Z"
        )
        time_max = (
            timeframe.get("end", future.isoformat() + "Z")
            if timeframe
            else future.isoformat() + "Z"
        )

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=100,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        formatted_events = []

        for event in events:
            formatted_events.append(
                {
                    "eventId": event["id"],
                    "summary": event.get("summary", "No Title"),
                    "start": event["start"].get("dateTime", event["start"].get("date")),
                    "end": event["end"].get("dateTime", event["end"].get("date")),
                    "colorId": event.get("colorId", "7"),  # Default to peacock color
                }
            )

        return {"success": True, "events": formatted_events}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_events(
    event_ids: List[Dict[str, str]],
) -> List[Dict[str, Union[str, bool, Dict]]]:
    """
    Get details for specific calendar events.

    Args:
        event_ids: List of dictionaries containing eventId

    Returns:
        List of dictionaries containing event details or error messages
    """
    service = get_calendar_service()
    if not service:
        return [{"success": False, "error": "Not authenticated"}]

    results = []
    for event in event_ids:
        try:
            event_result = (
                service.events()
                .get(calendarId="primary", eventId=event["eventId"])
                .execute()
            )

            formatted_event = {
                "eventId": event_result["id"],
                "summary": event_result.get("summary", "No Title"),
                "start": event_result["start"].get(
                    "dateTime", event_result["start"].get("date")
                ),
                "end": event_result["end"].get(
                    "dateTime", event_result["end"].get("date")
                ),
                "colorId": event_result.get("colorId", "7"),
            }

            results.append({"success": True, "event": formatted_event})
        except Exception as e:
            results.append({"success": False, "error": str(e)})

    return results


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
    chat_log = data.get("chat_log", [])

    # Get calendar events for the next 7 days
    timeframe = {
        "start": datetime.utcnow().isoformat() + "Z",
        "end": (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z",
    }

    events_result = list_events(timeframe)

    if not events_result.get("success"):
        return jsonify(
            {
                "bot_response": "Sorry, I couldn't access your calendar. Please make sure you're logged in."
            }
        )

    # Format calendar events for the prompt
    calendar_events = "Upcoming events for the next 7 days:\n"
    for event in events_result.get("events", []):
        start_time = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
        end_time = datetime.fromisoformat(event["end"].replace("Z", "+00:00"))
        calendar_events += f"- {event['summary']}: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')} UTC\n"

    if not events_result.get("events"):
        calendar_events += "No events scheduled.\n"

    # Get system prompt and format it with calendar events
    system_prompt = (
        "You are TimeCraft, an AI assistant integrated with Google Calendar to help users manage their time effectively and achieve their goals through intelligent scheduling and time-blocking. You have access to the user's calendar events and can create, update, and manage events.\n\nCAPABILITIES:\n- View upcoming calendar events\n- Create new calendar events with specific times\n- Update existing calendar events\n- Delete calendar events when appropriate\n- Suggest time-blocking strategies based on user goals\n- Help users organize their schedule efficiently\n\nCURRENT CALENDAR CONTEXT:\n"
        + calendar_events
        + '\n\nRESPONSE FORMAT:\nAnalyze the user\'s request and respond in ONE of these two formats (ALWAYS in JSON format):\n\n1. If clarification is needed, or you need to converse with the user and not perform an action:\n{\n    "type": "inquiry",\n    "message": "Clear, specific question to get necessary information from user, or a response to the user if applicable"\n}\n\n2. If action can be taken:\n{\n    "type": "action",\n    "actions": [\n        {\n            "operation": "create_events|update_events|delete_events",\n            "events": [\n                {\n                    // Event details following the required format for each operation\n                }\n            ]\n        }\n    ],\n    "message": "Clear explanation of what actions were taken and why"\n}\n\nGUIDELINES:\n- Always check calendar context before suggesting times\n- Prefer specific times over vague scheduling\n- Consider time-blocking best practices\n- Do not suggest times which overlap with other events\n- If multiple events are related, or changing one event influences the other, batch them together\n- Be proactive in suggesting optimal scheduling approaches\n- When not fully certain about the dates and times, ask for clarification rather than making assumptions all the time\n- Before outputting actions, double check all the details first with an inquiry\n- Use clear, conversational language in responses\n- You do not need to just ask for clarification in inquiries. You can provide suggestions and clarify assumptions\n- Format all times in UTC (e.g., "2024-11-24T14:00:00Z")\n\nExample of good responses:\nUser: "I need to study for 3 hours tomorrow"\nResponse: {\n    "type": "inquiry",\n    "message": "I see you have some free time tomorrow. Would you prefer to study in the morning between 9 AM-12 PM, or in the afternoon between 2 PM-5 PM?"\n}\n\nUser: "Schedule a team meeting for next Tuesday at 2pm for 1 hour"\nResponse: {\n    "type": "action",\n    "actions": [{\n        "operation": "create_events",\n        "events": [{\n            "summary": "Team Meeting",\n            "start": "2024-11-26T14:00:00Z",\n            "end": "2024-11-26T15:00:00Z"\n        }]\n    }],\n    "message": "I\'ve scheduled the team meeting for next Tuesday at 2 PM for one hour. Would you like me to add any specific agenda items to the event description?"\n}\n\nNote: if there are multiple messages in the chat, your messages will not be in JSON format as it was formatted for the user. Always provide a JSON formatted response.'
    )

    new_chat_log = []
    for log in chat_log:
        if log["role"] == "user":
            new_chat_log.append(log)
        else:
            new_chat_log.append(
                {
                    "role": "assistant",
                    "content": '{\n    "type": "inquiry",\n    "message": "'
                    + log["content"]
                    + '"\n}',
                }
            )

    # Make initial LLM call
    completion = groq.chat.completions.create(
        model="llama-3.2-90b-vision-preview",
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            *chat_log,
        ],
        temperature=0,
        max_tokens=1024,
        top_p=1,
        stream=False,
        stop=None,
        response_format={"type": "json_object"},
    )

    # Parse the LLM response
    try:
        response_content = completion.choices[0].message.content
        response_data = json.loads(response_content)

        if response_data["type"] == "inquiry":
            # For inquiries, return directly to the user
            return jsonify({"bot_response": response_data["message"]})

        elif response_data["type"] == "action":
            # Execute the specified actions
            results = []
            for action in response_data["actions"]:
                operation = action["operation"]
                events = action["events"]

                if operation == "create_events":
                    timezone = data.get("timezone", "UTC")
                    result = create_events(events, timezone)
                elif operation == "update_events":
                    result = update_events(events)
                elif operation == "delete_events":
                    result = delete_events(events)
                else:
                    result = [
                        {"success": False, "error": f"Unknown operation: {operation}"}
                    ]

                results.append({"operation": operation, "results": result})

            # Make second LLM call to generate response about the actions taken
            action_summary = json.dumps(results, indent=2)
            completion_2 = groq.chat.completions.create(
                model="llama-3.2-90b-vision-preview",
                messages=[
                    {
                        "role": "system",
                        "content": 'You are TimeCraft. Format the following action results into a friendly, clear message for the user. Focus on what was accomplished and any next steps or additional information the user might need. Do not provide the event ID. Start the message with "Done!"',
                    },
                    {
                        "role": "user",
                        "content": f"Original request: {message}\nAction results: {action_summary}\n Chat log: {chat_log}",
                    },
                ],
                temperature=0.7,  # Slightly higher temperature for more natural response
                max_tokens=1024,
                top_p=1,
                stream=False,
                stop=None,
            )

            return jsonify({"bot_response": completion_2.choices[0].message.content})

        else:
            return jsonify(
                {
                    "bot_response": "I'm sorry, I couldn't process that request properly. Please try again."
                }
            )

    except json.JSONDecodeError:
        print(completion.choices[0].message.content)
        return jsonify(
            {
                "bot_response": "I apologize, but I couldn't process that request properly. Could you please rephrase it?"
            }
        )
    except Exception as e:
        print(f"Error processing request: {str(e)}")
        return jsonify(
            {
                "bot_response": "I encountered an error while processing your request. Please try again."
            }
        )


if __name__ == "__main__":
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    app.run("localhost", 5000, debug=True)
