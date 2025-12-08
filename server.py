from datetime import datetime, date
import json
import os
import requests
import unicodedata
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from fastmcp import FastMCP
from wework import get_wework_data
from workflow import get_workflow_data
from goal import get_goal_data
from checkin_timeoff import get_checkin_data, ACCOUNT_TOKEN
from inside import get_inside_data

load_dotenv()

mcp = FastMCP(
    name="base-vn-assistant",
)

def normalize_search_name(name):
    """Chuẩn hóa tên để tìm kiếm (lowercase, NFC)"""
    if not name: return ""
    return unicodedata.normalize('NFC', name).strip().lower()

def find_user_info_by_name(target_name: str) -> Optional[Dict[str, str]]:
    """
    Find user info (username, name) via Account API using name.
    """
    try:
        target_normalized = normalize_search_name(target_name)
        
        # Search in Account API
        url = "https://account.base.vn/extapi/v1/users"
        payload = {'access_token': ACCOUNT_TOKEN}
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        response = requests.post(url, headers=headers, data=payload, timeout=30)
        
        if response.status_code == 200:
            response_json = response.json()
            user_list = []
            if isinstance(response_json, list):
                user_list = response_json
            elif isinstance(response_json, dict):
                user_list = response_json.get('users', [])
            
            # Find best match
            for user in user_list:
                u_name = user.get('name', '')
                if normalize_search_name(u_name) == target_normalized:
                    return {
                        'name': u_name,
                        'username': user.get('username', ''),
                        'id': str(user.get('id', ''))
                    }
                    
            # Relaxation: partial match if exact match fail? 
            # For now stick to exact normalized match to be safe.
            
    except Exception as e:
        print(f"Error finding user: {e}")
    return None


docstring = """
    Retrieve comprehensive employee data from Base.vn ecosystem.

    This tool fetches and aggregates data from 5 different Base.vn platforms to provide
    a complete 360-degree view of an employee's activities, performance, and status.

    Data retrieved includes:
        - Checkin (Base Checkin): Attendance records, time-off requests, and late/early stats.
        - WeWork (Base Wework): Task management, project participation, and overdue tasks.
        - Goal (Base Goal): OKR progress, key results, and goal alignment.
        - Workflow (Base Workflow): Job processing status, deadlines, and workflow participation.
        - Inside (Base Inside): Internal communication, posts, and social engagement.

    The returned data is a dictionary containing:
        - user_info: Basic user details resolved from the Name (username, id, email).
        - section: Dữ liệu đã phân tích cho từng module (checkin, wework, goal, workflow, inside),
                   gồm data (đầu vào content box) và raw_data (raw_df_records). Không trả về HTML.
        - sources: A dictionary với các key 'checkin', 'wework', 'goal', 'workflow', 'inside'.
                   Mỗi entry gồm:
                       - raw_data: Dữ liệu gốc dạng DataFrame (to_dict records) cho module đó.

    Args:
        name: Full name of the employee (e.g., 'Ngô Thị Thủy', 'Phạm Thanh Tùng').
              The tool automatically resolves this to the system username.
        year: Year for data context (e.g., 2024, 2025). Defaults to current system expectation.
        month: Month for data context (1-12). Defaults to current system expectation.

    Returns:
        A JSON-serializable dictionary with aggregated data from all sources.

    Raises:
        Exception: If the employee name cannot be resolved to a valid user.

    Examples:
        >>> # Get full report for Ngô Thị Thủy
        >>> result = get_base_data_by_name("Ngô Thị Thủy")
        
        >>> # Get report for specific time
        >>> result = get_base_data_by_name("Ngô Thị Thủy", year=2024, month=11)
"""

@mcp.tool(
    name="get_base_data_by_name",
    description=docstring,
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "openWorldHint": True
    }
)
async def get_base_data_by_name(
    name: str,
    year: int = 2025,
    month: int = 12
) -> Dict[str, Any]:
    
    # 1. Resolve User
    user_info = find_user_info_by_name(name)
    if not user_info:
        return {
            "error": f"Could not find employee with name: {name}. Please check exact spelling."
        }
    
    full_name = user_info['name']
    username = user_info['username']
    
    # 2. Fetch Data from all sources
    raw_results = {}
    
    # Checkin
    try:
        raw_results["checkin"] = get_checkin_data(full_name, year, month)
    except Exception as e:
        raw_results["checkin"] = None # Treat error as no data for formatting, or handle gracefully

    # WeWork
    try:
        raw_results["wework"] = get_wework_data(username)
    except Exception as e:
        raw_results["wework"] = None

    # Goal
    try:
        raw_results["goal"] = get_goal_data(full_name)
    except Exception as e:
        raw_results["goal"] = None

    # Workflow
    try:
        raw_results["workflow"] = get_workflow_data(full_name)
    except Exception as e:
        raw_results["workflow"] = None

    # Inside
    try:
        raw_results["inside"] = get_inside_data(full_name)
    except Exception as e:
        raw_results["inside"] = None

    # 3. Kết hợp dữ liệu (không trả về HTML)
    module_keys = ["checkin", "wework", "goal", "workflow", "inside"]
    sources_with_raw = {}
    section_data = {}

    for key in module_keys:
        raw_entry = raw_results.get(key)
        raw_data_payload = None
        analyzed_payload = raw_entry

        if isinstance(raw_entry, dict) and "raw_df_records" in raw_entry:
            raw_data_payload = raw_entry.get("raw_df_records")
            analyzed_payload = {k: v for k, v in raw_entry.items() if k != "raw_df_records"}
        else:
            raw_data_payload = raw_entry

        # Legacy-style sources payload (chỉ raw_data, không HTML)
        sources_with_raw[key] = {
            "raw_data": raw_data_payload
        }

        # New section payload: analyzed data + raw data (không HTML)
        section_data[key] = {
            "data": analyzed_payload,
            "raw_data": raw_data_payload
        }

    final_response = {
        "user_info": user_info,
        "section": section_data,
        "sources": sources_with_raw
    }

    return final_response

if __name__ == '__main__':
    mcp.run()
