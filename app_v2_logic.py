import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import pytz
from collections import Counter
import math
import os
import json
from dotenv import load_dotenv

load_dotenv()

# Tokens
GOAL_ACCESS_TOKEN = os.getenv('GOAL_ACCESS_TOKEN')
ACCOUNT_ACCESS_TOKEN = os.getenv('ACCOUNT_ACCESS_TOKEN')
TABLE_ACCESS_TOKEN = os.getenv('TABLE_ACCESS_TOKEN')
WEWORK_ACCESS_TOKEN = os.getenv('WEWORK_ACCESS_TOKEN')
HCM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Mappings
DEPT_ID_MAPPING = {
    "450": "BP Thị Trường",
    "451": "BP Cung Ứng",
    "452": "BP Nhân Sự Hành Chính",
    "453": "BP Tài Chính Kế Toán",
    "542": "Khối hiện trường (các vùng miền)",
    "651": "Ban Giám Đốc",
    "652": "BP R&D, Business Line mới"
}

TEAM_ID_MAPPING = {
    "307": "Đội Bán hàng - Chăm sóc khách hàng",
    "547": "Đội Nguồn Nhân Lực",
    "548": "Đội Kế toán - Quản trị",
    "1032": "Team Hoàn Thuế VAT (Nhóm)",
    "1128": "Đội Thanh Hóa (Miền Bắc)",
    "1129": "Đội Quy Nhơn",
    "1133": "Đội Hành chính - Số hóa",
    "1134": "Team Thực tập sinh - Thử nghiệm mới (Nhóm)",
    "1138": "Đội Marketing - AI",
    "1141": "Đội Tài chính - Đầu tư",
    "1148": "Đội Logistic quốc tế - Thị trường",
    "546": "Đội Mua hàng - Out source",
    "1130": "Đội Daknong",
    "1131": "Đội KCS VT-SG",
    "1135": "Đội Chuỗi cung ứng nội địa - Thủ tục XNK",
    "1132": "Đội Văn hóa - Chuyển hóa",
    "1136": "Đội Chất lượng - Sản phẩm",
    "1137": "Team 1 (Nhóm 1)",
    "1139": "Đội Data - Hệ thống - Số hóa",
    "1375": "AGILE _ DỰ ÁN 1"
}

def _make_request(url: str, data: dict, description: str = "") -> requests.Response:
    """Make HTTP request with simple error handling"""
    try:
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        return response
    except Exception as e:
        print(f"Error {description}: {e}")
        # Return a mock response with error json if needed, or re-raise
        # For simplicity in this logic module, we might re-raise or return None
        # But calling code expects response object or handles exception.
        raise e

def get_cycle_list() -> list:
    url = "https://goal.base.vn/extapi/v1/cycle/list"
    data = {'access_token_v2': GOAL_ACCESS_TOKEN}
    try:
        response = _make_request(url, data, "fetching cycle list")
        cycles_data = response.json()
        quarterly_cycles = []
        for cycle in cycles_data.get('cycles', []):
            if cycle.get('metatype') == 'quarterly':
                try:
                    start_time = datetime.fromtimestamp(float(cycle['start_time']))
                    end_time = datetime.fromtimestamp(float(cycle['end_time']))
                    quarterly_cycles.append({
                        'name': cycle['name'],
                        'id': str(cycle.get('id', '')),
                        'path': cycle['path'],
                        'start_time': start_time,
                        'end_time': end_time,
                    })
                except:
                    continue
        return sorted(quarterly_cycles, key=lambda x: x['start_time'], reverse=True)
    except:
        return []

def get_checkins_data(cycle_path: str) -> list:
    url = "https://goal.base.vn/extapi/v1/cycle/checkins"
    all_checkins = []
    print(f"Fetching checkins for {cycle_path}...")
    for page in range(1, 51):
        data = {"access_token_v2": GOAL_ACCESS_TOKEN, "path": cycle_path, "page": page}
        try:
            response = requests.post(url, data=data, timeout=30)
            if response.status_code != 200: break
            
            response_data = response.json()
            if isinstance(response_data, list) and len(response_data) > 0:
                response_data = response_data[0]
            
            checkins = response_data.get('checkins', [])
            if not checkins: break
            all_checkins.extend(checkins)
            if len(checkins) < 10: break
        except: break
    return all_checkins

