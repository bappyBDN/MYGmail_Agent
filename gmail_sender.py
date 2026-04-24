import os
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def send_gmail_reply(to_email, subject, body_text, thread_id, message_id):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(current_dir, 'token.json')
    
    if not os.path.exists(token_path):
        print("Error: token.json not found.")
        return False
        
    creds = Credentials.from_authorized_user_file(token_path)
    service = build('gmail', 'v1', credentials=creds)

    # ১. সাবজেক্ট ঠিক করা
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    # ২. MIMEText তৈরি (UTF-8 এবং From হেডারসহ)
    message = MIMEText(body_text, 'plain', 'utf-8')
    message['to'] = to_email
    message['from'] = 'me'  # এটি জিমেইলকে বলে যে আপনি নিজে পাঠাচ্ছেন
    message['subject'] = subject
    
    # ৩. থ্রেডিং হেডার (যাতে রিপ্লাই হিসেবে দেখায়)
    message['In-Reply-To'] = message_id
    message['References'] = message_id

    # ৪. এনকোডিং
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
    
    try:
        # ৫. মেসেজ সেন্ড করা
        sent_msg = service.users().messages().send(
            userId='me', 
            body={
                'raw': raw_message, 
                'threadId': thread_id
            }
        ).execute()
        
        print(f"✅ ইমেইল পাঠানো হয়েছে! Message ID: {sent_msg['id']}")
        return True
    except Exception as e:
        print(f"❌ এরর: {e}")
        return False