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
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

# ✅ Safety check for missing secrets
if not NOTION_TOKEN or not DATABASE_ID:
    raise ValueError("Missing NOTION_TOKEN or DATABASE_ID in environment variables.")



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

            name = extract_text(props.get("Candidate Name"))
            email = extract_text(props.get("Email"))
            company = extract_text(props.get("Company Name"))
            interview_time = extract_datetime(props.get("Interview Date"))
            reminder_sent_at = extract_datetime(props.get("Reminder Sent At"))

            if not name or not interview_time or not email:
                print(f"⚠️ Skipping due to missing data.")
                continue

            if reminder_sent_at:
                print(f"⏭ Already sent reminder to: {name}")
                continue

            now = datetime.datetime.now(LOCAL_TIMEZONE)
            diff = (interview_time - now).total_seconds()

            if 0 <= diff <= 3600:
                print(f"🔔 Sending reminder for {name} ({email})")

                subject = f"Interview Reminder | {company} | {interview_time.strftime('%I:%M %p on %d %b, %Y')}"
                body = f"""Hi {name},

This is a gentle reminder for your interview with {company} scheduled at {interview_time.strftime('%I:%M %p on %d %b, %Y')}.

Let me know if you face any issues in connecting.

All the best!

Regards,
Team TalentNiti"""

                send_email(service, email, subject, body)

                # Update Notion timestamp
                notion.pages.update(
                    page_id=result["id"],
                    properties={
                        "Reminder Sent At": {
                            "date": {
                                "start": now.isoformat()
                            }
                        }
                    }
                )
            else:
                print(f"⏭ Skipping {name} — interview not within 60-minute window.")

        except Exception as e:
            print(f"⚠️ Error processing a record: {e}")

    print("\n✅ Reminder check completed.")


if __name__ == "__main__":
    main()
