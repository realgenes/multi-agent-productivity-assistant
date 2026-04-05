from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.config import Settings


class CalendarConfigurationError(RuntimeError):
    """Raised when Google Calendar configuration is incomplete."""


class GoogleCalendarService:
    def __init__(self, settings: Settings):
        self.settings = settings
        if not settings.google_calendar_configured():
            raise CalendarConfigurationError(
                "Google Calendar is not configured. Set GOOGLE_CALENDAR_CLIENT_ID, "
                "GOOGLE_CALENDAR_CLIENT_SECRET, and GOOGLE_CALENDAR_REFRESH_TOKEN."
            )

    def list_upcoming_events(self, max_results: int = 10, days_ahead: int = 7) -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        time_min = now.isoformat().replace("+00:00", "Z")
        time_max = (now + timedelta(days=days_ahead)).isoformat().replace("+00:00", "Z")
        token = self._refresh_access_token()

        with httpx.Client(timeout=20) as client:
            response = client.get(
                f"https://www.googleapis.com/calendar/v3/calendars/{self.settings.google_calendar_id}/events",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "singleEvents": "true",
                    "orderBy": "startTime",
                    "maxResults": max_results,
                    "timeZone": self.settings.google_calendar_timezone,
                },
            )
            response.raise_for_status()
            payload = response.json()

        events: list[dict[str, Any]] = []
        for item in payload.get("items", []):
            start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
            end = item.get("end", {}).get("dateTime") or item.get("end", {}).get("date")
            events.append(
                {
                    "id": item.get("id"),
                    "title": item.get("summary") or "Untitled event",
                    "start": start,
                    "end": end,
                    "location": item.get("location"),
                    "description": item.get("description"),
                    "html_link": item.get("htmlLink"),
                }
            )
        return events

    def summarize_upcoming_events(self, max_results: int = 8, days_ahead: int = 7) -> dict[str, Any]:
        events = self.list_upcoming_events(max_results=max_results, days_ahead=days_ahead)
        if not events:
            return {"summary": "No calendar events found in the selected time range.", "events": []}

        lines = []
        for event in events:
            when = event["start"] or "unspecified"
            lines.append(f"{event['title']} at {when}")
        return {
            "summary": "Upcoming calendar events:\n" + "\n".join(lines),
            "events": events,
        }

    def _refresh_access_token(self) -> str:
        with httpx.Client(timeout=20) as client:
            response = client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": self.settings.google_calendar_client_id,
                    "client_secret": self.settings.google_calendar_client_secret,
                    "refresh_token": self.settings.google_calendar_refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            payload = response.json()

        token = payload.get("access_token")
        if not token:
            raise CalendarConfigurationError("Google OAuth token refresh succeeded but no access token was returned.")
        return token
