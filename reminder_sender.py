import os
import pytz
import datetime
from notion_client import Client
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# ⏰ Timezone setup
LOCAL_TIMEZONE = pytz.timezone("Asia/Kolkata")

# --- CONFIGURATION ---
NOTION_TOKEN = "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"
DATABASE_ID = "23cfd797cac480d497f0d1a29c3bd52c"

# 📧 Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.send']


# ✅ Authenticate Gmail
def authenticate_gmail():
    creds = None
    token_path = "token.json"
    creds_path = "credentials.json"

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception("Gmail API token is missing or expired.")
    return build('gmail', 'v1', credentials=creds)


# ✉️ Send Email
def send_email(service, to, subject, body):
    from email.mime.text import MIMEText
    import base64

    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    message_body = {'raw': raw}
    service.users().messages().send(userId="me", body=message_body).execute()


# 🧠 Safe text extraction
def extract_text(prop):
    if 'title' in prop and prop['title']:
        return prop['title'][0]['plain_text']
    elif 'rich_text' in prop and prop['rich_text']:
        return prop['rich_text'][0]['plain_text']
    return None


# 📅 Safe date parsing
def extract_datetime(prop):
    try:
        if prop and "date" in prop and prop["date"] and prop["date"]["start"]:
            return datetime.datetime.fromisoformat(prop["date"]["start"]).astimezone(LOCAL_TIMEZONE)
    except Exception as e:
        print(f"❌ Error parsing date: {e}")
    return None


# 🧠 Send reminder (you can modify this to send WhatsApp or email)
def send_reminder(name, phone, interview_time):
    print(f"📤 Reminder sent to {name} ({phone}) for interview at {interview_time.strftime('%Y-%m-%d %H:%M')}")
    # You can replace this with WhatsApp API or send_email() call


# 🚀 Main script
def main():
    print("⏳ Querying Notion database...")
    notion = Client(auth=NOTION_TOKEN)
    service = authenticate_gmail()

    try:
        response = notion.databases.query(database_id=DATABASE_ID)
        results = response.get("results", [])
        print(f"✅ Found {len(results)} interviews to process.")
    except Exception as e:
        print(f"❌ Failed to fetch data from Notion: {e}")
        return

    for result in results:
        try:
            props = result["properties"]

            name = extract_text(props.get("Name"))
            phone = extract_text(props.get("Phone"))
            interview_time = extract_datetime(props.get("Interview Time"))
            notified = props.get("Notified", {}).get("checkbox", False)

            if not name or not interview_time:
                print(f"⚠️ Skipping due to missing name or time.")
                continue

            if notified:
                print(f"⏭ Already notified: {name}")
                continue

            now = datetime.datetime.now(LOCAL_TIMEZONE)
            diff = (interview_time - now).total_seconds()

            if 0 <= diff <= 900:
                print(f"🔔 Sending reminder for {name} ({phone}) at {interview_time.strftime('%Y-%m-%d %H:%M')}")
                send_reminder(name, phone, interview_time)

                notion.pages.update(
                    page_id=result["id"],
                    properties={"Notified": {"checkbox": True}}
                )
            else:
                print(f"⏭ Skipping {name} — not within 15-minute window.")

        except Exception as e:
            print(f"⚠️ Error processing a record: {e}")

    print("\n✅ Reminder check completed.")


if __name__ == "__main__":
    main()
