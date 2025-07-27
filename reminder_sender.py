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


# ✅ Function to authenticate Gmail API
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


# ✉️ Function to send email
def send_email(service, to, subject, body):
    from email.mime.text import MIMEText
    import base64

    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    message_body = {'raw': raw}
    service.users().messages().send(userId="me", body=message_body).execute()


# 🧠 Safe extraction from Notion fields
def extract_text(prop):
    if 'title' in prop and prop['title']:
        return prop['title'][0]['plain_text']
    elif 'rich_text' in prop and prop['rich_text']:
        return prop['rich_text'][0]['plain_text']
    return None


# 📅 Extract datetime field safely
def extract_datetime(prop):
    try:
        if prop and "date" in prop and prop["date"] and prop["date"]["start"]:
            return datetime.datetime.fromisoformat(prop["date"]["start"]).astimezone(LOCAL_TIMEZONE)
    except Exception as e:
        print(f"❌ Error parsing date: {e}")
    return None


# 🧠 Main function
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

    for page in results:
        props = page["properties"]

        candidate_name = extract_text(props.get("Candidate Name", {}))
        email = extract_text(props.get("Email", {}))
        phone = extract_text(props.get("Phone Number", {}))
        company = extract_text(props.get("Company Name", {}))
        interview_time = extract_datetime(props.get("Interview Date", {}))

        # Print debug info for each record
        print(f"\n🔍 Checking record:")
        print(f"  Candidate: {candidate_name}, Email: {email}, Phone: {phone}")
        print(f"  Company: {company}, Interview: {interview_time}")

        # Skip if any field is missing
        if not all([candidate_name, email, phone, company, interview_time]):
            print("⚠️ Skipping due to missing fields.")
            continue

        now = datetime.datetime.now(LOCAL_TIMEZONE)
        delta = (interview_time - now).total_seconds() / 60  # in minutes

        if 0 <= delta <= 59:
            subject = f"Interview Reminder: {company}"
            body = f"Hi {candidate_name},\n\nThis is a quick reminder about your interview with {company} scheduled at {interview_time.strftime('%I:%M %p on %d-%b-%Y')}.\n\nBest of luck!\nRecruitment Team"
            try:
                send_email(service, email, subject, body)
                print(f"✅ Reminder email sent to {email}")
                # Optionally: update 'Reminder Sent At' in Notion here
            except Exception as e:
                print(f"❌ Failed to send email: {e}")
        else:
            print("⏱️ Not within 0-59 minutes range. Skipping.")

    print("\n✅ Reminder check completed.")


if __name__ == "__main__":
    main()
