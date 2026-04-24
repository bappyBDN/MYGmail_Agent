import os
import pandas as pd
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import create_client, Client

# ১. .env ফাইল লোড করা
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, '.env')
load_dotenv(dotenv_path=env_path, override=True)

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") 

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase API Key ঠিকমতো লোড হয়নি।")

# ২. ক্লায়েন্ট ইনিশিয়ালাইজ করা
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ৩. ফ্রি এম্বেডিং মডেল লোড করা (সম্পূর্ণ ফ্রি এবং আনলিমিটেড)
print("ফ্রি এম্বেডিং মডেল লোড হচ্ছে (প্রথমবার একটু সময় লাগতে পারে)...")
model = SentenceTransformer('all-MiniLM-L6-v2')

# ৪. CSV ফাইল রিড করা
csv_file_path = 'vizuara_courses_dummy_dataset_150.csv'
print(f"{csv_file_path} পড়া হচ্ছে...")
df = pd.read_csv(csv_file_path)

print("এম্বেডিং তৈরি এবং Supabase-এ সেভ করা শুরু হচ্ছে...")

# ৫. ডাটাবেসে সেভ করা
for index, row in df.iterrows():
    content = (
        f"Course Name: {row['Course name']}. "
        f"Description: {row['Course description']}. "
        f"Price: {row['Price']}. "
        f"Format: {row['Whether it is live or self-paced']}. "
        f"Duration: {row['Total duration in number of hours']} hours. "
        f"Audience: {row['Who the course is meant for']}"
    )
    
    try:
        # ফ্রি মডেল দিয়ে ৩৮৪ ডাইমেনশনের ভেক্টর তৈরি
        embedding_vector = model.encode(content).tolist()
        
        metadata = {
            "price": row['Price'],
            "start_date": row['Starting date'],
            "format": row['Whether it is live or self-paced'],
            "duration": row['Total duration in number of hours'],
            "audience": row['Who the course is meant for']
        }
        
        data = {
            "course_name": row['Course name'],
            "course_link": row['Course link'],
            "content": content,
            "embedding": embedding_vector,
            "metadata": metadata
        }
        
        supabase.table("course_embeddings").insert(data).execute()
        print(f"✅ সেভ হয়েছে: {row['Course name']}")
        
    except Exception as e:
        print(f"❌ এরর হয়েছে '{row['Course name']}': {e}")

print("🎉 নলেজ বেস সফলভাবে Supabase-এ সেভ হয়েছে!")