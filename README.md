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
- 💬 **Chat with AI assistant** for QA guidance and testing best practices
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

### 🤖 Test Case Generation Robot
- **AI-Powered Test Case Generation:**  
  Input requirements or user stories, and instantly generate comprehensive test cases in JSON format.
- **Multi-Language Support:**  
  Generate test cases in **English** or **Arabic** language.
- **Configurable Severity Levels:**  
  Critical, Major, Normal, Minor with descriptive tooltips.
- **Manual Test Case Authoring:**  
  Create, edit, and manage your own test cases with rich forms and attachment support.
- **Bulk Test Case Management:**  
  Select all, deselect all, copy, delete, and batch-generate automation code for multiple test cases.
- **Export to Excel:**  
  Download all test cases as Excel (.xlsx) file for external use.

### 🦾 Automation Code Generation Robot
- **Multiple Design Patterns:**
  - ✅ **Page Object Model (POM)** with `@FindBy` annotations
  - ✅ **OOP Principles** (Inheritance, Encapsulation, SOLID)
  - ✅ **Bot Style Architecture** - Fluent/chainable API for action sequences
  - ✅ **Data-Driven Testing** with `@DataProvider`
  - ✅ **BDD Style Comments** - Given-When-Then format
- **Combined or Separate Generation:**
  - Generate a single Java test class for multiple selected test cases
  - Generate separate Java classes per test case
- **Custom Instructions:**  
  Add your own requirements and instructions to customize generated code
- **Downloadable Artifacts:**  
  Download generated code as a ready-to-use ZIP archive.

### 📋 Test Plan Generation Robot
- **Comprehensive Test Plans:**  
  Generate professional test plans from requirements documents
- **Team Allocation:**  
  Add testers with specialization (Manual, Automation, Junior/Fresher) and experience levels
- **Timeline Planning:**  
  Set start and end dates with automatic working days calculation
- **Rich Output Sections:**
  - Test Plan Overview
  - Test Scope and Objectives
  - Test Strategy
  - Test Environment Requirements
  - Test Deliverables
  - Resource Allocation Table
  - Task Allocation Table
  - Test Schedule/Timeline Table
  - Risk Assessment Table
  - Entry and Exit Criteria
- **Export Options:**  
  Download as Markdown or Text file

### 💬 AI Chat Assistant Robot
- **24/7 QA Expert:**  
  Ask questions about testing strategies, automation frameworks, or specific testing challenges
- **Conversation History:**  
  Maintains chat context for natural conversation flow
- **Quick Prompts:**  
  Pre-defined prompts for common QA questions
- **Expert Guidance:**  
  Best practices, troubleshooting, and technical support

### 🎨 Enterprise UI/UX
- Modern, responsive Streamlit web app with advanced CSS styling
- Toast notifications for user feedback
- Expandable/collapsible test case cards
- File attachment previews for images
- Dark-themed code display
- Robot-themed status indicators

---

## 🏗️ Tech Stack

