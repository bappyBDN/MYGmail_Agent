# Vizuara AI Agent

An AI-powered email assistant for Vizuara that helps manage student inquiries, generate responses using RAG and LLMs, and track performance.

## Features

- Live Gmail inbox synchronization
- AI-generated responses using Groq (Llama 3) and Sentence Transformers
- RAG (Retrieval-Augmented Generation) with Supabase vector store
- Feedback collection system
- Email sending capabilities
- Analytics dashboard

## Setup

1. Clone the repository
2. Create a `.env` file with the following variables:
   ```
   NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
   SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
   GROK_API_KEY=your_groq_api_key
   ```
   Note: Never commit your `.env` file to version control.

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install streamlit groq google-auth google-auth-oauthlib google-api-python-client sentence-transformers supabase python-dotenv pandas
   ```

4. Set up Gmail API credentials:
   - Follow the [Gmail API quickstart](https://developers.google.com/gmail/api/quickstart/python)
   - Save the token as `token.json` in the project root

5. Run the application:
   ```bash
   streamlit run app.py
   ```
   or
   ```bash
   python -m streamlit run app.py
   ```

## Project Structure

- `app.py`: Main Streamlit application
- `gmail_sender.py`: Gmail sending functionality
- `fetch_emails.py`: Email fetching utilities
- `generate_reply.py`: Reply generation logic
- `setup_knowledge_base.py`: Script to initialize the Supabase vector store
- `requirements.txt`: Python dependencies

## Environment Variables

The following environment variables are required:
- `NEXT_PUBLIC_SUPABASE_URL`: Supabase project URL
- `SUPABASE_SERVICE_ROLE_KEY`: Supabase service role key
- `GROK_API_KEY`: Groq API key (for Llama 3 model)

## Data Privacy

This application processes email data locally and only sends AI-generated replies. No email content is stored permanently outside of your Supabase instance (if used for RAG) and feedback database.

## License
