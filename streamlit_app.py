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
import requests

# Load environment variables
load_dotenv()

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

# Initialize Gemini client if available
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

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
                errors.append(f"OpenAI: {str(e)}")
                raise e
        
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
    if not gemini_client:
        raise Exception("Gemini API key not configured")
    response = gemini_client.models.generate_content(
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
            design_instructions.append("- Object-Oriented Programming principles (Encapsulation, Inheritance, Polymorphism)")
            design_instructions.append("- Use inheritance with BaseTest and BasePage classes")
            design_instructions.append("- Apply SOLID principles")
        if use_data_driven:
            design_instructions.append("- Data-driven testing with @DataProvider")
            design_instructions.append("- External test data from JSON/Excel files")
        if use_bdd:
            design_instructions.append("- BDD style with descriptive method names")
            design_instructions.append("- Given-When-Then comments in test methods")
        if use_bot_style:
            design_instructions.append("- Bot Style Architecture Pattern")
            design_instructions.append("- Create a Bot class that encapsulates all user actions")
            design_instructions.append("- Fluent/chainable API for method chaining (return this)")
            design_instructions.append("- Bot methods should be action-oriented like: bot.login(user, pass).navigateTo(page).clickButton(name)")
            design_instructions.append("- Separate Bot class from Page Objects for reusable action sequences")
            design_instructions.append("- Bot should handle common workflows and complex user journeys")
        
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
            design_instructions.append("- Object-Oriented Programming principles (Encapsulation, Inheritance, Polymorphism)")
            design_instructions.append("- Use inheritance with BaseTest and BasePage classes")
            design_instructions.append("- Apply SOLID principles")
        if use_data_driven:
            design_instructions.append("- Data-driven testing with @DataProvider")
            design_instructions.append("- External test data from JSON/Excel files")
        if use_bdd:
            design_instructions.append("- BDD style with descriptive method names")
            design_instructions.append("- Given-When-Then comments in test methods")
        if use_bot_style:
            design_instructions.append("- Bot Style Architecture Pattern")
            design_instructions.append("- Create a Bot class that encapsulates all user actions")
            design_instructions.append("- Fluent/chainable API for method chaining (return this)")
            design_instructions.append("- Bot methods should be action-oriented like: bot.login(user, pass).navigateTo(page).clickButton(name)")
            design_instructions.append("- Separate Bot class from Page Objects for reusable action sequences")
            design_instructions.append("- Bot should handle common workflows and complex user journeys")
        
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
st.sidebar.markdown("### 🧭 Navigation")

page = st.sidebar.radio(
    "Select Page",
    ["🏠 Home", "🧪 Test Case Generator", "🤖 Test Automation", "📋 Test Plan Generator", "💬 AI Chat"],
    label_visibility="collapsed",
    key="main_navigation"
)

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
        
        st.markdown("---")
        st.markdown("**About**")
        st.markdown("Create professional test cases using AI")
    
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
        # This block runs only when page == "Test Case Generator".
        
        # To fix this, we need to restructure:
        # 1. Navigation (Top)
        # 2. Page Specific Settings (Middle) -> We need to move the API config code to run AFTER the page logic check.
        # 3. API Config (Bottom)

    
    tab1, tab2 = st.tabs(["Manual Creation", "Generate from Requirements"])
    
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
        
        # Export to Excel button
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
                if st.button(f"🚀 Generate Automation for {selected_count} Test Cases", key="gen_selected"):
                    st.session_state.selected_test_cases = [
                        tc for tc in st.session_state.test_cases 
                        if st.session_state.get(f"select_{tc['id']}", False)
                    ]
                    st.session_state.main_navigation = "🤖 Test Automation"
                    st.rerun()
            else:
                st.button("Generate Automation (Select Test Cases)", disabled=True)
            
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
                    
                    # Generate automation for single test case
                    if st.button("🤖 Generate", key=f"gen_single_{test_case['id']}"):
                        st.session_state.selected_test_cases = [test_case]
                        st.experimental_set_query_params(page="Test Automation")
                        st.rerun()
        
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
                    show_toast("✅ Test case updated successfully!")
                    st.rerun()  # FIXED: Changed from experimental_rerun to rerun
            
            with col2:
                if st.form_submit_button("Cancel", use_container_width=True):
                    st.session_state.editing_test_case = None
                    st.rerun()  # FIXED: Changed from experimental_rerun to rerun

# Test Automation Page
elif page == "Test Automation":
    st.subheader("🤖 Java Selenium Automation Generator")
    
    if st.session_state.selected_test_cases:
        st.success(f"Generating automation code for {len(st.session_state.selected_test_cases)} test cases")
        
        # Generation mode selection
        st.markdown('<div class="combined-toggle">', unsafe_allow_html=True)
        st.radio(
            "Generation Mode:",
            ["Combined Test Suite", "Separate Test Classes"],
            key="generation_mode",
            horizontal=True
        )
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Design Pattern Options
        st.markdown("### ⚙️ Code Generation Options")
        
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
        
        # Custom Prompt Section
        with st.expander("✏️ Custom Instructions (Optional)", expanded=False):
            custom_prompt = st.text_area(
                "Add your custom requirements or instructions:",
                placeholder="Example:\n- Use specific naming conventions\n- Add custom annotations\n- Include specific utility methods\n- Use particular assertion library",
                height=150,
                key="custom_automation_prompt"
            )
        
        # Generate automation code
        if st.button("Generate Automation Code", key="generate_automation", use_container_width=True):
            with st.spinner("Generating production-ready Java Selenium code..."):
                st.session_state.automation_code = {}
                
                # Get custom prompt value
                custom_prompt_value = st.session_state.get('custom_automation_prompt', '')
                
                if st.session_state.generation_mode == "Combined Test Suite":
                    # Generate combined test suite
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
                        show_toast("✅ Combined test suite generated successfully!")
                else:
                    # Generate separate files for each test case
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
                    show_toast("✅ Automation code generated successfully!")
        
        if st.session_state.automation_code:
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
                    label="Download Combined Test Suite",
                    data=zip_buffer,
                    file_name="CombinedTestSuite.zip",
                    mime="application/zip",
                    use_container_width=True
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
                                label=f"Download Code for {test_case['id']}",
                                data=zip_buffer,
                                file_name=f"{test_case['id']}_automation.zip",
                                mime="application/zip",
                                use_container_width=True
                            )
                        else:
                            st.info("Click 'Generate Automation Code' to create Java code")
        else:
            st.info("Click the button above to generate automation code")
    else:
        st.info("No test cases selected for automation")
        st.markdown("Go to **Test Case Generator** to create and select test cases")
        if st.button("Go to Test Case Generator"):
            st.experimental_set_query_params(page="Test Case Generator")
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
# Only show on Home page
if page == "Home":
    st.sidebar.markdown("---")

    # User API Key Inputs
    with st.sidebar.expander("🔑 API Configuration", expanded=False):
        st.caption("Enter your own API keys to override defaults. Keys are not saved to disk.")
        st.text_input("Gemini API Key", key="user_gemini_key", type="password", help="Overrides GEMINI_API_KEY from .env")
        st.text_input("OpenAI API Key", key="user_openai_key", type="password", help="Overrides OPENAI_API_KEY from .env")
        st.text_input("Anthropic API Key", key="user_anthropic_key", type="password", help="Overrides ANTHROPIC_API_KEY from .env")
        st.text_input("GitHub Token", key="user_github_token", type="password", help="Overrides GITHUB_TOKEN from .env")

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
