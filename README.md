# Consultant Assistant

## Overview
The **Consultant Assistant** is a tool powered by **LangGraph** designed to assist consultants in their daily workflows by integrating with various enterprise systems. While the initial focus is on Salesforce for CRM-related tasks, the tool is intended to expand to support additional systems such as **Egencia** for travel booking, **ChromeRiver** for expense management, **Workday** for feedback and HR tasks, and **time entry systems** for logging work hours. This assistant acts as a **consultant’s AI buddy**, helping drive sales, manage travel, submit expenses, track feedback, and ensure seamless time tracking.

The assistant utilizes OpenAI's **AzureChatOpenAI**, an interactive conversational agent, and **TrustCall** for data extraction. The tool maintains memory using **SQLite** and provides structured interaction through LangGraph's **state management and workflow execution.**

---

## Current Functionality
### Implemented Features
- **Salesforce Integration:** Supports retrieving, creating, and updating Salesforce records (Leads, Accounts, Opportunities, Contacts, Cases, and Tasks).
- **Memory Management:** Stores conversational state using SQLite and a memory store for persistence.
- **OCR Processing:** Extracts text from receipts and other documents for ingestion into integrated systems.
- **Interactive CLI:** Provides a command-line interface for user interaction.
- **Workflow Automation:** Implements LangGraph-based workflows for guided interactions.
- **Multi-turn Conversations:** Handles structured conversations while remembering context.

---

## Future Vision
### Planned Features
- **Egencia Integration:** Automate travel booking for consultants.
- **ChromeRiver Integration:** Enable receipt scanning and expense submission.
- **Workday Integration:** Streamline feedback submission and HR-related tasks.
- **Time Entry System Integration:** Automate work hour logging.
- **Advanced Memory Handling:** Enhance memory retention for long-term interactions.
- **Multi-User Support:** Expand the assistant to handle multiple consultants simultaneously.
- **GUI/Web Interface:** Develop a web-based UI for better usability.

---

## Installation
### Prerequisites
- Python 3.9+
- Salesforce account with API access (if using SFDC features)
- Azure OpenAI setup
- Egencia, ChromeRiver, Workday, or time entry system access as needed
- Tesseract OCR installed (for text extraction from images)

### Setup
1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd consultant-assistant
   ```
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Set up environment variables:**
   Create a `.env` file in the project root and add:
   ```env
   SFDC_USER=<your_salesforce_username>
   SFDC_PASS=<your_salesforce_password>
   SFDC_TOKEN=<your_salesforce_security_token>
   AZURE_OPENAI_ENDPOINT=<your_azure_openai_endpoint>
   AZURE_OPENAI_CHAT_DEPLOYMENT_NAME=<your_deployment_name>
   AZURE_OPENAI_API_VERSION=<api_version>
   AZURE_OPENAI_API_KEY=<your_api_key>
   ```
4. **Run the application:**
   ```bash
   python main.py
   ```
   Use `-d` or `--debug` for debug mode.

---

## Project Structure
```
├── main.py                  # Entry point for CLI interaction
├── salesforce_tools.py      # Salesforce API tools (CRM operations)
├── attachment_tools.py      # OCR tool for extracting text from receipts and documents
├── state_manager.py         # Singleton-based state management
├── states.py                # State definitions for LangGraph
├── sys_msg.py               # System messages and conversation management
├── helpers.py               # Utility functions for message processing
├── requirements.txt         # Dependencies
├── memory_store.db          # SQLite database for storing conversation memory
```

---

## Usage
### CLI Commands
1. Start the CLI:
   ```bash
   python main.py
   ```
2. Enter a command, e.g.,
   ```bash
   USER: Find lead with email john.doe@example.com
   ```
3. The assistant will interact with Salesforce (or other integrated systems) and return relevant information.
4. To exit, type:
   ```bash
   quit
   ```

### Example Interactions
#### Current Functionality
**Retrieving a Lead:**
```
USER: Find lead with email john.doe@example.com
ASSISTANT: I found a matching lead: John Doe, Company: Acme Corp.
```

**Submitting an Expense via OCR (for Future ChromeRiver Integration):**
```
USER: Upload this receipt image
ASSISTANT: Extracted text from the receipt. Where would you like to submit it?
```

#### Planned Functionality
**Booking a Flight with Egencia (Future Feature):**
```
USER: Book a flight to New York on March 15th.
ASSISTANT: I found the best options on Egencia. Would you like me to proceed with booking?
```

**Providing Feedback via Workday (Future Feature):**
```
USER: Submit performance feedback for Alex.
ASSISTANT: What would you like to include in the feedback?
```

**Logging Time Entry (Future Feature):**
```
USER: Log 8 hours of work for the Acme project.
ASSISTANT: Time entry submitted successfully.
```

---

## Dependencies
The tool uses various libraries, including:
- **LangChain & LangGraph** (for AI workflows)
- **Azure OpenAI** (for conversational AI)
- **Simple-Salesforce** (for Salesforce API interaction)
- **Pytesseract & PIL** (for OCR functionality)
- **SQLite** (for state management)
- **Egencia, ChromeRiver, Workday APIs** (planned future integrations)

Check `requirements.txt` for the full list.

---

## Contributing
Contributions are welcome! To contribute:
1. Fork the repository.
2. Create a feature branch.
3. Submit a pull request with detailed changes.