def get_goals_and_krs(cycle_path: str) -> tuple:
    url = "https://goal.base.vn/extapi/v1/cycle/get.full"
    data = {'access_token_v2': GOAL_ACCESS_TOKEN, 'path': cycle_path}
    try:
        response = requests.post(url, data=data, timeout=30)
        cycle_data = response.json()
        goals = cycle_data.get('goals', [])
        
        krs_url = "https://goal.base.vn/extapi/v1/cycle/krs"
        all_krs = []
        for page in range(1, 20):
            krs_data = {"access_token_v2": GOAL_ACCESS_TOKEN, "path": cycle_path, "page": page}
            res = requests.post(krs_url, data=krs_data, timeout=30)
            kd = res.json()
            if isinstance(kd, list) and kd: kd = kd[0]
            krs = kd.get("krs", [])
            if not krs: break
            all_krs.extend(krs)
            if len(krs) < 20: break
            
        return goals, all_krs
    except:
        return [], []

def get_user_names() -> list:
    """Get list of users from Account API"""
    url = "https://account.base.vn/extapi/v1/users"
    # Account token logic
    key = "access_token_v2" if "~" in ACCOUNT_ACCESS_TOKEN else "access_token"
    data = {key: ACCOUNT_ACCESS_TOKEN}
    try:
        response = requests.post(url, data=data, timeout=30)
        res_json = response.json()
        users_list = res_json.get('users', [])
        return [{'id': str(u.get('id', '')), 'name': u.get('name', ''), 'username': u.get('username', '')} for u in users_list]
    except:
        return []

def get_target_sub_goal_ids(target_id: str) -> list:
    url = "https://goal.base.vn/extapi/v1/target/get"
    data = {'access_token_v2': GOAL_ACCESS_TOKEN, 'id': str(target_id)}
    try:
        response = requests.post(url, data=data, timeout=10)
        response_data = response.json()
        if response_data and 'target' in response_data:
            cached_objs = response_data['target'].get('cached_objs', [])
            if isinstance(cached_objs, list):
                return [str(item.get('id')) for item in cached_objs if 'id' in item]
        return []
    except:
        return []

def parse_targets_logic(cycle_path: str) -> pd.DataFrame:
    url = "https://goal.base.vn/extapi/v1/cycle/get.full"
    data = {'access_token_v2': GOAL_ACCESS_TOKEN, 'path': cycle_path}
    try:
        response = requests.post(url, data=data, timeout=30)
        response_data = response.json()
        if not response_data or 'targets' not in response_data: return pd.DataFrame()
        
        all_targets = []
        raw_targets = response_data.get('targets', [])
        company_targets_map = {str(t.get('id', '')): {'id': str(t.get('id', '')), 'name': t.get('name', '')} for t in raw_targets if t.get('scope') == 'company'}
        
        collected_targets = []
        def extract_form_data(target_obj):
            form_data = {"Mức độ đóng góp vào mục tiêu công ty": "", "Mức độ ưu tiên mục tiêu của Quý": "", "Tính khó/tầm ảnh hưởng đến hệ thống": ""}
            if 'form' in target_obj and isinstance(target_obj['form'], list):
                for item in target_obj['form']:
                    key = item.get('name')
                    if key: form_data[key] = item.get('value')
            return form_data

        for t in raw_targets:
            t_id = str(t.get('id', ''))
            scope = t.get('scope', '')
            parent_id = str(t.get('parent_id') or '')
            
            if scope in ['dept', 'team'] and parent_id in company_targets_map:
                parent = company_targets_map[parent_id]
                target_data = {
                    'target_id': t_id,
                    'target_company_id': parent['id'],
                    'target_company_name': parent['name'],
                    'target_name': t.get('name', ''),
                    'target_scope': scope,
                    'target_dept_id': None, 'target_dept_name': None,
                    'target_team_id': None, 'target_team_name': None,
                    'team_id': str(t.get('team_id', '')),
                    'dept_id': str(t.get('dept_id', ''))
                }
                target_data.update(extract_form_data(t))
                collected_targets.append(target_data)
            elif scope == 'company':
                if 'cached_objs' in t and isinstance(t['cached_objs'], list):
                    for kr in t['cached_objs']:
                        sub_data = {
                            'target_id': str(kr.get('id', '')),
                            'target_company_id': t_id,
                            'target_company_name': t.get('name', ''),
                            'target_name': kr.get('name', ''),
                            'target_scope': kr.get('scope', ''),
                            'target_dept_id': None, 'target_dept_name': None,
                            'target_team_id': None, 'target_team_name': None,
                            'team_id': str(kr.get('team_id', '')),
                            'dept_id': str(kr.get('dept_id', ''))
                        }
                        sub_data.update(extract_form_data(kr))
                        collected_targets.append(sub_data)

        for i, target_data in enumerate(collected_targets):
            if target_data['target_scope'] == 'dept':
                target_data['target_dept_id'] = target_data['target_id']
                target_data['target_dept_name'] = target_data['target_name']
            elif target_data['target_scope'] == 'team':
                target_data['target_team_id'] = target_data['target_id']
                target_data['target_team_name'] = target_data['target_name']
                
            # Skipping get_target_sub_goal_ids call for speed if needed, but robust logic includes it
            # target_data['list_goal_id'] = get_target_sub_goal_ids(target_data['target_id'])
            # Since this is "review user work", maybe strict target mapping isn't 100% required if slow, but let's keep basic
            
            all_targets.append(target_data)
            
        return pd.DataFrame(all_targets)
    except Exception as e:
        print(f"Error parsing targets: {e}")
        return pd.DataFrame()

