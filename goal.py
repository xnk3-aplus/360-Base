
import pandas as pd
import numpy as np
import requests
import json
import warnings
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
import pytz
import calendar

# Configuration
warnings.filterwarnings('ignore')
import os
from dotenv import load_dotenv

load_dotenv()

# Constants
QUARTER_START_MONTHS = [1, 4, 7, 10]
MIN_WEEKLY_CHECKINS = 2
REQUEST_TIMEOUT = 30
MAX_PAGES_KRS = 50
MAX_PAGES_CHECKINS = 100

# Access Tokens
GOAL_ACCESS_TOKEN = os.getenv('GOAL_ACCESS_TOKEN')
ACCOUNT_ACCESS_TOKEN = os.getenv('ACCOUNT_ACCESS_TOKEN')

hcm_tz = pytz.timezone('Asia/Ho_Chi_Minh')
user_id_to_name_map = {}

def load_user_mapping():
    """Tải mapping user_id -> name từ API Account"""
    global user_id_to_name_map
    try:
        url = "https://account.base.vn/extapi/v1/users"
        payload = {'access_token': ACCOUNT_ACCESS_TOKEN}
        headers = {}
        
        response = requests.post(url, headers=headers, data=payload, timeout=30)
        
        if response.status_code == 200:
            response_json = response.json()
            
            user_list = []
            if isinstance(response_json, list):
                user_list = response_json
            elif isinstance(response_json, dict):
                user_list = response_json.get('users', [])
            
            if user_list:
                user_id_to_name_map = {
                    str(user.get('id', '')): user.get('name', '') 
                    for user in user_list 
                    if user.get('id') and user.get('name')
                }
        else:
            print(f"Không thể tải user mapping, status code: {response.status_code}")
    except Exception as e:
        print(f"Lỗi khi tải user mapping: {e}")

def get_user_name(user_id):
    """Lấy tên user từ user_id"""
    if not user_id:
        return 'N/A'
    return user_id_to_name_map.get(str(user_id), f"User_{user_id}")

class DateUtils:
    """Utility class for date calculations"""
    
    @staticmethod
    def get_last_friday_date() -> datetime:
        """Get last Friday date - always returns Friday of previous week"""
        today = datetime.now()
        current_weekday = today.weekday()
        days_to_monday_current_week = current_weekday
        monday_current_week = today - timedelta(days=days_to_monday_current_week)
        monday_previous_week = monday_current_week - timedelta(days=7)
        friday_previous_week = monday_previous_week + timedelta(days=4)
        return friday_previous_week

    @staticmethod
    def get_quarter_start_date() -> datetime:
        """Get current quarter start date"""
        today = datetime.now()
        quarter = (today.month - 1) // 3 + 1
        quarter_start_month = (quarter - 1) * 3 + 1
        return datetime(today.year, quarter_start_month, 1)

    @staticmethod
    def get_last_month_end_date() -> datetime:
        """Get last day of previous month"""
        today = datetime.now()
        first_day_current_month = datetime(today.year, today.month, 1)
        last_day_previous_month = first_day_current_month - timedelta(days=1)
        return last_day_previous_month.replace(hour=23, minute=59, second=59)

    @staticmethod
    def convert_timestamp_to_datetime(timestamp) -> Optional[str]:
        """Convert timestamp to datetime string in Asia/Ho_Chi_Minh timezone"""
        if timestamp is None or timestamp == '' or timestamp == 0:
            return None
        try:
            # Chuyển timestamp về UTC datetime
            dt_utc = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
            # Chuyển sang timezone Asia/Ho_Chi_Minh
            tz_hcm = pytz.timezone('Asia/Ho_Chi_Minh')
            dt_hcm = dt_utc.astimezone(tz_hcm)
            return dt_hcm.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return None

    @staticmethod
    def should_calculate_monthly_shift() -> bool:
        """Check if monthly shift should be calculated (not in months 1,4,7,10)"""
        return datetime.now().month not in QUARTER_START_MONTHS
    
    @staticmethod
    def is_last_week_of_month() -> bool:
        """Check if current week is the last week of month"""
        now = datetime.now()
        weeks = DateUtils._get_weeks_in_current_month()
        
        if not weeks:
            return False
        
        last_week = weeks[-1]
        return last_week['start_date'] <= now.date() <= last_week['end_date']
    
    @staticmethod
    def _get_weeks_in_current_month():
        """Get all weeks in current month"""
        now = datetime.now()
        year = now.year
        month = now.month
        
        first_day = datetime(year, month, 1)
        last_day = datetime(year, month, calendar.monthrange(year, month)[1])
        
        weeks = []
        current_date = first_day
        
        while current_date <= last_day:
            week_start = current_date - timedelta(days=current_date.weekday())
            week_start = max(week_start, first_day)
            
            week_end = week_start + timedelta(days=6)
            week_end = min(week_end, last_day)
            
            weeks.append({
                'week_number': len(weeks) + 1,
                'start_date': week_start.date(),
                'end_date': week_end.date(),
                'week_range': f"{week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m')}"
            })
            
            current_date = week_end + timedelta(days=1)
        
        return weeks


class User:
    """User class for OKR tracking"""
    
    def __init__(self, user_id, name, co_OKR=1, checkin=0, dich_chuyen_OKR=0, score=0):
        self.user_id = str(user_id)
        self.name = name
        self.co_OKR = co_OKR
        self.checkin = checkin
        self.dich_chuyen_OKR = dich_chuyen_OKR
        self.score = score
        self.OKR = {month: 0 for month in range(1, 13)}

    def update_okr(self, month, value):
        """Update OKR for specific month"""
        if 1 <= month <= 12:
            self.OKR[month] = value

    def calculate_score(self):
        """Calculate score based on criteria"""
        score = 0.5
        
        if self.checkin == 1:
            score += 0.5
        
        if self.co_OKR == 1:
            score += 1
        
        movement = self.dich_chuyen_OKR
        movement_scores = [
            (10, 0.15), (25, 0.25), (30, 0.5), (50, 0.75),
            (80, 1.25), (99, 1.5), (float('inf'), 2.5)
        ]
        
        for threshold, points in movement_scores:
            if movement < threshold:
                score += points
                break
        
        self.score = round(score, 2)

    def __repr__(self):
        return (f"User(id={self.user_id}, name={self.name}, co_OKR={self.co_OKR}, "
                f"checkin={self.checkin}, dich_chuyen_OKR={self.dich_chuyen_OKR}, score={self.score})")


