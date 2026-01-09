import os
import streamlit as st
from dotenv import load_dotenv
from google import genai
import json
import re
import base64
import PyPDF2
import docx
import pandas as pd
from io import BytesIO
import tempfile
from pathlib import Path
import zipfile
import time
import time
import requests
import json
import gspread
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Load environment variables
load_dotenv()

# Relax OAuth scope validation (Google adds openid/email/profile automatically)
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

# Streamlit app configuration
st.set_page_config(
    page_title="RoboTest AI Suite",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://www.linkedin.com/in/abdulrahman-kandil/',
        'Report a bug': "mailto:abdelrahmankandil50@gmail.com",
        'About': "# RoboTest AI Suite\nPowered by Advanced Agentic AI"
    }
)





# Configure AI Providers
# Check session state for user-provided keys, otherwise use environment variables
GEMINI_API_KEY = st.session_state.get("user_gemini_key", "") or os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = st.session_state.get("user_openai_key", "") or os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = st.session_state.get("user_anthropic_key", "") or os.getenv("ANTHROPIC_API_KEY")  # Claude API Key
GITHUB_TOKEN = st.session_state.get("user_github_token", "") or os.getenv("GITHUB_TOKEN")  # GitHub PAT with models scope
GITHUB_MODEL = os.getenv("GITHUB_MODEL", "openai/gpt-4o-mini")  # e.g., openai/gpt-4o, openai/gpt-4.1, or gpt-5 if available

# --- Google OAuth Configuration ---
# Update this with your deployed URL when pushing to production
DEPLOYED_REDIRECT_URI = "https://robotest-ai-suite.streamlit.app"
LOCAL_REDIRECT_URI = "http://localhost:8501"

def show_toast(message):
    """Show a toast notification"""
    # Use streamlit toast if available (v1.28+) or custom html
    try:
        st.toast(message)
    except:
        st.markdown(f"""
        <div class="toast">{message}</div>
        <style>
        .toast {{
            position: fixed;
            top: 5rem;
            right: 1rem;
            background-color: #2ecc71;
            color: white;
            padding: 1rem;
            border-radius: 0.5rem;
            z-index: 9999;
        }}
        </style>
        """, unsafe_allow_html=True)

def get_google_auth_flow(redirect_uri=None):
    """Create OAuth flow instance"""
    scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    # Try loading from secrets first (Deployment)
    try:
        if "google_oauth" in st.secrets and "json" in st.secrets["google_oauth"]:
            client_config = json.loads(st.secrets["google_oauth"]["json"])
            return InstalledAppFlow.from_client_config(
                client_config,
                scopes=scopes,
                redirect_uri=redirect_uri
            )
    except:
        pass # Fallback to file if secrets missing

    
    # Fallback to file (Local)
    return InstalledAppFlow.from_client_secrets_file(
        'client_secret.json', 
        scopes=scopes,
        redirect_uri=redirect_uri
    )

def handle_oauth_callback():
    """Handle the OAuth callback from Google"""
    # Prevent re-using code if already logged in
    if st.session_state.get("google_creds"):
        if "code" in st.query_params:
            st.query_params.clear()
        return

    if "code" in st.query_params:
        try:
            # 1. Try to get from session state
            redirect_uri = st.session_state.get("oauth_redirect_uri")
            
            # 2. If session state lost, infer from environment
            if not redirect_uri:
                # Heuristic: If we can access st.secrets, we are likely on Cloud
                try:
                    # Check for secrets existence (will fail locally if no secrets.toml)
                    if "google_oauth" in st.secrets:
                        redirect_uri = DEPLOYED_REDIRECT_URI
                    else:
                        redirect_uri = LOCAL_REDIRECT_URI
                except:
                    # Exception means no secrets file -> Localhost
                    redirect_uri = LOCAL_REDIRECT_URI
            
            # st.write(f"Debug: Using URI {redirect_uri}")
            
            # Create Flow
            flow = get_google_auth_flow(redirect_uri=redirect_uri)
            
            # Exchange code for token
            flow.fetch_token(code=st.query_params["code"])
            
            credentials = flow.credentials
            
            # Store in session state
            st.session_state.google_creds = credentials
            
            # Clear the code from URL to prevent reprocessing
            st.query_params.clear()
            
            # Set default page to Test Case Generator
            target_page = "🧪 Test Case Generator"
            st.session_state.main_navigation = target_page
            st.session_state.page = "Test Case Generator" 
            # Force Widget Update
            st.session_state["nav_radio_widget"] = target_page
        
            show_toast("✅ Successfully logged in with Google!")
            time.sleep(1) # Allow toast to be seen
            st.rerun()
        except Exception as e:
            st.error(f"Authentication Error: {str(e)}")
            # Do not clear params immediately so user can see error? 
            # Actually better to clear to avoid loops
            st.query_params.clear()

# Run callback handler immediately
handle_oauth_callback()

# Initialize Gemini client if available


# Model Configuration
GEMINI_MODEL = "models/gemini-flash-latest"
OPENAI_MODEL = "gpt-4o-mini"  # Cost-effective model, change to "gpt-4o" for better quality
CLAUDE_MODEL = "claude-sonnet-4-20250514"  # Fast and intelligent model

# Function to call AI (supports Gemini, OpenAI, and Claude)
def call_ai(prompt, provider=None):
    """
    Call AI API with automatic fallback.
    provider: "gemini", "openai", "claude", "github", or "auto" (tries in order)
    If not specified, uses the provider from session state
    """
    # Get provider from session state if not specified
    if provider is None:
        provider = st.session_state.get('ai_provider', 'auto')
    
    if provider == "auto":
        # Try providers in order: Gemini -> Claude -> OpenAI -> GitHub
        errors = []
        
        if GEMINI_API_KEY:
            try:
                return call_gemini(prompt)
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    st.warning("⚠️ Gemini quota exceeded. Trying next provider...")
                    errors.append(f"Gemini: {str(e)}")
                else:
                    raise e
        
        if ANTHROPIC_API_KEY:
            try:
                return call_claude(prompt)
            except Exception as e:
                st.warning("⚠️ Claude failed. Trying next provider...")
                errors.append(f"Claude: {str(e)}")
        
        if OPENAI_API_KEY:
            try:
                return call_openai(prompt)
            except Exception as e:
                st.warning("⚠️ OpenAI failed. Trying next provider...")
                errors.append(f"OpenAI: {str(e)}")
        
        if GITHUB_TOKEN:
            try:
                return call_github(prompt)
            except Exception as e:
                errors.append(f"GitHub: {str(e)}")
        
        if errors:
            raise Exception(f"All providers failed. Errors: {'; '.join(errors)}")
        raise Exception("No API keys configured. Please set at least one: GEMINI_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY, or GITHUB_TOKEN")
    
    elif provider == "gemini":
        return call_gemini(prompt)
    elif provider == "openai":
        return call_openai(prompt)
    elif provider == "claude":
        return call_claude(prompt)
    elif provider == "github":
        return call_github(prompt)
    else:
        raise Exception(f"Unknown provider: {provider}")

def call_gemini(prompt):
    """Call Gemini API"""
    # Get current API key from session state or env
    current_key = st.session_state.get("user_gemini_key", "") or os.getenv("GEMINI_API_KEY")
    if not current_key:
        raise Exception("Gemini API key not configured")
    
    # Create client with current key
    client = genai.Client(api_key=current_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )
    return response.text

def call_claude(prompt):
    """Call Anthropic Claude API"""
    if not ANTHROPIC_API_KEY:
        raise Exception("Anthropic API key not configured. Add ANTHROPIC_API_KEY to your .env file.")
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }
    
    data = {
        "model": CLAUDE_MODEL,
        "max_tokens": 8000,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "system": "You are an expert QA engineer with extensive experience in test automation and test planning."
    }
    
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers=headers,
        json=data
    )
    
    if response.status_code != 200:
        error_data = response.json()
        error_msg = error_data.get("error", {}).get("message", str(error_data))
        raise Exception(f"Claude API error: {error_msg}")
    
    return response.json()["content"][0]["text"]

def call_openai(prompt):
    """Call OpenAI API"""
    if not OPENAI_API_KEY:
        raise Exception("OpenAI API key not configured. Add OPENAI_API_KEY to your .env file.")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    data = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "You are an expert QA engineer with extensive experience in test automation and test planning."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 8000
    }
    
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=data
    )
    
    if response.status_code != 200:
        error_msg = response.json().get("error", {}).get("message", "Unknown error")
        raise Exception(f"OpenAI API error: {error_msg}")
    
    return response.json()["choices"][0]["message"]["content"]

def call_github(prompt):
    """Call GitHub Models (Copilot) API"""
    if not GITHUB_TOKEN:
        raise Exception("GitHub token not configured. Add GITHUB_TOKEN to your .env file.")
    
    # Use selected model from session state if available, else use .env default
    selected_model = st.session_state.get('github_model', GITHUB_MODEL)
    
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json"
    }
    data = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": "You are an expert QA engineer with extensive experience in test automation and test planning."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.7
    }
    response = requests.post(
        "https://models.github.ai/inference/chat/completions",
        headers=headers,
        json=data
    )
    if response.status_code != 200:
        try:
            error_msg = response.json()
        except Exception:
            error_msg = response.text
        raise Exception(f"GitHub Models API error: {error_msg}")
    resp = response.json()
    # GitHub Models returns choices/message/content similar to OpenAI
    return resp.get("choices", [{}])[0].get("message", {}).get("content", "")

# Check if at least one API key is available
if not GEMINI_API_KEY and not OPENAI_API_KEY and not ANTHROPIC_API_KEY and not GITHUB_TOKEN:
    # Do not stop the app; allow user to enter keys in the sidebar
    pass


