# 🤖 RoboTest AI Suite

**Enterprise-Grade Test Case Generator, Selenium Automation Code Builder & AI Test Plan Generator**

**Powered by Google Gemini, OpenAI ChatGPT, Anthropic Claude & Streamlit**

---

## Overview

The RoboTest AI Suite is an all-in-one AI-powered platform for quality engineers to:

- ✨ **Generate professional test cases** from requirements or user stories using AI
- 🧑‍💻 **Produce production-ready Java Selenium automation code** (TestNG, Page Object Model, Allure, Log4j2, etc.)
- 🏗️ **Build complete automation frameworks** adhering to enterprise standards
- 📋 **Generate comprehensive test plans** with team allocation, scheduling, and risk assessment
- � **Create professional bug reports** from rough notes automatically
- �💬 **Chat with AI assistant** for QA guidance and testing best practices
- 📄 **Manage, edit, and download** test cases and automation artifacts in a user-friendly Streamlit interface

This app leverages **multiple AI providers** with automatic fallback support, providing industry-leading test design and code generation capabilities.

---

## 🤖 AI Providers Supported

| Provider | Model | Features |
|----------|-------|----------|
| **Google Gemini** | gemini-flash-latest | Fast, cost-effective, great for test generation |
| **OpenAI** | gpt-4o-mini | Reliable, high-quality responses |
| **Anthropic Claude** | claude-sonnet-4-20250514 | Intelligent, nuanced understanding |

- **Auto-Fallback Mode:** Automatically tries providers in order (Gemini → Claude → OpenAI → GitHub) if one fails or quota is exceeded
- **Manual Selection:** Choose your preferred AI provider from the sidebar
- **Multi-Provider Support:** Configure API keys via `.env` file or directly in the UI (Sidebar inputs override `.env`).
- **GitHub Models (Copilot):** Use your GitHub PAT (`GITHUB_TOKEN`) and set `GITHUB_MODEL` (e.g., `openai/gpt-4o-mini` or `gpt-5` if available) to run models via GitHub Models API

---

## 🚀 Features

### 🐞 Bug Report Generation Robot (NEW)
- **AI-Powered Bug Reporting:**  
  Convert unstructured notes or rough descriptions into professional, standard bug reports.
- **Multi-Language Support:**  
  Input in English or Arabic, and generate reports in English (Professional) or Arabic (Technical).
- **Format:**  
  Standard JIRA-ready format with Severity, Priority, Steps to Reproduce, Expected vs Actual results.
- **Export:**  
  Copy to clipboard or download as Markdown file.

### 🤖 Test Case Generation Robot
- **⚡ Quick Commands (NEW):**  
  Instantly generate test cases using templates (Login, CRUD, API) or directly from **uploaded BRD/Requirement documents**.
- **Interactive Requirements (NEW):**  
  Upload requirements, preview extracted text, and refine instructions before generation.
- **AI-Powered Generation:**  
  Input requirements or user stories to get structured test cases in JSON format.
- **Multi-Language Support:**  
  Generate test cases in **English** or **Arabic** language.
- **Example-Based Learning:**  
  Upload your own test cases to teach the AI your preferred writing style.
- **Bulk Management:**  
  Select, edit, delete, and export test cases to Excel.

### 🦾 Automation Code Generation Robot
- **Multi-Framework Support:**
  - **Selenium WebDriver** (UI Testing)
  - **REST Assured** (API Testing) - **NEW**
- **API Spec Analysis (NEW):**
  - Upload Swagger/OpenAPI/Postman docs to generate precise API tests.
- **Enterprise Design Patterns:**
  - ✅ **Action-Based Testing (Bot Style)** - Generic ActionBot abstraction
  - ✅ **Page Object Model (POM)**
  - ✅ **Component Objects & Fluent Interfaces**
  - ✅ **Explicit Waits & Robust Error Handling**
  - ✅ **SLF4J/Log4j2 Logging**
- **Downloadable Artifacts:**  
  Download generated code as a ready-to-use ZIP archive.

### 📋 Test Plan Generation Robot
- **Comprehensive Test Plans:**  
  Generate professional test plans from requirements documents.
- **Team & Timeline Planning:**  
  AI-assisted resource allocation and schedule estimation.
- **Rich Output:**  
  Includes Test Strategy, Scope, Risk Assessment, and Entry/Exit Criteria.

### 💬 AI Chat Assistant Robot
- **24/7 QA Expert:**  
  Ask questions about testing strategies, automation frameworks, or specific testing challenges.

### 🎨 Enterprise UI/UX
- **Project Dashboard (NEW):** Real-time metrics on test cases and scripts generated.
- Modern, responsive Streamlit web app with advanced CSS styling.
- Toast notifications for user feedback.

---

## 🏗️ Tech Stack

- [Streamlit](https://streamlit.io/) — UI framework
- [Google Gemini](https://ai.google.dev/) — AI test case/code generation
- [OpenAI GPT-4](https://openai.com/) — AI test case/code generation
- [Anthropic Claude](https://anthropic.com/) — AI test case/code generation
- [gspread](https://docs.gspread.org/) — Google Sheets Integration
- [PyPDF2](https://pypi.org/project/pypdf2/) & [python-docx](https://pypi.org/project/python-docx/) — Document Parsing

---

## ⚡ Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/pasindu-kalubowila/QA_Test_Automation_Streamlit_App.git
cd QA_Test_Automation_Streamlit_App
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Set Up Environment Variables

Create a `.env` file in the project root:

```env
# At least one provider is required
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
# GitHub Models (Copilot)
GITHUB_TOKEN=your_github_pat_with_models_scope
GITHUB_MODEL=openai/gpt-4o-mini
```

### 4. Run the App

```bash
streamlit run streamlit_app.py
```

---

## 🧪 Usage

### 🏠 Home
- **Project Dashboard:** View live stats on created test cases and scripts.
- **What's New:** Check latest features and updates.
- Quick start guide & AI status.

### 🧪 Test Case Generator
- **Quick Commands:** Use "From BRD" to upload requirements and generate tests in one click.
- **Manual/AI Creation:** Flexible creation modes.
- **Output:** Structured table view with Excel export.

### 🤖 Test Automation
- **Select Framework:** Choose Selenium (UI) or REST Assured (API).
- **API Specs:** Upload Swagger/OpenAPI docs for API tests.
- **Bot Style:** Enable "Bot Style Architecture" for Action-based pattern.
- **Generate:** Download robust Java code.

### � Bug Report Generator
- **Input:** Describe bug in English or Arabic (or rough notes).
- **Context:** Select Environment and Browser.
- **Language:** Choose output language (English translation available).
- **Output:** Copy JIRA-ready markdown.

### � Test Plan Generator
- Upload requirements -> Generate full test strategy and plan.

---

## 🛡️ Enterprise Java Standards

- Java 17
- Selenium WebDriver & REST Assured
- TestNG
- Page Object Model (POM)
- ActionBot (Bot Style)
- Log4j2 Logging
- Allure Reporting
- Explicit Waits
- SOLID Principles

---

## 📂 File Upload Support

- **Test Case Attachments:** PNG, JPG, PDF, TXT
- **Requirements:** PDF, DOCX, TXT, CSV, XLSX
- **API Specs:** JSON, YAML, HTML

---

## 📝 Requirements

See [`requirements.txt`](./requirements.txt).

---

## 👤 Author

- [Abdelrahman Kandil](https://github.com/AbdelrahmanKandil)
- Developed by Abdelrahman Kandil

---

> 🤖🦾🦿 RoboTest AI Suite | Powered by Google Gemini, OpenAI ChatGPT, Anthropic Claude & Streamlit
