import os
from dotenv import load_dotenv

load_dotenv()
import json
import requests
import pandas as pd
import numpy as np
import pytz
import re
import unicodedata
import calendar
import warnings
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Time Constants
STANDARD_START_HOUR = 8
STANDARD_START_MINUTE = 30
STANDARD_END_HOUR = 17
STANDARD_END_MINUTE = 30

# TOKENS
CHECKIN_TOKEN = os.getenv('CHECKIN_TOKEN')
TIMEOFF_TOKEN = os.getenv('TIMEOFF_TOKEN')
ACCOUNT_TOKEN = os.getenv('ACCOUNT_TOKEN')

# Config
hcm_tz = pytz.timezone('Asia/Ho_Chi_Minh')
DEFAULT_EMPLOYEE_NAME = "Trần Thanh Sơn" # Default fallback

class ReasonClassifier:
    """Class để phân loại lý do nghỉ bằng cosine similarity"""
    
    def __init__(self):
        self.categories = {
            'annual_leave': {
                'keywords': [
                    'phép năm', 'nghỉ phép', 'annual leave', 'vacation', 'holiday',
                    'du lịch', 'đi chơi', 'nghỉ mát', 'resort', 'biển', 'núi',
                    'về quê', 'thăm quê', 'nghỉ dưỡng', 'thư giãn', 'relax',
                    'break', 'nghỉ ngơi', 'rest', 'phục hồi', 'tái tạo năng lượng',
                    'đi du lịch', 'travel', 'trip', 'picnic', 'tour', 'khám phá',
                    'nghỉ lễ', 'long weekend', 'nghỉ cuối tuần', 'staycation'
                ],
                'color': '#28a745',
                'icon': '🏖️',
                'label': 'Phép năm'
            },
            'personal': {
                'keywords': [
                    'cá nhân', 'việc riêng', 'bận việc cá nhân', 'công việc cá nhân',
                    'giải quyết việc', 'làm việc cá nhân', 'việc tư', 'tự do',
                    'mua sắm', 'đi ngân hàng', 'làm giấy tờ', 'visa', 'hộ chiếu',
                    'sửa nhà', 'chuyển nhà', 'dọn nhà', 'việc nhà'
                ],
                'color': '#6f42c1',
                'icon': '👤',
                'label': 'Cá nhân'
            },
            'remote': {
                'keywords': [
                    'remote', 'work from home', 'wfh', 'làm việc từ xa','outside',
                    'làm việc tại nhà', 'online', 'từ xa', 'không đến công ty',
                    'ở nhà làm việc', 'home office', 'telecommuting', 'virtual work'
                ],
                'color': '#17a2b8',
                'icon': '💻',
                'label': 'Remote'
            },
            'business': {
                'keywords': [
                    'công tác', 'business trip', 'công việc', 'meeting', 'họp',
                    'hội nghị', 'đào tạo', 'khóa học', 'seminar', 'conference',
                    'gặp khách hàng', 'partner', 'đối tác', 'dự án', 'project',
                    'ra ngoài công tác', 'đi công tác', 'business'
                ],
                'color': '#fd7e14',
                'icon': '💼',
                'label': 'Công tác'
            },
            'sick': {
                'keywords': [
                    'ốm', 'bệnh', 'đau', 'sốt', 'cảm', 'ho', 'khám bệnh', 'chữa bệnh',
                    'bác sĩ', 'bệnh viện', 'phòng khám', 'điều trị', 'thuốc', 'y tế',
                    'sức khỏe', 'không khỏe', 'mệt', 'kiệt sức', 'stress', 'lo âu',
                    'sick', 'ill', 'medical', 'doctor', 'hospital', 'fever', 'cold',
                    'đau đầu', 'đau bụng', 'đau răng', 'cúm', 'viêm họng', 'ho khan',
                    'sốt cao', 'sốt nhẹ', 'cảm lạnh', 'cảm cúm', 'không được khỏe',
                    'đi khám', 'tái khám', 'xét nghiệm', 'chụp phim', 'siêu âm'
                ],
                'color': '#dc3545',
                'icon': '🤒',
                'label': 'Đau ốm'
            },
            'special_leave': {
                'keywords': [
                    'thai sản', 'sinh con', 'maternity', 'paternity', 'đám cưới', 'cưới',
                    'wedding', 'đám tang', 'tang lễ', 'funeral', 'ma chay', 'hiếu hỷ',
                    'gia đình', 'bố', 'mẹ', 'con', 'vợ', 'chồng', 'ông', 'bà', 'cháu',
                    'họp mặt gia đình', 'việc gia đình', 'chăm sóc', 'người thân',
                    'khẩn cấp', 'gấp', 'emergency', 'cứu cấp', 'tai nạn', 'sự cố',
                    'bất ngờ', 'đột xuất'
                ],
                'color': '#e83e8c',
                'icon': '👨‍👩‍👧‍👦',
                'label': 'Chế độ đặc biệt'
            }
        }
        
        self.corpus = []
        self.category_names = []
        
        for category, data in self.categories.items():
            combined_text = ' '.join(data['keywords'])
            self.corpus.append(combined_text)
            self.category_names.append(category)
        
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words=None,
            lowercase=True,
            max_features=1000
        )
        
        self.category_vectors = self.vectorizer.fit_transform(self.corpus)
    
    def preprocess_text(self, text: str) -> str:
        if not text or pd.isna(text):
            return ""
        text = str(text).lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def classify_reason(self, reason: str, threshold: float = 0.15) -> Dict:
        if not reason or pd.isna(reason):
            return self.get_default_category()
        
        processed_reason = self.preprocess_text(reason)
        if not processed_reason:
            return self.get_default_category()
        
        rule_based_result = self._rule_based_classify(processed_reason)
        if rule_based_result:
            return rule_based_result
        
        try:
            reason_vector = self.vectorizer.transform([processed_reason])
            similarities = cosine_similarity(reason_vector, self.category_vectors)[0]
            max_similarity_idx = np.argmax(similarities)
            max_similarity = similarities[max_similarity_idx]
            
            if max_similarity >= threshold:
                best_category = self.category_names[max_similarity_idx]
                category_info = self.categories[best_category].copy()
                category_info['similarity'] = max_similarity
                category_info['category'] = best_category
                return category_info
            else:
                return self.get_default_category()
                
        except Exception as e:
            print(f"Error in classify_reason: {e}")
            return self.get_default_category()
    
    def _rule_based_classify(self, processed_reason: str) -> Optional[Dict]:
        sick_patterns = [
            r'\\b(ốm|bệnh|đau|sốt|ho|cảm|không khỏe|sick|ill|fever)\\b',
            r'\\b(khám bệnh|chữa bệnh|bác sĩ|bệnh viện|phòng khám|doctor|hospital)\\b',
            r'\\b(thuốc|điều trị|y tế|sức khỏe|medical)\\b'
        ]
        
        for pattern in sick_patterns:
            if re.search(pattern, processed_reason, re.IGNORECASE):
                sick_info = self.categories['sick'].copy()
                sick_info['similarity'] = 0.95
                sick_info['category'] = 'sick'
                return sick_info
        
        remote_patterns = [
            r'\\b(remote|wfh|work from home|làm việc tại nhà|làm việc từ xa)\\b',
            r'\\b(ở nhà làm việc|không đến công ty|home office)\\b'
        ]
        
        for pattern in remote_patterns:
            if re.search(pattern, processed_reason, re.IGNORECASE):
                remote_info = self.categories['remote'].copy()
                remote_info['similarity'] = 0.90
                remote_info['category'] = 'remote'
                return remote_info
        
        business_patterns = [
            r'\\b(công tác|business trip|meeting|họp|hội nghị)\\b',
            r'\\b(gặp khách hàng|partner|đối tác|conference)\\b',
            r'\\b(ra ngoài công tác|đi công tác)\\b'
        ]
        
        for pattern in business_patterns:
            if re.search(pattern, processed_reason, re.IGNORECASE):
                business_info = self.categories['business'].copy()
                business_info['similarity'] = 0.88
                business_info['category'] = 'business'
                return business_info
        
        return None
    
    def get_default_category(self) -> Dict:
        return {
            'color': '#6c757d',
            'icon': '📝',
            'label': 'Khác',
            'category': 'other',
            'similarity': 0.0
        }


