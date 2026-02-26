import json
import os
from datetime import datetime

def update_notebook():
    nb_path = r'c:\Users\Hii\Documents\New folder (9)\app_v2_all_notebook.ipynb'
    print(f"Reading notebook from: {nb_path}")
    
    with open(nb_path, 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    cells = nb['cells']
    
    # 1. Update Imports (Cell 2 or 3 usually, look for imports)
    found_import = False
    for cell in cells:
        if cell['cell_type'] == 'code' and "import requests" in "".join(cell['source']):
            print("Updating Import Cell...")
            cell['source'] = [
                "import sys, os, warnings, pytz\n",
                "import pandas as pd\n",
                "from datetime import datetime\n",
                "sys.path.append('.')\n",
                "\n",
                "# Import Modules\n",
                "try:\n",
                "    from app_v2_all import get_employee_info_from_api, create_email_html, format_ai_content_to_html, generate_ai_insight, hcm_tz, API_KEYS, EMAIL_GUI, MAT_KHAU\n",
                "    from checkin_timeoff import get_checkin_data, CheckinLoader, DetailedAttendanceAnalyzer\n",
                "    from wework import get_wework_data, WeWorkAPIClient\n",
                "    from goal import get_goal_data, GoalAPIClient\n",
                "    from inside import get_inside_data\n",
                "    from workflow import get_workflow_data\n",
                "    print('✅ Imported modules from local scripts successfully')\n",
                "except ImportError as e:\n",
                "    print(f'❌ Import Error: {e}')\n",
                "    print('⚠️ Please ensure python files (app_v2_all.py, etc.) are in the same directory')\n",
                "\n",
                "warnings.filterwarnings('ignore')\n"
            ]
            found_import = True
            break
            
    if not found_import:
        print("⚠️ Warning: Import cell not found.")

    # 2. Clear Redundant Code Cells
    targets = [
        "class InsightItem", 
        "class WeWorkAPIClient", 
        "class GoalAPIClient", 
        "class CheckinLoader", 
        "def get_all_news_and_articles", 
        "def get_workflow_data", 
        "def format_ai_content_to_html"
    ]
    
    new_cells = []
    for cell in cells:
        keep_cell = True
        if cell['cell_type'] == 'code':
            src = "".join(cell['source']).strip()
            # 1. Check against targets
            for t in targets:
                # Check for original code or already-replaced comments
                if src.startswith(t) or src.startswith(t.split('(')[0]) or src.startswith(f"# Code for {t}"): 
                    print(f"Removing redundant cell: {t}...")
                    keep_cell = False
                    break
            
            # 2. Check for empty cells
            if not src:
                print("Removing empty cell...")
                keep_cell = False
                
        if keep_cell:
            new_cells.append(cell)
            
    cells = new_cells
    nb['cells'] = cells

    # 3. Update Main Execution Cell
    main_code = [
        "\n",
        "# ==============================================================================\n",
        "# 🚀 MAIN EXECUTION\n",
        "# ==============================================================================\n",
        "\n",
        "def run_report_demo(target_name=\"Hoang Tran\"):\n",
        "    print(\"=\"*80)\n",
        "    print(f\"📧 DEMO: BÁO CÁO TỔNG HỢP CHO: {target_name.upper()}\")\n",
        "    print(\"=\"*80)\n",
        "    \n",
        "    # 1. Identify User\n",
        "    user_info = get_employee_info_from_api(target_name)\n",
        "    if not user_info:\n",
        "        print(f\"❌ Không tìm thấy nhân viên: {target_name}\")\n",
        "        return\n",
        "\n",
        "    emp_name = user_info['name']\n",
        "    emp_username = user_info.get('username', '')\n",
        "    emp_email = user_info.get('email', '')\n",
        "    join_date = user_info.get('since', '') # NEW: Get join date\n",
        "    \n",
        "    print(f\"✅ Found: {emp_name} ({emp_username}) - Join Date: {join_date}\")\n",
        "\n",
        "    # 2. Fetch Data\n",
        "    print(\"\\n🔄 Đang tải dữ liệu...\")\n",
        "    \n",
        "    # Server Data (Logic App)\n",
        "    try:\n",
        "        import app_v2_logic\n",
        "        # Reload to ensure latest changes if editing interactively\n",
        "        import importlib\n",
        "        importlib.reload(app_v2_logic)\n",
        "        server_data = app_v2_logic.get_review_user_work_plus_data(emp_name)\n",
        "        print(\"  - Server/Logic data: OK\")\n",
        "    except Exception as e:\n",
        "        print(f\"  - Server/Logic error: {e}\")\n",
        "        server_data = None\n",
        "        \n",
        "    # Standard Modules\n",
        "    # NEW: Pass join_date and date params to checkin\n",
        "    today = datetime.now()\n",
        "    checkin = get_checkin_data(emp_name, today.year, today.month, join_date=join_date)\n",
        "    \n",
        "    wework = get_wework_data(emp_username)\n",
        "    goal = get_goal_data(emp_name)\n",
        "    inside = get_inside_data(emp_name)\n",
        "    workflow = get_workflow_data(emp_name)\n",
        "    \n",
        "    print(\"  - Base Modules data: OK\")\n",
        "\n",
        "    # --- NEW: Recent Data Filter Logic ---\n",
        "    # Calculate one month ago\n",
        "    from datetime import timedelta\n",
        "    one_month_ago = today - timedelta(days=30)\n",
        "    one_month_ago_ts = one_month_ago.timestamp()\n",
        "\n",
        "    # Kiểm tra dữ liệu gần đây\n",
        "    has_recent_wework = False\n",
        "    if wework and wework.get('recent_tasks'):\n",
        "        for task in wework['recent_tasks']:\n",
        "            since_ts = task.get('since', 0)\n",
        "            if since_ts and float(since_ts) >= one_month_ago_ts:\n",
        "                has_recent_wework = True\n",
        "                break\n",
        "\n",
        "    has_recent_workflow = False\n",
        "    if workflow and workflow.get('latest_jobs'):\n",
        "        for job in workflow['latest_jobs']:\n",
        "            date_str = job.get('date', '')\n",
        "            if date_str and date_str != 'N/A':\n",
        "                try:\n",
        "                    job_date = datetime.strptime(date_str, '%d/%m/%Y %H:%M:%S')\n",
        "                    if job_date >= one_month_ago:\n",
        "                        has_recent_workflow = True\n",
        "                        break\n",
        "                except:\n",
        "                    pass\n",
        "\n",
        "    has_recent_goal = bool(goal and goal.get('weekly'))\n",
        "    active_sections_count = sum([has_recent_wework, has_recent_workflow, has_recent_goal])\n",
        "\n",
        "    if active_sections_count == 0:\n",
        "        print(f\"⚠️ {emp_name}: Không có dữ liệu gần đây. Vẫn gửi email cảnh báo.\")\n",
        "        wework = {\n",
        "            'summary': {'total_tasks': 0},\n",
        "            'is_warning_only': True\n",
        "        }\n",
        "        goal = None\n",
        "        workflow = None\n",
        "    else:\n",
        "        if not has_recent_wework: wework = None\n",
        "        if not has_recent_workflow: workflow = None\n",
        "        if not has_recent_goal: goal = None\n",
        "    # -------------------------------------\n",
        "\n",
        "    # 3. Generate HTML\n",
        "    print(\"\\n🎨 Đang tạo HTML báo cáo (kèm AI Insight)...\")\n",
        "    html_content = create_email_html(emp_name, checkin, wework, goal, inside, workflow, server_data)\n",
        "    \n",
        "    # 4. Preview / Send\n",
        "    preview_file = \"notebook_report_preview.html\"\n",
        "    with open(preview_file, \"w\", encoding=\"utf-8\") as f:\n",
        "        f.write(html_content)\n",
        "    print(f\"✅ Đã tạo file xem trước: {preview_file}\")\n",
        "    \n",
        "    # Uncomment to send\n",
        "    # send_email(emp_email, f\"BÁO CÁO TỔNG HỢP - {emp_name}\", html_content)\n",
        "\n",
        "# --- RUN ---\n",
        "run_report_demo(\"Hoang Tran\")\n"
    ]
    
    # Locate main cell
    found_main = False
    for cell in reversed(cells): # Search from end
        if cell['cell_type'] == 'code' and "def run_report_demo" in "".join(cell['source']):
            print("Updating Main Execution Cell...")
            cell['source'] = main_code
            found_main = True
            break
            
    if not found_main:
        print("⚠️ Warning: Main cell not found, appending...")
        cells.append({
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": main_code
        })

    # 4. Annotations for AI Section
    print("Adding Annotations...")
    for cell in cells:
        if cell['cell_type'] == 'markdown' and "## 🤖 AI & Email Functions" in "".join(cell['source']):
            src = "".join(cell['source'])
            if "### 📝 Note on AI Processing" not in src:
                annotation = "\n\n### 📝 Note on AI Processing\n" + \
                             "- **Model**: Gemini-3-flash-preview (via Ollama)\n" + \
                             "- **Privacy**: Data is processed locally/via private API.\n" + \
                             "- **Fallback**: Automatic key rotation enabled for API stability.\n"
                cell['source'].append(annotation)
                print("✅ Added AI Annotations.")
            break

    # Save
    with open(nb_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=4, ensure_ascii=False)
    print(f"✅ Notebook updated successfully: {nb_path}")

if __name__ == "__main__":
    update_notebook()