- [Streamlit](https://streamlit.io/) — UI framework
- [Google Gemini](https://ai.google.dev/) — AI test case/code generation
- [OpenAI GPT-4](https://openai.com/) — AI test case/code generation
- [Anthropic Claude](https://anthropic.com/) — AI test case/code generation
- [PyPDF2](https://pypi.org/project/pypdf2/), [python-docx](https://pypi.org/project/python-docx/), [pandas](https://pandas.pydata.org/) — File parsing
- [openpyxl](https://pypi.org/project/openpyxl/) — Excel file generation
- [requests](https://pypi.org/project/requests/) — API communication
- [Base64](https://docs.python.org/3/library/base64.html) — Attachment encoding

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
GITHUB_MODEL=openai/gpt-4o-mini  # or gpt-5 if available to your org
```

> **Note:** You need access to at least one AI provider:
> - [Google Gemini API](https://makersuite.google.com/app/apikey)
> - [OpenAI API](https://platform.openai.com/api-keys)
> - [Anthropic API](https://console.anthropic.com/)
> - [GitHub Models](https://docs.github.com/en/github-models/quickstart) (PAT with `models` scope)

### 4. Run the App

```bash
streamlit run streamlit_app.py
```

---

## 🧪 Usage

### 🏠 Home

- Welcome & feature summary with robot-themed UI
- AI provider status indicators (Online/Offline)
- Quick start guide
- Navigation sidebar with AI provider selection

### 🧪 Test Case Generator

- **Manual Creation:**  
  Fill in scenario, steps, expected results, and attach files/screenshots.
- **AI Generation:**  
  Enter user stories or requirements → Get instant, structured test cases.
- **Language Selection:**  
  Choose English or Arabic for generated test cases.
- **Severity Configuration:**  
  Set default severity (Critical/Major/Normal/Minor).
- **Bulk Actions:**  
  Select all, deselect all, copy, delete, or send test cases to automation.
- **Excel Export:**  
  Download all test cases as Excel file.

### 🤖 Test Automation

- **Design Pattern Selection:**
  - Page Object Model (POM)
  - OOP Principles
  - Bot Style Architecture
  - Data-Driven Testing
  - BDD Style Comments
- **Custom Instructions:**  
  Add specific requirements for code generation.
- **Combined Suite:**  
  Generate a single Java test class for multiple selected test cases.
- **Separate Files:**  
  Generate separate Java classes per test case.
- **Download ZIP:**  
  Download all Java source files as a ready-to-import zip.

### 📋 Test Plan Generator

- **Requirements Input:**  
  Upload files (PDF, DOCX, TXT, CSV, XLSX) or enter manually.
- **Timeline Configuration:**  
  Set start/end dates with working days calculation.
- **Team Configuration:**  
  Add testers with specialization and experience levels.
- **Custom Instructions:**  
  Add specific focus areas or requirements.
- **Export Options:**  
  Download as Markdown or Text file.

### 💬 AI Chat

- **Natural Conversation:**  
  Chat with AI about testing, automation, and QA.
- **Quick Prompts:**  
  Use pre-defined prompts for common questions.
- **Chat History:**  
  Clear or continue conversations.

---

## 🛡️ Enterprise Java Standards

- Java 17
- Selenium WebDriver
- TestNG
- Page Object Model (with `@FindBy`)
- Bot Style Architecture (Fluent API)
- WebDriver Factory (Factory Pattern)
- Singleton configuration
- Log4j2 logging
- Allure reporting annotations
- Explicit waits with `WebDriverWait`
- Thread-safe implementation
- Data-driven testing with `@DataProvider`
- BDD-style Given-When-Then comments
- SOLID principles
- Meaningful assertions

---

## 📂 File Upload Support

- **Test Case Attachments:**  
  - Images: PNG, JPG, JPEG
  - Docs: PDF, TXT
- **Requirement Uploads:**  
  - TXT, PDF, DOCX, CSV, XLSX (auto-parsed)
- **Test Plan Documents:**  
  - PDF, DOCX, TXT, CSV, XLSX

---

## 📝 Requirements

See [`requirements.txt`](./requirements.txt):

- `streamlit`
- `python-dotenv`
- `google-generativeai`
- `PyPDF2`
- `python-docx`
- `pandas`
- `openpyxl`
- `requests`
- `sentence_transformers`
- `faiss-cpu`
- `tabulate`
- `google-genai`

---

## 🔧 Configuration Options

### AI Provider Settings
- **Auto Mode:** Automatically uses available providers with fallback
- **Manual Mode:** Select specific provider (Gemini, Claude, or OpenAI)
- **UI Configuration:** Enter your personal API keys in the sidebar "🔑 API Configuration" expander (overrides environment variables).

### Test Case Settings
- **Module Name:** Customize test case ID prefix
- **Default Priority:** High, Medium, Low
- **Default Severity:** Critical, Major, Normal, Minor
- **Language:** English or Arabic
- **Clear After Save:** Auto-clear form after saving

### Automation Code Settings
- **Page Object Model:** Enable/disable POM pattern
- **OOP Principles:** Enable/disable inheritance and SOLID
- **Bot Style:** Enable/disable fluent API pattern
- **Data-Driven:** Enable/disable @DataProvider
- **BDD Style:** Enable/disable Given-When-Then comments
- **Custom Instructions:** Add specific requirements

---

## 🙌 Contributing

Pull requests are welcome!  
For major changes, please open an issue first to discuss what you would like to change.

---

## 📄 License

Proprietary/Private License — see [LICENSE](LICENSE).

- All rights reserved; no redistribution or publication permitted.
- No copying, modification, sublicensing, or commercial use without prior written consent.
- Provided “as is” without warranties; see LICENSE for full terms.

---

## 👤 Author

- [Abdelrahman Kandil](https://github.com/AbdelrahmanKandil)
- Developed by Abdelrahman Kandil

---

> 🤖🦾🦿 RoboTest AI Suite | Powered by Google Gemini, OpenAI ChatGPT, Anthropic Claude & Streamlit
>
> Copyright © 2026
