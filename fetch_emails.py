import streamlit as st
import os
import base64
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sentence_transformers import SentenceTransformer
from groq import Groq

# ১. সেটিংস ও ক্লায়েন্ট লোড
load_dotenv()
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
GROQ_API_KEY = os.getenv("GROK_API_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
groq_client = Groq(api_key=GROQ_API_KEY)

@st.cache_resource
def load_embed_model():
    return SentenceTransformer('all-MiniLM-L6-v2')

embed_model = load_embed_model()

st.set_page_config(page_title="Vizuara AI Agent", layout="wide")

# ২. জিমেইল ফাংশন (লাইভ ডেটা ফেচিং)
def get_gmail_service():
    if not os.path.exists('token.json'):
        st.error("token.json পাওয়া যায়নি! আগে fetch_emails.py রান করুন।")
        return None
    creds = Credentials.from_authorized_user_file('token.json')
    return build('gmail', 'v1', credentials=creds)

def fetch_live_emails():
    service = get_gmail_service()
    if not service: return []
    # ইনবক্সের লেটেস্ট ১৫টি ইমেইল (shuvo-র মেইল সহ সব আসবে)
    results = service.users().messages().list(userId='me', q="label:INBOX", maxResults=15).execute()
    messages = results.get('messages', [])
    
    email_list = []
    for msg in messages:
        m = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = m['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        from_info = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        
        body = ""
        try:
            payload = m.get('payload', {})
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            elif 'body' in payload and 'data' in payload['body']:
                body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
        except: body = "Content not readable."

        email_list.append({
            "gmail_id": msg['id'],
            "thread_id": msg['threadId'],
            "subject": subject,
            "from": from_info,
            "body": body
        })
    return email_list

# ৩. মেইন অ্যাপ ইন্টারফেস
st.title("📧 Vizuara AI Live Agent")

if st.sidebar.button("🔄 Sync Inbox (Live)"):
    with st.spinner("জিমেইল থেকে ইমেইল আনা হচ্ছে..."):
        st.session_state.live_emails = fetch_live_emails()

if 'live_emails' not in st.session_state:
    st.session_state.live_emails = []

# ৪. ইমেইল লিস্ট ডিসপ্লে
st.sidebar.subheader("Recent Inquiries")
for email in st.session_state.live_emails:
    # চেক করা এই ইমেইলের জন্য অলরেডি রিপ্লাই জেনারেট করা হয়েছে কি না
    db_check = supabase.table("replies").select("id").eq("email_id", email['gmail_id']).execute()
    icon = "✅" if db_check.data else "📩"
    
    if st.sidebar.button(f"{icon} {email['from'][:18]}...", key=email['gmail_id']):
        st.session_state.current_email = email

# ৫. ডিটেইলস এবং কন্ডিশনাল সেভিং লজিক
if 'current_email' in st.session_state:
    e = st.session_state.current_email
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Original Email")
        st.info(f"**From:** {e['from']}\n**Subject:** {e['subject']}")
        st.text_area("Email Content:", value=e['body'], height=350)
    
    with col2:
        st.subheader("AI Smart Reply")
        
        # ডাটাবেস থেকে চেক করা রিপ্লাই আছে কি না
        reply_res = supabase.table("replies").select("*").eq("email_id", e['gmail_id']).execute()
        
        if reply_res.data:
            # যদি অলরেডি ডাটাবেসে থাকে
            draft = reply_res.data[0]
            st.success("এটি ডাটাবেস থেকে লোড করা হয়েছে।")
            final_body = st.text_area("Edit Draft:", value=draft['ai_draft'], height=350)
            if st.button("🚀 Send Reply"):
                st.write("Sending logic...")
        else:
            # যদি ডাটাবেসে না থাকে
            st.warning("এই ইমেইলটি এখনও ডাটাবেসে সেভ করা হয়নি।")
            if st.button("🤖 Generate AI Draft & Save to DB"):
                with st.spinner("RAG + Groq কাজ করছে..."):
                    # ১. কোর্স রিট্রিভাল
                    query_vec = embed_model.encode(e['body']).tolist()
                    match_res = supabase.rpc('match_courses', {'query_embedding': query_vec, 'match_threshold': 0.2, 'match_count': 3}).execute()
                    context = "\n".join([f"- {c['course_name']}: {c['course_link']}" for c in match_res.data])
                    
                    # ২. Groq জেনারেশন
                    prompt = f"Inquiry: {e['body']}\n\nCourses:\n{context}\n\nWrite a professional reply."
                    chat = groq_client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.3-70b-versatile")
                    ai_reply = chat.choices[0].message.content
                    
                    # ৩. কন্ডিশনাল সেভিং: প্রথমে ইমেইলটি 'emails' টেবিলে সেভ করা
                    email_record = {
                        "gmail_message_id": e['gmail_id'],
                        "thread_id": e['thread_id'],
                        "from_email": e['from'],
                        "subject": e['subject'],
                        "body": e['body'],
                        "received_at": datetime.now().isoformat()
                    }
                    # যদি ইমেইলটি আগে থেকে না থাকে তবেই ইনসার্ট হবে (UPSERT লজিক)
                    supabase.table("emails").upsert(email_record, on_conflict="gmail_message_id").execute()
                    
                    # ৪. এরপর রিপ্লাইটি সেভ করা
                    supabase.table("replies").insert({
                        "email_id": e['gmail_id'],
                        "ai_draft": ai_reply,
                        "status": "draft"
                    }).execute()
                    
                    st.rerun()
else:
    st.info("ইনবক্স আপডেট করতে Sync বাটনে ক্লিক করুন এবং একটি ইমেইল সিলেক্ট করুন।")