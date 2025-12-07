import requests
import json
import smtplib
import unicodedata
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import pytz
from ollama import Client
import traceback
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import modules
from checkin_timeoff import get_checkin_data
from wework import get_wework_data, WeWorkAPIClient
from goal import get_goal_data
from inside import get_inside_data
from workflow import get_workflow_data

# ============================================================================
# CẤU HÌNH (CONSTANTS)
# ============================================================================
EMAIL_GUI = os.getenv('EMAIL_GUI')
MAT_KHAU = os.getenv('MAT_KHAU')  # Mật khẩu ứng dụng
# EMAIL_NHAN = "info@apluscorp.vn"
EMAIL_NHAN = "tts122403@gmail.com"

# API TOKENS (Cần thiết cho app.py để tìm kiếm nhân viên)
WEWORK_ACCESS_TOKEN = os.getenv('WEWORK_ACCESS_TOKEN')
ACCOUNT_ACCESS_TOKEN = os.getenv('ACCOUNT_ACCESS_TOKEN')

DEFAULT_EMPLOYEE_NAME = "Phạm Thanh Tùng"
hcm_tz = pytz.timezone('Asia/Ho_Chi_Minh')

# Global variable for user mapping
user_id_to_name_map = {}

def load_user_mapping():
    """Tải user mapping từ Account API và lưu vào biến global"""
    global user_id_to_name_map
    try:
        url = "https://account.base.vn/extapi/v1/users/get_list"
        payload = {
            'access_token': ACCOUNT_ACCESS_TOKEN
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
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

def get_ai_insight(context_text):
    """
    Generate a short, encouraging insight using AI based on the provided context.
    """
    try:
        client = Client()
        prompt = f"""
        Bạn là một trợ lý ảo phân tích hiệu suất làm việc. Dựa vào dữ liệu sau đây, hãy viết một câu nhận xét ngắn gọn (tối đa 2 câu), mang tính khích lệ hoặc cảnh báo nhẹ nhàng, hữu ích cho nhân viên.
        Dữ liệu: {context_text}
        Nhận xét:
        """
        response = client.generate(model='gpt-oss:120b-cloud', prompt=prompt)
        insight = response.get('response', '').strip()
        
        # Tiền xử lý insight để loại bỏ dấu ngoặc kép nếu có
        insight = insight.replace('"', '').replace("'", "")
        return insight
    except Exception as e:
        # print(f"Lỗi AI Insight: {e}")
        return "Hãy tiếp tục cố gắng để duy trì và cải thiện hiệu suất!"

# ============================================================================
# HÀM TẠO HTML EMAIL (GIAO DIỆN MỚI "ĐẸP HƠN")
# ============================================================================
def create_email_html(employee_name, checkin_data, wework_data, goal_data, inside_data, workflow_data):
    """Tạo nội dung HTML email với giao diện được cải thiện"""
    
    current_time_str = datetime.now(hcm_tz).strftime('%d/%m/%Y %H:%M:%S')

    # --- 1. Xử lý section GOAL (NÂNG CẤP INSIGHT) ---
    if goal_data and goal_data.get('weekly'):
        weekly = goal_data['weekly']
        behavior = goal_data.get('checkin_behavior', {}) or {}
        overall = goal_data.get('overall_behavior', {}) or {}
        
        # Tính toán Insight
        shift_val = weekly.get('okr_shift', 0)
        checkin_count = behavior.get('checkin_count_period', 0)
        checkin_freq = overall.get('checkin_frequency_per_week', 0)
        
        # Đánh giá định tính
        if shift_val > 0:
            trend_icon = "📈"
            trend_text = "Tăng trưởng tích cực"
            trend_color = "#155724" # Green
        elif shift_val < 0:
            trend_icon = "📉"
            trend_text = "Đang bị trượt mục tiêu"
            trend_color = "#dc3545" # Red
        else:
            trend_icon = "➖"
            trend_text = "Không có biến động"
            trend_color = "#856404" # Yellow
            
        # Đánh giá kỷ luật
        if checkin_count >= 2:
            discipline_text = "Kỷ luật Tốt (Duy trì đều đặn)"
        elif checkin_count == 1:
            discipline_text = "Cần cải thiện tần suất"
        else:
            discipline_text = "Cảnh báo: Thiếu tương tác hệ thống"

        # Tạo HTML cho danh sách goals
        goals_html = ""
        goals_list = goal_data.get('goals_list', [])
        if goals_list:
            goals_html += '<div style="margin-top: 15px; border-top: 1px dashed #ccc; padding-top: 10px;">'
            goals_html += '<div style="font-weight: 600; margin-bottom: 8px;">📋 Chi tiết Mục tiêu & Tốc độ:</div>'
            goals_html += '<table style="width: 100%; border-collapse: collapse; font-size: 13px;">'
            goals_html += '<tr style="background-color: #f0f0f0; text-align: left;">'
            goals_html += '<th style="padding: 5px; border: 1px solid #ddd;">Mục tiêu</th>'
            goals_html += '<th style="padding: 5px; border: 1px solid #ddd; width: 80px;">Tiến độ</th>'
            goals_html += '<th style="padding: 5px; border: 1px solid #ddd; width: 80px;">Tốc độ</th>'
            goals_html += '</tr>'
            
            for goal in goals_list:
                g_name = goal['name']
                g_val = goal['current_value']
                g_speed = goal['speed']
                
                # Xác định màu sắc dựa trên tốc độ
                if g_speed >= 1.0:
                    speed_color = "#155724" # Green
                    speed_bg = "#d4edda"
                    speed_text = "Tốt"
                elif g_speed >= 0.5:
                    speed_color = "#856404" # Yellow
                    speed_bg = "#fff3cd"
                    speed_text = "Khá"
                else:
                    speed_color = "#721c24" # Red
                    speed_bg = "#f8d7da"
                    speed_text = "Chậm"
                
                goals_html += f'<tr>'
                goals_html += f'<td style="padding: 5px; border: 1px solid #ddd;">{g_name}</td>'
                goals_html += f'<td style="padding: 5px; border: 1px solid #ddd; text-align: center;">{g_val:.1f}%</td>'
                goals_html += f'<td style="padding: 5px; border: 1px solid #ddd; text-align: center; background-color: {speed_bg}; color: {speed_color}; font-weight: bold;">{g_speed:.2f} ({speed_text})</td>'
                goals_html += f'</tr>'
            
            goals_html += '</table>'
            goals_html += '</div>'

        goal_content_box = f"""
        <div class="stats-box success-box"> 
            <div class="sub-header">🎯 Hiệu suất & Kỷ luật OKR:</div>
            <ul class="stat-list">
                <li><strong>Biến động tuần qua:</strong> <span style="color: {trend_color}; font-weight: bold;">{trend_icon} {shift_val:+.2f}% ({trend_text})</span></li>
                <li><strong>Kết quả hiện tại:</strong> {weekly['current_value']:.2f}% (Tuần trước: {weekly['last_friday_value']:.2f}%)</li>
                <li style="margin-top: 10px; border-top: 1px dashed #ccc; padding-top: 5px;"><strong>🔍 Phân tích hành vi (Integrity):</strong></li>
                <li>• Số lần Check-in trong kỳ: <strong>{checkin_count} lần</strong> - <em>{discipline_text}</em></li>
                <li>• Tần suất trung bình: <strong>{checkin_freq:.1f} lần/tuần</strong></li>
                <li>• Lần check-in cuối: <strong>{behavior.get('last_checkin_period', 'N/A')}</strong></li>
            </ul>
            {goals_html}
            <div class="evaluation-section" style="background-color: #fff; border: 1px solid #e0e0e0; margin-top:10px;">
                💡 <em>Insight (AI): {get_ai_insight(f"Goal OKR: Biến động {shift_val}%, Check-in {checkin_count} lần ({discipline_text}). Tốc độ hoàn thành mục tiêu trung bình: {sum(g['speed'] for g in goals_list)/len(goals_list) if goals_list else 0:.2f}.")}</em>
            </div>
        </div>
        """
    else:
        goal_content_box = """
        <div class="stats-box warning-box">
            <div class="sub-header">🚨 Cảnh báo OKR:</div>
            <ul class="stat-list warning-list">
                <li>❌ Hệ thống ghi nhận bạn <strong>chưa thiết lập OKR</strong> hoặc dữ liệu chưa đồng bộ.</li>
                <li>👉 Hành động ngay: Vui lòng review lại OKR cá nhân trên Base Goal.</li>
            </ul>
        </div>
        """
    # --- 2. Xử lý section WEWORK (NÂNG CẤP: BẮT LỖI KHÔNG DEADLINE & QUÁ HẠN) ---
    if wework_data:
        # Check flag warning
        if wework_data.get('is_warning_only'):
            wework_content_box = """
            <div class="stats-box warning-box">
                <div style="font-weight: bold; font-size: 16px; margin-bottom: 5px;">⚠️ Cần lưu ý:</div>
                <div>Hệ thống không ghi nhận hoạt động nào trên WeWork trong 1 tháng qua.</div>
                <div style="margin-top: 5px; font-size: 13px;">Hãy rà soát lại các công việc và cập nhật tiến độ ngay nhé!</div>
            </div>
            """
        else:
            s = wework_data['summary']
            stats_ext = wework_data.get('stats_extended', {})
        
            # Lấy số liệu mới
            completed_late = stats_ext.get('completed_late_count', 0)
            no_deadline = stats_ext.get('no_deadline_count', 0)
            overdue_tasks = stats_ext.get('overdue_tasks', [])
            upcoming_tasks = stats_ext.get('upcoming_deadline_tasks', [])
            
            # 1. Tạo HTML cho Upcoming Deadlines (Sắp đến hạn)
            upcoming_html = ""
            if upcoming_tasks:
                upcoming_list_items = ""
                for t in upcoming_tasks[:5]: # Limit 5
                    # Assuming 'deadline' is a timestamp and 'since' is also a timestamp
                    # Calculate days left based on deadline
                    deadline_ts = t.get('deadline')
                    days = 0
                    if deadline_ts:
                        try:
                            # Chú ý: deadline_ts có thể là string hoặc float/int
                            deadline_date = datetime.fromtimestamp(float(deadline_ts), hcm_tz)
                            today = datetime.now(hcm_tz)
                            delta = deadline_date - today
                            days = delta.days
                            if days < 0: # If deadline is in the past, but it's an upcoming task, it means it's very recent past or today
                                days = 0
                        except:
                            pass # Keep days as 0 if conversion fails
                    
                    day_str = "Hôm nay" if days == 0 else f"{days} ngày nữa"
                    upcoming_list_items += f"<div>• <span style='color:#e65100; font-weight:600;'>{t.get('name')}</span> ({day_str})</div>"
                
                upcoming_html = f"""
                <li style="margin-top: 10px; background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 3px solid #ffc107;">
                    <strong>⚠️ Sắp đến hạn (7 ngày tới):</strong>
                    <div style="font-size: 13px; margin-top: 4px;">{upcoming_list_items}</div>
                </li>
                """
                
            # 2. Tạo bảng Overdue Tasks (Quá hạn)
            overdue_table_html = ""
            if overdue_tasks:
                overdue_table_html += '<div style="margin-top: 15px; border-top: 1px dashed #ef9a9a; padding-top: 10px;">'
                overdue_table_html += '<div style="font-weight: 600; margin-bottom: 8px; color: #c62828;">🚨 Công việc QUÁ HẠN (Cần xử lý ngay):</div>'
                overdue_table_html += '<table style="width: 100%; border-collapse: collapse; font-size: 13px;">'
                overdue_table_html += '<tr style="background-color: #ffebee; text-align: left;">'
                overdue_table_html += '<th style="padding: 6px; border: 1px solid #ffcdd2;">Công việc / Dự án</th>'
                overdue_table_html += '<th style="padding: 6px; border: 1px solid #ffcdd2; width: 80px;">Ngày tạo</th>'
                overdue_table_html += '<th style="padding: 6px; border: 1px solid #ffcdd2; width: 90px;">Deadline</th>'
                overdue_table_html += '</tr>'
                
                for task in overdue_tasks[:10]: # Limit 10
                    t_name = task.get('name', 'No Name')
                    p_name = task.get('project_name', 'Unknown Project')
                    
                    # Ngày tạo
                    since_ts = task.get('since')
                    created_date = "N/A"
                    if since_ts:
                        try:
                            created_date = datetime.fromtimestamp(int(since_ts), hcm_tz).strftime('%d/%m')
                        except: pass
                        
                    # Deadline (chắc chắn là quá hạn rồi)
                    deadline_ts = task.get('deadline')
                    try:
                        deadline_date = datetime.fromtimestamp(int(deadline_ts), hcm_tz)
                        deadline_str = deadline_date.strftime('%d/%m')
                    except:
                        deadline_str = "Lỗi"
                    
                    overdue_table_html += f'<tr>'
                    overdue_table_html += f'<td style="padding: 6px; border: 1px solid #ffcdd2;">'
                    overdue_table_html += f'<div style="font-weight: 600; color: #333;">{t_name}</div>'
                    overdue_table_html += f'<div style="font-size: 11px; color: #666;">📂 {p_name}</div>'
                    overdue_table_html += f'</td>'
                    overdue_table_html += f'<td style="padding: 6px; border: 1px solid #ffcdd2; text-align: center;">{created_date}</td>'
                    overdue_table_html += f'<td style="padding: 6px; border: 1px solid #ffcdd2; text-align: center; color: #c62828; font-weight: bold;">{deadline_str}</td>'
                    overdue_table_html += f'</tr>'
                
                overdue_table_html += '</table>'
                overdue_table_html += '</div>'

            recent_tasks_html = ""

            wework_content_box = f"""
            <div class="stats-box wework-box">
                <div class="sub-header">📊 Quản trị công việc & Rủi ro (1 tháng gần nhất):</div>
                <ul class="stat-list">
                    <li>📋 Tổng quan: <strong>{s['total_tasks']} task</strong> (Done: {s['completion_rate']:.1f}%)</li>
                    <li>⚡ Tốc độ: <strong>{s['on_time_rate']:.1f}%</strong> công việc hoàn thành đúng hạn.</li>
                    <li>🐢 Hoàn thành muộn: <strong>{completed_late} task</strong></li>
                    <li>⚠️ Không Deadline: <strong>{no_deadline} task</strong></li>
                    {upcoming_html}
                </ul>
                {overdue_table_html}
                {recent_tasks_html}
                <div class="evaluation-section" style="background-color: #fff; border: 1px solid #e0e0e0; margin-top:10px;">
                     💡 <em>Insight (AI): {get_ai_insight(f"WeWork: Hoàn thành {s['completion_rate']:.1f}%, Đúng hạn {s['on_time_rate']:.1f}%. Trễ {completed_late} task, Quá hạn {len(overdue_tasks)} task.")}</em>
                </div>
            </div>
            """
    else:
        wework_content_box = """<div class="stats-box wework-box"><p><em>Chưa có dữ liệu công việc để phân tích.</em></p></div>"""


    # --- 3. Xử lý section CHECKIN (THAY THẾ 42H BẰNG PHÂN TÍCH THÓI QUEN) ---
    if checkin_data:
        s = checkin_data['summary']
        p = checkin_data['period']
        daily_records = checkin_data.get('daily_records', [])
        
        # 1. Phân tích Thói quen Check-in (Arrival Habits)
        early_arrival = 0 # Trước 8:00
        standard_arrival = 0 # 8:00 - 8:30
        late_arrival = 0 # Sau 8:30
        
        total_checkin_minutes = 0
        valid_checkin_count = 0
        
        # Thống kê theo thứ trong tuần để tìm "Ngày làm việc hiệu quả nhất"
        weekday_hours = {0: [], 1: [], 2: [], 3: [], 4: [], 5: [], 6: []} # 0 is Monday
        weekday_names = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "CN"]
        
        for r in daily_records:
            if r['status'] == 'present':
                # Phân tích giờ đến
                first_ci = r['checkin_details'].get('first_checkin') # String "HH:MM:SS"
                if first_ci:
                    h, m, _ = map(int, first_ci.split(':'))
                    total_minutes = h * 60 + m
                    total_checkin_minutes += total_minutes
                    valid_checkin_count += 1
                    
                    # Sử dụng checkin_status đã được tính toán từ checkin.py
                    c_status = r['checkin_details'].get('checkin_status', 'standard')
                    
                    if c_status == 'early':
                        early_arrival += 1
                    elif c_status == 'late':
                        late_arrival += 1
                    else:
                        standard_arrival += 1
                
                # Phân tích giờ làm theo thứ
                w_hours = r['checkin_details'].get('working_hours', 0)
                if w_hours > 0:
                    weekday = r['date'].weekday()
                    weekday_hours[weekday].append(w_hours)

        # Tính giờ check-in trung bình
        avg_checkin_str = "N/A"
        if valid_checkin_count > 0:
            avg_minutes = total_checkin_minutes / valid_checkin_count
            avg_h = int(avg_minutes // 60)
            avg_m = int(avg_minutes % 60)
            avg_checkin_str = f"{avg_h:02d}:{avg_m:02d}"

        # Tìm ngày làm việc năng suất nhất (Trung bình giờ làm cao nhất)
        best_weekday = "N/A"
        max_avg_hours = 0
        for w_idx, hours_list in weekday_hours.items():
            if hours_list:
                avg_h = sum(hours_list) / len(hours_list)
                if avg_h > max_avg_hours:
                    max_avg_hours = avg_h
                    best_weekday = weekday_names[w_idx]

        # Xác định "Phong cách" (Archetype)
        if valid_checkin_count > 0:
            if early_arrival > (standard_arrival + late_arrival):
                style_tag = "🌅 Early Bird (Đến sớm)"
                style_msg = "Bạn thích bắt đầu ngày mới sớm để có sự tĩnh lặng tập trung."
                style_color = "#28a745"
            elif late_arrival > 3:
                style_tag = "⚠️ Late Start (Đến trễ)"
                style_msg = "Giờ bắt đầu ngày làm việc của bạn đang bị trễ nhịp so với quy định."
                style_color = "#dc3545"
            else:
                style_tag = "⏰ Punctual (Đúng giờ)"
                style_msg = "Bạn có thói quen tuân thủ giờ giấc rất ổn định."
                style_color = "#17a2b8"
        else:
            style_tag = "Unknown"
            style_msg = "Chưa đủ dữ liệu."
            style_color = "#6c757d"

        # Tạo Visual Bar cho thói quen check-in
        total_days = early_arrival + standard_arrival + late_arrival
        if total_days > 0:
            p_early = (early_arrival / total_days) * 100
            p_std = (standard_arrival / total_days) * 100
            p_late = (late_arrival / total_days) * 100
        else:
            p_early = p_std = p_late = 0

        habit_bar_html = f"""
        <div style="display: flex; height: 12px; width: 100%; background: #eee; border-radius: 6px; overflow: hidden; margin-top: 8px;">
            <div style="width: {p_early}%; background: #28a745;" title="Đến sớm"></div>
            <div style="width: {p_std}%; background: #17a2b8;" title="Đúng giờ"></div>
            <div style="width: {p_late}%; background: #dc3545;" title="Đi trễ"></div>
        </div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; color: #666; margin-top: 4px;">
            <span><span style="color:#28a745">●</span> Sớm ({early_arrival})</span>
            <span><span style="color:#17a2b8">●</span> Chuẩn ({standard_arrival})</span>
            <span><span style="color:#dc3545">●</span> Trễ ({late_arrival})</span>
        </div>
        """

        checkin_content_box = f"""
        <div class="stats-box checkin-box">
            <div class="sub-header" style="display: flex; justify-content: space-between; align-items: center;">
                <span>📊 Tổng quan tháng {p['month']}/{p['year']}:</span>
                <span style="font-size: 12px; background: {style_color}; color: #fff; padding: 2px 8px; border-radius: 10px;">{style_tag}</span>
            </div>
            
            <div style="display: flex; justify-content: space-between; margin-bottom: 15px; text-align: center; border-bottom: 1px dashed #b3e5fc; padding-bottom: 15px;">
                <div style="flex: 1;">
                    <div style="font-size: 20px; font-weight: 700; color: #01579b;">{s['days_present']}/{s['total_working_days']}</div>
                    <div style="font-size: 12px; color: #666;">Ngày công thực tế</div>
                </div>

                <div style="flex: 1; border-left: 1px solid #eee; margin-left: 40px;">
                    <div style="font-size: 20px; font-weight: 700; color: #01579b;">{avg_checkin_str}</div>
                    <div style="font-size: 12px; color: #666;">Check-in trung bình</div>
                </div>
                
                </div>

            <div style="margin-bottom: 15px;">
                <div style="font-weight: 600; font-size: 14px; color: #444;">🎯 Xu hướng giờ giấc (Arrival Trend):</div>
                <div style="font-size: 13px; color: #555; margin-top: 4px;">
                    Bạn có xu hướng check-in lúc <strong>{avg_checkin_str}</strong>. {style_msg}
                </div>
                {habit_bar_html}
            </div>

            <div style="background-color: #fff; border: 1px solid #e0e0e0; padding: 10px; border-radius: 6px; font-size: 13px;">
                <div style="font-weight: 600; color: #d32f2f; margin-bottom: 5px;">⚠️ Dữ liệu cần lưu ý:</div>
                <ul style="margin: 0; padding-left: 20px; color: #333;">
                    <li>Vắng không phép/Chưa giải trình: <strong>{s['days_missing']} ngày</strong></li>
                    <li>Về sớm: <strong>{s['early_checkout_count']} lần</strong></li>
                    <li>Tỷ lệ chuyên cần (Adjusted): <strong>{s['adjusted_attendance_rate']:.1f}%</strong></li>
                </ul>
            </div>
        </div>
        """
    else:
        checkin_content_box = """<div class="stats-box checkin-box"><p><em>Không có dữ liệu chấm công để phân tích.</em></p></div>"""

    # --- 4. Xử lý section INSIDE (NÂNG CẤP: COMMUNITY IMPACT & CULTURE) ---
    if inside_data:
        s = inside_data['summary']
        latest_posts = inside_data['latest_posts']
        
        # 1. Phân tích Vai trò (Archetype Analysis)
        posts_count = s['employee_posts']
        given_reactions = s.get('employee_reactions_given', 0)
        received_reactions = s['employee_reactions']
        
        # Định danh dựa trên hành vi
        if posts_count > 0 and received_reactions >= 10:
            archetype = "🌟 Người truyền cảm hứng (Influencer)"
            archetype_desc = "Bạn tích cực chia sẻ và nhận được sự quan tâm lớn từ cộng đồng."
            archetype_color = "#6f42c1" # Tím
            archetype_bg = "#f3e5f5"
        elif posts_count > 0:
            archetype = "✍️ Người chia sẻ (Active Sharer)"
            archetype_desc = "Bạn đã bắt đầu đóng góp tiếng nói của mình. Hãy tiếp tục duy trì nhé!"
            archetype_color = "#007bff" # Xanh dương
            archetype_bg = "#e1f5fe"
        elif given_reactions >= 20:
            archetype = "❤️ Người ủng hộ nhiệt thành (Super Fan)"
            archetype_desc = "Bạn luôn là nguồn động viên tinh thần tuyệt vời cho đồng nghiệp."
            archetype_color = "#e91e63" # Hồng
            archetype_bg = "#fce4ec"
        elif given_reactions > 0:
            archetype = "👀 Người quan sát (Observer)"
            archetype_desc = "Bạn thường xuyên cập nhật tin tức nhưng ít tương tác. Hãy thử thả tim nhiều hơn nhé!"
            archetype_color = "#6c757d" # Xám
            archetype_bg = "#f8f9fa"
        else:
            archetype = "👻 Người ẩn danh (Ghost)"
            archetype_desc = "Hệ thống chưa ghi nhận tương tác của bạn. Đừng bỏ lỡ các tin tức thú vị!"
            archetype_color = "#343a40" # Đen nhạt
            archetype_bg = "#e9ecef"

        # 2. Tính toán Tác động (Impact Metrics)
        # Tỷ lệ tương tác trung bình trên mỗi bài viết (nếu có đăng bài)
        avg_engagement = 0
        if posts_count > 0:
            avg_engagement = received_reactions / posts_count
            impact_msg = f"Trung bình mỗi bài viết của bạn thu hút <strong>{avg_engagement:.1f}</strong> lượt tương tác."
        else:
            impact_msg = "Chia sẻ kiến thức hoặc câu chuyện của bạn để tăng sức ảnh hưởng nhé."

        # 3. Tạo HTML danh sách bài viết (News Feed style)
        posts_html = ""
        if latest_posts:
            for post in latest_posts[:3]: # Chỉ lấy 3 bài
                post_link = post.get('link', '#')
                # Xác định icon dựa trên loại bài
                p_icon = "📰" if post['type'] == 'news' else "📝"
                
                posts_html += f"""
                <div style="padding: 10px; border-bottom: 1px dashed #e0e0e0; display: flex; align-items: flex-start;">
                    <div style="font-size: 20px; margin-right: 10px;">{p_icon}</div>
                    <div style="flex: 1;">
                        <a href="{post_link}" style="font-weight: 600; color: #2c3e50; text-decoration: none; display: block; margin-bottom: 4px;">
                            {post['title']}
                        </a>
                        <div style="font-size: 12px; color: #888; display: flex; justify-content: space-between;">
                            <span>👤 {post['author']} • {post['date']}</span>
                            <span>❤️ {post['reactions_count']} • 👁️ {post['views_count']}</span>
                        </div>
                    </div>
                </div>
                """
        else:
            posts_html = "<div style='padding:10px; font-style:italic; color:#999'>Chưa có bài viết mới nào.</div>"

        inside_content_box = f"""
        <div class="stats-box inside-box">
            <div style="background-color: {archetype_bg}; padding: 12px; border-radius: 6px; margin-bottom: 15px;">
                <div style="font-weight: 700; color: {archetype_color}; font-size: 15px; margin-bottom: 4px;">
                    {archetype}
                </div>
                <div style="font-size: 13px; color: #555;">{archetype_desc}</div>
            </div>

            <div style="display: flex; gap: 15px; margin-bottom: 15px;">
                <div style="flex: 1; background: #fff; border: 1px solid #eee; border-radius: 6px; padding: 10px; text-align: center;">
                    <div style="font-size: 12px; font-weight: 700; color: #6f42c1; text-transform: uppercase; margin-bottom: 8px;">
                        📡 Sức lan tỏa
                    </div>
                    <div style="font-size: 24px; font-weight: 700; color: #333;">{s['employee_views']}</div>
                    <div style="font-size: 11px; color: #777;">Lượt xem bài của bạn</div>
                    <div style="margin-top: 5px; font-size: 13px;">
                        <span style="font-weight: bold; color: #6f42c1;">{s['employee_reactions']}</span> tim nhận được
                    </div>
                </div>

                <div style="flex: 1; background: #fff; border: 1px solid #eee; border-radius: 6px; padding: 10px; text-align: center;">
                    <div style="font-size: 12px; font-weight: 700; color: #e91e63; text-transform: uppercase; margin-bottom: 8px;">
                        🤝 Sự gắn kết
                    </div>
                    <div style="font-size: 24px; font-weight: 700; color: #333;">{s.get('employee_reactions_given', 0)}</div>
                    <div style="font-size: 11px; color: #777;">Lượt thả tim cho đồng nghiệp</div>
                    <div style="margin-top: 5px; font-size: 13px;">
                        <span style="font-weight: bold; color: #e91e63;">{s.get('employee_views_given', 0)}</span> bài đã đọc
                    </div>
                </div>
            </div>

            <div style="font-size: 13px; color: #555; margin-bottom: 20px; padding: 8px; background-color: #f8f9fa; border-radius: 4px;">
                💡 <strong>Insight:</strong> {impact_msg}
            </div>

            <div style="border-top: 1px solid #eee; padding-top: 15px;">
                <div style="font-weight: 600; color: #444; margin-bottom: 10px; font-size: 14px;">
                    🗞️ Tiêu điểm truyền thông nội bộ:
                </div>
                <div style="background: #fff; border: 1px solid #eee; border-radius: 6px;">
                    {posts_html}
                </div>
                <div style="text-align: right; margin-top: 8px;">
                    <a href="https://inside.base.vn" style="font-size: 12px; color: #004a99; text-decoration: none;">Xem thêm trên Inside →</a>
                </div>
            </div>
        </div>
        """
    else:
        inside_content_box = """<div class="stats-box inside-box"><p><em>Không có dữ liệu Inside để phân tích.</em></p></div>"""

    # --- 5. Xử lý section WORKFLOW (GIỮ ĐẶC TRƯNG RIÊNG CỦA WORKFLOW) ---
    if workflow_data and workflow_data.get('summary'):
        s = workflow_data['summary']
        stats_ext = workflow_data.get('stats_extended', {})
        latest_jobs = workflow_data['latest_jobs']
        
        # Lấy số liệu mở rộng
        completed_late = stats_ext.get('completed_late_count', 0)
        no_deadline = stats_ext.get('no_deadline_count', 0)
        overdue_jobs = stats_ext.get('overdue_jobs', [])
        upcoming_jobs = stats_ext.get('upcoming_deadline_jobs', [])
        
        # 1. Tính toán Insight về tốc độ xử lý (ĐẶC TRƯNG WORKFLOW)
        completion_rate = s['completion_rate']
        if completion_rate >= 80:
            insight_msg = "🚀 <strong>Tốc độ xử lý Tốt:</strong> Các luồng công việc được hoàn tất nhanh chóng, ít tồn đọng."
            insight_bg = "#e6fffa"
        elif completion_rate >= 50:
            insight_msg = "⚡ <strong>Hoạt động ổn định:</strong> Cần đẩy nhanh các nhiệm vụ đang thực hiện."
            insight_bg = "#fff3e0"
        else:
            insight_msg = "🐢 <strong>Cần lưu ý:</strong> Nhiều quy trình đang bị tắc nghẽn hoặc chưa được xử lý dứt điểm."
            insight_bg = "#fff5f5"
        
        # 2. Phân tích theo Workflow Name (ĐẶC TRƯNG WORKFLOW)
        workflow_stats = {}
        for job in latest_jobs:
            wf_name = job.get('workflow_name', 'N/A')
            if wf_name not in workflow_stats:
                workflow_stats[wf_name] = {'total': 0, 'active': 0}
            workflow_stats[wf_name]['total'] += 1
            if job.get('stage_metatype') not in ['done', 'failed']:
                workflow_stats[wf_name]['active'] += 1
        
        # Sắp xếp theo số lượng job (nhiều nhất trước)
        sorted_workflows = sorted(workflow_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        
        workflow_summary_html = ""
        if len(sorted_workflows) > 1:  # Chỉ hiển thị nếu có nhiều hơn 1 workflow
            workflow_summary_html = '<div style="margin-top: 10px; padding: 8px; background-color: #fff3e0; border-radius: 4px; border-left: 3px solid #ff9800;">'
            workflow_summary_html += '<strong>📊 Phân bố theo Quy trình:</strong><div style="font-size: 13px; margin-top: 4px;">'
            for wf_name, stats in sorted_workflows[:3]:  # Top 3
                workflow_summary_html += f"<div>• <strong>{wf_name}</strong>: {stats['total']} job ({stats['active']} đang xử lý)</div>"
            workflow_summary_html += '</div></div>'
        
        # 3. Tạo HTML cho Upcoming Deadlines (Vẫn hữu ích)
        upcoming_html = ""
        if upcoming_jobs:
            upcoming_list_items = ""
            for j in upcoming_jobs[:5]:
                days = j.get('days_left', 0)
                day_str = "Hôm nay" if days == 0 else f"{days} ngày nữa"
                job_name = j.get('name') or j.get('title', 'No Name')
                upcoming_list_items += f"<div>• <span style='color:#e65100; font-weight:600;'>{job_name}</span> ({day_str})</div>"
            
            upcoming_html = f"""
            <li style="margin-top: 10px; background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 3px solid #ffc107;">
                <strong>⚠️ Sắp đến hạn (7 ngày tới):</strong>
                <div style="font-size: 13px; margin-top: 4px;">{upcoming_list_items}</div>
            </li>
            """
        
        # 4. Tạo bảng Jobs đang xử lý với Stage (ĐẶC TRƯNG WORKFLOW - thay vì overdue)
        active_jobs = [job for job in latest_jobs if job.get('stage_metatype') not in ['done', 'failed']]
        
        jobs_table_html = ""
        if active_jobs:
            jobs_table_html = '<div style="margin-top: 15px; border-top: 1px dashed #ccc; padding-top: 10px;">'
            jobs_table_html += '<div style="font-weight: 600; margin-bottom: 8px; color: #555;">⚙️ Các công việc đang xử lý (theo giai đoạn):</div>'
            jobs_table_html += '<table style="width: 100%; border-collapse: collapse; font-size: 13px;">'
            jobs_table_html += '<tr style="background-color: #f0f0f0; text-align: left;">'
            jobs_table_html += '<th style="padding: 6px; border: 1px solid #ddd;">Công việc / Quy trình</th>'
            jobs_table_html += '<th style="padding: 6px; border: 1px solid #ddd; width: 120px;">Giai đoạn</th>'
            jobs_table_html += '<th style="padding: 6px; border: 1px solid #ddd; width: 80px;">Ngày tạo</th>'
            jobs_table_html += '</tr>'
            
            for job in active_jobs[:10]:  # Limit 10
                j_name = job.get('title', 'No Name')
                wf_name = job.get('workflow_name', 'N/A')
                stage_name = job.get('stage_name', 'N/A')
                
                # Ngày tạo
                created_date = "N/A"
                date_str = job.get('date', '')
                if date_str and date_str != 'N/A':
                    try:
                        # Extract date from "DD/MM/YYYY HH:MM:SS" format
                        created_date = date_str.split(' ')[0] if ' ' in date_str else date_str
                    except:
                        created_date = "N/A"
                
                # Stage color based on metatype (optional, keep subtle)
                stage_bg = "#e3f2fd"  # Light blue default
                
                jobs_table_html += f'<tr>'
                jobs_table_html += f'<td style="padding: 6px; border: 1px solid #ddd;">'
                jobs_table_html += f'<div style="font-weight: 600; color: #333;">{j_name}</div>'
                jobs_table_html += f'<div style="font-size: 11px; color: #666;">📂 {wf_name}</div>'
                jobs_table_html += f'</td>'
                jobs_table_html += f'<td style="padding: 6px; border: 1px solid #ddd; background-color: {stage_bg}; text-align: center; font-weight: 600;">{stage_name}</td>'
                jobs_table_html += f'<td style="padding: 6px; border: 1px solid #ddd; text-align: center;">{created_date}</td>'
                jobs_table_html += f'</tr>'
            
            jobs_table_html += '</table>'
            jobs_table_html += '</div>'
        
        workflow_content_box = f"""
        <div class="stats-box workflow-box">
            <div class="sub-header">⚙️ Vận hành & Quy trình (1 tháng gần nhất):</div>
            <ul class="stat-list">
                <li>📋 Tổng quan: <strong>{s['total_jobs']} job</strong> (Done: {s['completion_rate']:.1f}%)</li>
                <li>🏁 Đang xử lý: <strong>{s['doing_jobs']} job</strong> | Hoàn thành muộn: <strong>{completed_late} job</strong></li>
                <li>⚠️ Không Deadline: <strong>{no_deadline} job</strong></li>
                {upcoming_html}
                
                <li style="margin-top: 10px; padding: 8px; background-color: {insight_bg}; border-radius: 4px; font-size: 13px;">
                    {insight_msg}
                </li>
            </ul>
            {workflow_summary_html}
            {jobs_table_html}
             <div class="evaluation-section" style="background-color: #fff; border: 1px solid #e0e0e0; margin-top:10px;">
                 💡 <em>Insight (AI): {get_ai_insight(f"Workflow: Hoàn thành {s['completion_rate']:.1f}%. Đang xử lý {s['doing_jobs']} job. Quá hạn {len(overdue_jobs)} job. Tình trạng: {insight_msg}")}</em>
            </div>
        </div>
        """
    else:
        workflow_content_box = """<div class="stats-box workflow-box"><p><em>Không có dữ liệu quy trình xử lý.</em></p></div>"""
    # --- HTML TEMPLATE CHÍNH (VỚI CSS ĐƯỢC NÂNG CẤP) ---
    # *** ĐÂY LÀ PHẦN THAY ĐỔI LỚN NHẤT ***
    html_template = f"""
<html>
<head>
<style>
    body {{
        /* Cải thiện font chữ, dùng font hệ thống hiện đại */
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        line-height: 1.65; /* Tăng khoảng cách dòng cho dễ đọc */
        color: #212529; /* Màu chữ đen xám, dịu mắt hơn #333 */
        background-color: #f8f9fa; /* Nền xám rất nhạt cho body */
        margin: 0;
        padding: 20px;
    }}
    .email-container {{
        max-width: 700px; /* Thu hẹp 1 chút cho cân đối hơn */
        margin: 0 auto;
        background-color: #ffffff;
        padding: 30px;
        border-radius: 8px;
        /* Box shadow tinh tế hơn */
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #dee2e6; /* Thêm 1 viền mỏng */
    }}
    
    /* HEADER */
    .main-header {{
        font-size: 26px; /* Tăng kích thước 1 chút */
        font-weight: 700; /* Đậm hơn */
        color: #004a99; /* Màu xanh đậm hơn, chuyên nghiệp hơn */
        margin-bottom: 20px;
        border-bottom: 2px solid #004a99;
        padding-bottom: 15px;
    }}
    .greeting {{
        font-weight: 600; /* Semi-bold */
        color: #2c3e50;
        font-size: 16px;
        margin-bottom: 15px;
    }}
    .intro-text {{
        color: #495057; /* Màu chữ nội dung xám hơn */
        margin-bottom: 20px;
        font-size: 15px;
    }}
    .intro-text em {{
        font-style: italic;
        color: #004a99; /* Nhấn mạnh bằng màu xanh */
    }}
    .intro-text ul {{
        padding-left: 25px; /* Thụt lề rõ hơn */
    }}
    .report-date {{
        font-style: italic;
        color: #6c757d; /* Xám nhạt hơn cho thông tin phụ */
        font-size: 13px;
        margin-bottom: 30px;
    }}

    /* SECTIONS GENERAL */
    .section {{
        margin-bottom: 35px;
    }}
    .section-title {{
        font-size: 20px;
        font-weight: 700; /* Đậm */
        margin-bottom: 10px;
        color: #212529; /* Màu chữ chính, không dùng màu */
        
        /* Thay đổi: Dùng border-left để tạo màu nhấn */
        padding-left: 12px;
        border-left: 4px solid #ccc; /* Màu mặc định */
    }}
    .section-desc {{
        font-style: italic;
        font-weight: 500;
        margin-bottom: 15px;
        color: #555; /* Bỏ màu, dùng màu xám chung */
        font-size: 15px;
    }}
    
    /* Cập nhật các class màu nhấn cho border */
    .goal-title {{ border-left-color: #ffc107; }}
    .wework-title {{ border-left-color: #20c997; }}
    .checkin-title {{ border-left-color: #17a2b8; }}
    .inside-title {{ border-left-color: #6f42c1; }}
    .workflow-title {{ border-left-color: #fd7e14; }}

    /* STATS BOXES (Cải tiến thành dạng "Card") */
    .stats-box {{
        background-color: #ffffff; /* Nền trắng */
        border: 1px solid #e9ecef; /* Viền xám mỏng, tinh tế */
        padding: 20px; /* Tăng padding */
        border-radius: 8px; /* Bo góc rõ hơn */
        margin-top: 10px;
    }}
    
    /* Box trạng thái Cảnh báo (Warning) */
    .warning-box {{
        background-color: #fff3f3; /* Đỏ rất nhạt */
        border: 1px solid #f5c6cb;
        color: #721c24;
        border-left: 4px solid #dc3545; /* Viền trái đỏ đậm */
    }}
    
    /* Box trạng thái Thành công (Success) - cho Goal */
    .success-box {{
        background-color: #e6f7ec; /* Xanh lá rất nhạt */
        border: 1px solid #c3e6cb;
        color: #155724;
        border-left: 4px solid #28a745; /* Viền trái xanh đậm */
    }}
    
    /* Box màu cho WeWork - Xanh ngọc bích */
    .wework-box {{
        background-color: #e0f2f1; /* Xanh ngọc bích rất nhạt */
        border: 1px solid #80cbc4;
        color: #004d40;
        border-left: 4px solid #20c997; /* Viền trái xanh ngọc đậm */
    }}
    
    /* Box màu cho Checkin - Xanh dương */
    .checkin-box {{
        background-color: #e0f7fa; /* Xanh dương rất nhạt */
        border: 1px solid #b3e5fc;
        color: #01579b;
        border-left: 4px solid #17a2b8; /* Viền trái xanh dương đậm */
    }}
    
    /* Box màu cho Inside - Tím */
    .inside-box {{
        background-color: #f3e5f5; /* Tím rất nhạt */
        border: 1px solid #e1bee7;
        color: #4a148c;
        border-left: 4px solid #6f42c1; /* Viền trái tím đậm */
    }}
    
    /* Box màu cho Workflow - Cam */
    .workflow-box {{
        background-color: #fff3e0; /* Cam rất nhạt */
        border: 1px solid #ffe0b2;
        color: #e65100;
        border-left: 4px solid #fd7e14; /* Viền trái cam đậm */
    }}
    
    .sub-header {{
        font-weight: 600; /* Semi-bold */
        margin-bottom: 15px;
        font-size: 16px;
    }}
    .stat-list {{
        list-style-type: none;
        padding-left: 5px;
        margin: 0;
    }}
    .stat-list li {{
        margin-bottom: 10px; /* Tăng khoảng cách */
        font-size: 15px;
    }}
    /* Nhấn mạnh con số bằng màu xanh */
    .stat-list li strong {{
        color: #004a99;
        font-weight: 600;
    }}
    
    /* Màu chữ cho các box có màu nền */
    .success-box .stat-list li strong {{
        color: #155724; /* Xanh lá đậm */
    }}
    
    .wework-box .stat-list li strong {{
        color: #004d40; /* Xanh ngọc bích đậm */
    }}
    
    .checkin-box .stat-list li strong {{
        color: #01579b; /* Xanh dương đậm */
    }}
    
    .inside-box .stat-list li strong {{
        color: #4a148c; /* Tím đậm */
    }}
    
    .workflow-box .stat-list li strong {{
        color: #e65100; /* Cam đậm */
    }}
    
    .evaluation-section {{
        margin-top: 15px;
        font-size: 15px;
        background-color: #f8f9fa;
        padding: 12px 15px;
        border-radius: 6px;
    }}
    
    /* INSIDE POSTS SECTION */
    .latest-posts-section {{
        margin-top: 15px;
    }}
    .post-item {{
        background-color: #f8f9fa;
        border-left: 3px solid #6f42c1;
        padding: 15px;
        margin-bottom: 12px;
        border-radius: 6px;
    }}
    .post-title {{
        font-weight: 600;
        font-size: 15px;
        color: #212529;
        margin-bottom: 8px;
    }}
    .post-meta {{
        font-size: 13px;
        color: #6c757d;
        margin-bottom: 8px;
    }}
    .post-preview {{
        font-size: 14px;
        color: #495057;
        line-height: 1.5;
    }}
    .post-link {{
        margin-top: 10px;
        padding-top: 10px;
        border-top: 1px solid #dee2e6;
    }}
    .post-link a:hover {{
        text-decoration: underline !important;
    }}

    /* FOOTER MESSAGE (Tinh chỉnh lại) */
    .footer-message {{
        background-color: #eef6f8; /* Xanh dương nhạt hơn 1 chút */
        padding: 25px;
        border-radius: 8px;
        margin-top: 40px;
        border-left: 5px solid #17a2b8; /* Giữ nguyên viền trái */
    }}
    .footer-title {{
        font-weight: 700;
        color: #17a2b8; /* Dùng màu xanh của viền */
        margin-bottom: 10px;
        text-transform: uppercase;
        font-size: 16px;
    }}
    .footer-message p {{
        margin-bottom: 10px;
        color: #34495e;
    }}
</style>
</head>
<body>
    <div class="email-container">
        <div class="main-header">
            📊 BÁO CÁO TỔNG HỢP BASE.VN
        </div>
        <div class="greeting">
            Thân gửi Anh/Chị: {employee_name}
        </div>
        <div class="intro-text">
            <p>Tại APLUS, chúng ta tin rằng <em>"hiệu suất không chỉ là kết quả – mà là cách mỗi người hiện diện và cam kết trong hành động."</em></p>
            <p>Khác với nhiều môi trường khác, tại A Plus, chúng ta đang làm việc trên <strong>không gian số</strong> – nơi mọi hành động đều có thể đo lường, minh bạch và kế thừa.</p>
            <p>Ở đây, mỗi nhân sự được tạo điều kiện tối đa để thể hiện năng lực, tự chủ và sáng tạo – không giới hạn bởi giấy tờ, thủ tục hay "phòng ban".</p>
            <p><strong>Base không chỉ là hệ thống vận hành – mà là "tấm gương số" phản chiếu cách mỗi người chúng ta làm việc, tư duy và tương tác mỗi ngày.</strong></p>
            <p>70–90% công việc của bạn đang diễn ra trên đó – từng thao tác, phản hồi, cam kết, và kết quả đều đang nói thay bạn.</p>
            <p>Và chính vì Base phản ánh 70–90% công việc, nên nó cũng phản ánh <strong>70–90% con người bạn trong A Plus.</strong></p>
            <p>💡 <em>Cách bạn cập nhật task, giữ deadline, phản hồi đồng đội, xử lý vấn đề – tất cả đều là một phần của "dấu vân tay chuyên nghiệp" mà bạn đang để lại trong hệ thống.</em></p>
        </div>
        <div class="report-date">
            Ngày tạo báo cáo: {current_time_str}
        </div>

        {f'''<div class="section">
            <div class="section-title wework-title">🧭 BASE WEWORK – QUẢN LÝ CÔNG VIỆC</div>
            <div class="section-desc">Không gian làm việc số – nơi toàn bộ công việc, dự án, và kết quả của bạn được ghi nhận và kết nối liền mạch với đội nhóm.</div>
            {wework_content_box}
        </div>''' if wework_data else ''}

        {f'''<div class="section">
            <div class="section-title goal-title">🥇 BASE GOAL – TIẾN ĐỘ OKR</div>
            <div class="section-desc">OKR là kim chỉ nam giúp mỗi cá nhân kết nối mục tiêu của mình với tầm nhìn chung của APLUS.</div>
            {goal_content_box}
        </div>''' if goal_data else ''}

        {f'''<div class="section">
            <div class="section-title workflow-title">⚙️ BASE WORKFLOW – QUY TRÌNH & CÔNG VIỆC</div>
            <div class="section-desc">Hệ thống quản lý quy trình và công việc – nơi các công việc được theo dõi, quản lý và hoàn thành một cách có hệ thống.</div>
            {workflow_content_box}
        </div>''' if workflow_data else ''}

        {f'''<div class="section">
            <div class="section-title checkin-title">⏰ BASE CHECKIN – CHẤM CÔNG & CHUYÊN CẦN</div>
            <div class="section-desc">Ghi nhận sự hiện diện của bạn – không chỉ về mặt thời gian, mà còn thể hiện tính kỷ luật, sự tôn trọng và cam kết khi làm việc cùng đội ngũ.</div>
            {checkin_content_box}
        </div>''' if checkin_data else ''}

        <div class="section">
            <div class="section-title inside-title">💬 BASE INSIDE – CỘNG ĐỒNG & TƯƠNG TÁC</div>
            <div class="section-desc">Không gian chia sẻ và kết nối – nơi mỗi thành viên thể hiện sự tham gia tích cực, chia sẻ ý tưởng và xây dựng văn hóa công ty.</div>
            {inside_content_box}
        </div>

        <div class="footer-message">
            <div class="footer-title">💬 THÔNG ĐIỆP TỪ APLUS</div>
            <p>Cảm ơn bạn vì đã <strong>hiện diện trọn vẹn</strong> – không chỉ trong thời gian làm việc, mà trong tinh thần, thái độ và cam kết mà bạn mang đến mỗi ngày.</p>
            <p>Chúng ta đang làm việc trong một bối cảnh hoàn toàn mới – nơi <strong>"văn phòng" không còn là bốn bức tường, mà là một không gian số tốc độ cao</strong>, nơi mọi thứ vận hành như chiếc máy bay đang cất cánh.</p>
            <p>Và trong hành trình đó, A Plus đang đồng hành cùng bạn – để bạn <strong>làm quen, thích nghi và dẫn dắt</strong> với tư duy số, công cụ số và năng lực số.</p>
            <p><strong>Không ai bị bỏ lại phía sau</strong> – mỗi bước bạn thành thạo thêm một công cụ, là cả tập thể tiến gần hơn đến tầm nhìn "Digital – Smart – A Plus 2028."</p>
            <p>Hãy tiếp tục duy trì tinh thần cam kết và Integrity – vì chính bạn là một phần trong hành trình đưa APLUS trở thành <strong>minh chứng cho một công ty Việt Nam có Integrity hiện diện. </strong>💪</p>
        </div>
    </div>
</body>
</html>
    """
    return html_template


def normalize_search_name(name):
    """Chuẩn hóa tên để tìm kiếm (lowercase, NFC)"""
    if not name: return ""
    return unicodedata.normalize('NFC', name).strip().lower()

def get_employee_info_from_api(target_name):
    """Lấy thông tin nhân viên từ API"""
    try:
        target_normalized = normalize_search_name(target_name)
        
        # Thử tìm từ WeWork API (group aplus với filter) trước
        api_client = WeWorkAPIClient(WEWORK_ACCESS_TOKEN, ACCOUNT_ACCESS_TOKEN)
        employees_df = api_client.get_filtered_members()
        
        # Tìm trong DataFrame với chuẩn hóa
        found_in_wework = False
        employee_dict = {}
        
        if not employees_df.empty:
            for idx, row in employees_df.iterrows():
                if normalize_search_name(row.get('name', '')) == target_normalized:
                    employee_dict = row.to_dict()
                    found_in_wework = True
                    break
        
        if found_in_wework:
            return employee_dict
        
        # Nếu không tìm thấy, thử tìm từ Account API (tất cả users)
        print(f"⚠️ Không tìm thấy nhân viên trong WeWork group, đang tìm trong Account API...")
        
        # Tải user mapping nếu chưa có
        if not user_id_to_name_map:
            load_user_mapping()
        
        # Tìm trong Account API
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
            
            # Tìm nhân viên theo tên
            for user in user_list:
                if normalize_search_name(user.get('name', '')) == target_normalized:
                    # Chuyển đổi format để tương thích với WeWork format
                    return {
                        'id': str(user.get('id', '')),
                        'name': user.get('name', ''),
                        'username': user.get('username', ''),
                        'job': user.get('title', ''),
                        'email': user.get('email', '')
                    }
        
        print(f"⚠️ Không tìm thấy nhân viên: {target_name}")
        return None
    except Exception as e:
        print(f"❌ Lỗi khi lấy thông tin nhân viên: {e}")
        return None

def send_email(to_email, subject, html_content):
    """Gửi email"""
    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_GUI
        msg['To'] = to_email
        msg['Subject'] = subject
        part_html = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(part_html)
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_GUI, MAT_KHAU)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email đã được gửi thành công đến {to_email}")
        return True
    except Exception as e:
        print(f"❌ Lỗi khi gửi email: {str(e)}")
        return False

def main():
    print("="*80)
    print("📧 HỆ THỐNG GỬI EMAIL BÁO CÁO TỔNG HỢP BASE.VN (GIAO DIỆN MỚI)")
    print("="*80)
    
    # Có thể thay đổi tên nhân viên tại đây hoặc nhập từ bàn phím
    target_employee_name = DEFAULT_EMPLOYEE_NAME
    # target_employee_name = input("Nhập tên nhân viên cần gửi báo cáo: ")

    print(f"\n🔄 Đang lấy thông tin cho: {target_employee_name}...")
    employee_info = get_employee_info_from_api(target_employee_name)
    if not employee_info: return
    
    employee_name = employee_info['name']
    employee_username = employee_info['username']
    print(f"✅ Tìm thấy: {employee_name} ({employee_username})")
    
    now = datetime.now(hcm_tz)
    # Lấy dữ liệu cho tháng hiện tại
    year_to_check = now.year
    month_to_check = now.month
    
    print(f"📅 Lấy dữ liệu cho tháng: {month_to_check}/{year_to_check}")
    
    checkin_data = get_checkin_data(employee_name, year_to_check, month_to_check)
    wework_data = get_wework_data(employee_username)
    goal_data = get_goal_data(employee_name)
    inside_data = get_inside_data(employee_name)
    workflow_data = get_workflow_data(employee_name)
    
    # ============================================================================
    # KIỂM TRA DỮ LIỆU GẦN ĐÂY (1 tháng cho WeWork/Workflow, quý cho Goal)
    # ============================================================================
    one_month_ago = now - timedelta(days=30)
    one_month_ago_ts = one_month_ago.timestamp()
    
    # Kiểm tra WeWork có dữ liệu gần đây không (1 tháng)
    has_recent_wework = False
    if wework_data and wework_data.get('recent_tasks'):
        for task in wework_data['recent_tasks']:
            since_ts = task.get('since', 0)
            if since_ts and float(since_ts) >= one_month_ago_ts:
                has_recent_wework = True
                break
    
    # Kiểm tra Workflow có dữ liệu gần đây không (1 tháng)
    has_recent_workflow = False
    if workflow_data and workflow_data.get('latest_jobs'):
        for job in workflow_data['latest_jobs']:
            # Parse date string "DD/MM/YYYY HH:MM:SS"
            date_str = job.get('date', '')
            if date_str and date_str != 'N/A':
                try:
                    job_date = datetime.strptime(date_str, '%d/%m/%Y %H:%M:%S')
                    if job_date >= one_month_ago:
                        has_recent_workflow = True
                        break
                except:
                    pass
    
    # Kiểm tra Goal có dữ liệu không (theo quý - chỉ cần có data)
    has_recent_goal = bool(goal_data and goal_data.get('weekly'))
    
    # Đếm số sections có dữ liệu
    active_sections_count = sum([has_recent_wework, has_recent_workflow, has_recent_goal])
    
    print(f"\n📊 Kiểm tra dữ liệu gần đây:")
    print(f"   - WeWork (1 tháng): {'✅ Có' if has_recent_wework else '❌ Không'}")
    print(f"   - Workflow (1 tháng): {'✅ Có' if has_recent_workflow else '❌ Không'}")
    print(f"   - Goal (quý hiện tại): {'✅ Có' if has_recent_goal else '❌ Không'}")
    print(f"   - Tổng: {active_sections_count}/3 sections có dữ liệu")
    
    # Nếu không có dữ liệu nào, set wework_data thành None và tạo cảnh báo
    # Nếu không có dữ liệu nào, set wework_data thành None và tạo cảnh báo
    if active_sections_count == 0:
        print("⚠️ CẢNH BÁO: Không có dữ liệu gần đây từ WeWork, Workflow, hoặc Goal!")
        # Inject warning vào wework_data
        wework_data = {
            'summary': {'total_tasks': 0},
            'is_warning_only': True  # Flag để hiển thị warning
        }
        goal_data = None
        workflow_data = None
    else:
        # Nếu không có WeWork nhưng có Workflow/Goal thì set flag
        if not has_recent_wework:
            wework_data = None
        
        # Clear data nếu không có recent activity
        if not has_recent_workflow:
            workflow_data = None
        if not has_recent_goal:
            goal_data = None
    
    print("\n📝 Đang tạo nội dung email theo mẫu mới...")
    html_content = create_email_html(employee_name, checkin_data, wework_data, goal_data, inside_data, workflow_data)
    
    # Tùy chọn: Ghi ra file HTML để kiểm tra trước khi gửi
    try:
        with open("test_email_output_v2.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("✅ Đã lưu file test_email_output_v2.html để kiểm tra giao diện")
    except Exception as e:
        print(f"Lỗi khi ghi file test HTML: {e}")


    print(f"\n📤 Đang gửi email đến {EMAIL_NHAN}...")
    send_email(EMAIL_NHAN, f"BÁO CÁO TỔNG HỢP BASE.VN - {employee_name}", html_content)

if __name__ == "__main__":
    main()