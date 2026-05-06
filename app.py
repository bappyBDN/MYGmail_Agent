import streamlit as st
import os
import base64
import re
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sentence_transformers import SentenceTransformer
from groq import Groq


from gmail_sender import send_gmail_reply 


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


st.set_page_config(page_title="Vizuara AI Agent", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f4f7f6; }
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; transition: 0.3s; }
    .stButton>button:hover { background-color: #4F46E5; color: white; border: none; }
    .email-box { padding: 20px; border-radius: 10px; background-color: white; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    .status-tag { padding: 4px 8px; border-radius: 5px; font-size: 12px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)


def get_gmail_service():
    if not os.path.exists('token.json'):
        st.error("Error: token.json not found! Please run your login script first.")
        return None
    creds = Credentials.from_authorized_user_file('token.json')
    return build('gmail', 'v1', credentials=creds)

def fetch_live_emails():
    service = get_gmail_service()
    if not service: return []

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
        except: body = "Inquiry content is not readable."

        email_list.append({
            "gmail_id": msg['id'],
            "thread_id": msg['threadId'],
            "subject": subject,
            "from": from_info,
            "body": body
        })
    return email_list


tab_workspace, tab_analytics = st.tabs(["📥 Email Workspace", "📊 Performance & Feedback"])

# --- TAB 1: WORKSPACE ---
with tab_workspace:
    col_list, col_main = st.columns([1, 2])

    with col_list:
        st.subheader("Live Inbox")
        if st.button("🔄 Sync Live Inbox", use_container_width=True):
            with st.spinner("Syncing..."):
                st.session_state.live_emails = fetch_live_emails()
                st.rerun()

        if 'live_emails' not in st.session_state:
            st.session_state.live_emails = []

        st.divider()
        for email in st.session_state.live_emails:
           
            db_res = supabase.table("replies").select("status").eq("email_id", email['gmail_id']).execute()
            status_icon = "📩"
            if db_res.data:
                status_icon = "✅" if db_res.data[0]['status'] == 'sent' else "📝"
            
            if st.button(f"{status_icon} {email['from'][:18]}...", key=email['gmail_id']):
                st.session_state.current_email = email

    with col_main:
        if 'current_email' in st.session_state:
            e = st.session_state.current_email
            st.title("✉️ Email View")
            
            with st.container():
                st.markdown(f"**From:** {e['from']}")
                st.markdown(f"**Subject:** {e['subject']}")
                st.text_area("Inquiry:", value=e['body'], height=200, disabled=True)
            
            st.divider()

            
            db_reply = supabase.table("replies").select("*").eq("email_id", e['gmail_id']).execute()
            
            if db_reply.data:
                reply_record = db_reply.data[0]
                
                if reply_record['status'] == 'sent':
                    st.success(f"Email sent successfully on {reply_record.get('sent_at')}")
                    st.text_area("Sent Reply:", value=reply_record['ai_draft'], height=250, disabled=True)
                else:
                    st.subheader("🤖 Edit AI Draft")
                    final_body = st.text_area("You can modify the draft here:", value=reply_record['ai_draft'], height=300)
                    
                    if st.button("🚀 Send Reply Now", use_container_width=True):
                        with st.spinner("Sending..."):
                           
                            recipient = re.findall(r'[\w\.-]+@[\w\.-]+', e['from'])
                            to_addr = recipient[0] if recipient else e['from']
                            
                            if send_gmail_reply(to_addr, e['subject'], final_body, e['thread_id'], e['gmail_id']):
                                supabase.table("replies").update({
                                    "status": "sent", 
                                    "sent_at": datetime.now().isoformat(),
                                    "ai_draft": final_body
                                }).eq("id", reply_record['id']).execute()
                                st.success("Replied successfully! Check your Sent box.")
                                st.balloons()
                                st.rerun()

                
                st.divider()
                st.subheader("⭐ Feedback")
                with st.expander("Rate this AI Response"):
                    stars = st.select_slider("Rating:", options=[1, 2, 3, 4, 5], value=5, key=f"star_{e['gmail_id']}")
                    comment = st.text_area("Comments:", placeholder="Was the answer correct?", key=f"com_{e['gmail_id']}")
                    if st.button("Submit Feedback"):
                        supabase.table("feedback").insert({
                            "reply_id": reply_record['id'],
                            "star_rating": stars,
                            "text_feedback": comment
                        }).execute()
                        st.toast("Feedback saved!", icon="🌟")
            
            else:
                st.warning("No AI draft found for this inquiry.")
               
                tone = st.selectbox("Reply Tone:", ["Professional", "Friendly", "Concise"])
                
                if st.button("🪄 Generate AI Reply & Save to DB", use_container_width=True):
                    with st.spinner("RAG + Groq is working..."):
                       
                        query_vec = embed_model.encode(e['body']).tolist()
                        match_res = supabase.rpc('match_courses', {'query_embedding': query_vec, 'match_threshold': 0.2, 'match_count': 3}).execute()
                        context = "\n".join([f"- {c['course_name']}: {c['course_link']}" for c in match_res.data])
                        
                       
                        prompt = f"Counselor Tone: {tone}. Student Inquiry: {e['body']}. Related Courses: {context}. Task: Write a professional response."
                        chat = groq_client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.3-70b-versatile")
                        ai_reply = chat.choices[0].message.content
                        
                     
                        supabase.table("emails").upsert({"gmail_message_id": e['gmail_id'], "thread_id": e['thread_id'], "from_email": e['from'], "subject": e['subject'], "body": e['body'], "received_at": datetime.now().isoformat()}, on_conflict="gmail_message_id").execute()
                        supabase.table("replies").insert({"email_id": e['gmail_id'], "ai_draft": ai_reply, "status": "draft"}).execute()
                        st.rerun()
        else:
            st.info("👈 Select an email from the left sidebar to view details.")

# --- TAB 2: ANALYTICS ---
with tab_analytics:
    st.header("📊 AI Performance & Feedback Dashboard")
    
 
    replies_data = supabase.table("replies").select("status").execute()
    feedback_data = supabase.table("feedback").select("star_rating, text_feedback").execute()
    
    m1, m2, m3 = st.columns(3)
    if replies_data.data:
        df_r = pd.DataFrame(replies_data.data)
        m1.metric("Total Inquiries", len(df_r))
        m2.metric("Sent Replies", len(df_r[df_r['status'] == 'sent']))
    
    if feedback_data.data:
        df_f = pd.DataFrame(feedback_data.data)
        avg_star = df_f['star_rating'].mean()
        m3.metric("Avg. Satisfaction", f"{avg_star:.1f} / 5.0")
        
        st.divider()
        st.subheader("Recent Feedback Comments")
        st.dataframe(df_f.tail(10), use_container_width=True)
    else:
        st.write("No feedback received yet.")
