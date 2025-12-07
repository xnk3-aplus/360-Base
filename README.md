# Base.vn 360 Data Aggregator

This project integrates with the **Base.vn** ecosystem to aggregate employee data from multiple applications into a comprehensive 360-degree performance report. It can be run as a standalone email reporter or as a **Model Context Protocol (MCP)** server for AI agent integration.

## 🚀 Features

-   **Data Aggregation**: Fetches data from 5 key Base.vn modules:
    -   **Base WeWork**: Task management, deadlines, completion rates.
    -   **Base Goal**: OKR tracking, progress speed, weekly check-in integrity.
    -   **Base Checkin**: Attendance, punctuality analysis (Early/Late/Standard), timesheet verification.
    -   **Base Workflow**: Process job tracking, SLA performance.
    -   **Base Inside**: Internal communication, post engagement, and influence impact.
-   **Intelligent Formatting**: Generates structured HTML "content boxes" mimicking professional email reports.
-   **MCP Server Integration**: Exposes a `get_base_data_by_name` tool via FastMCP, allowing LLMs to retrieve and understand employee context.
-   **Smart User Resolution**: Automatically resolves employee names (e.g., "Ngô Thị Thủy") to internal Basenames and IDs.

## 🛠️ Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/xnk3-aplus/360-Base.git
    cd 360-Base
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration**:
    Create a `.env` file in the root directory (copied from the example below) and populate it with your Base.vn API access tokens. **Note: The `.env` file is ignored by git for security.**

    ```ini
    # .env example
    ACCOUNT_ACCESS_TOKEN=your_account_token
    WEWORK_ACCESS_TOKEN=your_wework_token
    WORKFLOW_ACCESS_TOKEN=your_workflow_token
    GOAL_ACCESS_TOKEN=your_goal_token
    INSIDE_API_KEY=your_inside_token
    CHECKIN_TOKEN=your_checkin_token
    TIMEOFF_TOKEN=your_timeoff_token
    ```

## 💻 Usage

### 1. Run as MCP Server (Recommended)
This starts a FastMCP server that exposes the data tools to an MCP client (like Claude Desktop or an AI Agent).

```bash
python server.py
```

-   **Tool**: `get_base_data_by_name(name: str)`
-   **Output**: JSON object containing user info and pre-formatted HTML content blocks for each platform.

### 2. Run as Standalone Reporter
You can run the core logic directly to generate a report for a specific employee (configurable in `app.py`).

```bash
python app.py
```

## 📂 Project Structure

-   `server.py`: Main MCP server entry point. Defines tools and handles requests.
-   `base_formatter.py`: Logic for formatting raw API data into beautiful HTML content boxes.
-   `app.py`: Legacy standalone application and testing utility.
-   **Modules**:
    -   `checkin_timeoff.py`: Handles attendance & time-off logic.
    -   `wework.py`: Project & task logic.
    -   `goal.py`: OKR logic.
    -   `workflow.py`: Process management logic.
    -   `inside.py`: Internal social network logic.

## 🔒 Security Note
This project handles sensitive employee data. Ensure your `.env` file is never committed to version control. The included `.gitignore` is pre-configured to exclude it.