class UserManager:
    """Manages user data and calculations"""
    
    def __init__(self, account_df, krs_df, checkin_df, cycle_df=None, final_df=None, users_with_okr_names=None, monthly_okr_data=None):
        self.account_df = account_df
        self.krs_df = krs_df
        self.checkin_df = checkin_df
        self.cycle_df = cycle_df
        self.final_df = final_df
        self.users_with_okr_names = users_with_okr_names or set()
        self.monthly_okr_data = monthly_okr_data or []
        
        self.user_name_map = self._create_user_name_map()
        self.users = self._create_users()

    def _create_user_name_map(self) -> Dict[str, str]:
        """Create user_id to name mapping"""
        user_map = {}
        if not self.account_df.empty and 'id' in self.account_df.columns and 'name' in self.account_df.columns:
            for _, row in self.account_df.iterrows():
                user_map[str(row['id'])] = row.get('name', 'Unknown')
        return user_map

    def _create_users(self) -> Dict[str, User]:
        """Create User objects for all account members"""
        users = {}
        
        if not self.account_df.empty and 'id' in self.account_df.columns and 'name' in self.account_df.columns:
            for _, row in self.account_df.iterrows():
                user_id = str(row.get('id'))
                name = row.get('name', 'Unknown')
                has_okr = 1 if name in self.users_with_okr_names else 0
                users[user_id] = User(user_id, name, co_OKR=has_okr)

        return users

    def update_checkins(self, start_date=None, end_date=None):
        """Update check-in status for each user"""
        for user in self.users.values():
            if self._meets_monthly_weekly_criteria(user.user_id):
                user.checkin = 1
            else:
                user.checkin = 0

    def _meets_monthly_weekly_criteria(self, user_id) -> bool:
        """Check if user has checkins in at least 2 weeks of current month"""
        result = self._get_monthly_weekly_criteria_details(user_id)
        return result['meets_criteria']
    
    def _get_monthly_weekly_criteria_details(self, user_id) -> dict:
        """Get detailed information about monthly weekly criteria for a user"""
        user_name = self.user_name_map.get(str(user_id), '')
        if not user_name:
            return {
                'meets_criteria': False,
                'weeks_with_checkins': 0,
                'total_weeks_in_month': 0,
                'checkins_count': 0,
                'week_details': []
            }
        
        now = datetime.now()
        current_month_weeks = self._get_weeks_in_current_month_from_checkin_py()
        current_month_year = f"{now.year}-{now.month:02d}"
        
        if self.final_df is None or self.final_df.empty:
            return {
                'meets_criteria': False,
                'weeks_with_checkins': 0,
                'total_weeks_in_month': len(current_month_weeks),
                'checkins_count': 0,
                'week_details': []
            }
        
        user_checkins = self.final_df[
            (self.final_df['goal_user_name'] == user_name) &
            (self.final_df['checkin_since'].notna()) &
            (self.final_df['checkin_since'] != '')
        ].copy()
        
        if user_checkins.empty:
            week_details = [{'week_range': week['week_range'], 'has_checkin': False, 'checkin_dates': []} 
                          for week in current_month_weeks]
            return {
                'meets_criteria': False,
                'weeks_with_checkins': 0,
                'total_weeks_in_month': len(current_month_weeks),
                'checkins_count': 0,
                'week_details': week_details
            }
        
        user_checkins['checkin_date'] = pd.to_datetime(user_checkins['checkin_since']).dt.date
        user_checkins['checkin_month_year'] = pd.to_datetime(user_checkins['checkin_since']).dt.strftime('%Y-%m')
        
        current_month_checkins = user_checkins[user_checkins['checkin_month_year'] == current_month_year].copy()
        
        if current_month_checkins.empty:
            week_details = [{'week_range': week['week_range'], 'has_checkin': False, 'checkin_dates': []} 
                          for week in current_month_weeks]
            return {
                'meets_criteria': False,
                'weeks_with_checkins': 0,
                'total_weeks_in_month': len(current_month_weeks),
                'checkins_count': 0,
                'week_details': week_details
            }
        
        def get_week_number(checkin_date):
            for week in current_month_weeks:
                if week['start_date'] <= checkin_date <= week['end_date']:
                    return week['week_number']
            return None
        
        current_month_checkins['week_number'] = current_month_checkins['checkin_date'].apply(get_week_number)
        user_weekly_checkins = current_month_checkins.groupby(['week_number']).size().reset_index(name='checkins_count')
        weeks_with_checkins = len(user_weekly_checkins['week_number'].unique())
        total_checkins = len(current_month_checkins)
        
        week_details = []
        week_checkins_map = {}
        
        for _, row in current_month_checkins.iterrows():
            week_num = row['week_number']
            if pd.notna(week_num):
                if week_num not in week_checkins_map:
                    week_checkins_map[week_num] = {}
                date_str = row['checkin_date'].strftime('%d/%m')
                if date_str not in week_checkins_map[week_num]:
                    week_checkins_map[week_num][date_str] = 0
                week_checkins_map[week_num][date_str] += 1
        
        for week in current_month_weeks:
            week_number = week['week_number']
            has_checkin = week_number in week_checkins_map
            
            checkin_dates = []
            if has_checkin:
                for date_str, count in sorted(week_checkins_map[week_number].items()):
                    if count == 1:
                        checkin_dates.append(date_str)
                    else:
                        checkin_dates.append(f"{date_str}-{count} lần")
            
            week_details.append({
                'week_range': week['week_range'],
                'has_checkin': has_checkin,
                'checkin_dates': checkin_dates
            })
        
        meets_criteria = weeks_with_checkins >= 2
        
        return {
            'meets_criteria': meets_criteria,
            'weeks_with_checkins': weeks_with_checkins,
            'total_weeks_in_month': len(current_month_weeks),
            'checkins_count': total_checkins,
            'week_details': week_details
        }

    def _get_weeks_in_current_month_from_checkin_py(self):
        """Get all weeks in current month"""
        now = datetime.now()
        year = now.year
        month = now.month
        
        first_day = datetime(year, month, 1)
        last_day = datetime(year, month, calendar.monthrange(year, month)[1])
        
        weeks = []
        current_date = first_day
        
        while current_date <= last_day:
            week_start = current_date - timedelta(days=current_date.weekday())
            week_start = max(week_start, first_day)
            
            week_end = week_start + timedelta(days=6)
            week_end = min(week_end, last_day)
            
            weeks.append({
                'week_number': len(weeks) + 1,
                'start_date': week_start.date(),
                'end_date': week_end.date(),
                'week_range': f"{week_start.strftime('%d/%m')} - {week_end.strftime('%d/%m')}"
            })
            
            current_date = week_end + timedelta(days=1)
        
        return weeks

    def update_okr_movement(self):
        """Update OKR movement for each user"""
        self._update_okr_movement_monthly()

    def _update_okr_movement_monthly(self):
        """Update OKR movement using values from Monthly OKR Analysis"""
        monthly_shift_map = {}
        if self.monthly_okr_data:
            for data in self.monthly_okr_data:
                monthly_shift_map[data['user_name']] = data['okr_shift_monthly']
        
        for user in self.users.values():
            user_name = user.name
            if user_name in monthly_shift_map:
                user.dich_chuyen_OKR = round(monthly_shift_map[user_name], 2)
            else:
                user.dich_chuyen_OKR = 0

    def calculate_scores(self):
        """Calculate scores for all users"""
        is_last_week = DateUtils.is_last_week_of_month()
        
        for user in self.users.values():
            if is_last_week:
                criteria_details = self._get_monthly_weekly_criteria_details(user.user_id)
                meets_criteria = criteria_details['meets_criteria']
                user.checkin = 1 if meets_criteria else 0
            else:
                user.checkin = 0
            
            user.calculate_score()

    def get_users(self) -> List[User]:
        """Return list of all users"""
        return list(self.users.values())