# Custom CSS for styling
st.markdown("""
<style>
:root {
    --primary: #2D1B69;
    --primary-light: #4A3A8C;
    --primary-dark: #1E1247;
    --secondary: #2ecc71;
    --dark: #2b2b2b;
    --light: #f8f8f8;
    --gray: #e0e0e0;
    --warning: #ff9800;
}
/* Hide default password reveal button in Edge/Internet Explorer */
input[type="password"]::-ms-reveal,
input[type="password"]::-ms-clear {
    display: none;
}
.header {
    color: var(--primary);
    padding: 15px 0;
    border-bottom: 3px solid var(--primary);
    margin-bottom: 20px;
}
.sidebar .sidebar-content {
    background-color: #f5f3fa;
}
.stButton>button {
    background-color: var(--primary);
    color: white;
    border-radius: 8px;
    padding: 12px 28px;
    font-weight: bold;
    transition: all 0.3s;
}
.stButton>button:hover {
    background-color: var(--primary-dark);
    transform: scale(1.05);
}
.stTextArea textarea {
    border: 2px solid var(--primary) !important;
    border-radius: 8px;
    padding: 12px;
}
.success-box {
    background-color: #e6f7e9;
    border-left: 5px solid var(--secondary);
    padding: 20px;
    margin: 25px 0;
    border-radius: 0 10px 10px 0;
}
.test-case-card {
    border: 1px solid var(--gray);
    border-radius: 10px;
    padding: 20px;
    margin: 15px 0;
    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    background-color: #ffffff;
    transition: transform 0.3s;
}
.test-case-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 6px 12px rgba(0,0,0,0.15);
}
.test-case-card h4 {
    color: var(--primary);
    border-bottom: 1px solid var(--gray);
    padding-bottom: 12px;
    margin-top: 0;
}
.highlight {
    background-color: #fffacd;
    padding: 4px 8px;
    border-radius: 5px;
    font-weight: bold;
}
.footer {
    text-align: center;
    padding: 25px;
    color: #666;
    font-size: 0.95rem;
    margin-top: 40px;
    border-top: 1px solid var(--gray);
}
.traceability-matrix {
    margin-top: 35px;
    border: 1px solid var(--gray);
    border-radius: 10px;
    padding: 20px;
    background-color: #f9f9f9;
}
.traceability-matrix h3 {
    color: var(--primary);
    margin-top: 0;
}
.search-results {
    background-color: #f0f8ff;
    padding: 20px;
    border-radius: 10px;
    margin: 15px 0;
}
.automation-code {
    background-color: var(--dark);
    color: var(--light);
    padding: 20px;
    border-radius: 10px;
    margin: 20px 0;
    font-family: 'Fira Code', monospace;
    overflow-x: auto;
}
.code-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 15px;
    padding-bottom: 10px;
    border-bottom: 1px solid #444;
}
.code-header h3 {
    color: var(--secondary);
    margin: 0;
}
.code-container {
    max-height: 500px;
    overflow-y: auto;
}
.btn-download {
    background-color: var(--secondary) !important;
    margin: 5px;
}
.btn-download:hover {
    background-color: #27ae60 !important;
}
.btn-generate {
    background-color: #9b59b6 !important;
}
.btn-generate:hover {
    background-color: #8e44ad !important;
}
.tab-content {
    padding: 20px 0;
}
.file-info {
    background-color: #e3f2fd;
    padding: 15px;
    border-radius: 8px;
    margin: 10px 0;
}
.form-section {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 20px;
    margin: 15px 0;
    background-color: #f9f9f9;
}
.form-header {
    background-color: #2D1B69;
    color: white;
    padding: 10px 15px;
    border-radius: 8px 8px 0 0;
    margin: -20px -20px 20px -20px;
}
.attachment-preview {
    max-width: 200px;
    max-height: 150px;
    border-radius: 5px;
    margin: 5px;
}
.framework-file {
    background-color: #f5f3fa;
    border-left: 4px solid #2D1B69;
    padding: 15px;
    margin: 10px 0;
    border-radius: 4px;
}
.file-name {
    font-weight: bold;
    color: #2D1B69;
}
.test-case-container {
    max-height: 600px;
    overflow-y: auto;
    padding: 15px;
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    margin: 15px 0;
}
.bulk-actions {
    display: flex;
    gap: 10px;
    margin-bottom: 20px;
    padding: 15px;
    background-color: #f8f9fa;
    border-radius: 8px;
}
.toast-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 1000;
}
.toast {
    padding: 15px 45px 15px 25px;
    background-color: #2ecc71;
    color: white;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    animation: fadeIn 0.3s ease-in-out;
    position: relative;
}
@keyframes fadeIn {
    0% { opacity: 0; transform: translateY(-20px); }
    100% { opacity: 1; transform: translateY(0); }
}
.draggable-item {
    padding: 12px;
    margin: 8px 0;
    background-color: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    cursor: grab;
    transition: all 0.2s;
}
.draggable-item:hover {
    background-color: #e9ecef;
    transform: translateY(-2px);
}
.draggable-item.dragging {
    opacity: 0.5;
    border: 2px dashed #2D1B69;
}
.combined-toggle {
    background-color: #e3f2fd;
    padding: 15px;
    border-radius: 10px;
    margin-bottom: 20px;
}
.test-plan-output {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    padding: 25px;
    margin: 20px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}
.test-plan-output h1, .test-plan-output h2, .test-plan-output h3 {
    color: var(--primary);
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 10px;
    margin-top: 25px;
}
.test-plan-output table {
    width: 100%;
    border-collapse: collapse;
    margin: 15px 0;
}
.test-plan-output th, .test-plan-output td {
    border: 1px solid #ddd;
    padding: 10px;
    text-align: left;
}
.test-plan-output th {
    background-color: var(--primary);
    color: white;
}
.test-plan-output tr:nth-child(even) {
    background-color: #f9f9f9;
}
.test-plan-output tr:hover {
    background-color: #f5f3fa;
}
.tester-card {
    background-color: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
}
</style>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

# App header
st.markdown('<div class="header"><h1>🤖 RoboTest AI Suite</h1></div>', unsafe_allow_html=True)

# Initialize session state
if 'test_cases' not in st.session_state:
    st.session_state.test_cases = []
if 'automation_code' not in st.session_state:
    st.session_state.automation_code = {}
if 'current_tc_id' not in st.session_state:
    st.session_state.current_tc_id = ""
if 'framework_generated' not in st.session_state:
    st.session_state.framework_generated = False
if 'framework_code' not in st.session_state:
    st.session_state.framework_code = {}
if 'file_content' not in st.session_state:
    st.session_state.file_content = ""
if 'show_toast' not in st.session_state:
    st.session_state.show_toast = False
if 'toast_message' not in st.session_state:
    st.session_state.toast_message = ""
if 'toast_time' not in st.session_state:
    st.session_state.toast_time = 0
if 'toast_type' not in st.session_state:
    st.session_state.toast_type = "success"  # success, error, warning, info
if 'selected_test_cases' not in st.session_state:
    st.session_state.selected_test_cases = []
if 'editing_test_case' not in st.session_state:
    st.session_state.editing_test_case = None
if 'test_cases_str' not in st.session_state:
    st.session_state.test_cases_str = ""
if 'generation_mode' not in st.session_state:
    st.session_state.generation_mode = "combined"  # combined or separate
if 'test_plan_testers' not in st.session_state:
    st.session_state.test_plan_testers = []
if 'generated_test_plan' not in st.session_state:
    st.session_state.generated_test_plan = ""
if 'ai_provider' not in st.session_state:
    st.session_state.ai_provider = "auto"  # auto, gemini, or openai
    
# Create a copy for form manipulation
manual_test_case_form = {
    "id": "TC_MANUAL_001",
    "title": "",
    "preconditions": [],
    "test_data": [],
    "test_steps": [],
    "expected_results": [],
    "priority": "Medium",
    "attachments": []
}

# File processing functions
def extract_text_from_txt(file):
    return file.read().decode("utf-8")

def extract_text_from_pdf(file):
    text = ""
    pdf_reader = PyPDF2.PdfReader(file)
    for page in pdf_reader.pages:
        text += page.extract_text()
    return text

def extract_text_from_docx(file):
    doc = docx.Document(BytesIO(file.read()))
    return "\n".join([para.text for para in doc.paragraphs])

def extract_text_from_csv(file):
    df = pd.read_csv(file)
    return df.to_markdown()

def extract_text_from_xlsx(file):
    df = pd.read_excel(file)
    return df.to_markdown()

FILE_PROCESSORS = {
    "text/plain": extract_text_from_txt,
    "application/pdf": extract_text_from_pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": extract_text_from_docx,
    "text/csv": extract_text_from_csv,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": extract_text_from_xlsx,
    "text/markdown": extract_text_from_txt,  # Markdown is text
    "application/octet-stream": extract_text_from_txt # Fallback for some md files type detection
}

# Function to generate test cases with Gemini
def generate_test_cases_from_prompt(prompt, num_cases, priority, severity="Major", language="English"):
    try:
        # Language instruction
        language_instruction = ""
        if language == "Arabic":
            language_instruction = "\n        - IMPORTANT: Generate all test case content (title, preconditions, test_data, test_steps, expected_results) in Arabic language.\n        - Use proper Arabic text and formatting.\n        - Keep only the JSON keys in English, but all values must be in Arabic."
        else:
            language_instruction = "\n        - Generate all content in English language."
        
        prompt_template = f"""
        You are a senior QA engineer with 15+ years of experience. 
        Generate {num_cases} comprehensive test cases based on the following requirements:
        
        {prompt}
        
        Instructions:
        - Default Priority: {priority}
        - Default Severity: {severity} (Critical=System crash, Major=Feature broken, Normal=General severity, Minor=Minor issue){language_instruction}
        - Format test cases in JSON with this structure:
        {{
            "test_cases": [
                {{
                    "id": "TC_001",
                    "title": "Test case title",
                    "preconditions": ["Precondition 1", "Precondition 2"],
                    "test_data": ["Data 1", "Data 2"],
                    "test_steps": ["Step 1", "Step 2", "Step 3"],
                    "expected_results": ["Expected result 1", "Expected result 2"],
                    "priority": "High/Medium/Low",
                    "severity": "Critical/Major/Normal/Minor",
                    "attachments": []
                }}
            ]
        }}
        """
        
        response_text = call_ai(prompt_template)
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            json_str = json_match.group()
            data = json.loads(json_str)
            return data.get("test_cases", [])
        return []
    except Exception as e:
        st.error(f"Error generating test cases: {str(e)}")
        return []

# Function to generate Java Selenium code for a test case
def generate_test_case_automation_code(test_case, use_pom=True, use_oop=True, use_data_driven=False, use_bdd=False, use_bot_style=False, custom_prompt=""):
    try:
        # Build design pattern instructions
        design_instructions = []
        if use_pom:
            design_instructions.append("- Page Object Model with @FindBy annotations")
            design_instructions.append("- Separate Page classes for each page")
            design_instructions.append("- Use Selenium 'By' locators (id, name, cssSelector, xpath) for dynamic or computed elements")
            design_instructions.append("- Combine @FindBy for static elements with By-based lookups in actions and waits")
            design_instructions.append("- Prefer stable CSS/XPath strategies; avoid brittle absolute XPaths; include meaningful locator names")
        if use_oop:
            design_instructions.append("- Object-Oriented Programming (OOP) & SOLID Principles")
            design_instructions.append("- Inheritance: Use BaseTest and BasePage classes")
            design_instructions.append("- Component Objects: Create reusable components (Table, Navbar) extending BaseComponent")
            design_instructions.append("- Fluent Interfaces: Method chaining for actions (e.g., login.enterUser().enterPass().clickSubmit())")
            design_instructions.append("- Encapsulation: Private WebElements, public action methods")
        if use_data_driven:
            design_instructions.append("- Data-driven testing with @DataProvider")
            design_instructions.append("- External test data from JSON/Excel files")
        if use_bdd:
            design_instructions.append("- BDD style with descriptive method names")
            design_instructions.append("- Given-When-Then comments in test methods")
        if use_bot_style:
            design_instructions.append("- Action-Based Testing (Bot Style)")
            design_instructions.append("- Create an ActionBot class that abstracts all WebDriver actions")
            design_instructions.append("- Bot methods should be generic: click(locator), type(locator, text), isDisplayed(locator), waitForElement(locator)")
            design_instructions.append("- Page classes should use the Bot for all interactions, not WebDriver directly")
            design_instructions.append("- This abstracts Selenium logic away from Page Objects")

        # Critical Enhancements (From Enhancement Guide)
        design_instructions.append("- Explicit Waits: Use WebDriverWait with ExpectedConditions. NEVER use Thread.sleep().")
        design_instructions.append("- Logging: Use SLF4J/Log4j2. Log INFO for flow, DEBUG for actions, ERROR for failures.")
        design_instructions.append("- Test Isolation: Use @BeforeMethod for setup and @AfterMethod for teardown. No shared state.")
        design_instructions.append("- Exception Handling: Wrap actions in try-catch, capture screenshots on failure, log stack traces.")
        design_instructions.append("- Locator Strategy: Priority ID > Name > CSS. Avoid absolute XPath. Use data-testid if available.")
        
        if not use_pom and not use_oop and not use_bot_style:
            design_instructions.append("- Simple linear test script without Page Object Model")
            design_instructions.append("- All code in single test class")
        
        design_str = chr(10).join(design_instructions) if design_instructions else "- Simple script structure"
        
        # Custom prompt section
        custom_section = f"\n\nAdditional Requirements:\n{custom_prompt}" if custom_prompt.strip() else ""
        
        prompt_template = f"""
        You are a super senior QA automation engineer with over 30 years of enterprise experience. 
        Write complete, production-grade Selenium test automation code in Java using TestNG.
        
        Based on the following test case:
        - Title: {test_case['title']}
        - Steps: 
        {chr(10).join(test_case['test_steps'])}
        - Expected Results: 
        {chr(10).join(test_case['expected_results'])}
        
        Design Pattern Requirements:
{design_str}
        
        Use the following enterprise standards:
        - Java 17
        - Selenium WebDriver
        - TestNG
        - Factory Pattern for WebDriver
        - Singleton for configuration
        - Log4j2 logging
        - Allure reporting annotations
        - Explicit waits with WebDriverWait
        - Meaningful assertions
        - Thread-safe implementation
        {custom_section}
        
        Output the code in the following format:
        
        // FILE: src/main/java/com/qa/pages/[PageName]Page.java
        [Java code here]
        
        // FILE: src/test/java/com/qa/tests/[TestName]Test.java
        [Java code here]
        """
        
        response_text = call_ai(prompt_template)
        return response_text
    except Exception as e:
        st.error(f"Error generating automation code: {str(e)}")
        return ""

# Function to generate combined Java Selenium code for multiple test cases
def generate_combined_automation_code(test_cases, use_pom=True, use_oop=True, use_data_driven=False, use_bdd=False, use_bot_style=False, custom_prompt=""):
    try:
        test_cases_str = "\n\n".join(
            [f"Test Case {idx+1}: {tc['title']}\n"
             f"Steps:\n{chr(10).join(tc['test_steps'])}\n"
             f"Expected Results:\n{chr(10).join(tc['expected_results'])}"
             for idx, tc in enumerate(test_cases)]
        )
        
        # Build design pattern instructions
        design_instructions = []
        if use_pom:
            design_instructions.append("- Page Object Model with @FindBy annotations")
            design_instructions.append("- Separate Page classes for each page")
            design_instructions.append("- Use Selenium 'By' locators (id, name, cssSelector, xpath) for dynamic or computed elements")
            design_instructions.append("- Combine @FindBy for static elements with By-based lookups in actions and waits")
            design_instructions.append("- Prefer stable CSS/XPath strategies; avoid brittle absolute XPaths; include meaningful locator names")
        if use_oop:
            design_instructions.append("- Object-Oriented Programming (OOP) & SOLID Principles")
            design_instructions.append("- Inheritance: Use BaseTest and BasePage classes")
            design_instructions.append("- Component Objects: Create reusable components (Table, Navbar) extending BaseComponent")
            design_instructions.append("- Fluent Interfaces: Method chaining for actions (e.g., login.enterUser().enterPass().clickSubmit())")
            design_instructions.append("- Encapsulation: Private WebElements, public action methods")
        if use_data_driven:
            design_instructions.append("- Data-driven testing with @DataProvider")
            design_instructions.append("- External test data from JSON/Excel files")
        if use_bdd:
            design_instructions.append("- BDD style with descriptive method names")
            design_instructions.append("- Given-When-Then comments in test methods")
        if use_bot_style:
            design_instructions.append("- Action-Based Testing (Bot Style)")
            design_instructions.append("- Create an ActionBot class that abstracts all WebDriver actions")
            design_instructions.append("- Bot methods should be generic and handle waits/exceptions: bot.click(locator), bot.type(locator, text)")
            design_instructions.append("- Use the ActionBot in Page classes to handle element interactions")
            design_instructions.append("- Ensure Test classes focus on business logic, Page classes on element structure, and Bot on WebDriver commands")

        # Critical Enhancements (From Enhancement Guide)
        design_instructions.append("- Explicit Waits: Use WebDriverWait with ExpectedConditions. NEVER use Thread.sleep().")
        design_instructions.append("- Logging: Use SLF4J/Log4j2. Log INFO for flow, DEBUG for actions, ERROR for failures.")
        design_instructions.append("- Test Isolation: Use @BeforeMethod for setup and @AfterMethod for teardown. No shared state.")
        design_instructions.append("- Exception Handling: Wrap actions in try-catch, capture screenshots on failure, log stack traces.")
        design_instructions.append("- Locator Strategy: Priority ID > Name > CSS. Avoid absolute XPath. Use data-testid if available.")
        
        if not use_pom and not use_oop and not use_bot_style:
            design_instructions.append("- Simple linear test script without Page Object Model")
            design_instructions.append("- All code in single test class")
        
        design_str = chr(10).join(design_instructions) if design_instructions else "- Simple script structure"
        
        # Custom prompt section
        custom_section = f"\n\nAdditional Requirements:\n{custom_prompt}" if custom_prompt.strip() else ""
        
        prompt_template = f"""
        You are a super senior QA automation engineer with over 30 years of enterprise experience. 
        Write complete, production-grade Selenium test automation code in Java using TestNG.
        
        Create a SINGLE test class that includes test methods for the following test cases:
        
        {test_cases_str}
        
        Design Pattern Requirements:
{design_str}
        
        Use the following enterprise standards:
        - Java 17
        - Selenium WebDriver
        - TestNG
        - Factory Pattern for WebDriver
        - Singleton for configuration
        - Log4j2 logging
        - Allure reporting annotations
        - Explicit waits with WebDriverWait
        - Meaningful assertions
        - Thread-safe implementation
        {custom_section}
        
        Output the code in the following format:
        
        // FILE: src/main/java/com/qa/pages/[PageName]Page.java
        [Java code here]
        
        // FILE: src/test/java/com/qa/tests/GeneratedTestSuite.java
        [Java code for the combined test suite]
        """
        
        response_text = call_ai(prompt_template)
        return response_text
    except Exception as e:
        st.error(f"Error generating combined automation code: {str(e)}")
        return ""

# Function to parse generated code
def parse_generated_code(code):
    files = {}
    current_file = None
    current_content = []
    
    for line in code.split('\n'):
        if line.startswith("// FILE: "):
            if current_file:
                files[current_file] = "\n".join(current_content)
                current_content = []
            current_file = line.split("// FILE: ")[1].strip()
        elif current_file:
            current_content.append(line)
    
    if current_file and current_content:
        files[current_file] = "\n".join(current_content)
    
    return files

# Function to detect test type from test case content
def detect_test_type(test_case):
    """
    Auto-detect test type from title and steps
    Returns: 'ui', 'api', 'unit_spec', or 'mixed'
    """
    title_lower = test_case.get('title', '').lower()
    steps_text = ' '.join(test_case.get('test_steps', [])).lower()
    combined_text = title_lower + ' ' + steps_text
    
    # Check for API indicators
    api_keywords = ['api', 'endpoint', 'request', 'response', 'json', 'rest', 'http', 'post', 'get', 'put', 'delete', 'status code', 'payload']
    if any(word in combined_text for word in api_keywords):
        return 'api'
    
    # Check for unit test indicators
    unit_keywords = ['function', 'method', 'class', 'unit', 'component', 'module', 'service', 'repository', 'controller', 'calculate', 'validate', 'parse']
    if any(word in combined_text for word in unit_keywords):
        return 'unit_spec'
    
    # Check for UI indicators
    ui_keywords = ['click', 'navigate', 'button', 'page', 'ui', 'screen', 'form', 'input', 'field', 'dropdown', 'checkbox', 'login', 'submit', 'display', 'verify']
    if any(word in combined_text for word in ui_keywords):
        return 'ui'
    
    return 'ui'  # Default to UI if unsure

# Function to learn patterns from example test cases
def learn_from_examples(example_contents):
    """
    Analyze test case examples and extract writing patterns
    Returns learned rules as structured data
    """
    try:
        examples_text = "\n\n---\n\n".join(example_contents)
        
        prompt = f"""
        You are an expert QA analyst. Analyze the following test case examples and extract the writing patterns and style.
        
        EXAMPLES:
        {examples_text}
        
        Analyze and return a JSON object with the following structure:
        {{
            "id_format": "The ID format pattern (e.g., TC-001, TC_MODULE_001)",
            "title_style": "Description of title writing style",
            "precondition_style": "How preconditions are written (numbered, bulleted, etc.)",
            "steps_style": "How steps are written (verb usage, numbering, detail level)",
            "expected_results_style": "How expected results are written",
            "common_fields": ["List of common fields used"],
            "priority_values": ["Priority values used"],
            "tone": "Formal/Informal/Technical",
            "special_patterns": ["Any unique patterns noticed"],
            "summary": "Brief summary of the overall writing style"
        }}
        
        Return ONLY the JSON object, no additional text.
        """
        
        response_text = call_ai(prompt)
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            return json.loads(json_match.group())
        return None
    except Exception as e:
        st.error(f"Error learning from examples: {str(e)}")
        return None

# Function to generate test cases with learned rules
def generate_test_cases_with_rules(prompt, num_cases, priority, severity, language, learned_rules=None):
    """
    Generate test cases using custom rules learned from examples
    """
    try:
        rules_instruction = ""
        if learned_rules:
            rules_instruction = f"""
            
        IMPORTANT: Follow these learned patterns from the user's examples:
        - ID Format: {learned_rules.get('id_format', 'TC_001')}
        - Title Style: {learned_rules.get('title_style', 'Descriptive')}
        - Steps Style: {learned_rules.get('steps_style', 'Numbered, imperative verbs')}
        - Expected Results: {learned_rules.get('expected_results_style', 'Clear outcomes')}
        - Tone: {learned_rules.get('tone', 'Professional')}
        - Special Patterns: {', '.join(learned_rules.get('special_patterns', []))}
        """
        
        language_instruction = ""
        if language == "Arabic":
            language_instruction = "\n        - IMPORTANT: Generate all test case content in Arabic language. Keep only JSON keys in English."
        else:
            language_instruction = "\n        - Generate all content in English language."
        
        prompt_template = f"""
        You are a senior QA engineer with 15+ years of experience. 
        Generate {num_cases} comprehensive test cases based on the following requirements:
        
        {prompt}
        
        Instructions:
        - Default Priority: {priority}
        - Default Severity: {severity}{language_instruction}{rules_instruction}
        - Categorize each test case as: "positive", "negative", or "edge_case"
        - Format test cases in JSON with this structure:
        {{
            "test_cases": [
                {{
                    "id": "TC_001",
                    "title": "Test case title",
                    "category": "positive/negative/edge_case",
                    "test_type": "ui/api/unit_spec",
                    "preconditions": ["Precondition 1", "Precondition 2"],
                    "test_data": ["Data 1", "Data 2"],
                    "test_steps": ["Step 1", "Step 2", "Step 3"],
                    "expected_results": ["Expected result 1", "Expected result 2"],
                    "priority": "High/Medium/Low",
                    "severity": "Critical/Major/Normal/Minor",
                    "attachments": []
                }}
            ],
            "summary": {{
                "total": 0,
                "positive": 0,
                "negative": 0,
                "edge_cases": 0,
                "ui_tests": 0,
                "api_tests": 0,
                "unit_specs": 0
            }}
        }}
        """
        
        response_text = call_ai(prompt_template)
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            json_str = json_match.group()
            data = json.loads(json_str)
            return data.get("test_cases", []), data.get("summary", {})
        return [], {}
    except Exception as e:
        st.error(f"Error generating test cases with rules: {str(e)}")
        return [], {}

# Function to generate REST Assured API automation code
def generate_rest_assured_code(test_case, use_bdd=True, custom_prompt="", api_spec="", learned_style=None):
    """
    Generate REST Assured API automation code
    Supports BDD style (given/when/then)
    Can use API spec documentation and learned coding style
    """
    try:
        bdd_instruction = ""
        if use_bdd:
            bdd_instruction = """
        - Use BDD style with given().when().then() pattern
        - Add descriptive method chaining
        - Use RequestSpecBuilder for reusable specs"""
        else:
            bdd_instruction = """
        - Use standard RestAssured syntax
        - Keep it simple and readable"""
        
        custom_section = f"\n\nAdditional Requirements:\n{custom_prompt}" if custom_prompt.strip() else ""
        
        # Add API spec context if provided
        api_spec_section = ""
        if api_spec:
            api_spec_section = f"""
        
        API SPECIFICATION CONTEXT:
        Use the following API documentation to ensure accurate endpoint URLs, methods, request/response formats:
        
        {api_spec[:3000]}  # Limit to 3000 chars to avoid token limits
        """
        
        # Add learned style instructions if available
        style_section = ""
        if learned_style:
            style_section = f"""
        
        CODING STYLE REQUIREMENTS (Learn from user's existing code):
        - Class Naming: {learned_style.get('class_naming', 'Standard naming')}
        - Method Naming: {learned_style.get('method_naming', 'Standard naming')}
        - Assertion Style: {learned_style.get('assertion_style', 'Standard assertions')}
        - Request Style: {learned_style.get('request_style', 'Standard requests')}
        - Response Handling: {learned_style.get('response_handling', 'Standard handling')}
        - Package Structure: {learned_style.get('package_structure', 'com.qa.api')}
        
        IMPORTANT: Match the user's coding style as closely as possible.
        """
        
        prompt_template = f"""
        You are a senior QA automation engineer with expertise in REST API testing.
        Write complete, production-grade REST Assured test code in Java using TestNG.
        
        Based on the following test case:
        - Title: {test_case['title']}
        - Steps: 
        {chr(10).join(test_case['test_steps'])}
        - Expected Results: 
        {chr(10).join(test_case['expected_results'])}
        
        API Testing Requirements:{bdd_instruction}
        {api_spec_section}
        {style_section}
        
        Include:
        Include:
        - TestNG annotations (@Test, @BeforeMethod, @AfterMethod) for test isolation
        - Request specifications (headers, content type, base URI)
        - Response validation (status code, body, headers)
        - JSON path assertions
        - SLF4J/Log4j2 Logging: Log Request details and Response status
        - Robust Error handling
        - Allure reporting annotations
        {custom_section}
        
        Output the code in the following format:
        
        // FILE: src/test/java/com/qa/api/tests/{test_case['id']}ApiTest.java
        [Java code here]
        
        // FILE: src/main/java/com/qa/api/specs/RequestSpecs.java
        [Java code here]
        """
        
        response_text = call_ai(prompt_template)
        return response_text
    except Exception as e:
        st.error(f"Error generating REST Assured code: {str(e)}")
        return ""

# Function to generate unit test specifications for developers
def generate_unit_test_specifications(test_case, output_format="markdown"):
    """
    Generate detailed unit test specifications for developers
    Provides clear requirements for what to test at component level
    """
    try:
        prompt_template = f"""
        You are a senior QA engineer creating unit test specifications for developers.
        
        Based on the following test case:
        - Title: {test_case['title']}
        - Steps: 
        {chr(10).join(test_case['test_steps'])}
        - Expected Results: 
        {chr(10).join(test_case['expected_results'])}
        - Preconditions:
        {chr(10).join(test_case.get('preconditions', []))}
        
        Generate a detailed unit test specification document that developers can use to implement unit tests.
        
        Include the following sections:
        
        1. **Overview**
           - Brief description of what needs to be tested
           - Component/Module being tested
        
        2. **Test Scenarios**
           - List all test scenarios with clear descriptions
           - Include positive, negative, and edge cases
        
        3. **Input Parameters**
           - List all input parameters for each scenario
           - Include valid and invalid values
           - Specify data types and constraints
        
        4. **Expected Outputs**
           - Expected return values
           - Expected exceptions/errors
           - State changes to verify
        
        5. **Mock/Stub Requirements**
           - External dependencies to mock
           - Expected mock behavior
        
        6. **Test Data**
           - Sample test data for each scenario
           - Boundary values
        
        7. **Assertions**
           - Specific assertions to implement
           - Verification points
        
        Format the output in clean, readable Markdown that developers can directly use.
        """
        
        response_text = call_ai(prompt_template)
        return response_text
    except Exception as e:
        st.error(f"Error generating unit test specifications: {str(e)}")
        return ""

# Function to generate combined automation code for multiple test cases (REST Assured)
def generate_combined_rest_assured_code(test_cases, use_bdd=True, custom_prompt="", api_spec="", learned_style=None):
    """Generate REST Assured code for multiple test cases with optional API spec and learned style"""
    try:
        test_cases_str = "\n\n".join(
            [f"Test Case {idx+1}: {tc['title']}\n"
             f"Steps:\n{chr(10).join(tc['test_steps'])}\n"
             f"Expected Results:\n{chr(10).join(tc['expected_results'])}"
             for idx, tc in enumerate(test_cases)]
        )
        
        bdd_instruction = "- Use BDD style with given().when().then() pattern" if use_bdd else "- Use standard RestAssured syntax"
        custom_section = f"\n\nAdditional Requirements:\n{custom_prompt}" if custom_prompt.strip() else ""
        
        # Add API spec context if provided
        api_spec_section = ""
        if api_spec:
            api_spec_section = f"""
        
        API SPECIFICATION:
        {api_spec[:3000]}
        """
        
        # Add learned style instructions if available
        style_section = ""
        if learned_style:
            style_section = f"""
        
        CODING STYLE (Match user's existing code):
        - Class Naming: {learned_style.get('class_naming', 'Standard')}
        - Method Naming: {learned_style.get('method_naming', 'Standard')}
        - Assertion Style: {learned_style.get('assertion_style', 'Standard')}
        - Request Style: {learned_style.get('request_style', 'Standard')}
        """
        
        prompt_template = f"""
        You are a senior QA automation engineer. Write a complete REST Assured test suite.
        
        Test Cases to automate:
        {test_cases_str}
        
        Requirements:
        {bdd_instruction}
        - TestNG annotations (@BeforeMethod/@AfterMethod for isolation)
        - Response validation & JSON path assertions
        - Allure reporting
        - Base test class with common setup
        - SLF4J/Log4j2 Logging (INFO for flows, DEBUG for requests)
        - Robust Exception Handling
        {api_spec_section}
        {style_section}
        {custom_section}
        
        Output format:
        
        // FILE: src/test/java/com/qa/api/tests/ApiTestSuite.java
        [Java code]
        
        // FILE: src/test/java/com/qa/api/base/BaseApiTest.java
        [Java code]
        
        // FILE: src/main/java/com/qa/api/specs/RequestSpecs.java
        [Java code]
        """
        
        response_text = call_ai(prompt_template)
        return response_text
    except Exception as e:
        st.error(f"Error generating combined REST Assured code: {str(e)}")
        return ""



# Function to show toast notification using Streamlit's built-in toast
def show_toast(message, rerun_after=False):
    if rerun_after:
        # Store message in session state to show after rerun
        st.session_state.pending_toast = message
    else:
        st.toast(message)

# Show pending toast if exists (called at start of each page)
def show_pending_toast():
    if 'pending_toast' in st.session_state and st.session_state.pending_toast:
        st.toast(st.session_state.pending_toast)
        st.session_state.pending_toast = None

# Custom CSS for enhanced navigation - softer colors
st.markdown("""
<style>
/* Sidebar styling - softer gradient */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f8fafc 0%, #e2e8f0 100%);
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
    color: #334155;
}

/* Logo styling */
.sidebar-logo {
    display: flex;
    justify-content: center;
    padding: 15px 10px;
    margin-bottom: 10px;
}
</style>
<style>
/* Animation classes */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}
.animate-fade-in {
    animation: fadeIn 0.8s ease-out forwards;
}

/* Hover effects for cards */
div[data-testid="column"] > div > div > div > div.step-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 10px 20px rgba(0,0,0,0.1);
    transition: all 0.3s ease;
}
</style>
""", unsafe_allow_html=True)

# Add Sumerge logo to sidebar
st.sidebar.image("Sumergelogo.png", use_container_width=True)

# Simple sidebar navigation - single click works
# Simple sidebar navigation - single click works
st.sidebar.markdown("### 🧭 Navigation")

nav_options = ["🏠 Home", "🧪 Test Case Generator", "🤖 Test Automation", "📋 Test Plan Generator", "🐞 Bug Report Generator", "💬 AI Chat"]

# Check for query param navigation BEFORE widget is rendered
query_page = st.query_params.get("page")
if query_page:
    # Map query param to nav option
    page_mapping = {
        "Test Automation": "🤖 Test Automation",
        "Test Case Generator": "🧪 Test Case Generator",
        "Test Plan Generator": "📋 Test Plan Generator",
        "Bug Report Generator": "🐞 Bug Report Generator",
        "AI Chat": "💬 AI Chat",
        "Home": "🏠 Home"
    }
    if query_page in page_mapping:
        # Set the navigation in session state BEFORE widget renders
        st.session_state.nav_radio_widget = page_mapping[query_page]
        st.session_state.main_navigation = page_mapping[query_page]
        # Clear the query param
        st.query_params.clear()

# Determine index based on session state if available
radio_kwargs = {
    "label": "Select Page",
    "options": nav_options,
    "label_visibility": "collapsed",
    "key": "nav_radio_widget"
}

if "nav_radio_widget" not in st.session_state:
    default_index = 0
    if "main_navigation" in st.session_state:
        try:
            default_index = nav_options.index(st.session_state.main_navigation)
        except ValueError:
            default_index = 0
    radio_kwargs["index"] = default_index

selected_option = st.sidebar.radio(**radio_kwargs)

# Sync selection back to main_navigation (though we use selected_option primarily)
st.session_state.main_navigation = selected_option
page = selected_option

# Remove emoji prefix for page matching
page = page.split(" ", 1)[1] if " " in page else page

# AI Provider Configuration in Sidebar
# API Configuration moved to only show on Home page (see end of file)

# Home Page
if page == "Home":
    # Welcome Section
    st.markdown("""
    <div class="animate-fade-in" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 40px; border-radius: 20px; color: white; text-align: center; margin-bottom: 30px; 
                box-shadow: 0 10px 20px rgba(0,0,0,0.1);">
        <h1 style="margin-top: 0; font-size: 2.8em; font-weight: 700;">🚀 Welcome to RoboTest AI Suite</h1>
        <p style="font-size: 1.3em; margin-bottom: 20px; opacity: 0.9;">
            The Intelligent AI-Powered QA Platform
        </p>
        <div style="display: flex; justify-content: center; gap: 20px; flex-wrap: wrap;">
            <div style="background: rgba(255,255,255,0.2); padding: 10px 20px; border-radius: 30px; backdrop-filter: blur(5px);">
                🤖 Test Generation
            </div>
            <div style="background: rgba(255,255,255,0.2); padding: 10px 20px; border-radius: 30px; backdrop-filter: blur(5px);">
                ⚡ Auto-Automation
            </div>
            <div style="background: rgba(255,255,255,0.2); padding: 10px 20px; border-radius: 30px; backdrop-filter: blur(5px);">
                💬 AI Assistant
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Project Dashboard
    st.markdown("### 📊 Project Dashboard")
    dash_col1, dash_col2, dash_col3, dash_col4 = st.columns(4)
    
    with dash_col1:
        st.metric("Test Cases Created", len(st.session_state.test_cases), help="Total test cases in current session")
    with dash_col2:
        # Calculate generated scripts count
        script_count = 0
        if st.session_state.get('automation_code'):
             if "combined" in st.session_state.automation_code:
                 script_count = len(st.session_state.automation_code["combined"])
             else:
                 script_count = sum(len(v) for v in st.session_state.automation_code.values())
        st.metric("Scripts Generated", script_count, help="Automation scripts generated")
    with dash_col3:
        st.metric("Active AI Model", st.session_state.get('model_provider', 'Gemini'), help="Current AI provider")
    with dash_col4:
        st.metric("Bug Reports", st.session_state.get('bug_reports_count', 0), help="Bug reports generated in this session")
    
    st.markdown("---")

    # Feature Highlights (What's New)
    with st.expander("✨ What's New in v2.0", expanded=True):
        st.markdown("""
        - **🐞 Bug Report Generator**: Convert rough notes into professional bug reports (English/Arabic).
        - **⚡ Quick Commands**: Generate test cases instantly from templates or BRD files!
        - **🤖 Advanced Automation**: Now supports **Action-Based Testing** (Bot Style) and **REST Assured**.
        - **🧱 Enterprise Patterns**: Component Objects, Fluent Interfaces, and robust error handling.
        - **📝 Interactive Requirements**: Upload docs, preview, and refine content before generation.
        - **🔌 API Testing**: Upload Swagger/OpenAPI specs for precise test generation.
        """)

    # Features Section with Robot Emojis
    st.markdown("### 🤖 What Can Our AI Robots Do For You?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #667eea; margin-bottom: 15px;">
            <h4>🤖 Test Case Generation Robot</h4>
            <p>Automatically generates comprehensive test cases from requirements, user stories, or documentation. 
            Our AI understands your needs and creates detailed test scenarios in seconds.</p>
            <ul>
                <li>📝 Convert requirements to test cases</li>
                <li>⚡ Instant generation with AI</li>
                <li>✅ Industry-standard formats</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #764ba2; margin-bottom: 15px;">
            <h4>🦾 Automation Code Robot</h4>
            <p>Generates production-ready Java Selenium automation code with TestNG, Page Object Model, 
            Allure reports, and enterprise best practices built-in.</p>
            <ul>
                <li>☕ Clean Java Selenium code</li>
                <li>📦 Complete framework structure</li>
                <li>🎯 Ready to execute</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #f093fb; margin-bottom: 15px;">
            <h4>🦿 Test Plan Generation Robot</h4>
            <p>Creates comprehensive test plans with team allocation, timeline estimation, 
            and resource planning. Perfect for sprint planning and project kickoffs.</p>
            <ul>
                <li>📋 Complete test strategies</li>
                <li>👥 Team allocation plans</li>
                <li>⏱️ Timeline estimates</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #4facfe; margin-bottom: 15px;">
            <h4>🤖💬 AI Chat Assistant Robot</h4>
            <p>Your personal QA expert available 24/7. Ask questions about testing strategies, 
            automation frameworks, or get help with specific testing challenges.</p>
            <ul>
                <li>💡 Expert QA guidance</li>
                <li>🎓 Testing best practices</li>
                <li>🔧 Technical support</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Quick Start Guide
    st.markdown("---")
    st.markdown("### 🚀 Quick Start Guide")
    
    steps_col1, steps_col2, steps_col3 = st.columns(3)
    
    with steps_col1:
        st.markdown("""
        <div class="step-card" style="text-align: center; padding: 20px; background-color: #e3f2fd; border-radius: 10px; height: 100%; transition: transform 0.3s;">
            <div style="font-size: 3em;">🤖</div>
            <h4 style="color: #1976d2;">Step 1: Generate</h4>
            <p>Use the <strong>Test Case Generator</strong> to create test cases from your requirements</p>
        </div>
        """, unsafe_allow_html=True)
        st.button("Go to Generator", key="nav_gen_btn", use_container_width=True, 
                 on_click=lambda: st.session_state.update(main_navigation="🧪 Test Case Generator"))
    
    with steps_col2:
        st.markdown("""
        <div class="step-card" style="text-align: center; padding: 20px; background-color: #f3e5f5; border-radius: 10px; height: 100%; transition: transform 0.3s;">
            <div style="font-size: 3em;">⚡</div>
            <h4 style="color: #7b1fa2;">Step 2: Automate</h4>
            <p>Visit <strong>Test Automation</strong> to generate Java Selenium automation code</p>
        </div>
        """, unsafe_allow_html=True)
        st.button("Go to Automation", key="nav_auto_btn", use_container_width=True,
                 on_click=lambda: st.session_state.update(main_navigation="🤖 Test Automation"))
    
    with steps_col3:
        st.markdown("""
        <div class="step-card" style="text-align: center; padding: 20px; background-color: #e8f5e9; border-radius: 10px; height: 100%; transition: transform 0.3s;">
            <div style="font-size: 3em;">🎯</div>
            <h4 style="color: #388e3c;">Step 3: Execute</h4>
            <p>Download your framework and run automated tests in your environment</p>
        </div>
        """, unsafe_allow_html=True)
        st.button("Go to Test Plan", key="nav_plan_btn", use_container_width=True,
                 on_click=lambda: st.session_state.update(main_navigation="📋 Test Plan Generator"))
    
    # AI Provider Status
    st.markdown("---")
    st.markdown("### 🤖 AI Robot Status")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if GEMINI_API_KEY:
            st.markdown("""
            <div style="background-color: #c8e6c9; padding: 15px; border-radius: 8px; text-align: center;">
                <div style="font-size: 2em;">🤖✅</div>
                <h5 style="color: #2e7d32; margin: 10px 0;">Google Gemini Robot</h5>
                <p style="color: #1b5e20; margin: 0;">Online & Ready</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background-color: #ffecb3; padding: 15px; border-radius: 8px; text-align: center;">
                <div style="font-size: 2em;">🤖⚠️</div>
                <h5 style="color: #f57c00; margin: 10px 0;">Google Gemini Robot</h5>
                <p style="color: #e65100; margin: 0;">Offline - Not Configured</p>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        if ANTHROPIC_API_KEY:
            st.markdown("""
            <div style="background-color: #c8e6c9; padding: 15px; border-radius: 8px; text-align: center;">
                <div style="font-size: 2em;">🦾✅</div>
                <h5 style="color: #2e7d32; margin: 10px 0;">Claude AI Robot</h5>
                <p style="color: #1b5e20; margin: 0;">Online & Ready</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background-color: #e1f5fe; padding: 15px; border-radius: 8px; text-align: center;">
                <div style="font-size: 2em;">🦾💤</div>
                <h5 style="color: #0277bd; margin: 10px 0;">Claude AI Robot</h5>
                <p style="color: #01579b; margin: 0;">Sleeping - Not Configured</p>
            </div>
            """, unsafe_allow_html=True)
    
    with col3:
        if OPENAI_API_KEY:
            st.markdown("""
            <div style="background-color: #c8e6c9; padding: 15px; border-radius: 8px; text-align: center;">
                <div style="font-size: 2em;">🦿✅</div>
                <h5 style="color: #2e7d32; margin: 10px 0;">OpenAI Robot</h5>
                <p style="color: #1b5e20; margin: 0;">Online & Ready</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background-color: #e1f5fe; padding: 15px; border-radius: 8px; text-align: center;">
                <div style="font-size: 2em;">🦿💤</div>
                <h5 style="color: #0277bd; margin: 10px 0;">OpenAI Robot</h5>
                <p style="color: #01579b; margin: 0;">Sleeping - Not Configured</p>
            </div>
            """, unsafe_allow_html=True)

    with col4:
        if GITHUB_TOKEN:
            st.markdown("""
            <div style="background-color: #c8e6c9; padding: 15px; border-radius: 8px; text-align: center;">
                <div style="font-size: 2em;">🐙✅</div>
                <h5 style="color: #2e7d32; margin: 10px 0;">GitHub Copilot</h5>
                <p style="color: #1b5e20; margin: 0;">Online & Ready</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background-color: #f3e5f5; padding: 15px; border-radius: 8px; text-align: center;">
                <div style="font-size: 2em;">🐙💤</div>
                <h5 style="color: #7b1fa2; margin: 10px 0;">GitHub Copilot</h5>
                <p style="color: #4a148c; margin: 0;">Sleeping - Not Configured</p>
            </div>
            """, unsafe_allow_html=True)

# Test Case Generator Page
elif page == "Test Case Generator":
    # Show any pending toast messages at start of page
    show_pending_toast()
    
    st.subheader("🧪 Test Case Generator")
    
    with st.sidebar:
        st.header("Configuration")
        module_name = st.text_input("**Module Name**", value="ReyadaServices", 
                                  help="Used in test case IDs (e.g., TC_REYADA_001)")
        
        priority = st.selectbox(
            "**Default Priority**",
            ["High", "Medium", "Low"],
            index=1
        )
        
        severity = st.selectbox(
            "**Default Severity**",
            ["Critical", "Major", "Normal", "Minor"],
            index=2,
            help="Critical: System crash, Major: Feature broken, Normal: General severity , Minor: Minor issue "
        )
        
        language = st.selectbox(
            "**🌐 Test Case Language**",
            ["English", "Arabic"],
            index=0,
            help="Select the language for generated test cases. English is default."
        )
        
        st.markdown("---")
        st.markdown("**Form Options**")
        clear_after_save = st.checkbox(
            "🧹 Clear fields after save",
            value=True,
            help="When enabled, all form fields will be cleared after saving a test case",
            key="clear_fields_after_save"
        )
                # Move API Configuration down, but keep it accessible if needed here or handle via main sidebar area logic
        # Ideally, general config should be global, but if specific to this page, keep here.
        # User requested moving these ABOVE the API provider. 
        # Since API provider is in the global sidebar (lines 875-1017), we need to restructure the global sidebar code
        # or inject these settings earlier.
        
        # ACTUALLY, the better approach is to move the global API configuration block (lines 875-1017) 
        # to AFTER the page-specific sidebar content, OR move this page-specific content to the top of the sidebar.
        # The user wants "Configuration... to be above api provider".
        
        # Let's remove this block from here and instead add it to the top global sidebar area or 
        # use `st.sidebar` order. Streamlit renders sidebar elements in order of execution.
        # Currently, global sidebar (nav & API) runs FIRST (lines 853-1017).
        # Google Sheets Authentication
        st.markdown("---")
        st.markdown("**☁️ Google Sheets**")
        
        if 'google_creds' not in st.session_state:
            st.session_state.google_creds = None

        if not st.session_state.google_creds:
            st.info("Login to save test cases to Drive.")
            
            # Check if secrets or file exists
            has_secrets = False
            try:
                if "google_oauth" in st.secrets and "json" in st.secrets["google_oauth"]:
                    has_secrets = True
            except:
                pass
                
            has_file = os.path.exists('client_secret.json')
            
            if has_secrets or has_file:
                # Checkbox for deployment context
                # Default to Deployed URL (Cloud). Check this box only if running on localhost.
                use_localhost = st.checkbox("Running on Localhost?", value=False, key="sidebar_localhost_check")
                redirect_uri = LOCAL_REDIRECT_URI if use_localhost else DEPLOYED_REDIRECT_URI
                st.session_state["oauth_redirect_uri"] = redirect_uri
                
                try:
                    flow = get_google_auth_flow(redirect_uri=redirect_uri)
                    auth_url, _ = flow.authorization_url(
                        prompt='consent', 
                        access_type='offline',
                        include_granted_scopes='true'
                    )
                    st.link_button("🔑 Login with Google", auth_url, use_container_width=True)
                    st.caption(f"Redirecting to: `{redirect_uri}`")
                except Exception as e:
                    st.error(f"Config Error: {e}")
            else:
                 st.warning("⚠️ Google Config missing (Secrets or client_secret.json).")
        else:
             st.success("✅ Connected to Google")
             if st.button("🚪 Logout", key="sidebar_logout"):
                 st.session_state.google_creds = None
                 st.rerun()
                 
        st.markdown("---")
        st.markdown("**About**")
        st.markdown("Create professional test cases using AI")
    

    
    st.title("Test Case Generator")
    
    # User Guidance for Google Sheets
    if not st.session_state.get('google_creds'):
        st.info("💡 **Tip**: To save your TestCases directly to Google Sheets, please **Login via the Sidebar** BEFORE creating your test case to avoid losing your work during the reload.")
    
    # Quick Commands Section
    with st.expander("⚡ Quick Commands - Fast Test Generation", expanded=False):
        st.markdown("Select a template and provide minimal input for instant test case generation!")
        
        quick_command = st.selectbox(
            "Choose a quick command:",
            ["Select a template...", "📄 From BRD/Requirements File", "🔐 Login Feature Tests", 
             "📝 CRUD Operations", "🔗 API Endpoint Tests", "🛒 E-commerce Flow",
             "👤 User Registration", "🔍 Search Feature"],
            key="quick_command"
        )
        
        if quick_command != "Select a template...":
            st.markdown("---")
            
            # Dynamic inputs based on selected command
            if quick_command == "📄 From BRD/Requirements File":
                st.markdown("### 📄 Generate from BRD/Requirements")
                
                input_tab1, input_tab2 = st.tabs(["📂 Upload File", "✍️ Paste Text"])
                
                final_req_content = ""
                
                with input_tab1:
                    brd_quick_file = st.file_uploader(
                        "Upload BRD or Requirements Document",
                        type=['md', 'txt', 'pdf', 'docx', 'csv', 'xlsx'],
                        key="quick_brd"
                    )
                    
                    if brd_quick_file:
                        try:
                            if brd_quick_file.type in FILE_PROCESSORS:
                                raw_content = FILE_PROCESSORS[brd_quick_file.type](brd_quick_file)
                            else:
                                raw_content = brd_quick_file.read().decode('utf-8')
                                
                            st.success(f"✅ Loaded {len(raw_content)} characters")
                            st.caption("You can edit the extracted text below to focus on specific parts:")
                            final_req_content = st.text_area("Extracted Requirements Content", value=raw_content, height=200, key="brd_edit")
                        except Exception as e:
                            st.error(f"Error reading file: {e}")
                
                with input_tab2:
                    direct_input = st.text_area("Paste requirements here...", height=200, key="brd_paste")
                    if direct_input:
                        final_req_content = direct_input

                # Additional instructions
                focus_area = st.text_area("💡 Additional Instructions / Focus Area", 
                                        placeholder="e.g., 'Focus only on the payment gateway scenarios' or 'Ignore the admin panel section'",
                                        height=100)
                
                num_cases_quick = st.slider("Number of test cases", 5,10,15,20,30, key="quick_num_brd")
                
                if st.button("🚀 Generate from Requirements", key="gen_brd_quick", use_container_width=True, disabled=not final_req_content):
                    with st.spinner("Generating test cases from requirements..."):
                        try:
                            focus_instruction = f"\nUSER INSTRUCTIONS: {focus_area}" if focus_area else ""
                            prompt = f"Based on the following requirements, generate comprehensive test cases:{focus_instruction}\n\nREQUIREMENTS:\n{final_req_content}"
                            
                            generated = generate_test_cases_from_prompt(prompt, num_cases_quick, priority, severity, language)
                            if generated:
                                for i, tc in enumerate(generated):
                                    tc["id"] = f"TC_{module_name}_Q{len(st.session_state.test_cases) + i + 1}"
                                    tc["selected"] = False
                                st.session_state.test_cases.extend(generated)
                                show_toast(f"✅ Generated {len(generated)} test cases!")
                        except Exception as e:
                            st.error(f"Error: {e}")
            
            elif quick_command == "🔐 Login Feature Tests":
                st.markdown("### 🔐 Login Feature Test Cases")
                login_url = st.text_input("Login Page URL or Description", placeholder="https://example.com/login or 'Mobile app login screen'")
                has_2fa = st.checkbox("Has Two-Factor Authentication?")
                has_social = st.checkbox("Has Social Login (Google/Facebook)?")
                num_cases_quick = st.slider("Number of test cases", 5, 25, 12, key="quick_num_login")
                
                if st.button("🚀 Generate Login Tests", key="gen_login_quick", use_container_width=True, disabled=not login_url):
                    with st.spinner("Generating login test cases..."):
                        extras = []
                        if has_2fa: extras.append("2FA/OTP verification")
                        if has_social: extras.append("Social login (Google, Facebook)")
                        extras_str = f"\nAdditional features: {', '.join(extras)}" if extras else ""
                        
                        prompt = f"""Generate comprehensive test cases for a login feature:
                        Login Page: {login_url}
                        {extras_str}
                        
                        Include: valid login, invalid credentials, empty fields, locked accounts, password reset, remember me, session handling"""
                        
                        generated = generate_test_cases_from_prompt(prompt, num_cases_quick, priority, severity, language)
                        if generated:
                            for i, tc in enumerate(generated):
                                tc["id"] = f"TC_{module_name}_LOGIN{len(st.session_state.test_cases) + i + 1}"
                                tc["selected"] = False
                            st.session_state.test_cases.extend(generated)
                            show_toast(f"✅ Generated {len(generated)} login test cases!")
            
            elif quick_command == "📝 CRUD Operations":
                st.markdown("### 📝 CRUD Operations Test Cases")
                entity_name = st.text_input("Entity Name", placeholder="e.g., User, Product, Order")
                entity_fields = st.text_input("Main Fields (comma-separated)", placeholder="e.g., name, email, phone, address")
                num_cases_quick = st.slider("Number of test cases", 5, 25, 15, key="quick_num_crud")
                
                if st.button("🚀 Generate CRUD Tests", key="gen_crud_quick", use_container_width=True, disabled=not entity_name):
                    with st.spinner("Generating CRUD test cases..."):
                        prompt = f"""Generate comprehensive CRUD test cases for {entity_name} entity.
                        Fields: {entity_fields if entity_fields else 'standard fields'}
                        
                        Cover: Create new {entity_name}, Read/View {entity_name}, Update {entity_name}, Delete {entity_name},
                        validation, required fields, duplicate handling, bulk operations, filtering, sorting, pagination"""
                        
                        generated = generate_test_cases_from_prompt(prompt, num_cases_quick, priority, severity, language)
                        if generated:
                            for i, tc in enumerate(generated):
                                tc["id"] = f"TC_{module_name}_CRUD{len(st.session_state.test_cases) + i + 1}"
                                tc["selected"] = False
                            st.session_state.test_cases.extend(generated)
                            show_toast(f"✅ Generated {len(generated)} CRUD test cases!")
            
            elif quick_command == "🔗 API Endpoint Tests":
                st.markdown("### 🔗 API Endpoint Test Cases")
                api_input_method = st.radio("How to provide API info?", ["Type Endpoint", "Upload Technical Doc"], horizontal=True)
                
                api_info = ""
                if api_input_method == "Type Endpoint":
                    endpoint = st.text_input("Endpoint URL", placeholder="/api/v1/users")
                    method = st.selectbox("HTTP Method", ["GET", "POST", "PUT", "DELETE", "PATCH"])
                    params = st.text_input("Parameters (optional)", placeholder="id, name, status")
                    api_info = f"Endpoint: {method} {endpoint}\nParameters: {params}"
                else:
                    api_doc = st.file_uploader("Upload API Documentation", type=['json', 'yaml', 'yml', 'md', 'txt', 'pdf', 'docx'], key="quick_api_doc")
                    if api_doc:
                        try:
                            if api_doc.type in FILE_PROCESSORS:
                                api_info = FILE_PROCESSORS[api_doc.type](api_doc)
                            else:
                                api_info = api_doc.read().decode('utf-8')
                        except:
                            st.error("Could not read file")
                
                num_cases_quick = st.slider("Number of test cases", 5, 25, 12, key="quick_num_api")
                
                if st.button("🚀 Generate API Tests", key="gen_api_quick", use_container_width=True, disabled=not api_info):
                    with st.spinner("Generating API test cases..."):
                        prompt = f"""Generate comprehensive API test cases:
                        {api_info}
                        
                        Cover: success responses, error codes (400, 401, 403, 404, 500), validation, authentication, 
                        rate limiting, pagination, filtering, edge cases, boundary values"""
                        
                        generated = generate_test_cases_from_prompt(prompt, num_cases_quick, priority, severity, language)
                        if generated:
                            for i, tc in enumerate(generated):
                                tc["id"] = f"TC_{module_name}_API{len(st.session_state.test_cases) + i + 1}"
                                tc["selected"] = False
                            st.session_state.test_cases.extend(generated)
                            show_toast(f"✅ Generated {len(generated)} API test cases!")
            
            elif quick_command == "🛒 E-commerce Flow":
                st.markdown("### 🛒 E-commerce Flow Test Cases")
                features = st.multiselect("Select features to test:", 
                    ["Product Browse", "Shopping Cart", "Checkout", "Payment", "Order History", "Wishlist", "Reviews"])
                num_cases_quick = st.slider("Number of test cases", 5, 30, 15, key="quick_num_ecom")
                
                if st.button("🚀 Generate E-commerce Tests", key="gen_ecom_quick", use_container_width=True, disabled=not features):
                    with st.spinner("Generating e-commerce test cases..."):
                        prompt = f"""Generate comprehensive e-commerce test cases for:
                        Features: {', '.join(features)}
                        
                        Cover: add to cart, remove from cart, quantity changes, price calculations, 
                        discounts/coupons, shipping options, payment methods, order confirmation"""
                        
                        generated = generate_test_cases_from_prompt(prompt, num_cases_quick, priority, severity, language)
                        if generated:
                            for i, tc in enumerate(generated):
                                tc["id"] = f"TC_{module_name}_ECOM{len(st.session_state.test_cases) + i + 1}"
                                tc["selected"] = False
                            st.session_state.test_cases.extend(generated)
                            show_toast(f"✅ Generated {len(generated)} e-commerce test cases!")
            
            elif quick_command == "👤 User Registration":
                st.markdown("### 👤 User Registration Test Cases")
                reg_fields = st.text_input("Registration Fields", placeholder="e.g., name, email, password, phone")
                has_email_verify = st.checkbox("Email Verification Required?")
                num_cases_quick = st.slider("Number of test cases", 5, 20, 12, key="quick_num_reg")
                
                if st.button("🚀 Generate Registration Tests", key="gen_reg_quick", use_container_width=True):
                    with st.spinner("Generating registration test cases..."):
                        verify = "\n- Email verification flow" if has_email_verify else ""
                        prompt = f"""Generate comprehensive user registration test cases.
                        Fields: {reg_fields if reg_fields else 'standard registration fields'}
                        {verify}
                        
                        Cover: valid registration, validation errors, duplicate email, password requirements,
                        terms acceptance, optional fields, confirmation messages"""
                        
                        generated = generate_test_cases_from_prompt(prompt, num_cases_quick, priority, severity, language)
                        if generated:
                            for i, tc in enumerate(generated):
                                tc["id"] = f"TC_{module_name}_REG{len(st.session_state.test_cases) + i + 1}"
                                tc["selected"] = False
                            st.session_state.test_cases.extend(generated)
                            show_toast(f"✅ Generated {len(generated)} registration test cases!")
            
            elif quick_command == "🔍 Search Feature":
                st.markdown("### 🔍 Search Feature Test Cases")
                search_entity = st.text_input("What can be searched?", placeholder="e.g., Products, Users, Articles")
                search_filters = st.text_input("Available Filters (optional)", placeholder="e.g., category, price range, date")
                num_cases_quick = st.slider("Number of test cases", 5, 20, 10, key="quick_num_search")
                
                if st.button("🚀 Generate Search Tests", key="gen_search_quick", use_container_width=True, disabled=not search_entity):
                    with st.spinner("Generating search test cases..."):
                        prompt = f"""Generate comprehensive search feature test cases for searching: {search_entity}
                        Filters: {search_filters if search_filters else 'standard filters'}
                        
                        Cover: basic search, empty search, special characters, no results, partial matches,
                        filtering, sorting, pagination, search suggestions, recent searches"""
                        
                        generated = generate_test_cases_from_prompt(prompt, num_cases_quick, priority, severity, language)
                        if generated:
                            for i, tc in enumerate(generated):
                                tc["id"] = f"TC_{module_name}_SEARCH{len(st.session_state.test_cases) + i + 1}"
                                tc["selected"] = False
                            st.session_state.test_cases.extend(generated)
                            show_toast(f"✅ Generated {len(generated)} search test cases!")
    
    tab1, tab2, tab3 = st.tabs(["Manual Creation", "Generate from Requirements", "🎓 Learn from Examples"])
    
    with tab1:
        st.subheader("Create Manual Test Case")
        
        # Check if we need to reset the form (flag set after previous save)
        if st.session_state.get('reset_form', False):
            # Clear the flag
            st.session_state.reset_form = False
            # Use form with clear_on_submit to handle the actual clearing
        
        # Determine if form should clear on submit based on user preference
        should_clear = st.session_state.get('clear_fields_after_save', True)
        
        with st.form("manual_test_case_form", clear_on_submit=should_clear):
            st.markdown('<div class="form-section">', unsafe_allow_html=True)
            st.markdown('<div class="form-header"><h4>Test Case Details</h4></div>', unsafe_allow_html=True)
            
            title = st.text_input("Test Scenario*", 
                                 placeholder="User login with valid credentials")
            
            col1, col2 = st.columns(2)
            with col1:
                preconditions = st.text_area("Preconditions", 
                                           placeholder="1. User is registered\n2. Application is running", 
                                           height=100)
            with col2:
                test_data = st.text_area("Test Data", 
                                       placeholder="Username: testuser\nPassword: Test@123", 
                                       height=100)
            
            steps = st.text_area("Test Steps*", 
                                placeholder="1. Navigate to login page\n2. Enter username\n3. Enter password\n4. Click login button", 
                                height=150)
            
            expected = st.text_area("Expected Results*", 
                                  placeholder="1. User is redirected to dashboard\n2. Welcome message is displayed", 
                                  height=100)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="form-section">', unsafe_allow_html=True)
            st.markdown('<div class="form-header"><h4>Attachments</h4></div>', unsafe_allow_html=True)
            attachments = st.file_uploader("Upload files (any type)", 
                                         accept_multiple_files=True)
            
            # Display attachments preview
            if attachments:
                st.subheader("Attachment Preview")
                cols = st.columns(4)
                for i, file in enumerate(attachments):
                    if file.type.startswith('image'):
                        with cols[i % 4]:
                            st.image(file, caption=file.name, width=100)
                    else:
                        with cols[i % 4]:
                            st.info(f"📄 {file.name}")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            submitted = st.form_submit_button("Save Test Case", use_container_width=True)
            
            if submitted:
                if not title or not steps or not expected:
                    st.error("Please fill in all required fields (marked with *)")
                else:
                    # Process attachments
                    attachments_data = []
                    for file in attachments:
                        if file.type.startswith('image'):
                            content = base64.b64encode(file.read()).decode('utf-8')
                            attachments_data.append({
                                "name": file.name,
                                "type": file.type,
                                "content": content
                            })
                        else:
                            attachments_data.append({
                                "name": file.name,
                                "type": file.type,
                                "content": file.read()
                            })
                    
                    # Create test case object
                    test_case = {
                        "id": f"TC_{module_name}_{len(st.session_state.test_cases) + 1}",
                        "title": title,
                        "preconditions": [p.strip() for p in preconditions.split('\n') if p.strip()],
                        "test_data": [d.strip() for d in test_data.split('\n') if d.strip()],
                        "test_steps": [s.strip() for s in steps.split('\n') if s.strip()],
                        "expected_results": [e.strip() for e in expected.split('\n') if e.strip()],
                        "priority": priority,
                        "severity": severity,
                        "attachments": attachments_data,
                        "selected": False
                    }
                    
                    # Save to session state
                    st.session_state.test_cases.append(test_case)
                    
                    # Show appropriate toast message
                    if st.session_state.get('clear_fields_after_save', True):
                        show_toast("✅ Test case saved! Form cleared.")
                    else:
                        show_toast("✅ Test case saved successfully!")

                    # Store for post-save actions
                    st.session_state.last_saved_case = test_case
                    st.session_state.reset_form = True
                    st.rerun()
    

        # Post-Save Options (Download / Upload to Drive)
        if st.session_state.get('last_saved_case'):
            ls_case = st.session_state.last_saved_case
            st.success(f"Test Case '{ls_case['title']}' Saved Successfully!")
            
            ps_col1, ps_col2 = st.columns(2)
            
            with ps_col1:
                # Prepare Excel for single case
                single_df = pd.DataFrame([{
                    'ID': ls_case['id'],
                    'Title': ls_case['title'],
                    'Priority': ls_case['priority'],
                    'Preconditions': '\n'.join(ls_case['preconditions']),
                    'Test Data': '\n'.join(ls_case.get('test_data', [])),
                    'Test Steps': '\n'.join(ls_case['test_steps']),
                    'Expected Results': '\n'.join(ls_case['expected_results'])
                }])
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    single_df.to_excel(writer, index=False, sheet_name='Test Case')
                output.seek(0)
                
                st.download_button(
                    label="📥 Download as Excel",
                    data=output,
                    file_name=f"{ls_case['id']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_single_excel"
                )

            with ps_col2:
                # Check for Google Auth
                if not st.session_state.get('google_creds'):
                     st.warning("⚠️ To save to Google Sheets, please **Login** in the Sidebar.")
                     st.caption("Logging in will reload the page, so do it *before* creating test cases.")
                else:
                    # Authenticated User
                    sheet_name = st.text_input("Target Sheet Name", value="RoboTest Cases", key="target_sheet_name")
                    
                    if st.button("☁️ Save to Google Sheet", use_container_width=True, key="btn_save_gs"):
                        try:
                            # Authenticate gspread
                            client = gspread.authorize(st.session_state.google_creds)
                            
                            # Open or Create Sheet
                            try:
                                sheet = client.open(sheet_name).sheet1
                            except gspread.SpreadsheetNotFound:
                                sh = client.create(sheet_name)
                                sheet = sh.sheet1
                                sheet.append_row(['ID', 'Title', 'Priority', 'Severity', 'Preconditions', 'Test Data', 'Test Steps', 'Expected Results'])
                                
                            # Prepare row
                            row = [
                                ls_case['id'],
                                ls_case['title'],
                                ls_case['priority'],
                                ls_case.get('severity', 'Normal'),
                                '\n'.join(ls_case['preconditions']),
                                '\n'.join(ls_case.get('test_data', [])),
                                '\n'.join(ls_case['test_steps']),
                                '\n'.join(ls_case['expected_results'])
                            ]
                            
                            sheet.append_row(row)
                            st.success(f"✅ Saved to Google Sheet: {sheet_name}")
                        except Exception as e:
                            st.error(f"Failed to save to Google Sheet: {repr(e)}")
                            # Do not auto-logout, let user see error
                            # if "401" in str(e) or "403" in str(e):
                            #    st.session_state.google_creds = None
                            #    st.rerun()
            st.markdown("---")
            
    with tab2:
        st.subheader("Generate Test Cases from Requirements")
        
        # File upload section
        st.markdown("**Upload Requirements Document (Optional)**")
        uploaded_files = st.file_uploader(
            "Upload requirements files (PDF, DOCX, TXT, CSV, XLSX, MD)", 
            accept_multiple_files=True,
            type=['pdf', 'docx', 'txt', 'csv', 'xlsx', 'md'],
            key="requirements_uploader"
        )
        
        # Display uploaded files
        if uploaded_files:
            st.info(f"📁 {len(uploaded_files)} file(s) uploaded")
            for file in uploaded_files:
                st.caption(f"• {file.name} ({file.type})")
        
        st.markdown("**Or Enter Requirements Manually:**")
        user_story = st.text_area(
            "Enter your user story or requirements:",
            height=250,
            placeholder="As a registered user, I want to log in to the application so that I can access my dashboard...",
            label_visibility="collapsed"
        )
        
        num_test_cases = st.slider(
            "Number of Test Cases to Generate (1-50)",
            min_value=1,
            max_value=50,
            value=10,
            step=1
        )
        
        if st.button("Generate Test Cases", use_container_width=True):
            # Process uploaded files
            extracted_content = ""
            if uploaded_files:
                with st.spinner("Processing uploaded files..."):
                    for file in uploaded_files:
                        try:
                            if file.type in FILE_PROCESSORS:
                                content = FILE_PROCESSORS[file.type](file)
                                extracted_content += f"\n\n--- Content from {file.name} ---\n{content}"
                            else:
                                # Try to read as text for unknown types
                                try:
                                    content = file.read().decode("utf-8")
                                    extracted_content += f"\n\n--- Content from {file.name} ---\n{content}"
                                except:
                                    st.warning(f"Could not process {file.name}")
                        except Exception as e:
                            st.warning(f"Error processing {file.name}: {str(e)}")
            
            # Combine manual input and file content
            combined_requirements = user_story
            if extracted_content:
                combined_requirements = f"{user_story}\n\n{extracted_content}" if user_story else extracted_content
            
            if combined_requirements:
                with st.spinner(f"Generating {num_test_cases} professional test cases..."):
                    generated_cases = generate_test_cases_from_prompt(combined_requirements, num_test_cases, priority, severity, language)
                    
                    if generated_cases:
                        # Assign unique IDs
                        for i, tc in enumerate(generated_cases):
                            tc["id"] = f"TC_{module_name}_G{len(st.session_state.test_cases) + i + 1}"
                            tc["selected"] = False
                            # Ensure severity field exists
                            if "severity" not in tc:
                                tc["severity"] = severity
                            # Ensure attachments field exists
                            if "attachments" not in tc:
                                tc["attachments"] = []
                        
                        st.session_state.test_cases.extend(generated_cases)
                        show_toast(f"✅ Successfully generated {len(generated_cases)} test cases!")
                    else:
                        st.error("Failed to generate test cases. Please try again with more specific requirements.")
            else:
                st.warning("Please enter requirements or upload a file to generate test cases")
    
    with tab3:
        st.subheader("🎓 Learn from Your Examples")
        st.markdown("""
        Upload your existing test cases as examples, and the AI will **learn your writing style** 
        to generate new test cases that match your format and conventions.
        """)
        
        # Initialize session state for learned rules
        if 'learned_rules' not in st.session_state:
            st.session_state.learned_rules = None
        
        # Step 1: Upload Examples
        st.markdown("### Step 1: Upload Example Test Cases")
        st.info("📁 Upload 3-5 of your best test case examples (MD, TXT, PDF, DOCX)")
        
        example_files = st.file_uploader(
            "Upload example test cases",
            accept_multiple_files=True,
            type=['md', 'txt', 'pdf', 'docx'],
            key="example_uploader"
        )
        
        if example_files:
            st.success(f"✅ {len(example_files)} example(s) uploaded")
            for f in example_files:
                with st.expander(f"📄 {f.name}"):
                    try:
                        if f.type in FILE_PROCESSORS:
                            content = FILE_PROCESSORS[f.type](f)
                        else:
                            content = f.read().decode('utf-8')
                            f.seek(0)
                        st.text(content[:500] + "..." if len(content) > 500 else content)
                    except:
                        st.warning("Could not preview this file")
        
        # Step 2: Learn Patterns
        st.markdown("### Step 2: Analyze Patterns")
        
        if st.button("🔍 Learn from Examples", use_container_width=True, disabled=not example_files):
            with st.spinner("Analyzing your test case examples..."):
                # Extract content from all examples
                example_contents = []
                for f in example_files:
                    try:
                        if f.type in FILE_PROCESSORS:
                            content = FILE_PROCESSORS[f.type](f)
                        else:
                            content = f.read().decode('utf-8')
                            f.seek(0)
                        example_contents.append(content)
                    except Exception as e:
                        st.warning(f"Could not process {f.name}: {e}")
                
                if example_contents:
                    learned = learn_from_examples(example_contents)
                    if learned:
                        st.session_state.learned_rules = learned
                        show_toast("✅ Successfully learned patterns from your examples!")
                    else:
                        st.error("Could not learn patterns. Please try with different examples.")
        
        # Display learned patterns
        if st.session_state.learned_rules:
            st.markdown("### 📊 Learned Patterns")
            rules = st.session_state.learned_rules
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**ID Format:** `{rules.get('id_format', 'N/A')}`")
                st.markdown(f"**Title Style:** {rules.get('title_style', 'N/A')}")
                st.markdown(f"**Tone:** {rules.get('tone', 'N/A')}")
            with col2:
                st.markdown(f"**Steps Style:** {rules.get('steps_style', 'N/A')}")
                st.markdown(f"**Expected Results:** {rules.get('expected_results_style', 'N/A')}")
            
            if rules.get('special_patterns'):
                st.markdown("**Special Patterns:**")
                for pattern in rules.get('special_patterns', []):
                    st.markdown(f"- {pattern}")
            
            st.info(f"💡 **Summary:** {rules.get('summary', 'N/A')}")
            
            # Step 3: Generate with Learned Style
            st.markdown("### Step 3: Generate Test Cases with Learned Style")
            
            # Option to upload BRD or enter requirements
            req_input_method = st.radio(
                "How would you like to provide requirements?",
                ["📝 Type Requirements", "📁 Upload BRD/Requirements File", "🔄 Both"],
                horizontal=True,
                key="req_input_method"
            )
            
            learn_requirements = ""
            
            # Text input for requirements
            if req_input_method in ["📝 Type Requirements", "🔄 Both"]:
                learn_requirements = st.text_area(
                    "Enter requirements to generate test cases:",
                    height=150,
                    placeholder="Describe the feature or functionality you want to test...",
                    key="learn_requirements"
                )
            
            # File upload for BRD
            if req_input_method in ["📁 Upload BRD/Requirements File", "🔄 Both"]:
                brd_file = st.file_uploader(
                    "Upload BRD or Requirements Document",
                    type=['md', 'txt', 'pdf', 'docx', 'csv', 'xlsx'],
                    key="brd_uploader",
                    help="Upload your Business Requirements Document, User Stories, or any requirements file"
                )
                
                if brd_file:
                    st.success(f"✅ Uploaded: {brd_file.name}")
                    try:
                        # Extract content from the uploaded file
                        if brd_file.type in FILE_PROCESSORS:
                            brd_content = FILE_PROCESSORS[brd_file.type](brd_file)
                        else:
                            brd_content = brd_file.read().decode('utf-8')
                            brd_file.seek(0)
                        
                        # Show preview
                        with st.expander("📄 Preview uploaded requirements", expanded=False):
                            st.text(brd_content[:1000] + "..." if len(brd_content) > 1000 else brd_content)
                        
                        # Combine with typed requirements if "Both" is selected
                        if req_input_method == "🔄 Both" and learn_requirements:
                            learn_requirements = f"{learn_requirements}\n\n--- Uploaded Requirements ---\n\n{brd_content}"
                        else:
                            learn_requirements = brd_content
                    except Exception as e:
                        st.error(f"Could not read file: {e}")
            
            learn_col1, learn_col2 = st.columns(2)
            with learn_col1:
                learn_num_cases = st.slider("Number of test cases", 1, 30, 10, key="learn_num")
            with learn_col2:
                learn_test_type = st.selectbox(
                    "Test Type",
                    ["All Types", "UI Tests", "API Tests", "Unit Test Specs"],
                    key="learn_test_type"
                )
            
            # Enable button if we have requirements from either source
            has_requirements = bool(learn_requirements and learn_requirements.strip())
            
            if st.button("🚀 Generate with Learned Style", use_container_width=True, disabled=not has_requirements):
                with st.spinner(f"Generating {learn_num_cases} test cases with your style..."):
                    generated, summary = generate_test_cases_with_rules(
                        learn_requirements, 
                        learn_num_cases, 
                        priority, 
                        severity, 
                        language,
                        st.session_state.learned_rules
                    )
                    
                    if generated:
                        # Assign unique IDs and add to test cases
                        for i, tc in enumerate(generated):
                            tc["id"] = f"TC_{module_name}_L{len(st.session_state.test_cases) + i + 1}"
                            tc["selected"] = False
                            if "severity" not in tc:
                                tc["severity"] = severity
                            if "attachments" not in tc:
                                tc["attachments"] = []
                        
                        st.session_state.test_cases.extend(generated)
                        
                        # Show summary
                        if summary:
                            st.success(f"""
                            ✅ Generated {len(generated)} test cases!
                            📊 **Summary:** Positive: {summary.get('positive', 0)} | Negative: {summary.get('negative', 0)} | Edge Cases: {summary.get('edge_cases', 0)}
                            """)
                        else:
                            show_toast(f"✅ Generated {len(generated)} test cases with your style!")
                    else:
                        st.error("Failed to generate test cases. Please try again.")
            
            # Option to clear learned rules
            if st.button("🗑️ Clear Learned Patterns", key="clear_rules"):
                st.session_state.learned_rules = None
                st.rerun()

    
    # Export to Excel function
    def export_test_cases_to_excel(test_cases):
        """Convert test cases to Excel file"""
        data = []
        for tc in test_cases:
            data.append({
                'ID': tc['id'],
                'Title': tc['title'],
                'Priority': tc['priority'],
                'Preconditions': '\n'.join(tc.get('preconditions', [])),
                'Test Data': '\n'.join(tc.get('test_data', [])),
                'Test Steps': '\n'.join(tc.get('test_steps', [])),
                'Expected Results': '\n'.join(tc.get('expected_results', []))
            })
        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Test Cases')
        output.seek(0)
        return output
    
    # Bulk actions
    if st.session_state.test_cases:
        st.subheader("Test Case Management")
        
        # Google Sheet Configuration for Bulk Actions
        target_sheet_bulk = "RoboTest Cases"
        if st.session_state.get('google_creds'):
             target_sheet_bulk = st.text_input("Target Google Sheet", value="RoboTest Cases", key="bulk_sheet_name")

        # Export to Excel button (All)
        excel_file = export_test_cases_to_excel(st.session_state.test_cases)
        st.download_button(
            label="📥 Export All Test Cases to Excel",
            data=excel_file,
            file_name="test_cases.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="export_excel"
        )
        
        # Bulk actions container
        with st.container():
            st.markdown('<div class="bulk-actions">', unsafe_allow_html=True)
            
            # Select All button (using button instead of checkbox for reliable behavior)
            col_sel1, col_sel2, col_sel3 = st.columns([1, 1, 3])
            with col_sel1:
                if st.button("✅ Select All", key="select_all_btn", use_container_width=True):
                    for tc in st.session_state.test_cases:
                        st.session_state[f"select_{tc['id']}"] = True
                    st.rerun()
            with col_sel2:
                if st.button("⬜ Deselect All", key="deselect_all_btn", use_container_width=True):
                    for tc in st.session_state.test_cases:
                        st.session_state[f"select_{tc['id']}"] = False
                    st.rerun()
            
            # Copy all button
            if st.button("Copy All Test Cases", key="copy_all"):
                # Create a copyable string of all test cases
                test_cases_str = "\n\n".join(
                    [f"ID: {tc['id']}\nTitle: {tc['title']}\nPriority: {tc['priority']}\nSeverity: {tc.get('severity', 'N/A')}\n\nSteps:\n" + 
                     "\n".join([f"- {step}" for step in tc['test_steps']]) +
                     "\n\nExpected Results:\n" + 
                     "\n".join([f"- {result}" for result in tc['expected_results']])
                    for tc in st.session_state.test_cases]
                )
                
                st.session_state.test_cases_str = test_cases_str
                st.rerun()
            
            # Calculate selected count using session state keys
            selected_count = sum(1 for tc in st.session_state.test_cases 
                               if st.session_state.get(f"select_{tc['id']}", False))
            
            if selected_count > 0:
                # Group buttons for selected actions
                b_col1, b_col2, b_col3 = st.columns(3)
                
                selected_cases = [
                        tc for tc in st.session_state.test_cases 
                        if st.session_state.get(f"select_{tc['id']}", False)
                    ]

                with b_col1:
                    if st.button(f"🚀 Automate ({selected_count})", key="gen_selected"):
                        st.session_state.selected_test_cases = selected_cases
                        st.query_params["page"] = "Test Automation"
                        st.rerun()
                
                with b_col2:
                    # Export Selected to Excel
                    excel_selected = export_test_cases_to_excel(selected_cases)
                    st.download_button(
                        label=f"📥 Export ({selected_count}) to Excel",
                        data=excel_selected,
                        file_name=f"selected_test_cases_{selected_count}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                        key="export_selected_excel"
                    )

                with b_col3:
                    # Save Selected to Google Sheet
                    if st.session_state.get('google_creds'):
                        if st.button(f"☁️ Save ({selected_count}) to Sheet", key="save_selected_gs"):
                             try:
                                client = gspread.authorize(st.session_state.google_creds)
                                try:
                                    sheet = client.open(target_sheet_bulk).sheet1
                                except gspread.SpreadsheetNotFound:
                                    sh = client.create(target_sheet_bulk)
                                    sheet = sh.sheet1
                                    sheet.append_row(['ID', 'Title', 'Priority', 'Severity', 'Preconditions', 'Test Data', 'Test Steps', 'Expected Results'])
                                
                                # Bulk prepare rows
                                rows_to_append = []
                                for tc in selected_cases:
                                    rows_to_append.append([
                                        tc['id'],
                                        tc['title'],
                                        tc['priority'],
                                        tc.get('severity', 'Normal'),
                                        '\n'.join(tc['preconditions']),
                                        '\n'.join(tc.get('test_data', [])),
                                        '\n'.join(tc['test_steps']),
                                        '\n'.join(tc['expected_results'])
                                    ])
                                
                                sheet.append_rows(rows_to_append)
                                st.success(f"✅ Saved {selected_count} cases to '{target_sheet_bulk}'")
                                time.sleep(2)
                             except Exception as e:
                                st.error(f"Failed: {e}")
                    else:
                         st.button(f"☁️ Save ({selected_count})", disabled=True, help="Login to Google first")

            else:
                st.info("Select test cases to perform bulk actions")
            
            # Delete selected button
            if st.button("🗑️ Delete Selected", key="delete_selected"):
                # Count selected BEFORE deleting using session state
                count_to_delete = sum(1 for tc in st.session_state.test_cases 
                                     if st.session_state.get(f"select_{tc['id']}", False))
                if count_to_delete > 0:
                    # Get IDs to delete
                    ids_to_delete = [tc['id'] for tc in st.session_state.test_cases 
                                    if st.session_state.get(f"select_{tc['id']}", False)]
                    # Remove from test_cases
                    st.session_state.test_cases = [
                        tc for tc in st.session_state.test_cases 
                        if not st.session_state.get(f"select_{tc['id']}", False)
                    ]
                    # Clean up session state keys for deleted items
                    for tc_id in ids_to_delete:
                        if f"select_{tc_id}" in st.session_state:
                            del st.session_state[f"select_{tc_id}"]
                    show_toast(f"✅ Deleted {count_to_delete} test cases", rerun_after=True)
                    st.rerun()
                else:
                    show_toast("⚠️ No test cases selected")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Test case container with scroll
        st.markdown('<div class="test-case-container">', unsafe_allow_html=True)
        
        # Display all test cases
        for idx, test_case in enumerate(st.session_state.test_cases):
            with st.container():
                col1, col2, col3 = st.columns([1, 10, 2])
                
                with col1:
                    # Initialize checkbox state if not exists
                    if f"select_{test_case['id']}" not in st.session_state:
                        st.session_state[f"select_{test_case['id']}"] = False
                    # Checkbox for selection - controlled by session state key only
                    st.checkbox("", 
                               key=f"select_{test_case['id']}",
                               label_visibility="collapsed")
                
                with col2:
                    # Test case card
                    with st.expander(f"{test_case['id']}: {test_case['title']}", expanded=False):
                        st.markdown(f"**Priority:** `{test_case['priority']}` | **Severity:** `{test_case.get('severity', 'N/A')}`")
                        
                        if test_case['preconditions']:
                            st.markdown("**Preconditions:**")
                            for pre in test_case['preconditions']:
                                st.markdown(f"- {pre}")
                        
                        if test_case.get('test_data'):
                            st.markdown("**Test Data:**")
                            for data in test_case['test_data']:
                                st.markdown(f"- {data}")
                        
                        st.markdown("**Steps:**")
                        for step in test_case['test_steps']:
                            st.markdown(f"- {step}")
                        
                        st.markdown("**Expected Results:**")
                        for result in test_case['expected_results']:
                            st.markdown(f"- {result}")
                        
                        if test_case.get('attachments'):
                            st.markdown("**Attachments:**")
                            for attachment in test_case['attachments']:
                                if attachment['type'].startswith('image'):
                                    st.image(base64.b64decode(attachment['content']), caption=attachment['name'], use_column_width=True)
                                else:
                                    st.download_button(
                                        label=f"Download {attachment['name']}",
                                        data=attachment['content'],
                                        file_name=attachment['name'],
                                        mime=attachment['type'],
                                        key=f"attach_{test_case['id']}_{attachment['name']}"
                                    )
                
                with col3:
                    # Edit button
                    if st.button("✏️ Edit", key=f"edit_{test_case['id']}"):
                        st.session_state.editing_test_case = test_case
                        st.session_state.editing_index = idx
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    else:
        st.info("No test cases created yet. Create or generate test cases to get started.")
    
    # Copy all test cases modal
    if st.session_state.test_cases_str:
        st.text_area("Copy all test cases", 
                    st.session_state.test_cases_str, 
                    height=300)
        if st.button("Close", key="close_copy"):
            st.session_state.test_cases_str = ""
            st.rerun()
    
    # Edit test case modal
    if st.session_state.editing_test_case:
        test_case = st.session_state.editing_test_case
        idx = st.session_state.editing_index
        
        with st.form(f"edit_form_{test_case['id']}"):
            st.subheader(f"Editing: {test_case['id']}")
            
            title = st.text_input("Test Scenario*", value=test_case['title'])
            
            col1, col2 = st.columns(2)
            with col1:
                preconditions = st.text_area("Preconditions", 
                                           value="\n".join(test_case['preconditions']), 
                                           height=100)
            with col2:
                test_data = st.text_area("Test Data", 
                                       value="\n".join(test_case.get('test_data', [])), 
                                       height=100)
            
            steps = st.text_area("Test Steps*", 
                                value="\n".join(test_case['test_steps']), 
                                height=150)
            
            expected = st.text_area("Expected Results*", 
                                  value="\n".join(test_case['expected_results']), 
                                  height=100)
            
            priority = st.selectbox(
                "Priority",
                ["High", "Medium", "Low"],
                index=["High", "Medium", "Low"].index(test_case['priority'])
            )
            
            # Form actions
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Save Changes", use_container_width=True):
                    # Update test case
                    st.session_state.test_cases[idx] = {
                        "id": test_case['id'],
                        "title": title,
                        "preconditions": [p.strip() for p in preconditions.split('\n') if p.strip()],
                        "test_data": [d.strip() for d in test_data.split('\n') if d.strip()],
                        "test_steps": [s.strip() for s in steps.split('\n') if s.strip()],
                        "expected_results": [e.strip() for e in expected.split('\n') if e.strip()],
                        "priority": priority,
                        "attachments": test_case.get('attachments', []),  # FIXED: Use get with default
                        "selected": test_case.get('selected', False)
                    }
                    st.session_state.editing_test_case = None
                    show_toast("✅ Test case created/updated successfully!")
                    
                    # Store last saved case for post-save actions
                    st.session_state.last_saved_case = st.session_state.test_cases[idx] if st.session_state.get('editing_test_case') else test_case
                    
                    st.session_state.editing_test_case = None
                    st.session_state.reset_form = True # Flag to clear form on next run if needed
                    st.rerun()  # FIXED: Changed from experimental_rerun to rerun
            
            with col2:
                if st.form_submit_button("Cancel", use_container_width=True):
                    st.session_state.editing_test_case = None
                    st.rerun()  # FIXED: Changed from experimental_rerun to rerun
        
        # Post-Save Options (Download / Upload to Drive)
        if st.session_state.get('last_saved_case'):
            ls_case = st.session_state.last_saved_case
            st.success(f"Test Case '{ls_case['title']}' Saved Successfully!")
            
            ps_col1, ps_col2 = st.columns(2)
            
            with ps_col1:
                # Prepare Excel for single case
                single_df = pd.DataFrame([{
                    'ID': ls_case['id'],
                    'Title': ls_case['title'],
                    'Priority': ls_case['priority'],
                    'Preconditions': '\n'.join(ls_case['preconditions']),
                    'Test Data': '\n'.join(ls_case.get('test_data', [])),
                    'Test Steps': '\n'.join(ls_case['test_steps']),
                    'Expected Results': '\n'.join(ls_case['expected_results'])
                }])
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    single_df.to_excel(writer, index=False, sheet_name='Test Case')
                output.seek(0)
                
                st.download_button(
                    label="📥 Download as Excel",
                    data=output,
                    file_name=f"{ls_case['id']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="dl_single_excel_edit"
                )

            with ps_col2:
                if st.button("☁️ Save to Google Sheet", use_container_width=True, key="btn_save_gs"):
                    if st.session_state.get('gs_creds') and st.session_state.get('gs_sheet_url'):
                        try:
                            # Authenticate
                            scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
                            creds = Credentials.from_service_account_info(st.session_state.gs_creds, scopes=scope)
                            client = gspread.authorize(creds)
                            
                            # Open sheet
                            try:
                                sheet = client.open_by_url(st.session_state.gs_sheet_url).sheet1
                            except gspread.SpreadsheetNotFound:
                                # Try opening by name
                                sheet = client.open(st.session_state.gs_sheet_url).sheet1
                                
                            # Prepare row
                            row = [
                                ls_case['id'],
                                ls_case['title'],
                                ls_case['priority'],
                                ls_case.get('severity', 'Normal'),
                                '\n'.join(ls_case['preconditions']),
                                '\n'.join(ls_case.get('test_data', [])),
                                '\n'.join(ls_case['test_steps']),
                                '\n'.join(ls_case['expected_results'])
                            ]
                            
                            # Check headers and add if empty
                            if not sheet.get_all_values():
                                sheet.append_row(['ID', 'Title', 'Priority', 'Severity', 'Preconditions', 'Test Data', 'Test Steps', 'Expected Results'])
                            
                            sheet.append_row(row)
                            st.success(f"✅ Saved to Google Sheet: {st.session_state.gs_sheet_url}")
                        except Exception as e:
                            st.error(f"Failed to save to Google Sheet: {str(e)}")
                    else:
                        st.warning("⚠️ Please configure Google Sheets credentials in the sidebar first.")
            st.markdown("---")

# Test Automation Page
elif page == "Test Automation":
    st.subheader("🤖 Test Automation Generator")
    
    if st.session_state.selected_test_cases:
        st.success(f"✅ {len(st.session_state.selected_test_cases)} test cases selected for automation")
        
        # Show selected test cases summary
        with st.expander("📋 Selected Test Cases", expanded=False):
            for tc in st.session_state.selected_test_cases:
                st.markdown(f"- **{tc['id']}**: {tc['title']}")
        
        st.markdown("---")
        
        # Framework Selection
        st.markdown("### 🛠️ Select Automation Framework")
        automation_framework = st.selectbox(
            "Choose framework based on your test type:",
            ["🖥️ Selenium WebDriver (UI Tests)", "🔗 REST Assured (API Tests)", "📋 Unit Test Specifications (For Developers)"],
            key="automation_framework"
        )
        
        # Generation mode selection (for Selenium and REST Assured)
        if "Selenium" in automation_framework or "REST Assured" in automation_framework:
            st.radio(
                "Generation Mode:",
                ["Combined Test Suite", "Separate Test Classes"],
                key="generation_mode",
                horizontal=True
            )
        
        # Design Pattern Options - shown based on framework selection
        st.markdown("### ⚙️ Code Generation Options")
        
        # Framework-specific options
        if "Selenium" in automation_framework:
            col_opt1, col_opt2 = st.columns(2)
            with col_opt1:
                use_pom = st.checkbox("📄 Use Page Object Model (POM)", value=True, 
                                      help="Separate page elements and actions into Page classes")
                use_oop = st.checkbox("🏗️ Use OOP Principles", value=True,
                                      help="Apply inheritance, encapsulation, and SOLID principles")
                use_bot_style = st.checkbox("🤖 Bot Style Architecture", value=False,
                                            help="Fluent/chainable Bot class for action sequences")
            with col_opt2:
                use_data_driven = st.checkbox("📊 Data-Driven Testing", value=False,
                                              help="Use @DataProvider for parameterized tests")
                use_bdd = st.checkbox("📝 BDD Style Comments", value=False,
                                      help="Add Given-When-Then style comments")
        elif "REST Assured" in automation_framework:
            # REST Assured specific options
            col_opt1, col_opt2 = st.columns(2)
            with col_opt1:
                use_bdd = st.checkbox("📝 BDD Style (given/when/then)", value=True,
                                      help="Use BDD style with given().when().then() pattern")
                use_data_driven = st.checkbox("📊 Data-Driven Testing", value=False,
                                              help="Use @DataProvider for parameterized API tests")
            with col_opt2:
                use_oop = st.checkbox("🏗️ Base Test Class", value=True,
                                      help="Create reusable base test class")
            use_pom = False
            use_bot_style = False
            
            st.markdown("---")
            
            # API Specification Upload Section
            st.markdown("### 📄 API Documentation (Optional)")
            st.info("Upload API specs (Swagger/OpenAPI) or technical docs from developers for more accurate test generation")
            
            api_spec_file = st.file_uploader(
                "Upload API Specification",
                type=['json', 'yaml', 'yml', 'md', 'txt', 'pdf', 'docx'],
                key="api_spec_uploader",
                help="Swagger, OpenAPI, Postman collection, or any API documentation"
            )
            
            api_spec_content = ""
            if api_spec_file:
                st.success(f"✅ Uploaded: {api_spec_file.name}")
                try:
                    if api_spec_file.type in FILE_PROCESSORS:
                        api_spec_content = FILE_PROCESSORS[api_spec_file.type](api_spec_file)
                    else:
                        api_spec_content = api_spec_file.read().decode('utf-8')
                        api_spec_file.seek(0)
                    
                    with st.expander("📋 Preview API Spec", expanded=False):
                        st.code(api_spec_content[:2000] + "..." if len(api_spec_content) > 2000 else api_spec_content)
                    
                    # Store in session state for use in generation
                    st.session_state.api_spec_content = api_spec_content
                except Exception as e:
                    st.error(f"Could not read file: {e}")
            
            st.markdown("---")
            
            # Learn from Existing REST Assured Scripts
            st.markdown("### 🎓 Learn from Your Scripts (Optional)")
            st.info("Upload your existing REST Assured scripts and AI will learn your coding style")
            
            example_scripts = st.file_uploader(
                "Upload Example REST Assured Scripts",
                type=['java', 'txt'],
                accept_multiple_files=True,
                key="rest_assured_examples",
                help="Upload 1-3 of your best REST Assured test scripts"
            )
            
            learned_script_style = None
            if example_scripts:
                st.success(f"✅ {len(example_scripts)} script(s) uploaded")
                
                # Preview uploaded scripts
                for script in example_scripts:
                    with st.expander(f"📄 {script.name}", expanded=False):
                        content = script.read().decode('utf-8')
                        script.seek(0)
                        st.code(content[:1500] + "..." if len(content) > 1500 else content, language='java')
                
                # Learn button
                if st.button("🔍 Learn from Scripts", key="learn_rest_scripts"):
                    with st.spinner("Analyzing your REST Assured coding style..."):
                        script_contents = []
                        for script in example_scripts:
                            content = script.read().decode('utf-8')
                            script.seek(0)
                            script_contents.append(content)
                        
                        # Use AI to learn patterns
                        learn_prompt = f"""
                        Analyze these REST Assured test scripts and extract the coding patterns and style:
                        
                        {chr(10).join(['---SCRIPT---' + chr(10) + s for s in script_contents])}
                        
                        Return a JSON with:
                        {{
                            "package_structure": "How packages are organized",
                            "class_naming": "Class naming convention",
                            "method_naming": "Method naming convention",
                            "assertion_style": "How assertions are written",
                            "request_style": "How requests are structured",
                            "response_handling": "How responses are validated",
                            "logging_approach": "Logging style used",
                            "special_patterns": ["List of unique patterns"]
                        }}
                        """
                        
                        try:
                            response = call_ai(learn_prompt)
                            json_match = re.search(r'\{[\s\S]*\}', response)
                            if json_match:
                                st.session_state.learned_rest_style = json.loads(json_match.group())
                                show_toast("✅ Learned your REST Assured coding style!")
                        except Exception as e:
                            st.error(f"Error learning style: {e}")
                
                # Display learned style
                if st.session_state.get('learned_rest_style'):
                    style = st.session_state.learned_rest_style
                    with st.expander("📊 Learned Style", expanded=True):
                        cols = st.columns(2)
                        with cols[0]:
                            st.markdown(f"**Class Naming:** {style.get('class_naming', 'N/A')}")
                            st.markdown(f"**Method Naming:** {style.get('method_naming', 'N/A')}")
                            st.markdown(f"**Request Style:** {style.get('request_style', 'N/A')}")
                        with cols[1]:
                            st.markdown(f"**Assertion Style:** {style.get('assertion_style', 'N/A')}")
                            st.markdown(f"**Response Handling:** {style.get('response_handling', 'N/A')}")
                    
                    if st.button("🗑️ Clear Learned Style", key="clear_rest_style"):
                        del st.session_state.learned_rest_style
                        st.rerun()
        else:  # Unit Test Specifications
            st.info("📋 Unit Test Specifications will generate detailed documentation for developers to implement unit tests.")
            output_format = st.selectbox(
                "Output Format:",
                ["Markdown", "Detailed Report"],
                key="unit_spec_format"
            )
            use_pom = False
            use_oop = False
            use_bot_style = False
            use_data_driven = False
            use_bdd = False
        
        # Custom Prompt Section
        with st.expander("✏️ Custom Instructions (Optional)", expanded=False):
            custom_prompt = st.text_area(
                "Add your custom requirements or instructions:",
                placeholder="Example:\n- Use specific naming conventions\n- Add custom annotations\n- Include specific utility methods\n- Use particular assertion library",
                height=150,
                key="custom_automation_prompt"
            )
        
        # Generate button - different label based on framework
        button_label = "Generate Selenium Code" if "Selenium" in automation_framework else \
                       "Generate REST Assured Code" if "REST Assured" in automation_framework else \
                       "Generate Unit Test Specifications"
        
        if st.button(f"🚀 {button_label}", key="generate_automation", use_container_width=True):
            custom_prompt_value = st.session_state.get('custom_automation_prompt', '')
            
            # Framework-specific generation
            if "Selenium" in automation_framework:
                with st.spinner("Generating production-ready Java Selenium code..."):
                    st.session_state.automation_code = {}
                    
                    if st.session_state.get('generation_mode') == "Combined Test Suite":
                        automation_code = generate_combined_automation_code(
                            st.session_state.selected_test_cases,
                            use_pom=use_pom,
                            use_oop=use_oop,
                            use_data_driven=use_data_driven,
                            use_bdd=use_bdd,
                            use_bot_style=use_bot_style,
                            custom_prompt=custom_prompt_value
                        )
                        if automation_code:
                            st.session_state.automation_code["combined"] = parse_generated_code(automation_code)
                            show_toast("✅ Combined Selenium test suite generated successfully!")
                    else:
                        for test_case in st.session_state.selected_test_cases:
                            automation_code = generate_test_case_automation_code(
                                test_case,
                                use_pom=use_pom,
                                use_oop=use_oop,
                                use_data_driven=use_data_driven,
                                use_bdd=use_bdd,
                                use_bot_style=use_bot_style,
                                custom_prompt=custom_prompt_value
                            )
                            st.session_state.automation_code[test_case['id']] = parse_generated_code(automation_code)
                        show_toast("✅ Selenium automation code generated successfully!")
            
            elif "REST Assured" in automation_framework:
                with st.spinner("Generating production-ready REST Assured API test code..."):
                    st.session_state.automation_code = {}
                    
                    # Get API spec and learned style from session state
                    api_spec = st.session_state.get('api_spec_content', '')
                    learned_style = st.session_state.get('learned_rest_style', None)
                    
                    if st.session_state.get('generation_mode') == "Combined Test Suite":
                        automation_code = generate_combined_rest_assured_code(
                            st.session_state.selected_test_cases,
                            use_bdd=use_bdd,
                            custom_prompt=custom_prompt_value,
                            api_spec=api_spec,
                            learned_style=learned_style
                        )
                        if automation_code:
                            st.session_state.automation_code["combined"] = parse_generated_code(automation_code)
                            show_toast("✅ Combined REST Assured test suite generated successfully!")
                    else:
                        for test_case in st.session_state.selected_test_cases:
                            automation_code = generate_rest_assured_code(
                                test_case,
                                use_bdd=use_bdd,
                                custom_prompt=custom_prompt_value,
                                api_spec=api_spec,
                                learned_style=learned_style
                            )
                            st.session_state.automation_code[test_case['id']] = parse_generated_code(automation_code)
                        show_toast("✅ REST Assured automation code generated successfully!")
            
            else:  # Unit Test Specifications
                with st.spinner("Generating unit test specifications for developers..."):
                    st.session_state.unit_test_specs = {}
                    
                    for test_case in st.session_state.selected_test_cases:
                        specs = generate_unit_test_specifications(test_case)
                        st.session_state.unit_test_specs[test_case['id']] = specs
                    
                    show_toast(f"✅ Generated specifications for {len(st.session_state.selected_test_cases)} test cases!")
        
        # Display results based on framework
        if "Unit Test Specifications" in automation_framework and st.session_state.get('unit_test_specs'):
            st.markdown("### 📋 Generated Unit Test Specifications")
            
            for tc in st.session_state.selected_test_cases:
                if tc['id'] in st.session_state.unit_test_specs:
                    with st.expander(f"📄 {tc['id']}: {tc['title']}", expanded=False):
                        st.markdown(st.session_state.unit_test_specs[tc['id']])
                        
                        # Download button for each specification
                        st.download_button(
                            label=f"📥 Download {tc['id']} Spec",
                            data=st.session_state.unit_test_specs[tc['id']],
                            file_name=f"{tc['id']}_unit_test_spec.md",
                            mime="text/markdown",
                            key=f"dl_spec_{tc['id']}"
                        )
            
            # Download all specifications as a single file
            all_specs = "\n\n---\n\n".join([
                f"# {tc['id']}: {tc['title']}\n\n{st.session_state.unit_test_specs.get(tc['id'], '')}"
                for tc in st.session_state.selected_test_cases
            ])
            st.download_button(
                label="📥 Download All Specifications",
                data=all_specs,
                file_name="unit_test_specifications.md",
                mime="text/markdown",
                key="dl_all_specs",
            )
        
        # Display automation code for Selenium/REST Assured
        if st.session_state.get('automation_code'):
            # Combined Test Suite View
            if st.session_state.generation_mode == "Combined Test Suite" and "combined" in st.session_state.automation_code:
                st.markdown("### 🧩 Combined Test Suite")
                
                # Display automation code
                st.subheader("Generated Automation Code")
                
                for file_name, content in st.session_state.automation_code["combined"].items():
                    with st.expander(f"📄 {file_name}"):
                        st.code(content, language='java')
                
                # Create a zip file for download
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
                    for file_name, content in st.session_state.automation_code["combined"].items():
                        zip_file.writestr(file_name, content)
                
                zip_buffer.seek(0)
                st.download_button(
                    label="📥 Download Combined Test Suite (.zip)",
                    data=zip_buffer,
                    file_name="CombinedTestSuite.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key="dl_combined_suite"
                )
                
                # Display test cases in suite
                st.markdown("### Test Cases in this Suite")
                for test_case in st.session_state.selected_test_cases:
                    with st.expander(f"{test_case['id']}: {test_case['title']}"):
                        st.markdown(f"**Priority:** `{test_case['priority']}` | **Severity:** `{test_case.get('severity', 'N/A')}`")
                        st.markdown("**Steps:**")
                        for step in test_case['test_steps']:
                            st.markdown(f"- {step}")
                        
                        st.markdown("**Expected Results:**")
                        for result in test_case['expected_results']:
                            st.markdown(f"- {result}")
            
            # Separate Files View
            elif st.session_state.generation_mode == "Separate Test Classes":
                # Tabs for each test case
                tabs = st.tabs([f"Test Case: {tc['id']}" for tc in st.session_state.selected_test_cases])
                
                for idx, test_case in enumerate(st.session_state.selected_test_cases):
                    with tabs[idx]:
                        st.markdown(f"### {test_case['title']}")
                        st.markdown(f"**ID:** {test_case['id']} | **Priority:** `{test_case['priority']}` | **Severity:** `{test_case.get('severity', 'N/A')}`")
                        
                        # Display test case details
                        with st.expander("Test Case Details", expanded=False):
                            st.markdown("**Steps:**")
                            for step in test_case['test_steps']:
                                st.markdown(f"- {step}")
                            
                            st.markdown("**Expected Results:**")
                            for result in test_case['expected_results']:
                                st.markdown(f"- {result}")
                        
                        # Display automation code
                        if test_case['id'] in st.session_state.automation_code:
                            st.subheader("Generated Automation Code")
                            
                            for file_name, content in st.session_state.automation_code[test_case['id']].items():
                                with st.expander(f"📄 {file_name}"):
                                    st.code(content, language='java')
                            
                            # Create a zip file for download
                            zip_buffer = BytesIO()
                            with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
                                for file_name, content in st.session_state.automation_code[test_case['id']].items():
                                    zip_file.writestr(file_name, content)
                            
                            zip_buffer.seek(0)
                            st.download_button(
                                label=f"📥 Download Code for {test_case['id']} (.zip)",
                                data=zip_buffer,
                                file_name=f"{test_case['id']}_automation.zip",
                                mime="application/zip",
                                use_container_width=True,
                                key=f"dl_code_{test_case['id']}"
                            )
                        else:
                            st.info("Click 'Generate Automation Code' to create Java code")
        else:
            st.info("Click the button above to generate automation code")
    else:
        st.info("No test cases selected for automation")
        st.markdown("Go to **Test Case Generator** to create and select test cases")
        if st.button("Go to Test Case Generator"):
            st.query_params["page"] = "Test Case Generator"
            st.rerun()

# Test Plan Generator Page
elif page == "Test Plan Generator":
    st.subheader("📋 AI Test Plan Generator")
    st.markdown("Generate comprehensive, professional test plans from your requirements documents.")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("Test Plan Configuration")
        st.markdown("---")
        st.markdown("**About**")
        st.markdown("Generate AI-powered test plans with team allocation and scheduling.")
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Requirements Input
        st.markdown("### 📄 Requirements Document")
        
        # File upload
        uploaded_req_file = st.file_uploader(
            "Upload requirements file (PDF, DOCX, TXT, CSV, XLSX)",
            type=['pdf', 'docx', 'txt', 'csv', 'xlsx'],
            key="test_plan_file"
        )
        
        # Or manual input
        st.markdown("**Or enter requirements manually:**")
        requirements_text = st.text_area(
            "Requirements Text",
            height=200,
            placeholder="Enter your project requirements, user stories, or feature specifications here...",
            key="requirements_manual"
        )
        
        # Custom instructions
        with st.expander("✏️ Custom Instructions (Optional)"):
            custom_instructions = st.text_area(
                "Add specific instructions for the AI:",
                placeholder="Example:\n- Focus on security testing\n- Include performance test cases\n- Prioritize mobile functionality",
                height=100,
                key="custom_instructions"
            )
    
    with col2:
        # Timeline
        st.markdown("### 📅 Timeline")
        start_date = st.date_input("Start Date", key="plan_start_date")
        end_date = st.date_input("End Date", key="plan_end_date")
        
        if start_date and end_date:
            if end_date >= start_date:
                total_days = (end_date - start_date).days + 1
                # Calculate working days (Mon-Fri)
                working_days = 0
                current = start_date
                from datetime import timedelta
                while current <= end_date:
                    if current.weekday() < 5:  # Monday = 0, Sunday = 6
                        working_days += 1
                    current += timedelta(days=1)
                
                st.info(f"📊 **{total_days}** total days | **{working_days}** working days")
            else:
                st.error("End date must be after start date")
        
        # Team Members
        st.markdown("### 👥 Test Team")
        
        if st.button("➕ Add Tester", key="add_tester_btn"):
            st.session_state.test_plan_testers.append({
                "id": len(st.session_state.test_plan_testers) + 1,
                "specialization": "Manual",
                "experience": 2
            })
            st.rerun()
        
        if not st.session_state.test_plan_testers:
            st.caption("No testers added yet. Add team members to allocate tasks.")
        
        # Display testers
        for idx, tester in enumerate(st.session_state.test_plan_testers):
            with st.container():
                st.markdown(f"**Tester {idx + 1}**")
                col_a, col_b = st.columns(2)
                with col_a:
                    specialization = st.selectbox(
                        "Specialization",
                        ["Manual", "Automation", "Junior/Fresher"],
                        index=["Manual", "Automation", "Junior/Fresher"].index(tester.get("specialization", "Manual")),
                        key=f"spec_{idx}"
                    )
                    st.session_state.test_plan_testers[idx]["specialization"] = specialization
                with col_b:
                    experience = st.slider(
                        "Experience (years)",
                        0, 10, 
                        tester.get("experience", 2),
                        key=f"exp_{idx}"
                    )
                    st.session_state.test_plan_testers[idx]["experience"] = experience
                
                if st.button("🗑️ Remove", key=f"remove_{idx}"):
                    st.session_state.test_plan_testers.pop(idx)
                    st.rerun()
                st.markdown("---")
    
    # Generate Test Plan Button
    st.markdown("---")
    
    # Validation
    has_requirements = bool(uploaded_req_file or requirements_text.strip())
    has_testers = len(st.session_state.test_plan_testers) > 0
    
    if not has_requirements:
        st.warning("⚠️ Please upload a requirements file or enter requirements manually.")
    if not has_testers:
        st.warning("⚠️ Please add at least one tester to the team.")
    
    generate_btn_disabled = not (has_requirements and has_testers)
    
    if st.button("🚀 Generate Test Plan", use_container_width=True, disabled=generate_btn_disabled, type="primary"):
        with st.spinner("Generating comprehensive test plan... This may take a moment."):
            try:
                # Extract requirements content
                requirements_content = requirements_text
                
                if uploaded_req_file:
                    file_type = uploaded_req_file.type
                    if file_type in FILE_PROCESSORS:
                        requirements_content = FILE_PROCESSORS[file_type](uploaded_req_file)
                    elif uploaded_req_file.name.endswith('.txt'):
                        requirements_content = uploaded_req_file.read().decode('utf-8')
                
                # Build timeline string
                timeline_str = "Not specified"
                if start_date and end_date:
                    timeline_str = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
                
                # Build team string
                team_str = "\n".join([
                    f"{t['specialization']} Tester {idx+1}: {t['experience']} years of experience"
                    for idx, t in enumerate(st.session_state.test_plan_testers)
                ])
                
                # Build prompt
                prompt = f"""You are an experienced QA Lead. Generate a comprehensive Test Plan based on the following requirements.

REQUIREMENTS DOCUMENT:
{requirements_content}

EXECUTION TIMELINE:
{timeline_str}

TEST TEAM:
{team_str}

Please generate a detailed Test Plan in Markdown format that includes:

1. **Test Plan Overview** - Brief introduction and purpose

2. **Test Scope and Objectives** - What will be tested and goals

3. **Test Strategy** - Overall approach and methodology

4. **Test Environment Requirements** - Infrastructure and setup needs

5. **Test Deliverables** - List of documents and artifacts

6. **Resource Allocation** - Presented as a TABLE with columns:
   - Tester Name/ID
   - Years of Experience
   - Specialization
   - Assigned Tasks/Modules
   - Estimated Effort
   - Responsibilities

7. **Task Allocation** - Presented as a TABLE with columns:
   - Task ID
   - Task Description
   - Assigned Tester
   - Priority
   - Status
   - Dependencies
   - Estimated Duration

8. **Test Schedule/Timeline** - Presented as a TABLE with columns:
   - Phase/Milestone
   - Start Date
   - End Date
   - Duration
   - Responsible Tester
   - Deliverables

9. **Risk Assessment** - Presented as a TABLE with columns:
   - Risk ID
   - Risk Description
   - Probability (High/Medium/Low)
   - Impact (High/Medium/Low)
   - Mitigation Strategy
   - Owner

10. **Entry and Exit Criteria** - Clear criteria for starting and completing testing

IMPORTANT: Use proper Markdown formatting with tables, headers, and bullet points."""

                # Add custom instructions if provided
                if custom_instructions:
                    prompt += f"\n\nADDITIONAL CUSTOM INSTRUCTIONS:\n{custom_instructions}"
                
                # Call AI API (auto-fallback between Gemini and OpenAI)
                response_text = call_ai(prompt)
                
                st.session_state.generated_test_plan = response_text
                
            except Exception as e:
                st.error(f"Error generating test plan: {str(e)}")
    
    # Display generated test plan
    if st.session_state.generated_test_plan:
        st.markdown("---")
        st.markdown("### 📋 Generated Test Plan")
        
        # Export buttons
        col_exp1, col_exp2, col_exp3 = st.columns(3)
        with col_exp1:
            st.download_button(
                label="📥 Download as Markdown",
                data=st.session_state.generated_test_plan,
                file_name="test_plan.md",
                mime="text/markdown",
                use_container_width=True
            )
        with col_exp2:
            # Convert to plain text for TXT download
            st.download_button(
                label="📄 Download as Text",
                data=st.session_state.generated_test_plan,
                file_name="test_plan.txt",
                mime="text/plain",
                use_container_width=True
            )
        with col_exp3:
            if st.button("🔄 Regenerate", use_container_width=True):
                st.session_state.generated_test_plan = ""
                st.rerun()
        
        # Display the test plan
        st.markdown('<div class="test-plan-output">', unsafe_allow_html=True)
        st.markdown(st.session_state.generated_test_plan)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Disclaimer
        st.info("⚠️ **AI-Generated Content**: This test plan was generated by AI. Please review and adjust according to your specific project needs.")

# Bug Report Generator Page
elif page == "Bug Report Generator":
    st.subheader("🐞 AI Bug Report Generator")
    st.info("Describe the bug in plain English or Arabic. select the **Output Language** below (Default: English).")
    
    col_input, col_preview = st.columns([1, 1])
    
    with col_input:
        st.markdown("### 📝 Bug Details")
        
        # Context Fields
        c1, c2, c3 = st.columns(3)
        with c1:
            env = st.selectbox("Environment", ["PROD", "UAT", "Testing", "Staging", "DEV"], index=2)
        with c2:
            browser = st.selectbox("Browser", ["Chrome", "Edge", "Firefox", "Safari", "Mobile"], index=0)
        with c3:
            report_lang = st.selectbox("Output Language", ["English", "Arabic (العربية)"], index=0)
        
        # Description
        bug_description = st.text_area(
            "What happened? (Rough Notes)", 
            placeholder="e.g. I tried to login... OR \nمثال: حاولت تسجيل الدخول...",
            height=300
        )
        
        # Screenshot (Visual only for now, unless we verify vision model availability)
        uploaded_screenshot = st.file_uploader("Upload Screenshot (Optional)", type=['png', 'jpg', 'jpeg'])

        generate_btn = st.button("🚀 Generate Bug Report", use_container_width=True, disabled=not bug_description)

    with col_preview:
        st.markdown("### 📋 Formatted Report")
        
        if generate_btn and bug_description:
            with st.spinner("Analyzing and formatting bug report..."):
                try:
                    # Construct Prompt
                    prompt = f"""
                    Act as a Senior QA Engineer. Convert this unstructured bug description into a standard, professional Bug Report for JIRA/DevOps.
                    
                    CONTEXT:
                    Environment: {env}
                    Browser: {browser}
                    Target Language: {report_lang}
                    
                    UNSTRUCTURED INPUT:
                    {bug_description}
                    
                    INSTRUCTIONS:
                    1. Create a clear, concise Title.
                    2. Estimate Severity and Priority based on the context.
                    3. Extract clear Steps to Reproduce.
                    4. Clearly separate Expected and Actual results.
                    5. Use professional technical language.
                    6. LANGUAGE HANDLING:
                       - If Target Language is English: TRANSLATE any non-English input (like Arabic) into professional English.
                       - If Target Language is Arabic: Translate content to professional technical Arabic, keeping technical terms in English.
                    
                    OUTPUT FORMAT (Markdown):
                    ### [Bug ID]: [Concise Title in Target Language]
                    
                    **Severity**: [Critical/High/Medium/Low] | **Priority**: [High/Medium/Low]
                    
                    **Description**:
                    [Professional summary of the issue]
                    
                    **Preconditions**:
                    [Any implied setup]
                    
                    **Steps to Reproduce**:
                    1. [Step 1]
                    2. [Step 2]
                    ...
                    
                    **Actual Result**:
                    [What happened]
                    
                    **Expected Result**:
                    [What should have happened]
                    
                    **Environment details**:
                    {env} | {browser}
                    """
                    
                    report = call_ai(prompt)
                    st.session_state.last_bug_report = report
                    
                    # Increment counter
                    if 'bug_reports_count' not in st.session_state:
                        st.session_state.bug_reports_count = 0
                    st.session_state.bug_reports_count += 1
                    
                    st.toast("✅ Bug Report Generated!")
                    
                except Exception as e:
                    st.error(f"Error generating report: {e}")

        if "last_bug_report" in st.session_state:
             # Display the markdown report
             st.markdown(st.session_state.last_bug_report)
             
             st.markdown("---")
             st.caption("Copy for JIRA / DevOps /RTC:")
             st.code(st.session_state.last_bug_report, language='markdown')
             
             # Export Options
             st.download_button(
                 "📥 Download Report (.md)",
                 data=st.session_state.last_bug_report,
                 file_name=f"Bug_Report_{int(time.time())}.md",
                 mime="text/markdown"
             )

# AI Chat Page
elif page == "AI Chat":
    st.subheader("💬 AI Chat Assistant")
    st.markdown("Chat with AI about testing, automation, QA best practices, or anything else!")
    
    # Initialize chat history in session state
    if 'chat_messages' not in st.session_state:
        st.session_state.chat_messages = []
    
    # Initialize file uploader key
    if 'file_uploader_key' not in st.session_state:
        st.session_state.file_uploader_key = 0

    # Custom CSS for chat
    st.markdown("""
    <style>
    .chat-container {
        max-height: 500px;
        overflow-y: auto;
        padding: 10px;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        margin-bottom: 20px;
        background-color: #f9f9f9;
    }
    .user-message {
        background-color: #2D1B69;
        color: white;
        padding: 10px 15px;
        border-radius: 15px 15px 5px 15px;
        margin: 10px 0;
        margin-left: 20%;
        text-align: right;
    }
    .ai-message {
        background-color: #e8e8e8;
        color: #333;
        padding: 10px 15px;
        border-radius: 15px 15px 15px 5px;
        margin: 10px 0;
        margin-right: 20%;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Display chat messages
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.chat_messages:
            if message["role"] == "user":
                st.markdown(f'<div class="user-message">🧑 {message["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="ai-message">🤖 {message["content"]}</div>', unsafe_allow_html=True)
    
    # Clear chat button
    if st.session_state.chat_messages:
        if st.button("🗑️ Clear Chat History", key="clear_chat_main"):
            st.session_state.chat_messages = []
            # Reset file uploader by changing its key
            st.session_state.file_uploader_key += 1
            st.rerun()
    
    # File Uploader in main area
    with st.expander("📎 Attach File to Message", expanded=False):
        st.caption("Upload a file to provide context for your next question.")
        chat_context_file = st.file_uploader(
            "Choose file", 
            type=['pdf', 'docx', 'txt', 'csv', 'xlsx', 'md'],
            key=f"chat_file_uploader_{st.session_state.file_uploader_key}",
            label_visibility="collapsed"
        )

    # Chat input using Streamlit's chat_input (auto-clears after send, no page reload feel)
    user_input = st.chat_input("Ask me anything about testing, automation, QA...")
    
    # Process message
    if user_input:
        # Check for uploaded file in sidebar
        chat_context_file = st.session_state.get(f'chat_file_uploader_{st.session_state.file_uploader_key}')
        file_context = ""
        
        if chat_context_file:
            try:
                # Determine file type and process
                file_type = chat_context_file.type
                # Simple extension check for markdown if type is generic or missing
                if chat_context_file.name.lower().endswith('.md'):
                     file_type = "text/markdown"
                
                if file_type in FILE_PROCESSORS:
                    content = FILE_PROCESSORS[file_type](chat_context_file)
                    file_context = f"\n\n--- ATTACHED FILE: {chat_context_file.name} ---\n{content}\n-----------------------------\n"
                elif file_type.startswith('text/'):
                     # Try treating as text
                     content = chat_context_file.read().decode("utf-8")
                     file_context = f"\n\n--- ATTACHED FILE: {chat_context_file.name} ---\n{content}\n-----------------------------\n"
                
                if file_context:
                    st.session_state.chat_messages.append({"role": "system", "content": f"📎 Attached context from file: **{chat_context_file.name}**"})
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")

        # Add user message to history
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        
        # Build conversation context
        conversation_context = "You are a helpful AI assistant specializing in QA, testing, and software development. Be conversational, friendly, and helpful.\n\n"
        
        # Add file context if available
        if file_context:
             conversation_context += f"USER ATTACHED A FILE. HERE IS THE CONTENT:\n{file_context}\n\n"
        
        # Include recent conversation history (last 10 messages for context)
        recent_messages = st.session_state.chat_messages[-10:]
        for msg in recent_messages[:-1]:  # Exclude the latest user message as it's already in prompt
            if msg["role"] == "system": continue # Skip system messages in prompt context to avoid confusion
            role = "User" if msg["role"] == "user" else "Assistant"
            conversation_context += f"{role}: {msg['content']}\n\n"
        
        conversation_context += f"User: {user_input}\n\nAssistant:"
        
        # Generate AI response
        with st.spinner("AI is thinking..."):
            try:
                ai_response = call_ai(conversation_context)
                st.session_state.chat_messages.append({"role": "assistant", "content": ai_response})
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.session_state.chat_messages.append({"role": "assistant", "content": f"Sorry, I encountered an error: {str(e)}"})
        
        st.rerun()
    
    # Sidebar actions for chat
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 💬 Chat Options")
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.chat_messages = []
            # Reset file uploader by changing its key
            st.session_state.file_uploader_key += 1
            st.rerun()
        
        
        # Example prompts
        st.markdown("**Quick Prompts:**")
        example_prompts = [
            "What are best practices for writing test cases?",
            "Explain the difference between unit and integration tests",
            "How do I set up Selenium WebDriver?",
            "What is the testing pyramid?",
            "Tips for effective bug reporting"
        ]
        for prompt in example_prompts:
            if st.button(f"💡 {prompt[:30]}...", key=f"prompt_{prompt[:10]}", use_container_width=True):
                st.session_state.chat_messages.append({"role": "user", "content": prompt})
                with st.spinner("AI is thinking..."):
                    try:
                        ai_response = call_ai(f"You are a helpful AI assistant specializing in QA and testing. Answer this question:\n\n{prompt}")
                        st.session_state.chat_messages.append({"role": "assistant", "content": ai_response})
                    except Exception as e:
                        st.session_state.chat_messages.append({"role": "assistant", "content": f"Sorry, I encountered an error: {str(e)}"})
                st.rerun()

# Footer (hide on AI Chat page - chat_input is fixed at bottom)
if page != "AI Chat":
    st.markdown("""
    <div style="text-align: center; padding: 15px; margin-top: 30px; border-top: 1px solid #e0e0e0;">
        <p style="font-size: 0.9em; color: #666; margin: 5px 0;">
            🤖🦾🦿⚡ <strong>RoboTest AI Suite</strong> | Powered by Gemini, Claude, OpenAI & GitHub Models
        </p>
        <p style="font-size: 0.8em; color: #999; margin: 5px 0;">
            Copyright © 2026 | Developed by Abdelrahman Kandil
        </p>
    </div>
    """, unsafe_allow_html=True)
# --- GLOBAL SIDEBAR CONFIGURATION (RENDERED LAST) ---
# This ensures it appears below any page-specific sidebar content
st.sidebar.markdown("---")

# User API Key Inputs - Available on all pages
with st.sidebar.expander("🔑 API Configuration", expanded=False):
    st.caption("Enter your own API keys to override defaults. Keys are not saved to disk.")
    st.text_input("Gemini API Key", key="user_gemini_key", type="password", help="Overrides GEMINI_API_KEY from .env")
    st.text_input("OpenAI API Key", key="user_openai_key", type="password", help="Overrides OPENAI_API_KEY from .env")
    st.text_input("Anthropic API Key", key="user_anthropic_key", type="password", help="Overrides ANTHROPIC_API_KEY from .env")
    st.text_input("GitHub Token", key="user_github_token", type="password", help="Overrides GITHUB_TOKEN from .env")

# Only show provider selection on Home page
if page == "Home":

    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ AI Provider")

    # Build provider options based on available API keys
    provider_options = ["Auto (Recommended)"]
    provider_values = ["auto"]
    if GEMINI_API_KEY:
        provider_options.append("Google Gemini")
        provider_values.append("gemini")
    if ANTHROPIC_API_KEY:
        provider_options.append("Claude (Anthropic)")
        provider_values.append("claude")
    if OPENAI_API_KEY:
        provider_options.append("OpenAI (ChatGPT)")
        provider_values.append("openai")
    if GITHUB_TOKEN:
        provider_options.append("GitHub Models (Copilot)")
        provider_values.append("github")

    # Ensure provider is valid (in case keys changed)
    current_provider_idx = 0
    if st.session_state.ai_provider in provider_values:
        current_provider_idx = provider_values.index(st.session_state.ai_provider)

    selected_provider_idx = st.sidebar.selectbox(
        "Select AI Provider",
        range(len(provider_options)),
        format_func=lambda x: provider_options[x],
        index=current_provider_idx,
        help="Auto mode tries providers in order: Gemini → Claude → OpenAI → GitHub"
    )
    st.session_state.ai_provider = provider_values[selected_provider_idx]

    # GitHub Models dropdown (shown when GitHub is selected)
    if st.session_state.ai_provider == "github":
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🤖 GitHub Model Selection")
        
        # List of all available GitHub Models
        github_models = [
            # OpenAI GPT Models
            "openai/gpt-5",
            "openai/gpt-5-chat",
            "openai/gpt-5-mini",
            "openai/gpt-5-nano",
            "openai/gpt-4.1",
            "openai/gpt-4.1-mini",
            "openai/gpt-4.1-nano",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            # OpenAI Reasoning Models
            "openai/o1",
            "openai/o1-mini",
            "openai/o1-preview",
            "openai/o3",
            "openai/o3-mini",
            "openai/o4-mini",
            # OpenAI Embedding Models
            "openai/text-embedding-3-small",
            "openai/text-embedding-3-large",
            # Microsoft Phi Models
            "microsoft/phi-4",
            "microsoft/phi-4-mini-instruct",
            "microsoft/phi-4-mini-reasoning",
            "microsoft/phi-4-multimodal-instruct",
            "microsoft/phi-4-reasoning",
            "microsoft/phi-3-medium-128k-instruct",
            "microsoft/phi-3-mini-128k-instruct",
            # Microsoft Reasoning Models
            "microsoft/mai-ds-r1",
            # AI21 Labs Models
            "ai21/jamba-1.5-large",
            # Meta Llama Models
            "meta/llama-4-scout-17b-16e-instruct",
            "meta/llama-4-maverick-17b-128e-instruct-fp8",
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.2-90b-vision-instruct",
            "meta/llama-3.2-11b-vision-instruct",
            "meta/llama-3.1-405b-instruct",
            "meta/llama-3.1-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            # Cohere Models
            "cohere/command-r-plus-08-2024",
            "cohere/command-r-08-2024",
            "cohere/command-a",
            # Mistral AI Models
            "mistralai/mistral-small-3.1",
            "mistralai/codestral-25.01",
            "mistralai/mistral-medium-3",
            "mistralai/ministral-3b",
            "mistralai/mistral-large",
            "mistralai/mistral-nemo",
            # DeepSeek Models
            "deepseek/deepseek-v3-0324",
            "deepseek/deepseek-r1-0528",
            "deepseek/deepseek-r1",
            # xAI Grok Models
            "xai/grok-3",
            "xai/grok-3-mini",
            # Google Gemma Models
            "google/gemma-2-27b-it",
            "google/gemma-2-9b-it",
        ]
        
        selected_model = st.sidebar.selectbox(
            "Choose Model",
            github_models,
            index=github_models.index(GITHUB_MODEL) if GITHUB_MODEL in github_models else 0,
            help="Select a model from the GitHub Models marketplace. Visit https://github.com/marketplace?type=models for available models."
        )
        
        # Update session state with selected model
        st.session_state.github_model = selected_model
        
        st.sidebar.info(f"📌 Selected: `{selected_model}`")

    # Show API status
    st.sidebar.markdown("**API Status:**")
    if GEMINI_API_KEY:
        st.sidebar.markdown("✅ Gemini API configured")
    else:
        st.sidebar.markdown("❌ Gemini API not configured")
    if ANTHROPIC_API_KEY:
        st.sidebar.markdown("✅ Claude API configured")
    else:
        st.sidebar.markdown("❌ Claude API not configured")
    if OPENAI_API_KEY:
        st.sidebar.markdown("✅ OpenAI API configured")
    else:
        st.sidebar.markdown("❌ OpenAI API not configured")
    if GITHUB_TOKEN:
        st.sidebar.markdown("✅ GitHub Models configured")
    else:
        st.sidebar.markdown("❌ GitHub Models not configured")

    st.sidebar.caption("💡 Add API keys to your `.env` file")