def _get_full_data_logic(cycle_path: str) -> list:
    try:
        checkins = get_checkins_data(cycle_path)
        goals, krs = get_goals_and_krs(cycle_path)
        targets_df = parse_targets_logic(cycle_path)
        
        user_list = get_user_names()
        user_map = {u['id']: u['name'] for u in user_list}
        goal_map = {str(g['id']): g for g in goals}
        
        targets_map = {}
        if not targets_df.empty:
            for _, row in targets_df.iterrows():
                targets_map[str(row['target_id'])] = row.to_dict()
                
        full_data = []
        
        def extract_fv(form_array, field_name):
            if not form_array or not isinstance(form_array, list): return ""
            for item in form_array:
                if item.get('name') == field_name: return item.get('value', item.get('display', ""))
            return ""

        def cvt_time(ts):
            if not ts: return ''
            try:
                dt_utc = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                return dt_utc.astimezone(HCM_TZ).strftime('%Y-%m-%d %H:%M:%S')
            except:
                return ''

        for kr in krs:
            kr_id = str(kr.get('id', ''))
            if not kr_id: continue
            
            goal_id = str(kr.get('goal_id', ''))
            goal = goal_map.get(goal_id, {})
            goal_user_id = str(goal.get('user_id', ''))
            target_id_ref = str(goal.get('target_id', ''))
            t_info = targets_map.get(target_id_ref, {})
            
            g_dept_id = str(goal.get('dept_id', '0'))
            g_team_id = str(goal.get('team_id', '0'))
            
            base_row = {
                'goal_id': goal_id,
                'goal_name': goal.get('name', ''),
                'goal_content': goal.get('content', ''),
                'goal_since': cvt_time(goal.get('since')),
                'goal_current_value': goal.get('current_value', 0),
                'goal_user_id': goal_user_id,
                'goal_target_id': target_id_ref,
                'kr_id': kr_id,
                'kr_name': kr.get('name', ''),
                'kr_content': kr.get('content', ''),
                'goal_user_name': user_map.get(goal_user_id, f"User_{goal_user_id}"),
                # Target info
                'target_id': t_info.get('target_id', ''),
                'target_name': t_info.get('target_name', ''),
                'target_company_name': t_info.get('target_company_name', ''),
                'dept_name': DEPT_ID_MAPPING.get(g_dept_id, ""),
                'team_name': TEAM_ID_MAPPING.get(g_team_id, ""),
                'Mức độ đóng góp vào mục tiêu công ty': extract_fv(goal.get('form', []), 'Mức độ đóng góp vào mục tiêu công ty'),
                'Mức độ ưu tiên mục tiêu của Quý': extract_fv(goal.get('form', []), 'Mức độ ưu tiên mục tiêu của Quý'),
                'Tính khó/tầm ảnh hưởng đến hệ thống': extract_fv(goal.get('form', []), 'Tính khó/tầm ảnh hưởng đến hệ thống'),
            }
            # Merge other target fields if needed
            
            kr_checkins = [c for c in checkins if str(c.get('obj_export', {}).get('id', '')) == kr_id]
            
            if not kr_checkins:
                row = base_row.copy()
                row.update({'checkin_id': '', 'checkin_name': '', 'checkin_since': '', 'cong_viec_tiep_theo': '', 'checkin_kr_current_value': 0, 'checkin_user_id': ''})
                full_data.append(row)
            else:
                for c in kr_checkins:
                    row = base_row.copy()
                    c_form = c.get('form', [])
                    row.update({
                        'checkin_id': str(c.get('id', '')),
                        'checkin_name': c.get('name', ''),
                        'checkin_since': cvt_time(c.get('since')),
                        'cong_viec_tiep_theo': extract_fv(c_form, 'Công việc tiếp theo') or extract_fv(c_form, 'Mô tả tiến độ') or extract_fv(c_form, 'Những công việc quan trọng, trọng yếu, điểm nhấn thực hiện trong Tuần để đạt được kết quả (không phải công việc giải quyết hàng ngày)') or '',
                        'checkin_kr_current_value': c.get('current_value', 0),
                        'checkin_user_id': str(c.get('user_id', ''))
                    })
                    full_data.append(row)
        return full_data
    except Exception as e:
        print(f"Error fetching full data: {e}")
        return []