class GoalAPIClient:
    """Client for handling API requests"""
    
    def __init__(self, goal_token: str, account_token: str):
        self.goal_token = goal_token
        self.account_token = account_token

    def _make_request(self, url: str, data: Dict, description: str = "") -> requests.Response:
        """Make HTTP request with error handling"""
        try:
            response = requests.post(url, data=data, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Error {description}: {e}")
            raise

    def get_filtered_members(self) -> pd.DataFrame:
        """Get filtered members from account API"""
        url = "https://account.base.vn/extapi/v1/group/get"
        data = {"access_token": self.account_token, "path": "aplus"}
        
        response = self._make_request(url, data, "fetching account members")
        response_data = response.json()
        
        members = response_data.get('group', {}).get('members', [])
        
        df = pd.DataFrame([
            {
                'id': str(m.get('id', '')),
                'name': m.get('name', ''),
                'username': m.get('username', ''),
                'job': m.get('title', ''),
                'email': m.get('email', '')
            }
            for m in members
        ])
        
        return self._apply_member_filters(df)

    def _apply_member_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply filters to member dataframe"""
        excluded_jobs = 'kcs|agile|khu vực|sa ti co|trainer|specialist|no|chuyên gia|xnk|vat|trưởng phòng thị trường'
        filtered_df = df[~df['job'].str.lower().str.contains(excluded_jobs, na=False)]
        filtered_df = filtered_df[filtered_df['username'] != 'ThuAn']
        filtered_df = filtered_df[filtered_df['username'] != 'HienNguyen']
        return filtered_df

    def get_cycle_list(self) -> List[Dict]:
        """Get list of quarterly cycles"""
        url = "https://goal.base.vn/extapi/v1/cycle/list"
        data = {'access_token': self.goal_token}

        response = self._make_request(url, data, "fetching cycle list")
        data = response.json()

        quarterly_cycles = []
        for cycle in data.get('cycles', []):
            if cycle.get('metatype') == 'quarterly':
                try:
                    start_time = datetime.fromtimestamp(float(cycle['start_time']), tz=timezone.utc)
                    quarterly_cycles.append({
                        'name': cycle['name'],
                        'path': cycle['path'],
                        'start_time': start_time,
                        'formatted_start_time': start_time.strftime('%d/%m/%Y')
                    })
                except (ValueError, TypeError) as e:
                    print(f"Error parsing cycle {cycle.get('name', 'Unknown')}: {e}")
                    continue

        return sorted(quarterly_cycles, key=lambda x: x['start_time'], reverse=True)

    def get_account_users(self) -> pd.DataFrame:
        """Get users from Account API"""
        url = "https://account.base.vn/extapi/v1/users"
        data = {"access_token": self.account_token}

        response = self._make_request(url, data, "fetching account users")
        json_response = response.json()
        
        if isinstance(json_response, list) and len(json_response) > 0:
            json_response = json_response[0]

        account_users = json_response.get('users', [])
        return pd.DataFrame([{
            'id': str(user['id']),
            'name': user['name'],
            'username': user['username']
        } for user in account_users])

    def get_goals_data(self, cycle_path: str) -> pd.DataFrame:
        """Get goals data from API"""
        url = "https://goal.base.vn/extapi/v1/cycle/get.full"
        data = {'access_token': self.goal_token, 'path': cycle_path}

        response = self._make_request(url, data, "fetching goals data")
        data = response.json()

        goals_data = []
        for goal in data.get('goals', []):
            goals_data.append({
                'goal_id': goal.get('id'),
                'goal_name': goal.get('name', 'Unknown Goal'),
                'goal_content': goal.get('content', ''),
                'goal_since': DateUtils.convert_timestamp_to_datetime(goal.get('since')),
                'goal_current_value': goal.get('current_value', 0),
                'goal_user_id': str(goal.get('user_id', '')),
                'goal_target_id': str(goal.get('target_id', '')) if goal.get('target_id') else '',
            })

        return pd.DataFrame(goals_data)
    
    def parse_targets_data(self, cycle_path: str) -> pd.DataFrame:
        """Parse targets data from API to create target mapping"""
        url = "https://goal.base.vn/extapi/v1/cycle/get.full"
        data = {'access_token': self.goal_token, 'path': cycle_path}

        response = self._make_request(url, data, "fetching targets data")
        response_data = response.json()
        
        if not response_data or 'targets' not in response_data:
            return pd.DataFrame()
        
        all_targets = []
        
        # Iterate over each main "Objective" (Company Target)
        for objective in response_data.get('targets', []):
            objective_id = objective.get('id')
            objective_name = objective.get('name')
            
            # Ensure the objective has Key Results (cached_objs)
            if 'cached_objs' in objective and isinstance(objective['cached_objs'], list):
                # Iterate over each "Key Result" (sub-target)
                for kr in objective['cached_objs']:
                    target_data = {
                        'target_id': str(kr.get('id', '')),
                        'target_company_id': str(objective_id) if objective_id else '',
                        'target_company_name': objective_name if objective_name else '',
                        'target_name': kr.get('name', ''),
                        'target_scope': kr.get('scope', ''),
                        'target_dept_id': None,
                        'target_dept_name': None,
                        'target_team_id': None,
                        'target_team_name': None
                    }
                    
                    # Điền dữ liệu cho cột dept/team dựa trên scope
                    if target_data['target_scope'] == 'dept':
                        target_data['target_dept_id'] = target_data['target_id']
                        target_data['target_dept_name'] = target_data['target_name']
                    elif target_data['target_scope'] == 'team':
                        target_data['target_team_id'] = target_data['target_id']
                        target_data['target_team_name'] = target_data['target_name']
                    
                    all_targets.append(target_data)
        
        return pd.DataFrame(all_targets)

    def get_krs_data(self, cycle_path: str) -> pd.DataFrame:
        """Get KRs data from API with pagination"""
        url = "https://goal.base.vn/extapi/v1/cycle/krs"
        all_krs = []
        
        for page in range(1, MAX_PAGES_KRS + 1):
            data = {"access_token": self.goal_token, "path": cycle_path, "page": page}

            response = self._make_request(url, data, f"loading KRs at page {page}")
            response_data = response.json()

            if isinstance(response_data, list) and len(response_data) > 0:
                response_data = response_data[0]

            krs_list = response_data.get("krs", [])
            if not krs_list:
                break

            for kr in krs_list:
                all_krs.append({
                    'kr_id': str(kr.get('id', '')),
                    'kr_name': kr.get('name', 'Unknown KR'),
                    'kr_content': kr.get('content', ''),
                    'kr_since': DateUtils.convert_timestamp_to_datetime(kr.get('since')),
                    'kr_current_value': kr.get('current_value', 0),
                    'kr_user_id': str(kr.get('user_id', '')),
                    'goal_id': kr.get('goal_id'),
                })

        return pd.DataFrame(all_krs)

    def get_all_checkins(self, cycle_path: str) -> List[Dict]:
        """Get all checkins with pagination"""
        url = "https://goal.base.vn/extapi/v1/cycle/checkins"
        all_checkins = []
        
        for page in range(1, MAX_PAGES_CHECKINS + 1):
            data = {"access_token": self.goal_token, "path": cycle_path, "page": page}

            response = self._make_request(url, data, f"loading checkins at page {page}")
            response_data = response.json()

            if isinstance(response_data, list) and len(response_data) > 0:
                response_data = response_data[0]

            checkins = response_data.get('checkins', [])
            if not checkins:
                break

            all_checkins.extend(checkins)

            if len(checkins) < 20:
                break

        return all_checkins


class DataProcessor:
    """Handles data processing and transformations"""
    
    @staticmethod
    def extract_checkin_data(all_checkins: List[Dict]) -> pd.DataFrame:
        """Extract checkin data into DataFrame"""
        checkin_list = []

        for checkin in all_checkins:
            try:
                checkin_id = checkin.get('id', '')
                checkin_name = checkin.get('name', '')
                user_id = str(checkin.get('user_id', ''))
                since_timestamp = checkin.get('since', '')
                since_date = DataProcessor._convert_timestamp_to_datetime(since_timestamp) or ''
                
                form_data = checkin.get('form', [])
                form_value = form_data[0].get('value', '') if form_data else ''
                
                obj_export = checkin.get('obj_export', {})
                target_name = obj_export.get('name', '') if obj_export else ''
                kr_id = str(obj_export.get('id', '')) if obj_export else ''
                current_value = checkin.get('current_value', 0)
                
                checkin_list.append({
                    'checkin_id': checkin_id,
                    'checkin_name': checkin_name,
                    'checkin_since': since_date,
                    'checkin_since_timestamp': since_timestamp,
                    'cong_viec_tiep_theo': form_value,
                    'checkin_target_name': target_name,
                    'checkin_kr_current_value': current_value,
                    'kr_id': kr_id,
                    'checkin_user_id': user_id
                })
                
            except Exception as e:
                print(f"Warning: Error processing checkin {checkin.get('id', 'Unknown')}: {e}")
                continue

        return pd.DataFrame(checkin_list)

    @staticmethod
    def _convert_timestamp_to_datetime(timestamp):
        """Convert timestamp to datetime string in Asia/Ho_Chi_Minh timezone"""
        if timestamp is None or timestamp == '' or timestamp == 0:
            return None
        try:
            # Chuyển timestamp về UTC datetime
            dt_utc = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
            # Chuyển sang timezone Asia/Ho_Chi_Minh
            tz_hcm = pytz.timezone('Asia/Ho_Chi_Minh')
            dt_hcm = dt_utc.astimezone(tz_hcm)
            return dt_hcm.strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return None

    @staticmethod
    def clean_final_data(df: pd.DataFrame) -> pd.DataFrame:
        """Clean and prepare final dataset"""
        try:
            df['kr_current_value'] = pd.to_numeric(df['kr_current_value'], errors='coerce').fillna(0.00)
            df['checkin_kr_current_value'] = pd.to_numeric(df['checkin_kr_current_value'], errors='coerce').fillna(0.00)

            df['kr_since'] = df['kr_since'].fillna(df['goal_since'])
            df['checkin_since'] = df['checkin_since'].fillna(df['kr_since'])

            columns_to_drop = ['goal_user_id', 'kr_user_id']
            existing_columns_to_drop = [col for col in columns_to_drop if col in df.columns]
            if existing_columns_to_drop:
                df = df.drop(columns=existing_columns_to_drop)

            return df
        except Exception as e:
            print(f"Error cleaning data: {e}")
            return df


class OKRCalculator:
    """Handles OKR calculations and analysis"""
    
    @staticmethod
    def calculate_current_value(df: pd.DataFrame) -> float:
        """Calculate current OKR value"""
        try:
            unique_goals = df.groupby('goal_name')['goal_current_value'].first().reset_index()
            unique_goals['goal_current_value'] = pd.to_numeric(unique_goals['goal_current_value'], errors='coerce').fillna(0)
            return unique_goals['goal_current_value'].mean() if len(unique_goals) > 0 else 0
        except Exception as e:
            print(f"Error calculating current value: {e}")
            return 0

    @staticmethod
    def calculate_reference_value(reference_date: datetime, df: pd.DataFrame) -> Tuple[float, List[Dict]]:
        """Calculate OKR value as of reference date"""
        try:
            df = df.copy()
            df['checkin_since_dt'] = pd.to_datetime(df['checkin_since'], errors='coerce')

            unique_krs = df['kr_id'].dropna().unique()
            goal_values_dict = {}
            kr_details = []

            for kr_id in unique_krs:
                kr_data = df[df['kr_id'] == kr_id].copy()
                
                actual_checkins_before_date = kr_data[
                    (kr_data['checkin_since_dt'] <= reference_date) &
                    (kr_data['checkin_name'].notna()) &
                    (kr_data['checkin_name'] != '')
                ]

                goal_name = kr_data.iloc[0]['goal_name'] if len(kr_data) > 0 else f"Unknown_{kr_id}"

                if len(actual_checkins_before_date) > 0:
                    latest_checkin = actual_checkins_before_date.sort_values('checkin_since_dt').iloc[-1]
                    kr_value = pd.to_numeric(latest_checkin['checkin_kr_current_value'], errors='coerce')
                    kr_value = kr_value if not pd.isna(kr_value) else 0

                    if goal_name not in goal_values_dict:
                        goal_values_dict[goal_name] = []
                    goal_values_dict[goal_name].append(kr_value)

                    kr_details.append({
                        'kr_id': kr_id,
                        'goal_name': goal_name,
                        'kr_value': kr_value,
                        'checkin_date': latest_checkin['checkin_since_dt'],
                        'source': f'checkin_before_{reference_date.strftime("%Y%m%d")}'
                    })
                else:
                    goal_key = f"{goal_name}_no_checkin_{kr_id}"
                    goal_values_dict[goal_key] = [0]

                    kr_details.append({
                        'kr_id': kr_id,
                        'goal_name': goal_name,
                        'kr_value': 0,
                        'checkin_date': None,
                        'source': 'no_checkin_default'
                    })

            goal_averages = []
            normalized_goal_values = {}
            for key, values in goal_values_dict.items():
                if '_no_checkin_' in key: # Individual KR mapped to Goal
                     goal_averages.append(0)
                else: # Real Goal with KRs
                    avg_val = np.mean(values)
                    goal_averages.append(avg_val)
                    normalized_goal_values[key] = avg_val
            
            # Re-normalize: Group by Goal Name proper
            # The logic above is slightly complex in original code, simplifying:
            # Group KR values by goal_name
            final_goal_values = defaultdict(list)
            for item in kr_details:
                final_goal_values[item['goal_name']].append(item['kr_value'])
            
            final_averages = []
            for g_name, vals in final_goal_values.items():
                final_averages.append(np.mean(vals))

            return (np.mean(final_averages) if final_averages else 0), kr_details

        except Exception as e:
            print(f"Error calculating reference value: {e}")
            return 0, []

class OKRAnalysisSystem:
    """Main system for OKR analysis"""
    
    def __init__(self, goal_token: str, account_token: str):
        self.api_client = GoalAPIClient(goal_token, account_token)
        self.checkin_path = None
        self.final_df = None
        self.user_manager = None
        self.target_df = None 

    def get_cycle_list(self) -> List[Dict]:
        return self.api_client.get_cycle_list()

    def load_and_process_data(self) -> Optional[pd.DataFrame]:
        """Load and process all OKR data"""
        if not self.checkin_path:
            raise ValueError("Checkin path not set")

        print("1. Loading raw data...")
        # Sử dụng API client để lấy các DataFrame
        goals_df = self.api_client.get_goals_data(self.checkin_path)
        krs_df = self.api_client.get_krs_data(self.checkin_path)
        
        # Load targets/structure data
        self.target_df = self.api_client.parse_targets_data(self.checkin_path)
        
        # Load checkins
        all_checkins = self.api_client.get_all_checkins(self.checkin_path)
        checkin_df = DataProcessor.extract_checkin_data(all_checkins)
        
        account_df = self.api_client.get_filtered_members()

        print("2. Merging data...")
        if goals_df.empty or krs_df.empty:
            print("No goals or KRs data found")
            return None

        # Merge Goals and KRs
        merged_df = pd.merge(goals_df, krs_df, on='goal_id', how='right', suffixes=('_goal', '_kr'))
        
        # Map user names
        if not account_df.empty and 'id' in account_df.columns:
            id_to_name = dict(zip(account_df['id'].astype(str), account_df['name']))
            id_to_username = dict(zip(account_df['id'].astype(str), account_df['username']))
            merged_df['goal_user_name'] = merged_df['goal_user_id'].map(id_to_name)
            merged_df['goal_username'] = merged_df['goal_user_id'].map(id_to_username)
        else:
            merged_df['goal_user_name'] = 'Unknown'
            merged_df['goal_username'] = 'unknown'

        # Xác định user có OKR
        users_with_okr_names = set(merged_df['goal_user_name'].dropna().unique())

        # Merge with Checkins
        self.final_df = pd.merge(merged_df, checkin_df, on='kr_id', how='left')
        
        # Merge with Targets (Alignment Info)
        if not self.target_df.empty:
            # Merge dựa trên kr_id = target_id
            self.final_df = pd.merge(self.final_df, self.target_df, 
                                   left_on='kr_id', right_on='target_id', 
                                   how='left', suffixes=('', '_target'))
        else:
            # Thêm cột trống nếu không có target data
            for col in ['target_company_name', 'target_dept_name', 'target_team_name']:
                self.final_df[col] = None

        self.final_df = DataProcessor.clean_final_data(self.final_df)
        
        # Initialize User Manager
        self.user_manager = UserManager(
            account_df, krs_df, checkin_df, 
            final_df=self.final_df,
            users_with_okr_names=users_with_okr_names
        )

        return self.final_df

    def analyze_missing_goals_and_checkins(self) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """Analyze users with missing goals or checkins"""
        if self.user_manager is None:
            return [], [], []

        users = self.user_manager.get_users()
        no_goals = []
        no_checkins = []
        goals_no_checkins = []

        # Get list of users who have checkins
        users_with_checkins_ids = set(self.final_df[
            (self.final_df['checkin_name'].notna()) & 
            (self.final_df['checkin_name'] != '')
        ]['goal_user_id'].unique())
        
        # Get list of users who have goals
        users_with_goals_ids = set(self.final_df['goal_user_id'].unique())

        account_users = self.api_client.get_account_users()
        
        for _, user in account_users.iterrows():
            user_id = str(user['id'])
            user_name = user['name']
            username = user['username']

            # Check goals
            if user_id not in users_with_goals_ids:
                no_goals.append({
                    'id': user_id, 
                    'name': user_name,
                    'username': username
                })

            # Check checkins (absolute - ever checked in for this cycle)
            if user_id not in users_with_checkins_ids:
                no_checkins.append({
                    'id': user_id, 
                    'name': user_name,
                    'username': username
                })
                
                # Has goals but no checkins
                if user_id in users_with_goals_ids:
                    goals_no_checkins.append({
                        'id': user_id, 
                        'name': user_name,
                        'username': username
                    })

        return no_goals, no_checkins, goals_no_checkins

    def calculate_okr_shifts_by_user(self) -> List[Dict]:
        """Calculate weekly OKR shifts for all users"""
        if self.final_df is None or self.final_df.empty:
            return []

        last_friday = DateUtils.get_last_friday_date()
        date_str = last_friday.strftime('%d/%m/%Y')
        print(f"Calculating shift vs {date_str}...")

        user_shifts = []
        grouped = self.final_df.groupby('goal_user_name')

        for user_name, group in grouped:
            if pd.isna(user_name): continue

            # Current Value
            current_value = OKRCalculator.calculate_current_value(group)
            
            # Reference Value (Last Friday)
            last_friday_value, kr_details = OKRCalculator.calculate_reference_value(last_friday, group)
            
            # Shift
            shift = current_value - last_friday_value

            user_shifts.append({
                'user_name': user_name,
                'current_value': round(current_value, 2),
                'last_friday_value': round(last_friday_value, 2),
                'okr_shift': round(shift, 2),
                'kr_details_count': len(kr_details)
            })
            
        return sorted(user_shifts, key=lambda x: x['okr_shift'], reverse=True)
    
    def calculate_okr_shifts_by_user_monthly(self) -> List[Dict]:
        """Calculate monthly OKR shifts"""
        if self.final_df is None or self.final_df.empty:
            return []
            
        if not DateUtils.should_calculate_monthly_shift():
            return []
            
        last_month_end = DateUtils.get_last_month_end_date()
        date_str = last_month_end.strftime('%d/%m/%Y')
        print(f"Calculating MONTHLY shift vs {date_str}...")
        
        user_shifts = []
        grouped = self.final_df.groupby('goal_user_name')

        for user_name, group in grouped:
            if pd.isna(user_name): continue

            current_value = OKRCalculator.calculate_current_value(group)
            last_month_value, _ = OKRCalculator.calculate_reference_value(last_month_end, group)
            shift = current_value - last_month_value

            user_shifts.append({
                'user_name': user_name,
                'okr_shift_monthly': round(shift, 2)
            })
            
        return user_shifts

    def analyze_checkin_behavior(self) -> Tuple[List[Dict], List[Dict]]:
        """Analyze checkin behavior, both period-based and overall frequency"""
        if self.final_df is None or self.user_manager is None:
            return [], []

        # Period checkins (Quarterly/Cycle based)
        period_checkins = []
        
        grouped = self.final_df.groupby('goal_user_name')
        
        # Calculate weeks in cycle approx
        # Using simple assumption or data min/max
        try:
            start_dates = pd.to_datetime(self.final_df['checkin_since'], errors='coerce')
            if not start_dates.dropna().empty:
                min_date = start_dates.min()
                max_date = datetime.now()
                total_weeks = max(1, (max_date - min_date).days // 7)
            else:
                total_weeks = 12 # Default quarter
        except:
            total_weeks = 12

        for user_name, group in grouped:
            # Count checkin events (unique checkin ids)
            # Filter non-empty checkin names
            checkins = group[
                (group['checkin_name'].notna()) & 
                (group['checkin_name'] != '')
            ]
            
            checkin_count = checkins['checkin_id'].nunique()
            
            period_checkins.append({
                'user_name': user_name,
                'checkin_count_period': checkin_count,
                'checkin_rate_period': round(checkin_count / total_weeks, 2), # avg per week
                'total_weeks': total_weeks
            })
            
        # Overall checkins (detailed weekly analysis via UserManager logic)
        overall_checkins = []
        
        # Reuse logic from UserManager to get detailed weekly stats if needed
        # Or simple grouping
        
        # Let's count weeks with at least one checkin
        for user_name, group in grouped:
            checkins = group[
                (group['checkin_name'].notna()) & 
                (group['checkin_name'] != '')
            ].copy()
            
            if checkins.empty:
                overall_checkins.append({
                    'user_name': user_name,
                    'total_checkins': 0,
                    'weeks_with_checkin': 0,
                    'checkin_frequency_per_week': 0,
                    'last_week_checkins': 0
                })
                continue
                
            checkins['checkin_date'] = pd.to_datetime(checkins['checkin_since'], errors='coerce')
            checkins['week_year'] = checkins['checkin_date'].dt.strftime('%Y-%U')
            
            weeks_with_checkin = checkins['week_year'].nunique()
            total_checkins = checkins['checkin_id'].nunique()
            
            # Last week checkins (approximate)
            last_week_start = datetime.now() - timedelta(days=7)
            last_week_checkins = checkins[checkins['checkin_date'] >= last_week_start]['checkin_id'].nunique()

            overall_checkins.append({
                'user_name': user_name,
                'total_checkins': total_checkins,
                'weeks_with_checkin': weeks_with_checkin,
                'checkin_frequency_per_week': round(total_checkins / total_weeks, 2),
                'last_week_checkins': last_week_checkins
            })
            
        return period_checkins, overall_checkins


    def analyze_alignment_contribution(self) -> Dict[str, Dict]:
        """
        Phân tích tỷ lệ KRs của người dùng được căn chỉnh (aligned) 
        với mục tiêu của Công ty, Bộ phận và Đội nhóm.
        """
        try:
            if self.final_df is None or self.final_df.empty:
                return {}

            # Lấy các KRs duy nhất cho mỗi người dùng
            # Chúng ta dùng kr_id để tránh đếm lặp do join với checkins
            user_krs_df = self.final_df.drop_duplicates(subset=['goal_user_name', 'kr_id'])
            
            # Lọc ra các KRs hợp lệ (có goal_user_name và kr_id)
            user_krs_df = user_krs_df[
                user_krs_df['goal_user_name'].notna() & 
                user_krs_df['kr_id'].notna()
            ]

            grouped = user_krs_df.groupby('goal_user_name')
            alignment_data = {}

            for user_name, krs in grouped:
                total_krs = krs['kr_id'].nunique()
                
                if total_krs == 0:
                    continue

                # Đếm số KRs có căn chỉnh
                aligned_company = krs['target_company_name'].notna().sum()
                aligned_dept = krs['target_dept_name'].notna().sum()
                aligned_team = krs['target_team_name'].notna().sum()

                # Tính tỷ lệ phần trăm
                company_pct = (aligned_company / total_krs) * 100
                dept_pct = (aligned_dept / total_krs) * 100
                team_pct = (aligned_team / total_krs) * 100
                
                # Tính tỷ lệ căn chỉnh tổng hợp (ít nhất 1)
                aligned_any = krs[
                    (krs['target_company_name'].notna()) |
                    (krs['target_dept_name'].notna()) |
                    (krs['target_team_name'].notna())
                ].shape[0]
                any_pct = (aligned_any / total_krs) * 100

                alignment_data[user_name] = {
                    'total_krs': total_krs,
                    'aligned_company_krs': int(aligned_company),
                    'aligned_dept_krs': int(aligned_dept),
                    'aligned_team_krs': int(aligned_team),
                    'aligned_any_krs': int(aligned_any),
                    'company_alignment_pct': round(company_pct, 2),
                    'dept_alignment_pct': round(dept_pct, 2),
                    'team_alignment_pct': round(team_pct, 2),
                    'total_alignment_pct': round(any_pct, 2),
                }

            return alignment_data

        except Exception as e:
            print(f"Lỗi khi phân tích đóng góp căn chỉnh: {e}")
            return {}

    def generate_comprehensive_okr_report(self) -> Dict:
        """Tổng hợp báo cáo OKR toàn diện"""
        try:
            report = {
                'summary': {},
                'weekly_okr_analysis': {},
                'progress_comparison': {},
                'alerts_and_warnings': {},
                'organization_health': {},
                'detailed_user_analysis': [],
                'alignment_analysis': {}
            }

            # 1. Phân tích OKR theo tuần
            weekly_shifts = self.calculate_okr_shifts_by_user()
            report['weekly_okr_analysis'] = self._analyze_weekly_okr_performance(weekly_shifts)

            # 2. Phân tích hành vi check-in
            period_checkins, overall_checkins = self.analyze_checkin_behavior()
            report['checkin_analysis'] = {
                'period_checkins': period_checkins,
                'overall_checkins': overall_checkins
            }

            # 3. Phân tích thiếu sót
            no_goals, no_checkins, goals_no_checkins = self.analyze_missing_goals_and_checkins()
            report['alerts_and_warnings'] = self._generate_alerts_and_warnings(no_goals, no_checkins, goals_no_checkins, weekly_shifts, period_checkins)

            # 4. Phân tích căn chỉnh (Đóng góp)
            alignment_analysis = self.analyze_alignment_contribution()
            report['alignment_analysis'] = alignment_analysis

            # 5. Tổng quan sức khỏe tổ chức
            report['organization_health'] = self._calculate_organization_health(weekly_shifts, period_checkins, overall_checkins)

            # 6. Phân tích chi tiết từng user
            report['detailed_user_analysis'] = self._create_detailed_user_analysis(
                weekly_shifts, period_checkins, overall_checkins, alignment_analysis
            )

            # 7. Tổng hợp
            report['summary'] = self._create_summary_report(report)

            return report

        except Exception as e:
            print(f"Lỗi khi tạo báo cáo tổng hợp: {e}")
            return {}

    def _analyze_weekly_okr_performance(self, weekly_shifts: List[Dict]) -> Dict:
        """Phân tích hiệu suất OKR theo tuần"""
        if not weekly_shifts:
            return {}

        # Thống kê cơ bản
        total_users = len(weekly_shifts)
        users_with_positive_shift = len([u for u in weekly_shifts if u.get('okr_shift', 0) > 0])
        users_with_negative_shift = len([u for u in weekly_shifts if u.get('okr_shift', 0) < 0])

        # Tính trung bình
        avg_shift = np.mean([u.get('okr_shift', 0) for u in weekly_shifts])
        avg_current_value = np.mean([u.get('current_value', 0) for u in weekly_shifts])
        avg_kr_count = np.mean([u.get('kr_details_count', 0) for u in weekly_shifts])

        # Phân loại hiệu suất
        high_performers = [u for u in weekly_shifts if u.get('okr_shift', 0) >= 20]
        medium_performers = [u for u in weekly_shifts if 5 <= u.get('okr_shift', 0) < 20]
        low_performers = [u for u in weekly_shifts if u.get('okr_shift', 0) < 5]

        return {
            'total_users': total_users,
            'users_positive_shift': users_with_positive_shift,
            'users_negative_shift': users_with_negative_shift,
            'avg_shift': round(avg_shift, 2),
            'avg_current_value': round(avg_current_value, 2),
            'avg_kr_count': round(avg_kr_count, 1),
            'performance_distribution': {
                'high_performers': len(high_performers),
                'medium_performers': len(medium_performers),
                'low_performers': len(low_performers),
                'high_performers_list': high_performers[:10],  # Top 10
                'low_performers_list': low_performers[:10]     # Bottom 10
            }
        }

    def _generate_alerts_and_warnings(self, no_goals: List[Dict], no_checkins: List[Dict],
                                    goals_no_checkins: List[Dict], weekly_shifts: List[Dict],
                                    period_checkins: List[Dict]) -> Dict:
        """Tạo cảnh báo và thông báo"""
        alerts = {
            'critical_issues': [],
            'moderate_issues': [],
            'improvement_opportunities': []
        }

        # Cảnh báo nghiêm trọng: không có goals
        for user in no_goals:
            alerts['critical_issues'].append({
                'type': 'NO_GOALS',
                'user': user['name'],
                'username': user['username'],
                'message': f"Thành viên {user['name']} chưa thiết lập OKR",
                'priority': 'HIGH'
            })

        # Cảnh báo nghiêm trọng: không có check-ins
        for user in no_checkins:
            alerts['critical_issues'].append({
                'type': 'NO_CHECKINS',
                'user': user['name'],
                'username': user['username'],
                'message': f"Thành viên {user['name']} chưa thực hiện check-in nào",
                'priority': 'HIGH'
            })

        # Cảnh báo vừa phải: có goals nhưng không check-in
        for user in goals_no_checkins:
            alerts['moderate_issues'].append({
                'type': 'GOALS_NO_CHECKINS',
                'user': user['name'],
                'username': user['username'],
                'message': f"Thành viên {user['name']} có OKR nhưng chưa check-in",
                'priority': 'MEDIUM'
            })

        # Cảnh báo hiệu suất thấp
        low_performers = [u for u in weekly_shifts if u.get('okr_shift', 0) < 0]
        for user in low_performers:
            alerts['moderate_issues'].append({
                'type': 'LOW_PERFORMANCE',
                'user': user['user_name'],
                'shift': user.get('okr_shift', 0),
                'message': f"Thành viên {user['user_name']} có tiến độ OKR âm ({user.get('okr_shift', 0):.2f})",
                'priority': 'MEDIUM'
            })

        # Cơ hội cải thiện: ít check-ins
        infrequent_checkins = [u for u in period_checkins if u.get('checkin_count_period', 0) < 2]
        for user in infrequent_checkins:
            alerts['improvement_opportunities'].append({
                'type': 'INFREQUENT_CHECKINS',
                'user': user['user_name'],
                'checkin_count': user.get('checkin_count_period', 0),
                'message': f"Thành viên {user['user_name']} chỉ có {user.get('checkin_count_period', 0)} check-in trong kỳ",
                'priority': 'LOW'
            })

        return alerts

    def _calculate_organization_health(self, weekly_shifts: List[Dict],
                                    period_checkins: List[Dict],
                                    overall_checkins: List[Dict]) -> Dict:
        """Tính toán sức khỏe tổng thể của tổ chức"""
        health_metrics = {
            'okr_health_score': 0,
            'checkin_health_score': 0,
            'overall_health_score': 0,
            'trends': {},
            'recommendations': []
        }

        # Tính điểm sức khỏe OKR (0-100)
        if weekly_shifts:
            positive_shifts = len([u for u in weekly_shifts if u.get('okr_shift', 0) > 0])
            total_users = len(weekly_shifts)
            okr_health_score = (positive_shifts / total_users) * 100
            health_metrics['okr_health_score'] = round(okr_health_score, 1)

        # Tính điểm sức khỏe check-in (0-100)
        if period_checkins:
            users_with_checkins = len([u for u in period_checkins if u.get('checkin_count_period', 0) > 0])
            total_users = len(period_checkins)
            checkin_health_score = (users_with_checkins / total_users) * 100
            health_metrics['checkin_health_score'] = round(checkin_health_score, 1)

        # Điểm tổng thể
        health_metrics['overall_health_score'] = round(
            (health_metrics['okr_health_score'] + health_metrics['checkin_health_score']) / 2, 1
        )

        # Xu hướng
        health_metrics['trends'] = self._analyze_health_trends()

        # Đề xuất
        health_metrics['recommendations'] = self._generate_health_recommendations(health_metrics)

        return health_metrics

    def _analyze_health_trends(self) -> Dict:
        """Phân tích xu hướng sức khỏe"""
        # Đây là nơi phân tích xu hướng nếu có dữ liệu lịch sử
        # Hiện tại trả về xu hướng cơ bản dựa trên dữ liệu hiện tại
        return {
            'okr_trend': 'stable',  # stable, improving, declining
            'checkin_trend': 'stable',
            'overall_trend': 'stable',
            'confidence': 'medium'
        }

    def _generate_health_recommendations(self, health_metrics: Dict) -> List[str]:
        """Tạo đề xuất cải thiện"""
        recommendations = []

        if health_metrics['okr_health_score'] < 60:
            recommendations.append("Tập trung cải thiện tiến độ OKR của các thành viên có hiệu suất thấp")

        if health_metrics['checkin_health_score'] < 70:
            recommendations.append("Khuyến khích các thành viên thực hiện check-in đều đặn hơn")

        if health_metrics['overall_health_score'] < 65:
            recommendations.append("Cần có kế hoạch hành động để cải thiện sức khỏe OKR tổng thể")

        if not recommendations:
            recommendations.append("Tiếp tục duy trì hiệu suất OKR hiện tại")

        return recommendations

    def _create_detailed_user_analysis(self, weekly_shifts: List[Dict],
                                     period_checkins: List[Dict],
                                     overall_checkins: List[Dict],
                                     alignment_analysis: Dict[str, Dict]) -> List[Dict]:
        """Tạo phân tích chi tiết cho từng user"""
        user_analysis = []

        for shift_data in weekly_shifts:
            user_name = shift_data['user_name']

            # Tìm thông tin check-in của user này
            user_period_checkin = next((u for u in period_checkins if u['user_name'] == user_name), {})
            user_overall_checkin = next((u for u in overall_checkins if u['user_name'] == user_name), {})
            
            # Tìm thông tin căn chỉnh (đóng góp) của user này
            user_alignment_data = alignment_analysis.get(user_name, {
                'total_krs': 0,
                'company_alignment_pct': 0,
                'dept_alignment_pct': 0,
                'team_alignment_pct': 0,
                'total_alignment_pct': 0
            })

            # Tạo phân tích tổng hợp cho user
            analysis = {
                'user_name': user_name,
                'okr_performance': {
                    'weekly_shift': shift_data.get('okr_shift', 0),
                    'current_value': shift_data.get('current_value', 0),
                    'reference_value': shift_data.get('last_friday_value', 0),
                    'kr_count': shift_data.get('kr_details_count', 0),
                    'performance_level': self._classify_performance(shift_data.get('okr_shift', 0))
                },
                'checkin_behavior': {
                    'period_checkins': user_period_checkin.get('checkin_count_period', 0),
                    'total_checkins': user_overall_checkin.get('total_checkins', 0),
                    'checkin_rate': user_period_checkin.get('checkin_rate_period', 0),
                    'frequency_per_week': user_overall_checkin.get('checkin_frequency_per_week', 0),
                    'last_week_checkins': user_overall_checkin.get('last_week_checkins', 0)
                },
                'alignment_contribution': user_alignment_data,
                'risk_assessment': self._assess_user_risk(shift_data, user_period_checkin, user_overall_checkin),
                'recommendations': self._generate_user_recommendations(shift_data, user_period_checkin)
            }

            user_analysis.append(analysis)

        return sorted(user_analysis, key=lambda x: x['okr_performance']['weekly_shift'], reverse=True)

    def _classify_performance(self, shift_value: float) -> str:
        """Phân loại hiệu suất"""
        if shift_value >= 20:
            return 'Xuất sắc'
        elif shift_value >= 10:
            return 'Tốt'
        elif shift_value >= 0:
            return 'Đạt yêu cầu'
        else:
            return 'Cần cải thiện'

    def _assess_user_risk(self, shift_data: Dict, period_checkin: Dict, overall_checkin: Dict) -> Dict:
        """Đánh giá rủi ro của user"""
        risk_score = 0
        risk_factors = []

        # Kiểm tra tiến độ OKR
        if shift_data.get('okr_shift', 0) < 0:
            risk_score += 30
            risk_factors.append('Tiến độ OKR âm')

        # Kiểm tra số lượng check-in
        if period_checkin.get('checkin_count_period', 0) < 2:
            risk_score += 25
            risk_factors.append('Ít check-in trong kỳ')

        # Kiểm tra tần suất check-in
        if overall_checkin.get('checkin_frequency_per_week', 0) < 1:
            risk_score += 20
            risk_factors.append('Tần suất check-in thấp')

        # Kiểm tra số KR
        if shift_data.get('kr_details_count', 0) == 0:
            risk_score += 25
            risk_factors.append('Không có KR hoạt động')

        # Phân loại rủi ro
        if risk_score >= 60:
            risk_level = 'Cao'
        elif risk_score >= 30:
            risk_level = 'Trung bình'
        else:
            risk_level = 'Thấp'

        return {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'risk_factors': risk_factors
        }

    def _generate_user_recommendations(self, shift_data: Dict, period_checkin: Dict) -> List[str]:
        """Tạo đề xuất cho từng user"""
        recommendations = []
        shift = shift_data.get('okr_shift', 0)
        checkins = period_checkin.get('checkin_count_period', 0)

        if shift < 0:
            recommendations.append('Tập trung cải thiện tiến độ OKR')

        if checkins < 2:
            recommendations.append('Tăng cường tần suất check-in (ít nhất 2 lần/tuần)')

        if shift_data.get('kr_details_count', 0) == 0:
            recommendations.append('Thiết lập các KR cụ thể và đo lường được')

        if not recommendations:
            recommendations.append('Tiếp tục duy trì hiệu suất tốt')

        return recommendations

    def _create_summary_report(self, report: Dict) -> Dict:
        """Tạo báo cáo tổng hợp"""
        summary = {
            'report_generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'key_metrics': {},
            'top_issues': [],
            'highlights': []
        }

        # Các chỉ số chính
        weekly_analysis = report.get('weekly_okr_analysis', {})
        alerts = report.get('alerts_and_warnings', {})
        health = report.get('organization_health', {})

        summary['key_metrics'] = {
            'total_active_users': weekly_analysis.get('total_users', 0),
            'okr_health_score': health.get('okr_health_score', 0),
            'checkin_health_score': health.get('checkin_health_score', 0),
            'overall_health_score': health.get('overall_health_score', 0),
            'critical_issues': len(alerts.get('critical_issues', [])),
            'moderate_issues': len(alerts.get('moderate_issues', []))
        }

        # Các vấn đề hàng đầu
        top_issues = []
        for issue in alerts.get('critical_issues', [])[:5]:
            top_issues.append(f"{issue['type']}: {issue['user']}")
        for issue in alerts.get('moderate_issues', [])[:3]:
            top_issues.append(f"{issue['type']}: {issue['user']}")
        summary['top_issues'] = top_issues

        # Điểm nổi bật
        highlights = []
        if health.get('overall_health_score', 0) >= 80:
            highlights.append('Sức khỏe OKR tổng thể rất tốt')
        elif health.get('overall_health_score', 0) >= 65:
            highlights.append('Sức khỏe OKR tổng thể ở mức tốt')
        else:
            highlights.append('Cần cải thiện sức khỏe OKR tổng thể')

        perf_dist = weekly_analysis.get('performance_distribution', {})
        if perf_dist.get('high_performers', 0) > 0:
            highlights.append(f'Có {perf_dist["high_performers"]} thành viên xuất sắc')

        summary['highlights'] = highlights

        return summary


def print_report(report: Dict):
    """Hiển thị báo cáo tổng hợp một cách dễ đọc"""
    summary = report.get('summary', {})

    print(f"\n📊 THÔNG TIN TỔNG QUAN")
    print("-" * 50)
    print(f"Thời gian tạo báo cáo: {summary.get('report_generated', 'N/A')}")
    print(f"Tổng số thành viên: {summary.get('key_metrics', {}).get('total_active_users', 0)}")
    print(f"Điểm sức khỏe OKR: {summary.get('key_metrics', {}).get('okr_health_score', 0)}/100")
    print(f"Điểm sức khỏe Check-in: {summary.get('key_metrics', {}).get('checkin_health_score', 0)}/100")
    print(f"Điểm sức khỏe tổng thể: {summary.get('key_metrics', {}).get('overall_health_score', 0)}/100")

    # Điểm nổi bật
    highlights = summary.get('highlights', [])
    if highlights:
        print(f"\n✨ ĐIỂM NỔI BẬT:")
        for highlight in highlights:
            print(f"  • {highlight}")

    # Các vấn đề hàng đầu
    top_issues = summary.get('top_issues', [])
    if top_issues:
        print(f"\n⚠️  CÁC VẤN ĐỀ HÀNG ĐẦU:")
        for issue in top_issues:
            print(f"  • {issue}")

    # Phân tích OKR theo tuần
    weekly_analysis = report.get('weekly_okr_analysis', {})
    if weekly_analysis:
        print(f"\n📈 PHÂN TÍCH OKR THEO TUẦN")
        print("-" * 50)
        print(f"Tổng số người dùng: {weekly_analysis.get('total_users', 0)}")
        print(f"Người dùng có tiến độ tích cực: {weekly_analysis.get('users_positive_shift', 0)}")
        print(f"Người dùng có tiến độ âm: {weekly_analysis.get('users_negative_shift', 0)}")
        print(f"Giá trị thay đổi trung bình: {weekly_analysis.get('avg_shift', 0):.2f}")
        print(f"Giá trị hiện tại trung bình: {weekly_analysis.get('avg_current_value', 0):.2f}")

        perf_dist = weekly_analysis.get('performance_distribution', {})
        print(f"\nPhân loại hiệu suất:")
        print(f"  • Xuất sắc (≥20): {perf_dist.get('high_performers', 0)} người")
        print(f"  • Tốt (10-19): {perf_dist.get('medium_performers', 0)} người")
        print(f"  • Đạt yêu cầu (0-9): {len([u for u in report.get('detailed_user_analysis', []) if u['okr_performance']['performance_level'] == 'Đạt yêu cầu'])} người")
        print(f"  • Cần cải thiện (<0): {perf_dist.get('low_performers', 0)} người")

    # Cảnh báo và thông báo
    alerts = report.get('alerts_and_warnings', {})
    if alerts:
        print(f"\n🚨 CẢNH BÁO VÀ THÔNG BÁO")
        print("-" * 50)

        critical_issues = alerts.get('critical_issues', [])
        if critical_issues:
            print(f"Vấn đề nghiêm trọng ({len(critical_issues)}):")
            for issue in critical_issues[:5]:  # Hiển thị tối đa 5 vấn đề
                print(f"  • {issue['message']}")

        moderate_issues = alerts.get('moderate_issues', [])
        if moderate_issues:
            print(f"\nVấn đề vừa phải ({len(moderate_issues)}):")
            for issue in moderate_issues[:5]:  # Hiển thị tối đa 5 vấn đề
                print(f"  • {issue['message']}")

        opportunities = alerts.get('improvement_opportunities', [])
        if opportunities:
            print(f"\nCơ hội cải thiện ({len(opportunities)}):")
            for opportunity in opportunities[:3]:  # Hiển thị tối đa 3 cơ hội
                print(f"  • {opportunity['message']}")

    # Sức khỏe tổ chức
    health = report.get('organization_health', {})
    if health:
        print(f"\n🏥 SỨC KHỎE TỔ CHỨC")
        print("-" * 50)
        print(f"Điểm sức khỏe OKR: {health.get('okr_health_score', 0)}/100")
        print(f"Điểm sức khỏe Check-in: {health.get('checkin_health_score', 0)}/100")
        print(f"Điểm sức khỏe tổng thể: {health.get('overall_health_score', 0)}/100")

        trends = health.get('trends', {})
        print(f"\nXu hướng:")
        print(f"  • OKR: {trends.get('okr_trend', 'N/A')}")
        print(f"  • Check-in: {trends.get('checkin_trend', 'N/A')}")
        print(f"  • Tổng thể: {trends.get('overall_trend', 'N/A')}")

        recommendations = health.get('recommendations', [])
        if recommendations:
            print(f"\n💡 Đề xuất:")
            for rec in recommendations:
                print(f"  • {rec}")

    # Top performers
    detailed_analysis = report.get('detailed_user_analysis', [])
    if detailed_analysis:
        print(f"\n🏆 TOP PERFORMERS (TOP 10)")
        print("-" * 50)

        top_performers = detailed_analysis[:10]
        for i, user in enumerate(top_performers, 1):
            perf = user['okr_performance']
            checkin = user['checkin_behavior']
            align = user.get('alignment_contribution', {})
            align_pct = align.get('total_alignment_pct', 0)
            
            print(f"{i}. {user['user_name']}")
            print(f"   • Tiến độ tuần: {perf['weekly_shift']:.2f} | Mức độ: {perf['performance_level']}")
            print(f"   • Đóng góp (Căn chỉnh): {align_pct:.1f}% KRs ({align.get('aligned_any_krs', 0)}/{align.get('total_krs', 0)})")
            print(f"   • Check-in kỳ này: {checkin['period_checkins']} lần | Tổng cộng: {checkin['total_checkins']} lần")
            print(f"   • Điểm rủi ro: {user['risk_assessment']['risk_level']} ({user['risk_assessment']['risk_score']})")

        # Bottom performers
        bottom_performers = [u for u in detailed_analysis if u['okr_performance']['weekly_shift'] < 0]
        if bottom_performers:
            print(f"\n⚠️  CẦN HỖ TRỢ (Bottom performers)")
            print("-" * 50)
            for i, user in enumerate(bottom_performers[:5], 1):
                perf = user['okr_performance']
                risk = user['risk_assessment']
                print(f"{i}. {user['user_name']}")
                print(f"   • Tiến độ tuần: {perf['weekly_shift']:.2f} | Mức độ: {perf['performance_level']}")
                print(f"   • Điểm rủi ro: {risk['risk_level']} | Các vấn đề: {', '.join(risk['risk_factors'][:2])}")

                recs = user.get('recommendations', [])
                if recs:
                    print(f"   • Đề xuất: {recs[0]}")

    print(f"\n" + "="*80)
    print("📋 BÁO CÁO HOÀN THÀNH")
    print("="*80)

def get_goal_data(employee_name):
    """Lấy dữ liệu Goal/OKR bao gồm cả điểm số và hành vi check-in"""
    try:
        print(f"\n🔄 Đang tải dữ liệu Goal/OKR & Phân tích hành vi cho {employee_name}...")
        analyzer = OKRAnalysisSystem(GOAL_ACCESS_TOKEN, ACCOUNT_ACCESS_TOKEN)
        cycles = analyzer.get_cycle_list()
        if not cycles: return None
        
        # Chọn chu kỳ mới nhất
        analyzer.checkin_path = cycles[0]['path']
        analyzer.load_and_process_data()
        
        # 1. Lấy dữ liệu biến động điểm số (Weekly Shift)
        weekly_shifts = analyzer.calculate_okr_shifts_by_user()
        employee_weekly = next((u for u in weekly_shifts if u['user_name'] == employee_name), None)
        
        # 2. Lấy dữ liệu hành vi Check-in (Discipline)
        # goal.py có hàm analyze_checkin_behavior trả về (period_checkins, overall_checkins)
        period_checkins, overall_checkins = analyzer.analyze_checkin_behavior()
        
        employee_period_checkin = next((u for u in period_checkins if u['user_name'] == employee_name), None)
        employee_overall_checkin = next((u for u in overall_checkins if u['user_name'] == employee_name), None)
        
        # 3. Lấy danh sách mục tiêu chi tiết và tính tốc độ
        # Lấy user_id từ mapping
        employee_user_id = None
        if not user_id_to_name_map:
            load_user_mapping()
            
        for uid, name in user_id_to_name_map.items():
            if name == employee_name:
                employee_user_id = uid
                break
        
        goals_list = []
        fraction_of_time = 0.0

        raw_goal_records = []

        if employee_user_id:
            # Lấy dữ liệu goals từ API (thông qua analyzer.api_client)
            # Lưu ý: analyzer.api_client là object APIClient được khởi tạo trong OKRAnalysisSystem
            df_goals = analyzer.api_client.get_goals_data(analyzer.checkin_path)
            
            if not df_goals.empty:
                # Lọc goal của user
                user_goals = df_goals[df_goals['goal_user_id'] == str(employee_user_id)].copy()
                
                # Tính toán fraction_of_time
                # Giả sử cycle là quý, lấy start_time từ cycle info
                cycle_start = None
                for cycle in cycles:
                    if cycle['path'] == analyzer.checkin_path:
                        cycle_start = cycle['start_time'] # datetime object (UTC)
                        break
                
                fraction_of_time = 1.0
                if cycle_start:
                    # Chuyển về timezone HCM để so sánh
                    cycle_start_hcm = cycle_start.astimezone(hcm_tz)
                    now_hcm = datetime.now(hcm_tz)
                    
                    # Giả định quý dài 90 ngày
                    cycle_duration_days = 90
                    possible_days_passed = (now_hcm - cycle_start_hcm).days
                    days_passed = max(0, possible_days_passed)
                    
                    if days_passed <= 0:
                        fraction_of_time = 0.01 # Tránh chia cho 0
                    else:
                        fraction_of_time = min(days_passed / cycle_duration_days, 1.0)
                
                if not user_goals.empty:
                    raw_goal_records = user_goals.astype(str).to_dict(orient="records")

                for _, row in user_goals.iterrows():
                    current_val = float(row.get('goal_current_value', 0))
                    # Target value thường là 100% cho OKR, hoặc cần lấy từ target nếu có. 
                    # Ở đây giả định goal_current_value là % hoàn thành (0-100)
                    
                    # Tính tốc độ: percent_complete / fraction_of_time
                    # percent_complete là 0-100, fraction_of_time là 0-1
                    # Để ra tỉ lệ (ví dụ 1.0 là đúng tiến độ), ta dùng (current_val / 100) / fraction_of_time
                    
                    percent_complete = current_val # Giả sử giá trị là %, ví dụ 45.5
                    
                    if fraction_of_time > 0:
                        speed = (percent_complete / 100.0) / fraction_of_time
                    else:
                        speed = 0
                        
                    goals_list.append({
                        'name': row.get('goal_name', 'Unknown'),
                        'current_value': current_val,
                        'speed': speed
                    })

        return {
            'weekly': employee_weekly,
            'checkin_behavior': employee_period_checkin,
            'overall_behavior': employee_overall_checkin,
            'cycle_name': cycles[0]['name'],
            'goals_list': goals_list,
            'fraction_of_time': fraction_of_time,
            'raw_df_records': raw_goal_records
        }
    except Exception as e:
        print(f"❌ Lỗi khi lấy dữ liệu Goal: {e}")
        return None

if __name__ == "__main__":
    analyzer = OKRAnalysisSystem(GOAL_ACCESS_TOKEN, ACCOUNT_ACCESS_TOKEN)

    # Get cycles
    cycles = analyzer.get_cycle_list()
    if cycles:
        # Select first cycle
        selected_cycle = cycles[0]
        analyzer.checkin_path = selected_cycle['path']

        # Load data
        df = analyzer.load_and_process_data()

        if df is not None:
            print(f"Loaded {len(df)} records")

            # Analyze missing goals
            no_goals, no_checkins, goals_no_checkins = analyzer.analyze_missing_goals_and_checkins()
            print(f"Members without goals: {len(no_goals)}")
            print(f"Members without checkins: {len(no_checkins)}")

            # Calculate OKR shifts
            weekly_shifts = analyzer.calculate_okr_shifts_by_user()
            print(f"Weekly OKR shifts calculated for {len(weekly_shifts)} users")

            # Generate comprehensive OKR report
            print("\n" + "="*80)
            print("🎯 BÁO CÁO OKR TỔNG HỢP")
            print("="*80)

            comprehensive_report = analyzer.generate_comprehensive_okr_report()

            if comprehensive_report:
                print_report(comprehensive_report)
            else:
                print("Không thể tạo báo cáo tổng hợp do thiếu dữ liệu")