class EmployeeManager:
    """Class để quản lý thông tin nhân viên"""
    
    def __init__(self, account_token: str):
        self.account_token = account_token
        self.request_timeout = 30
        self.username_to_name_map = {}
        self.username_to_since_map = {}
        self._load_employee_mapping()
    
    def _make_request(self, url: str, data: Dict, description: str = "") -> requests.Response:
        try:
            response = requests.post(url, data=data, timeout=self.request_timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            print(f"Error {description}: {e}")
            raise
    
    def _load_employee_mapping(self):
        url = "https://account.base.vn/extapi/v1/group/get"
        data = {"access_token": self.account_token, "path": "nvvanphong"}
        
        try:
            response = self._make_request(url, data, "fetching account members")
            response_data = response.json()
            members = response_data.get('group', {}).get('members', [])
            self.username_to_name_map = {
                m.get('username', ''): m.get('name', '') 
                for m in members 
                if m.get('username') and m.get('name')
            }
            self.username_to_since_map = {
                m.get('username', ''): m.get('since', '') 
                for m in members 
                if m.get('username') and m.get('since')
            }
        except Exception as e:
            print(f"Lỗi khi lấy danh sách nhân viên: {e}")
            self.username_to_name_map = {}
            self.username_to_since_map = {}
    
    def get_name_by_username(self, username: str) -> str:
        if not username:
            return ''
        return self.username_to_name_map.get(username, username)
    
    def get_since_by_username(self, username: str) -> str:
        """Lấy trường 'since' (timestamp) của nhân viên theo username"""
        if not username:
            return ''
        return self.username_to_since_map.get(username, '')


class TimeoffProcessor:
    """Class để xử lý dữ liệu timeoff"""
    
    def __init__(self, timeoff_token: str, account_token: str):
        self.timeoff_token = timeoff_token
        self.employee_manager = EmployeeManager(account_token)
        
    def get_base_timeoff_data(self, start_date=None, end_date=None, start_date_from=None, start_date_to=None, end_date_from=None, end_date_to=None):
        url = "https://timeoff.base.vn/extapi/v1/timeoff/list"

        # Tạo payload với các tham số tùy chọn
        payload_data = {'access_token': self.timeoff_token,'items_per_page': 100}

        if start_date_from:
            payload_data['start_date_from'] = start_date_from
        if start_date_to:
            payload_data['start_date_to'] = start_date_to
        if end_date_from:
            payload_data['end_date_from'] = end_date_from
        if end_date_to:
            payload_data['end_date_to'] = end_date_to

        payload = '&'.join([f'{k}={v}' for k, v in payload_data.items()])
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = requests.post(url, headers=headers, data=payload)
        return response.json()
    
    def extract_form_data(self, form_list):
        form_data = {}
        for form_item in form_list:
            if form_item.get('name') and form_item.get('value'):
                form_data[form_item['name']] = form_item['value']
        return form_data
    
    def extract_shift_values(self, shifts_data):
        shift_values = []
        if not shifts_data or not isinstance(shifts_data, list):
            return shift_values
        
        for shift_day in shifts_data:
            shifts = shift_day.get('shifts', [])
            for shift in shifts:
                if shift.get('value'):
                    shift_values.append(shift['value'])
        return shift_values
    
    def clean_vietnamese_text(self, text):
        text = unicodedata.normalize('NFD', text)
        text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
        text = text.replace(' ', '_').replace('/', '_').replace('(', '').replace(')', '').replace('-', '_').lower()
        return text
    
    def convert_timestamp_to_date(self, timestamp):
        if timestamp and timestamp != '0':
            try:
                # Sử dụng timezone Asia/Ho_Chi_Minh để tránh lệch múi giờ
                utc_dt = datetime.fromtimestamp(int(timestamp), tz=pytz.UTC)
                vietnam_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                return utc_dt.astimezone(vietnam_tz)
            except:
                return None
        return None
    
    def convert_approvals_to_names(self, approvals: List[str]) -> str:
        if not approvals:
            return ''
        approval_names = []
        for username in approvals:
            name = self.employee_manager.get_name_by_username(username)
            approval_names.append(name)
        return ', '.join(approval_names)
    
    def create_ly_do_column_and_cleanup(self, df):
        if df.empty:
            return df
            
        df_copy = df.copy()
        df_copy['ly_do'] = ''
        
        priority_columns = ['ly_do_xin_nghi_phep', 'ly_do_xin_nghi_chinh', 'ly_do_xin_nghi']
        
        for col in priority_columns:
            if col in df_copy.columns:
                mask = (
                    (df_copy['ly_do'] == '') & 
                    (df_copy[col].notna()) & 
                    (df_copy[col].astype(str).str.strip() != '')
                )
                df_copy.loc[mask, 'ly_do'] = df_copy.loc[mask, col].astype(str).str.strip()
        
        business_mask = (
            (df_copy['ly_do'] == '') & 
            (df_copy['metatype'] == 'business')
        )
        df_copy.loc[business_mask, 'ly_do'] = 'business'

        outside_mask = (
            (df_copy['ly_do'] == '') & 
            (df_copy['metatype'] == 'outside')
        )
        df_copy.loc[outside_mask, 'ly_do'] = 'remote'
        
        columns_to_drop = [col for col in priority_columns if col in df_copy.columns]
        if columns_to_drop:
            df_copy = df_copy.drop(columns=columns_to_drop)
        
        return df_copy
    
    def extract_timeoff_to_dataframe(self, api_response):
        timeoffs_data = []
        
        if 'timeoffs' in api_response:
            for timeoff in api_response['timeoffs']:
                form_data = self.extract_form_data(timeoff.get('form', []))
                approvals = timeoff.get('approvals', [])
                approval_names = self.convert_approvals_to_names(approvals)
                total_shifts = len(timeoff.get('shifts', []))
                
                total_leave_days = 0
                for shift_day in timeoff.get('shifts', []):
                    for shift in shift_day.get('shifts', []):
                        if 'num_leave' in shift:
                            total_leave_days += float(shift.get('num_leave', 0))
                
                final_approver_username = ''
                final_approver_name = ''
                if timeoff.get('data', {}).get('final_approved'):
                    final_approver_username = timeoff['data']['final_approved'].get('username', '')
                    final_approver_name = self.employee_manager.get_name_by_username(final_approver_username)
                
                username = timeoff.get('username', '')
                employee_name = self.employee_manager.get_name_by_username(username)
                
                start_date = self.convert_timestamp_to_date(timeoff.get('start_date'))
                end_date = self.convert_timestamp_to_date(timeoff.get('end_date'))

                buoi_nghi = self.extract_shift_values(timeoff.get('shifts', []))
                
                timeoff_record = {
                    'id': timeoff.get('id'),
                    'employee_name': employee_name,
                    'username': username,
                    'state': timeoff.get('state'),
                    'metatype': timeoff.get('metatype'),
                    'paid_timeoff': timeoff.get('paid_timeoff'),
                    'start_date': start_date,
                    'end_date': end_date,
                    'total_leave_days': total_leave_days,
                    'total_shifts': total_shifts,
                    'buoi_nghi': buoi_nghi,
                    'approvals': approval_names,
                    'final_approver': final_approver_name,
                    'workflow': timeoff.get('workflow'),
                    'created_time': self.convert_timestamp_to_date(timeoff.get('since')),
                    'last_update': self.convert_timestamp_to_date(timeoff.get('last_update')),
                }
                
                column_mapping = {
                    'Lý do xin nghỉ phép': 'ly_do_xin_nghi_phep',
                    'Lý do xin nghỉ': 'ly_do_xin_nghi',  
                    'Lý do': 'ly_do_xin_nghi',
                    'Ghi chú': 'ghi_chu',
                    'Lý do cá nhân': 'ly_do_ca_nhan',
                    'Bận việc cá nhân': 'ban_viec_ca_nhan',
                    'Việc riêng': 'viec_rieng'
                }
                
                for key, value in form_data.items():
                    if key in column_mapping:
                        clean_key = column_mapping[key]
                    else:
                        clean_key = self.clean_vietnamese_text(key)
                    timeoff_record[clean_key] = value
                
                timeoff_record['ly_do_xin_nghi_chinh'] = (
                    form_data.get('Lý do xin nghỉ phép', '') or 
                    form_data.get('Lý do xin nghỉ', '') or
                    form_data.get('Lý do', '') or
                    form_data.get('Lý do cá nhân', '') or
                    form_data.get('Bận việc cá nhân', '') or
                    form_data.get('Việc riêng', '')
                )
                
                timeoffs_data.append(timeoff_record)
        
        df = pd.DataFrame(timeoffs_data)
        
        if not df.empty and 'created_time' in df.columns:
            df = df.sort_values('created_time', ascending=False)
        
        df = self.create_ly_do_column_and_cleanup(df)
        
        return df

    def get_shift_time_range(self, buoi_nghi_list):
        """Phân tích buổi nghỉ và trả về thông tin thời gian"""
        if not buoi_nghi_list or not isinstance(buoi_nghi_list, list):
            return {'is_all_day': True, 'start_time': None, 'end_time': None}

        if len(buoi_nghi_list) >= 2:
            # Nếu nghỉ cả ngày (cả 2 buổi), trả về danh sách 2 sự kiện
            return {
                'is_all_day': True,
                'shift_events': [
                    {'start_time': '08:00:00', 'end_time': '12:00:00'},
                    {'start_time': '13:00:00', 'end_time': '17:30:00'}
                ]
            }

        if len(buoi_nghi_list) == 1:
            shift = buoi_nghi_list[0]
            shift_time_mapping = {
                '8:00-12:00': {'start_time': '08:00:00', 'end_time': '12:00:00'},
                '13:00-17:30': {'start_time': '13:00:00', 'end_time': '17:30:00'}
            }

        return {'is_all_day': True, 'start_time': None, 'end_time': None}

    def process_and_structure_timeoff(self, row: pd.Series, classifier: ReasonClassifier) -> Optional[List[Dict]]:
        """Xử lý chi tiết một yêu cầu nghỉ và trả về một list các bản ghi đã được cấu trúc"""
        if pd.isna(row['start_date']) or pd.isna(row['end_date']):
            return None

        # Phân loại lý do
        reason_result = classifier.classify_reason(str(row['ly_do'])) if row['ly_do'] and str(row['ly_do']).strip() else classifier.get_default_category()

        # Tạo tiêu đề cơ bản
        base_title = f"{reason_result['icon']} {row['employee_name']}"
        if row['ly_do'] and row['ly_do'] != '':
            reason_short = row['ly_do'][:50] + "..." if len(row['ly_do']) > 50 else row['ly_do']
            base_title += f" - {reason_short}"
        base_title += f" ({reason_result['label']})"

        # Tạo mô tả chi tiết cơ bản
        description_parts = [
            f"👤 Nhân viên: {row['employee_name']}",
            f"📊 Trạng thái: {row['state']}",
            f"📋 Loại: {row['metatype']}",
            f"📅 Tổng số ngày nghỉ: {row.get('total_leave_days', 'N/A')}",
            f"📝 Lý do: {row.get('ly_do', 'Không có')}",
            f"✅ Người duyệt: {row.get('final_approver', 'N/A')}",
            f"🤖 AI Phân loại: {reason_result['label']} (confidence: {reason_result.get('similarity', 0):.2f})",
            f"🔗 Base Timeoff ID: {row['id']}"
        ]
        base_description = "\\n".join(description_parts)

        # Xử lý thời gian
        buoi_nghi = row.get('buoi_nghi', [])
        time_info = self.get_shift_time_range(buoi_nghi)

        start_date = row['start_date'].date()
        end_date = row['end_date'].date()
        num_days = (end_date - start_date).days + 1

        processed_leaves = []

        for day_offset in range(num_days):
            current_date = start_date + timedelta(days=day_offset)
            
            if time_info.get('shift_events'):
                # Nghỉ cả ngày - tạo 2 bản ghi cho sáng và chiều
                for i, shift_time in enumerate(time_info['shift_events']):
                    processed_leaves.append({
                        'title': f"{base_title} - Ngày {day_offset + 1}/{num_days} - Buổi {i+1}",
                        'description': base_description,
                        'start': f"{current_date.strftime('%Y-%m-%d')}T{shift_time['start_time']}",
                        'end': f"{current_date.strftime('%Y-%m-%d')}T{shift_time['end_time']}",
                        'is_all_day': False,
                        'category': reason_result['label']
                    })
            elif time_info['is_all_day']:
                # Nghỉ cả ngày - tạo 1 bản ghi all-day
                processed_leaves.append({
                    'title': f"{base_title} - Ngày {day_offset + 1}/{num_days}",
                    'description': base_description,
                    'start': current_date.strftime('%Y-%m-%d'),
                    'end': (current_date + timedelta(days=1)).strftime('%Y-%m-%d'),
                    'is_all_day': True,
                    'category': reason_result['label']
                })
            else:
                # Nghỉ một buổi cụ thể
                processed_leaves.append({
                    'title': f"{base_title} - Ngày {day_offset + 1}/{num_days}",
                    'description': base_description,
                    'start': f"{current_date.strftime('%Y-%m-%d')}T{time_info['start_time']}",
                    'end': f"{current_date.strftime('%Y-%m-%d')}T{time_info['end_time']}",
                    'is_all_day': False,
                    'category': reason_result['label']
                })

        return processed_leaves

class CheckinLoader:
    """Load dữ liệu checkin"""
    
    def __init__(self, token: str):
        self.token = token
    
    def load_checkin_data(self, start_date=None, end_date=None):
        url = "https://checkin.base.vn/extapi/v1/getlogs"
        
        if start_date is None:
            now = datetime.now(hcm_tz)
            start_date = datetime(now.year, now.month, 1, 0, 0, 0)
        
        if end_date is None:
            end_date = datetime.now(hcm_tz)
        
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int(end_date.timestamp())
        
        payload = {
            'access_token': self.token,
            'start_date': start_timestamp,
            'end_date': end_timestamp
        }
        
        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != 1:
                return pd.DataFrame()
            
            return self._parse_checkin_data(data)
        except Exception as e:
            # st.error(f"❌ Error loading checkin: {e}") # Removed st dependency
            print(f"❌ Error loading checkin: {e}")
            return pd.DataFrame()
    
    def _parse_checkin_data(self, data):
        checkin_records = []
        
        for employee in data.get('logs', []):
            emp_id = employee.get('id')
            emp_code = employee.get('code')
            emp_name = employee.get('name')
            emp_email = employee.get('email')
            
            if 'logs' not in employee:
                continue
            
            for date_key, date_log in employee['logs'].items():
                try:
                    checkin_date = datetime.fromtimestamp(int(date_key), hcm_tz)
                except:
                    continue
                
                if 'logs' not in date_log:
                    continue
                
                for idx, log in enumerate(date_log['logs']):
                    try:
                        checkin_timestamp = int(log.get('time', 0))
                        checkin_time = datetime.fromtimestamp(checkin_timestamp, hcm_tz)
                    except:
                        continue
                    
                    record = {
                        'employee_id': emp_id,
                        'employee_code': emp_code,
                        'employee_name': emp_name,
                        'email': emp_email,
                        'checkin_date': checkin_date.date(),
                        'checkin_datetime': checkin_time,
                        'checkin_hour': checkin_time.hour,
                        'checkin_minute': checkin_time.minute,
                        'is_checkout': int(log.get('checkout', 0)),
                        'checkin_order': idx + 1,
                        'note': log.get('note', '')
                    }
                    
                    checkin_records.append(record)
        
        if not checkin_records:
            return pd.DataFrame()
        
        df = pd.DataFrame(checkin_records)
        df['checkin_date'] = pd.to_datetime(df['checkin_date'])
        df = df.sort_values(['employee_code', 'checkin_datetime'])
        df = df.reset_index(drop=True)
        
        return df


class DetailedAttendanceAnalyzer:
    """Phân tích chi tiết chấm công từng nhân viên"""
    
    def __init__(self, df_checkin: pd.DataFrame, df_timeoff: pd.DataFrame = None, employee_manager: EmployeeManager = None):
        self.df_checkin = df_checkin.copy() if not df_checkin.empty else pd.DataFrame()
        self.df_timeoff = df_timeoff.copy() if df_timeoff is not None and not df_timeoff.empty else pd.DataFrame()
        self.employee_manager = employee_manager
        
        # Chuẩn hóa dữ liệu
        if not self.df_checkin.empty:
            self.df_checkin['checkin_date'] = pd.to_datetime(self.df_checkin['checkin_date'])
        
        if not self.df_timeoff.empty:
            self.df_timeoff['start_date'] = pd.to_datetime(self.df_timeoff['start_date'])
            self.df_timeoff['end_date'] = pd.to_datetime(self.df_timeoff['end_date'])
        
        # Tạo mapping từ employee_name -> username
        self.name_to_username_map = {}
        # Từ df_timeoff
        if not self.df_timeoff.empty and 'username' in self.df_timeoff.columns and 'employee_name' in self.df_timeoff.columns:
            for _, row in self.df_timeoff.iterrows():
                if pd.notna(row['employee_name']) and pd.notna(row['username']):
                    self.name_to_username_map[row['employee_name']] = row['username']
        # Từ employee_manager (reverse mapping từ username -> name)
        if self.employee_manager:
            for username, name in self.employee_manager.username_to_name_map.items():
                if name and name not in self.name_to_username_map:
                    self.name_to_username_map[name] = username
    
    def _get_working_days(self, year: int, month: int, include_today: bool = False):
        """Lấy danh sách ngày làm việc trong tháng (chỉ thứ 2-6, không tính thứ 7 và CN)"""
        cal = calendar.monthcalendar(year, month)
        working_days = []
        today = datetime.now(hcm_tz).date()
        
        for week in cal:
            for day_idx, day in enumerate(week):
                # Bỏ qua ngày 0 (không tồn tại)
                if day == 0:
                    continue
                
                current_date = datetime(year, month, day).date()
                
                # Chỉ lấy thứ 2-6 (weekday 0-4), loại trừ thứ 7 (5) và CN (6)
                if current_date.weekday() > 4:  # 5 = Saturday, 6 = Sunday
                    continue
                
                # Chỉ tính ngày đã qua (hoặc bao gồm hôm nay nếu include_today=True)
                if include_today:
                    if current_date <= today:
                        working_days.append(current_date)
                else:
                    if current_date < today:
                        working_days.append(current_date)
        
        return working_days
    
    def _detect_holidays(self, working_days: List, df_checkin: pd.DataFrame) -> List:
        """Tự động phát hiện ngày nghỉ lễ dựa trên tỷ lệ chấm công thấp"""
        if df_checkin.empty:
            return []
        
        all_employees = df_checkin['employee_name'].nunique()
        if all_employees == 0:
            return []
        
        holidays = []
        for day in working_days:
            employees_present = df_checkin[
                df_checkin['checkin_date'].dt.date == day
            ]['employee_name'].nunique()
            
            # Nếu < 10% nhân viên có mặt thì coi như ngày nghỉ lễ
            if (employees_present / all_employees) <= 0.1:
                holidays.append(day)
        
        return holidays
    
    def _get_employee_timeoff_days(self, emp_name: str, working_days: List, 
                                   year: int, month: int) -> Dict:
        """Lấy chi tiết ngày nghỉ phép của nhân viên"""
        if self.df_timeoff.empty:
            return {'dates': [], 'total_days': 0, 'details': []}
        
        # Tìm tên tương tự trong timeoff data nếu không tìm thấy chính xác
        actual_timeoff_name = emp_name
        if not self.df_timeoff.empty:
            exact_match = self.df_timeoff[self.df_timeoff['employee_name'] == emp_name]
            if exact_match.empty:
                # Tìm tên tương tự
                unique_timeoff_names = self.df_timeoff['employee_name'].unique()
                emp_name_normalized = self._normalize_name(emp_name)
                
                for name in unique_timeoff_names:
                    name_normalized = self._normalize_name(name)
                    if (emp_name_normalized == name_normalized or
                        emp_name_normalized in name_normalized or 
                        name_normalized in emp_name_normalized):
                        actual_timeoff_name = name
                        break
        
        # Filter timeoff của nhân viên (sử dụng tên đã tìm được)
        emp_timeoff = self.df_timeoff[
            (self.df_timeoff['employee_name'] == actual_timeoff_name) &
            (self.df_timeoff['start_date'].dt.year == year) &
            (self.df_timeoff['start_date'].dt.month == month)
        ]
        
        timeoff_dates = []
        timeoff_details = []
        
        for _, row in emp_timeoff.iterrows():
            start_date = row['start_date'].date()
            end_date = row['end_date'].date()
            
            # Lấy các ngày trong khoảng timeoff
            current = start_date
            while current <= end_date:
                if current in working_days:
                    timeoff_dates.append(current)
                    timeoff_details.append({
                        'date': current,
                        'reason': row.get('ly_do', 'Không có lý do'),
                        'type': row.get('metatype', 'unknown'),
                        'state': row.get('state', 'unknown'),
                        'timeoff_id': row.get('id', '')
                    })
                current += timedelta(days=1)
        
        return {
            'dates': sorted(list(set(timeoff_dates))),
            'total_days': len(set(timeoff_dates)),
            'details': timeoff_details
        }
    
    def _analyze_daily_checkin(self, emp_name: str, date, df_checkin: pd.DataFrame) -> Dict:
        """Phân tích chi tiết chấm công trong 1 ngày"""
        date_checkin = df_checkin[
            (df_checkin['employee_name'] == emp_name) &
            (df_checkin['checkin_date'].dt.date == date)
        ].sort_values('checkin_datetime')
        
        if date_checkin.empty:
            return {
                'status': 'missing',
                'checkins': [],
                'first_checkin': None,
                'last_checkout': None,
                'is_late': False,
                'is_early_checkout': False,
                'total_records': 0,
                'working_hours': 0,
                'warnings': ['❌ Không có bản ghi chấm công']
            }
        
        warnings = []
        checkins = []
        
        # Tách checkin và checkout
        checkin_records = date_checkin[date_checkin['is_checkout'] == 0]
        checkout_records = date_checkin[date_checkin['is_checkout'] == 1]
        
        for _, record in date_checkin.iterrows():
            checkin_time = record['checkin_datetime']
            checkins.append({
                'time': checkin_time.strftime('%H:%M:%S'),
                'is_checkout': bool(record['is_checkout']),
                'note': record.get('note', '')
            })
        
        first_checkin = date_checkin.iloc[0]['checkin_datetime']
        last_checkin = date_checkin.iloc[-1]['checkin_datetime']
        
        # Tính số giờ làm việc: checkout - checkin - 1
        working_hours = 0
        if not checkin_records.empty and not checkout_records.empty:
            # Lấy checkin đầu tiên và checkout cuối cùng
            first_checkin_time = checkin_records.iloc[0]['checkin_datetime']
            last_checkout_time = checkout_records.iloc[-1]['checkin_datetime']
            
            # Tính số giờ: checkout - checkin - 1
            time_diff = last_checkout_time - first_checkin_time
            working_hours = max(0, time_diff.total_seconds() / 3600 - 1)
        
        # Phân loại check-in (Mới)
        # Early: < 8:00
        # Standard: 8:00 - 8:30
        # Late: > 8:30
        checkin_minutes = first_checkin.hour * 60 + first_checkin.minute
        checkin_status = 'standard'
        
        if checkin_minutes < 8 * 60:
            checkin_status = 'early'
        elif checkin_minutes > 8 * 60 + 30:
            checkin_status = 'late'
            
        # Kiểm tra đi trễ (sau 8:30) - Giữ logic cũ cho tương thích nhưng cập nhật biến
        is_late = (checkin_status == 'late')
        
        if is_late:
            warnings.append(f'⏰ Đi trễ: Check-in lúc {first_checkin.strftime("%H:%M")}')
        elif checkin_status == 'early':
             # Có thể thêm warning hoặc info nếu muốn, hiện tại giữ nguyên
             pass

        
        # Kiểm tra về sớm (trước 17:30)
        is_early_checkout = False
        if len(date_checkin) > 1:
            is_early_checkout = (last_checkin.hour < STANDARD_END_HOUR) or \
                                (last_checkin.hour == STANDARD_END_HOUR and last_checkin.minute < STANDARD_END_MINUTE)
            if is_early_checkout:
                warnings.append(f'🏃 Về sớm: Check-out lúc {last_checkin.strftime("%H:%M")}')
        else:
            warnings.append('⚠️ Chỉ có 1 lần chấm công (thiếu check-out)')
        
        # Kiểm tra số lần chấm công bất thường
        if len(date_checkin) > 4:
            warnings.append(f'❓ Số lần chấm công nhiều ({len(date_checkin)} lần)')
        
        return {
            'status': 'present',
            'checkins': checkins,
            'first_checkin': first_checkin.strftime('%H:%M:%S'),
            'last_checkout': last_checkin.strftime('%H:%M:%S') if len(date_checkin) > 1 else None,
            'is_late': is_late,
            'checkin_status': checkin_status, # Thêm trường này
            'is_early_checkout': is_early_checkout,
            'total_records': len(date_checkin),
            'working_hours': round(working_hours, 2),
            'warnings': warnings if warnings else ['✅ Bình thường']
        }

    
    def _get_since_by_employee_name(self, emp_name: str) -> str:
        """Lấy trường 'since' (timestamp) từ employee_name"""
        if not self.employee_manager:
            return ''
        
        # Tìm username từ mapping
        username = self.name_to_username_map.get(emp_name, '')
        if not username:
            return ''
        
        return self.employee_manager.get_since_by_username(username)
    
    def _convert_since_timestamp_to_date(self, since_timestamp: str) -> Optional[datetime]:
        """Chuyển đổi timestamp 'since' thành datetime để dễ so sánh"""
        if not since_timestamp or since_timestamp == '':
            return None
        
        try:
            timestamp = int(since_timestamp)
            return datetime.fromtimestamp(timestamp, tz=pytz.UTC).astimezone(pytz.timezone('Asia/Ho_Chi_Minh'))
        except (ValueError, TypeError, OSError):
            return None
    
    def _calculate_weekly_hours(self, daily_records: List[Dict], year: int, month: int) -> List[Dict]:
        """Tính tổng giờ làm việc theo tuần (không khuyết sang tháng khác)"""
        weekly_hours = []
        
        # Nhóm các ngày theo tuần
        weeks_dict = {}
        
        for record in daily_records:
            if record['status'] != 'present' or record.get('is_timeoff', False):
                continue
            
            date = record['date']
            working_hours = record.get('checkin_details', {}).get('working_hours', 0)
            
            # Xác định tuần (ISO week)
            week_num = date.isocalendar()[1]
            week_year = date.isocalendar()[0]
            
            # Chỉ tính tuần trong cùng tháng và năm
            if week_year == year and date.month == month:
                week_key = (week_year, week_num)
                
                if week_key not in weeks_dict:
                    # Tìm ngày đầu và cuối của tuần (thứ 2 đến chủ nhật)
                    monday = date - timedelta(days=date.weekday())
                    sunday = monday + timedelta(days=6)
                    
                    # Kiểm tra xem tuần có hoàn toàn trong tháng không
                    # Chỉ tính nếu cả tuần đều trong cùng tháng và năm
                    days_in_week = [monday + timedelta(days=i) for i in range(7)]
                    days_in_month = [d for d in days_in_week if d.year == year and d.month == month]
                    
                    # Chỉ tính nếu tuần có ít nhất 5 ngày trong tháng (để đảm bảo không khuyết quá nhiều)
                    if len(days_in_month) >= 5:
                        weeks_dict[week_key] = {
                            'week': week_num,
                            'year': week_year,
                            'start_date': min(days_in_month),
                            'end_date': max(days_in_month),
                            'days': [],
                            'total_hours': 0
                        }
                    else:
                        # Bỏ qua tuần này vì quá khuyết sang tháng khác
                        continue
                
                if week_key in weeks_dict:
                    weeks_dict[week_key]['days'].append({
                        'date': date,
                        'working_hours': working_hours
                    })
                    weeks_dict[week_key]['total_hours'] += working_hours
        
        # Chuyển đổi thành list và kiểm tra đủ 42 giờ
        for week_key, week_data in sorted(weeks_dict.items()):
            week_data['total_hours'] = round(week_data['total_hours'], 2)
            week_data['is_compliant'] = week_data['total_hours'] >= 42
            week_data['shortfall'] = max(0, 42 - week_data['total_hours'])
            weekly_hours.append(week_data)
        
        return weekly_hours
    
    def _normalize_name(self, name: str) -> str:
        """Chuẩn hóa tên để so sánh (bỏ dấu, lowercase, bỏ khoảng trắng)"""
        if not name:
            return ""
        # Bỏ dấu tiếng Việt
        nfd = unicodedata.normalize('NFD', name)
        no_diacritics = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
        return no_diacritics.lower().replace(' ', '')
    
    def _find_similar_name(self, emp_name: str) -> str:
        """Tìm tên tương tự trong dữ liệu checkin nếu không tìm thấy chính xác"""
        if self.df_checkin.empty:
            return emp_name
        
        # Kiểm tra tên chính xác trước
        exact_match = self.df_checkin[self.df_checkin['employee_name'] == emp_name]
        if not exact_match.empty:
            return emp_name
        
        # Tìm tên tương tự
        unique_names = self.df_checkin['employee_name'].unique()
        emp_name_normalized = self._normalize_name(emp_name)
        
        for name in unique_names:
            name_normalized = self._normalize_name(name)
            # So sánh sau khi normalize
            if (emp_name_normalized == name_normalized or
                emp_name_normalized in name_normalized or 
                name_normalized in emp_name_normalized):
                print(f"   💡 Tìm thấy tên tương tự trong checkin: '{name}' (thay vì '{emp_name}')")
                return name
        
        return emp_name
    
    def analyze_employee_detail(self, emp_name: str, year: int, month: int) -> Dict:
        """Phân tích chi tiết một nhân viên"""
        
        # Tìm tên tương tự nếu không tìm thấy chính xác
        actual_checkin_name = self._find_similar_name(emp_name)
        
        # Lấy ngày làm việc
        working_days = self._get_working_days(year, month, include_today=False)
        holidays = self._detect_holidays(working_days, self.df_checkin)
        actual_working_days = [d for d in working_days if d not in holidays]
        
        # Lọc checkin của nhân viên (sử dụng tên đã tìm được)
        emp_checkin = self.df_checkin[
            (self.df_checkin['employee_name'] == actual_checkin_name) &
            (self.df_checkin['checkin_date'].dt.year == year) &
            (self.df_checkin['checkin_date'].dt.month == month)
        ]
        
        # Lấy thông tin nghỉ phép (sử dụng tên gốc từ Account API)
        timeoff_info = self._get_employee_timeoff_days(emp_name, actual_working_days, year, month)
        
        # Lấy trường 'since' (ngày vào làm) - thử cả hai tên
        since_timestamp = self._get_since_by_employee_name(emp_name)
        if not since_timestamp:
            # Thử với tên trong checkin data
            since_timestamp = self._get_since_by_employee_name(actual_checkin_name)
        since_date = self._convert_since_timestamp_to_date(since_timestamp)
        
        # Phân tích từng ngày
        daily_records = []
        days_with_checkin = set()
        late_count = 0
        early_checkout_count = 0
        missing_days = []
        total_working_hours = 0
        
        for day in actual_working_days:
            # Bỏ qua các ngày trước ngày vào làm
            if since_date and day < since_date.date():
                continue
            
            # Sử dụng tên trong checkin data để phân tích
            day_analysis = self._analyze_daily_checkin(actual_checkin_name, day, emp_checkin)
            
            # Kiểm tra xem ngày này có nghỉ phép không
            is_timeoff = day in timeoff_info['dates']
            timeoff_detail = None
            if is_timeoff:
                timeoff_detail = next((x for x in timeoff_info['details'] if x['date'] == day), None)
            
            # Xác định status
            if is_timeoff:
                day_analysis['status'] = 'timeoff'
                day_analysis['timeoff_reason'] = timeoff_detail['reason'] if timeoff_detail else 'Nghỉ phép'
                day_analysis['timeoff_state'] = timeoff_detail.get('state', '')
            elif day_analysis['status'] == 'present':
                days_with_checkin.add(day)
                if day_analysis['is_late']:
                    late_count += 1
                if day_analysis['is_early_checkout']:
                    early_checkout_count += 1
                # Cộng tổng giờ làm việc
                total_working_hours += day_analysis.get('working_hours', 0)
            else:
                missing_days.append(day)
            
            daily_records.append({
                'date': day,
                'date_str': day.strftime('%d/%m/%Y'),
                'weekday': day.strftime('%A'),
                'status': day_analysis['status'],
                'is_timeoff': is_timeoff,
                'timeoff_reason': timeoff_detail['reason'] if timeoff_detail else None,
                'checkin_details': day_analysis,
                'day_type': 'Nghỉ phép' if is_timeoff else ('Có mặt' if day_analysis['status'] == 'present' else 'Vắng')
            })
        
        # Tính tổng giờ làm việc theo tuần
        weekly_hours = self._calculate_weekly_hours(daily_records, year, month)
        
        # Kiểm tra các tuần không đủ 42 giờ
        non_compliant_weeks = [w for w in weekly_hours if not w['is_compliant']]
        
        # Tính toán thống kê
        total_working_days = len(actual_working_days)
        days_present = len(days_with_checkin)
        days_timeoff = timeoff_info['total_days']
        days_missing = len(missing_days)
        
        # Attendance rates
        attendance_rate = (days_present / total_working_days * 100) if total_working_days > 0 else 0
        adjusted_working_days = total_working_days - days_timeoff
        adjusted_attendance_rate = (days_present / adjusted_working_days * 100) if adjusted_working_days > 0 else 100
        
        # Cảnh báo
        warnings = []
        if days_missing > 0:
            warnings.append(f'⚠️ Thiếu {days_missing} ngày công chưa giải trình')
        if late_count > 3:
            warnings.append(f'⏰ Đi trễ {late_count} lần trong tháng')
        if early_checkout_count > 3:
            warnings.append(f'🏃 Về sớm {early_checkout_count} lần trong tháng')
        if adjusted_attendance_rate < 85:
            warnings.append(f'📉 Tỷ lệ chuyên cần thấp: {adjusted_attendance_rate:.1f}%')
        
        # Cảnh báo về tuần không đủ 42 giờ
        if non_compliant_weeks:
            for week in non_compliant_weeks:
                warnings.append(f'⚠️ Tuần {week["week"]} không đủ 42 giờ: {week["total_hours"]}h (thiếu {week["shortfall"]:.2f}h)')
        
        # Gợi ý hành động
        action_required = []
        if days_missing > 0:
            action_required.append(f'📝 Cần bù công hoặc giải trình cho {days_missing} ngày: ' + 
                                 ', '.join([d.strftime('%d/%m') for d in missing_days]))
        if late_count > 5:
            action_required.append('⚠️ Cần cải thiện giờ giấc đến công ty')
        if non_compliant_weeks:
            action_required.append(f'⚠️ Cần đảm bảo đủ 42 giờ/tuần cho {len(non_compliant_weeks)} tuần')
        
        return {
            'employee_name': emp_name,  # Giữ tên gốc từ input
            'actual_checkin_name': actual_checkin_name,  # Tên thực tế trong checkin data
            'since': since_timestamp,
            'since_date': since_date.strftime('%d/%m/%Y') if since_date else None,
            'period': {
                'year': year,
                'month': month,
                'month_name': calendar.month_name[month]
            },
            'summary': {
                'total_working_days': total_working_days,
                'days_present': days_present,
                'days_timeoff': days_timeoff,
                'days_missing': days_missing,
                'days_with_issues': late_count + early_checkout_count,
                'late_count': late_count,
                'early_checkout_count': early_checkout_count,
                'attendance_rate': round(attendance_rate, 2),
                'adjusted_attendance_rate': round(adjusted_attendance_rate, 2),
                'total_working_hours': round(total_working_hours, 2),
                'weekly_hours': weekly_hours,
                'non_compliant_weeks_count': len(non_compliant_weeks)
            },
            'daily_records': daily_records,
            'missing_dates': [d.strftime('%d/%m/%Y') for d in missing_days],
            'timeoff_dates': [d.strftime('%d/%m/%Y') for d in timeoff_info['dates']],
            'warnings': warnings,
            'action_required': action_required,
            'evaluation': self._evaluate_performance(adjusted_attendance_rate, late_count, days_missing)
        }
    
    def _evaluate_performance(self, attendance_rate: float, late_count: int, missing_days: int) -> str:
        """Đánh giá hiệu suất"""
        if attendance_rate >= 95 and late_count == 0 and missing_days == 0:
            return '⭐ Xuất sắc - Hoàn hảo'
        elif attendance_rate >= 90 and late_count <= 2 and missing_days <= 1:
            return '✅ Tốt - Đạt yêu cầu'
        elif attendance_rate >= 80 and late_count <= 5 and missing_days <= 3:
            return '⚠️ Trung bình - Cần chú ý'
        else:
            return '❌ Kém - Cần cải thiện ngay'
    
    def generate_all_employees_report(self, year: int, month: int) -> List[Dict]:
        """Tạo báo cáo cho tất cả nhân viên"""
        if self.df_checkin.empty:
            print("❌ Không có dữ liệu checkin")
            return []
        
        all_employees = sorted(self.df_checkin['employee_name'].unique())
        reports = []
        
        print(f"\n🔄 Đang phân tích {len(all_employees)} nhân viên...")
        
        for idx, emp_name in enumerate(all_employees, 1):
            print(f"  [{idx}/{len(all_employees)}] Phân tích: {emp_name}")
            report = self.analyze_employee_detail(emp_name, year, month)
            reports.append(report)
        
        return reports
    
    def export_to_json(self, reports: List[Dict], filename: str):
        """Xuất báo cáo ra file JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(reports, f, ensure_ascii=False, indent=2, default=str)
        print(f"✅ Đã xuất báo cáo ra file: {filename}")
    
    def export_to_csv(self, reports: List[Dict], filename: str):
        """Xuất báo cáo tổng hợp ra CSV"""
        data = []
        for report in reports:
            weekly_info = []
            if report['summary'].get('weekly_hours'):
                for week in report['summary']['weekly_hours']:
                    weekly_info.append(f"Week {week['week']}: {week['total_hours']:.2f}h ({'✅' if week['is_compliant'] else '❌'})")
            
            data.append({
                'Nhân viên': report['employee_name'],
                'Since (timestamp)': report.get('since', ''),
                'Since (ngày)': report.get('since_date', ''),
                'Tháng': f"{report['period']['month']}/{report['period']['year']}",
                'Tổng ngày LV': report['summary']['total_working_days'],
                'Ngày có mặt': report['summary']['days_present'],
                'Ngày nghỉ phép': report['summary']['days_timeoff'],
                'Ngày vắng': report['summary']['days_missing'],
                'Đi trễ': report['summary']['late_count'],
                'Về sớm': report['summary']['early_checkout_count'],
                'Tổng giờ làm việc': report['summary'].get('total_working_hours', 0),
                'Số tuần không đủ 42h': report['summary'].get('non_compliant_weeks_count', 0),
                'Attendance (%)': report['summary']['attendance_rate'],
                'Attendance điều chỉnh (%)': report['summary']['adjusted_attendance_rate'],
                'Đánh giá': report['evaluation'],
                'Ngày vắng chi tiết': ', '.join(report['missing_dates']),
                'Ngày nghỉ phép chi tiết': ', '.join(report['timeoff_dates']),
                'Thống kê theo tuần': ' | '.join(weekly_info)
            })
        
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"✅ Đã xuất báo cáo tổng hợp ra file: {filename}")


def calculate_daily_working_hours(checkin_time, checkout_time):
    """Tính số giờ làm việc trong ngày dựa trên checkin/checkout"""
    if not checkin_time or not checkout_time:
        return 0
    
    # Logic tính toán (giả định nghỉ trưa 1 tiếng nếu làm cả ngày)
    # Nếu checkin sáng và checkout chiều -> trừ 1h nghỉ trưa
    # Nếu chỉ làm sáng hoặc chỉ làm chiều -> không trừ
    
    start = checkin_time
    end = checkout_time
    
    # Đặt mốc thời gian nghỉ trưa
    noon_start = start.replace(hour=12, minute=0, second=0)
    noon_end = start.replace(hour=13, minute=0, second=0)
    
    duration = (end - start).total_seconds() / 3600
    
    # Nếu thời gian làm việc bao trùm giờ nghỉ trưa thì trừ đi 1 tiếng
    if start < noon_start and end > noon_end:
        duration -= 1
        
    return max(0, duration)

def calculate_weekly_hours_from_checkin(checkin_data, employee_name, start_date, end_date):
    """
    Tính tổng số giờ làm việc trong tuần từ dữ liệu checkin
    Lưu ý: Logic này tương tự DetailedAttendanceAnalyzer._calculate_weekly_hours 
    nhưng được viết lại để dùng độc lập nếu cần.
    Trong thực tế, nên dùng DetailedAttendanceAnalyzer để đồng nhất logic.
    Hàm này giữ lại để tương thích với các đoạn code cũ nếu có.
    """
    if checkin_data.empty:
        return 0, []

    # Filter data for employee and date range
    mask = (checkin_data['employee_name'] == employee_name) & \
           (checkin_data['checkin_date'] >= pd.Timestamp(start_date)) & \
           (checkin_data['checkin_date'] <= pd.Timestamp(end_date))
    emp_data = checkin_data[mask]
    
    if emp_data.empty:
        # Thử tìm tên tương tự
        def normalize_name(name):
            if not isinstance(name, str): return ""
            nfd = unicodedata.normalize('NFD', name)
            return "".join(c for c in nfd if unicodedata.category(c) != 'Mn').lower().replace(" ", "")

        norm_name = normalize_name(employee_name)
        unique_names = checkin_data['employee_name'].unique()
        found_name = None
        for name in unique_names:
            if normalize_name(name) == norm_name:
                found_name = name
                break
        
        if found_name:
            mask = (checkin_data['employee_name'] == found_name) & \
                   (checkin_data['checkin_date'] >= pd.Timestamp(start_date)) & \
                   (checkin_data['checkin_date'] <= pd.Timestamp(end_date))
            emp_data = checkin_data[mask]
    
    if emp_data.empty:
        return 0, []

    total_hours = 0
    daily_details = []
    
    # Group by date
    for date, group in emp_data.groupby(emp_data['checkin_date'].dt.date):
        # Lấy checkin đầu và checkout cuối
        checkins = group[group['is_checkout'] == 0]['checkin_datetime']
        checkouts = group[group['is_checkout'] == 1]['checkin_datetime']
        
        daily_hours = 0
        if not checkins.empty and not checkouts.empty:
             first_in = checkins.min()
             last_out = checkouts.max()
             daily_hours = calculate_daily_working_hours(first_in, last_out)
        
        total_hours += daily_hours
        daily_details.append({
            'date': date,
            'hours': daily_hours
        })
            
    return total_hours, daily_details

def timestamp_to_hcm(ts):
    """Chuyển timestamp/string sang string format HCM"""
    if not ts or str(ts) == '0':
        return 'N/A'
    try:
        dt = datetime.fromtimestamp(int(ts), hcm_tz)
        return dt.strftime('%d/%m/%Y %H:%M')
    except:
        return 'N/A'

def get_checkin_data(employee_name, year, month):
    """Lấy và phân tích dữ liệu checkin"""
    try:
        print(f"🔄 Đang tải dữ liệu Checkin/Timeoff cho {employee_name} ({month}/{year})...")
        
        # 1. Load data
        checkin_loader = CheckinLoader(CHECKIN_TOKEN)
        # Lấy range cả tháng
        start_date = datetime(year, month, 1, 0, 0, 0, tzinfo=hcm_tz)
        _, last_day = calendar.monthrange(year, month)
        end_date = datetime(year, month, last_day, 23, 59, 59, tzinfo=hcm_tz)
        
        df_checkin = checkin_loader.load_checkin_data(start_date, end_date)
        
        timeoff_processor = TimeoffProcessor(TIMEOFF_TOKEN, ACCOUNT_TOKEN)
        # Payload cho timeoff
        timeoff_start_str = start_date.strftime('%Y-%m-%d')
        timeoff_end_str = end_date.strftime('%Y-%m-%d')
        # API timeoff cần start_date_from/to
        # Lưu ý: check lại TimeoffProcessor.get_base_timeoff_data arguments
        # Nó mapping: start_date_from -> payload['start_date_from']
        raw_timeoff = timeoff_processor.get_base_timeoff_data(
            start_date_from=timeoff_start_str,
            end_date_to=timeoff_end_str
        )
        df_timeoff = timeoff_processor.extract_timeoff_to_dataframe(raw_timeoff)
        
        employee_manager = EmployeeManager(ACCOUNT_TOKEN)
        
        # 2. Analyze
        analyzer = DetailedAttendanceAnalyzer(df_checkin, df_timeoff, employee_manager)
        report = analyzer.analyze_employee_detail(employee_name, year, month)
        
        if not report:
            print("⚠️ Không thể tạo báo cáo chi tiết.")
            return None
            
        print(f"📊 Kết quả chấm công tháng {month}/{year}:")
        print(f"   - Tổng công: {report['summary']['days_present']}/{report['summary']['total_working_days']} ngày")
        print(f"   - Tỷ lệ chuyên cần: {report['summary']['attendance_rate']}% (Điều chỉnh: {report['summary']['adjusted_attendance_rate']}%)")
        print(f"   - Đi trễ: {report['summary']['late_count']} lần")
        print(f"   - Về sớm: {report['summary']['early_checkout_count']} lần")
        print(f"   - Nghỉ phép: {report['summary']['days_timeoff']} ngày")
        print(f"   - Không phép: {report['summary']['days_missing']} ngày")
        print(f"   - Đánh giá: {report['evaluation']}")

        # Validate checkin for current week/period for Goal alignment
        # Logic này để trả về dữ liệu cho phần Goal Integration
        # Lấy danh sách checkin trong tuần hiện tại hoặc gần nhất
        last_checkin_str = 'N/A'
        checkin_count_period = 0
        if report['daily_records']:
            # Sort by date desc
            sorted_recs = sorted(report['daily_records'], key=lambda x: x['date'], reverse=True)
            # Find last checkin
            for rec in sorted_recs:
                if rec['status'] == 'present':
                    last_checkin_str = rec['date_str'] + " " + rec['checkin_details'].get('first_checkin', '')
                    break
            
            # Count checkin in current week? 
            # Giả sử period ở đây là "tuần này" cho mục đích OKR
            # report đang là MONTHLY.
            # Lấy today
            today = datetime.now(hcm_tz).date()
            start_week = today - timedelta(days=today.weekday())
            end_week = start_week + timedelta(days=6)
            
            checkin_count_period = sum(1 for rec in report['daily_records'] 
                                      if rec['status'] == 'present' and 
                                      start_week <= rec['date'] <= end_week)

        raw_df_records = {
            "checkin": df_checkin.astype(str).to_dict(orient="records") if df_checkin is not None else [],
            "timeoff": df_timeoff.astype(str).to_dict(orient="records") if df_timeoff is not None else []
        }

        return {
            'summary': report['summary'],
            'period': report['period'],
            'daily_records': report['daily_records'],
            'evaluation': report['evaluation'],
            'checkin_count_monthly': report['summary']['days_present'], # Tổng công tháng
            'checkin_count_period': checkin_count_period, # Công tuần này (approx)
            'last_checkin': last_checkin_str,
            'late_count': report['summary']['late_count'],
            'missing_days': report['summary']['days_missing'],
            'raw_df_records': raw_df_records
        }
            
    except Exception as e:
        print(f"❌ Lỗi khi lấy dữ liệu Checkin: {e}")
        import traceback
        traceback.print_exc()
        return None

