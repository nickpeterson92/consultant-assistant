# Salesforce Assistant

## Overview
The **Salesforce Assistant** is a tool powered by **LangGraph** that integrates with Salesforce to assist users with various CRM-related tasks, such as retrieving, creating, updating, and managing Salesforce records. The assistant utilizes OpenAI's **AzureChatOpenAI**, an interactive conversational agent, and **TrustCall** for data extraction. The tool maintains memory using **SQLite** and provides structured interaction through LangGraph's **state management and workflow execution.**

## Features
- **Salesforce Integration:** Enables seamless interaction with Salesforce objects like Leads, Accounts, Opportunities, Contacts, Cases, and Tasks.
- **Memory Management:** Stores conversational state using SQLite and a memory store for persistence.
- **OCR Processing:** Extracts text from image files using Tesseract OCR.
- **Interactive CLI:** Provides a command-line interface for user interaction.
- **Workflow Automation:** Implements LangGraph-based workflows for guided interactions.
- **Multi-turn Conversations:** Handles structured conversations while remembering context.

---

## Installation
### Prerequisites
- Python 3.9+
- Salesforce account with API access
- Azure OpenAI setup
- Tesseract OCR installed (for text extraction from images)

### Setup
1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd salesforce-assistant
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
├── salesforce_tools.py      # Salesforce API tools (CRUD operations)
├── attachment_tools.py      # OCR tool for extracting text from images
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
3. The assistant will interact with Salesforce and return relevant information.
4. To exit, type:
   ```bash
   quit
   ```

### Example Interactions
**Retrieving a Lead:**
```
USER: Find lead with email john.doe@example.com
ASSISTANT: I found a matching lead: John Doe, Company: Acme Corp.
```

**Creating an Opportunity:**
```
USER: Create an opportunity named "Big Deal" with $100,000 for Acme Corp.
ASSISTANT: Opportunity "Big Deal" has been created successfully.
```

---

## Dependencies
The tool uses various libraries, including:
- **LangChain & LangGraph** (for AI workflows)
- **Azure OpenAI** (for conversational AI)
- **Simple-Salesforce** (for Salesforce API interaction)
- **Pytesseract & PIL** (for OCR functionality)
- **SQLite** (for state management)

Check `requirements.txt` for the full list.

---

## Future Enhancements
- **GUI/Web Interface:** Adding a web-based interface for better usability.
- **Advanced Memory Handling:** Enhancing memory retention for long-term interactions.
- **Multi-User Support:** Expanding the assistant to handle multiple users simultaneously.

---

## Contributing
Contributions are welcome! To contribute:
1. Fork the repository.
2. Create a feature branch.
3. Submit a pull request with detailed changes.

---

## License
This project is licensed under the MIT License.