def get_cosine_similarity(str1: str, str2: str) -> float:
    if not str1 or not str2: return 0.0
    s1, s2 = str1.lower(), str2.lower()
    def get_grams(text, n=2): return [text[i:i+n] for i in range(len(text)-n+1)]
    n = 2 if len(s1) > 2 and len(s2) > 2 else 1
    vec1 = Counter(get_grams(s1, n))
    vec2 = Counter(get_grams(s2, n))
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum([vec1[x] * vec2[x] for x in intersection])
    sum1 = sum([vec1[x]**2 for x in vec1.keys()])
    sum2 = sum([vec2[x]**2 for x in vec2.keys()])
    denominator = math.sqrt(sum1) * math.sqrt(sum2)
    return float(numerator) / denominator if denominator else 0.0

def find_user_by_name(name_query, user_list):
    if not name_query or not user_list: return None
    normalized_query = name_query.lower().strip()
    # Exact
    for u in user_list:
        if u['username'].lower().strip() == normalized_query or u['name'].lower().strip() == normalized_query:
            return u['id'], u['name'], u['username']
    # Fuzzy
    best_match = None
    highest_score = 0.0
    for u in user_list:
        score = get_cosine_similarity(normalized_query, u['name'])
        if score > highest_score:
            highest_score = score
            best_match = (u['id'], u['name'], u['username'])
    return best_match if highest_score >= 0.3 else None

