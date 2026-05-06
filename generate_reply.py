import os
from dotenv import load_dotenv
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
from groq import Groq


current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '.env')
load_dotenv(dotenv_path=env_path, override=True)

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

GROQ_API_KEY = os.getenv("GROK_API_KEY") 

if not SUPABASE_URL or not SUPABASE_KEY or not GROQ_API_KEY:
    raise ValueError("Supabase বা Groq এর API Key পাওয়া যায়নি। .env ফাইল চেক করুন।")


supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = Groq(api_key=GROQ_API_KEY)


embed_model = SentenceTransformer('all-MiniLM-L6-v2')

def generate_and_save_draft():
    print("🚀 Groq AI রিপ্লাই জেনারেটর চালু হচ্ছে...")
    
   
    emails_res = supabase.table("emails").select("*").order("received_at", desc=True).limit(1).execute()
    
    if not emails_res.data:
        print("❌ ডাটাবেসে কোনো ইমেইল পাওয়া যায়নি।")
        return
        
    email = emails_res.data[0]
    email_id = email['id']
    email_body = email['body']
    
   
    existing_reply = supabase.table("replies").select("id").eq("email_id", email_id).execute()
    if existing_reply.data:
        print(f"⏩ '{email['subject']}' এর ড্রাফট আগেই তৈরি করা আছে।")
        return

    print(f"📧 প্রসেস করা হচ্ছে: '{email['subject']}'")
    
  
    query_vector = embed_model.encode(email_body).tolist()
    match_res = supabase.rpc('match_courses', {
        'query_embedding': query_vector,
        'match_threshold': 0.2, 
        'match_count': 3
    }).execute()
    
    context_courses = ""
    for idx, course in enumerate(match_res.data):
        context_courses += f"Course {idx+1}: {course['course_name']}\nLink: {course['course_link']}\nDetails: {course['content']}\n\n"
        
   
    print("✍️ Groq AI দিয়ে রিপ্লাই তৈরি করা হচ্ছে...")
    prompt = f"""
    You are a professional student counselor for 'Vizuara'. 
    Below is an inquiry from a student:
    "{email_body}"
    
    Relevant courses from our database:
    {context_courses if context_courses else "No specific course found."}
    
    Instructions: 
    - Be polite, professional, and helpful.
    - Recommend the specific courses found above with their links.
    - Sign as 'Vizuara Support Team'.
    """
    
  
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="llama-3.3-70b-versatile",
    )
    
    ai_draft_text = chat_completion.choices[0].message.content
    
  
    reply_data = {
        "email_id": email_id,
        "ai_draft": ai_draft_text,
        "status": "draft"
    }
    
    try:
        supabase.table("replies").insert(reply_data).execute()
        print("\n✅ Groq ড্রাফট সফলভাবে তৈরি এবং Supabase-এ সেভ হয়েছে!")
        print("-" * 30 + f"\nPreview:\n{ai_draft_text[:250]}...\n" + "-" * 30)
    except Exception as e:
        print(f" সেভ এরর: {e}")

if __name__ == '__main__':
    generate_and_save_draft()