def get_review_user_work_plus_data(user_name: str, cycle_arg: str = None) -> dict:
    # 1. User Map
    user_map = get_user_names()
    user_info = find_user_by_name(user_name, user_map)
    if not user_info:
        raise ValueError(f"Không tìm thấy user '{user_name}'")
    target_user_id, target_user_real_name, target_user_username = user_info
    print(f"Fetching data for: {target_user_real_name} ({target_user_username} - {target_user_id})")
    
    # 2. OKR Data
    okr_data = []
    cycles = get_cycle_list()
    if cycles:
        cycle_path = cycles[0]['path']
        if cycle_arg:
            # Simple match
            for c in cycles:
                if cycle_arg.lower() in c['name'].lower():
                    cycle_path = c['path']
                    break
        
        full_data = _get_full_data_logic(cycle_path)
        for item in full_data:
            if str(item.get('goal_user_id', '')) == str(target_user_id) or str(item.get('checkin_user_id', '')) == str(target_user_id):
                okr_data.append(item)
    
    # 3. WeWork Data
    wework_result = {"tasks": [], "count": 0}
    try:
        # Auth header
        k = "access_token_v2" if "~" in WEWORK_ACCESS_TOKEN else "access_token"
        auth_wework = {k: WEWORK_ACCESS_TOKEN}
        
        # Project map
        proj_map = {}
        try:
            r = requests.post("https://wework.base.vn/extapi/v3/project/list", data=auth_wework, timeout=10)
            if r.status_code==200: 
                for p in r.json().get('projects', []): proj_map[str(p['id'])] = p['name']
            r = requests.post("https://wework.base.vn/extapi/v3/department/list", data=auth_wework, timeout=10)
            if r.status_code==200:
                 for d in r.json().get('departments', []): proj_map[str(d['id'])] = d['name']
        except: pass
        
        url_tasks = "https://wework.base.vn/extapi/v3/user/tasks"
        payload = {**auth_wework, 'user': target_user_id}
        resp = requests.post(url_tasks, data=payload, timeout=30)
        
        if resp.status_code == 200:
            all_tasks = resp.json().get('tasks', [])
            threshold_date = datetime.now() - timedelta(days=30)
            
            # Helper to strip HTML
            import re
            def _clean(raw): return re.sub(re.compile('<.*?>'), '', str(raw)).strip().replace('&nbsp;', ' ') if raw else ""
            def _fmt(ts): 
                if not ts: return ""
                try:
                    val = int(ts)
                    # Filter out 0 or basically anything before 2020 to be safe/clean? 
                    # Or just filter out 0 (1970). 
                    # 0 timestamp is 1970-01-01 07:00:00 GMT+7
                    if val < 100000: return "" 
                    return datetime.fromtimestamp(val, HCM_TZ).strftime('%d/%m/%Y %H:%M')
                except:
                    return ""

            for t in all_tasks:
                # FILTERING LOGIC:
                # 1. Task assigned to user (user_id == target_id)
                # 2. OR Task created by user AND unassigned (creator_id == target_id AND user_id == "0")
                
                t_user_id = str(t.get('user_id', ''))
                t_creator_id = str(t.get('creator_id', ''))
                t_username = str(t.get('username', '')).strip()
                
                is_assigned_to_me = (t_user_id == str(target_user_id))
                
                # Check for unassigned status stricter: 
                # ID must be 0/empty AND username must not indicate another person
                is_unassigned_id = (t_user_id == "0" or not t_user_id)
                
                # If username is present (not 0/empty) and different from me, it IS assigned to someone
                # (Even if user_id is somehow 0, we trust username if present)
                is_actually_unassigned = is_unassigned_id
                if t_username and t_username != '0':
                    # If username exists and is not me, then it's assigned to others
                    if t_username.lower() != target_user_username.lower():
                        is_actually_unassigned = False

                is_self_created_unassigned = (t_creator_id == str(target_user_id) and is_actually_unassigned)
                
                # LOGIC: Assigned to me OR (Created by me AND Unassigned)
                if not (is_assigned_to_me or is_self_created_unassigned):
                    continue

                last_update = int(t.get('last_update', 0) or t.get('since', 0))
                if datetime.fromtimestamp(last_update) < threshold_date: continue
                
                item = {
                    'name': t.get('name'),
                    'project': proj_map.get(str(t.get('project_id', '')), "Chưa phân loại"),
                    'status': 'Done' if float(t.get('complete', 0)) == 100 else 'Pending',
                    'deadline': _fmt(t.get('deadline')),
                    'last_update': _fmt(t.get('last_update')),
                    'content': _clean(t.get('content', '')),
                    'result': _clean(t.get('result', {}).get('content', '') or t.get('result_content', ''))
                }
                wework_result["tasks"].append(item)
            wework_result["count"] = len(wework_result["tasks"])
    except Exception as e:
        print(f"WeWork fetch error: {e}")

    return {
        "name": target_user_real_name,
        "goal": okr_data,
        "wework": wework_result
    }
