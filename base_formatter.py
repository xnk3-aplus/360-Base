from datetime import datetime, timedelta
import pytz


hcm_tz = pytz.timezone('Asia/Ho_Chi_Minh')



def format_email_content(employee_name, checkin_data, wework_data, goal_data, inside_data, workflow_data):
    """
    Format data into HTML content boxes matching the email template.
    Returns a dictionary with HTML strings for each section and the full email HTML.
    """
    current_time_str = datetime.now(hcm_tz).strftime('%d/%m/%Y %H:%M:%S')

    # --- 1. GOAL SECTION ---
    if goal_data and goal_data.get('weekly'):
        weekly = goal_data['weekly']
        behavior = goal_data.get('checkin_behavior', {}) or {}
        overall = goal_data.get('overall_behavior', {}) or {}
        
        shift_val = weekly.get('okr_shift', 0)
        checkin_count = behavior.get('checkin_count_period', 0)
        checkin_freq = overall.get('checkin_frequency_per_week', 0)
        
        if shift_val > 0:
            trend_icon, trend_text, trend_color = "📈", "Tăng trưởng tích cực", "#155724"
        elif shift_val < 0:
            trend_icon, trend_text, trend_color = "📉", "Đang bị trượt mục tiêu", "#dc3545"
        else:
            trend_icon, trend_text, trend_color = "➖", "Không có biến động", "#856404"
            
        if checkin_count >= 2:
            discipline_text = "Kỷ luật Tốt (Duy trì đều đặn)"
        elif checkin_count == 1:
            discipline_text = "Cần cải thiện tần suất"
        else:
            discipline_text = "Cảnh báo: Thiếu tương tác hệ thống"

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
                
                if g_speed >= 1.0:
                    speed_color, speed_bg, speed_text = "#155724", "#d4edda", "Tốt"
                elif g_speed >= 0.5:
                    speed_color, speed_bg, speed_text = "#856404", "#fff3cd", "Khá"
                else:
                    speed_color, speed_bg, speed_text = "#721c24", "#f8d7da", "Chậm"
                
                goals_html += f'<tr><td style="padding: 5px; border: 1px solid #ddd;">{g_name}</td>'
                goals_html += f'<td style="padding: 5px; border: 1px solid #ddd; text-align: center;">{g_val:.1f}%</td>'
                goals_html += f'<td style="padding: 5px; border: 1px solid #ddd; text-align: center; background-color: {speed_bg}; color: {speed_color}; font-weight: bold;">{g_speed:.2f} ({speed_text})</td></tr>'
            goals_html += '</table></div>'

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
        </div>
        """
    else:
        goal_content_box = ""

    # --- 2. WEWORK SECTION ---
    if wework_data:
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
            completed_late = stats_ext.get('completed_late_count', 0)
            no_deadline = stats_ext.get('no_deadline_count', 0)
            overdue_tasks = stats_ext.get('overdue_tasks', [])
            upcoming_tasks = stats_ext.get('upcoming_deadline_tasks', [])
            
            upcoming_html = ""
            if upcoming_tasks:
                upcoming_list_items = ""
                for t in upcoming_tasks[:5]:
                    deadline_ts = t.get('deadline')
                    days = 0
                    if deadline_ts:
                        try:
                            deadline_date = datetime.fromtimestamp(float(deadline_ts), hcm_tz)
                            days = max(0, (deadline_date - datetime.now(hcm_tz)).days)
                        except: pass
                    day_str = "Hôm nay" if days == 0 else f"{days} ngày nữa"
                    upcoming_list_items += f"<div>• <span style='color:#e65100; font-weight:600;'>{t.get('name')}</span> ({day_str})</div>"
                
                upcoming_html = f"""
                <li style="margin-top: 10px; background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 3px solid #ffc107;">
                    <strong>⚠️ Sắp đến hạn (7 ngày tới):</strong>
                    <div style="font-size: 13px; margin-top: 4px;">{upcoming_list_items}</div>
                </li>
                """
                
            overdue_table_html = ""
            if overdue_tasks:
                overdue_table_html += '<div style="margin-top: 15px; border-top: 1px dashed #ef9a9a; padding-top: 10px;">'
                overdue_table_html += '<div style="font-weight: 600; margin-bottom: 8px; color: #c62828;">🚨 Công việc QUÁ HẠN (Cần xử lý ngay):</div>'
                overdue_table_html += '<table style="width: 100%; border-collapse: collapse; font-size: 13px;">'
                overdue_table_html += '<tr style="background-color: #ffebee; text-align: left;">'
                overdue_table_html += '<th style="padding: 6px; border: 1px solid #ffcdd2;">Công việc / Dự án</th><th style="padding: 6px; border: 1px solid #ffcdd2; width: 80px;">Ngày tạo</th><th style="padding: 6px; border: 1px solid #ffcdd2; width: 90px;">Deadline</th></tr>'
                
                for task in overdue_tasks[:10]:
                    t_name = task.get('name', 'No Name')
                    p_name = task.get('project_name', 'Unknown Project')
                    created_date = "N/A"
                    if task.get('since'):
                        try: created_date = datetime.fromtimestamp(int(task.get('since')), hcm_tz).strftime('%d/%m')
                        except: pass
                    deadline_str = "Lỗi"
                    if task.get('deadline'):
                        try: deadline_str = datetime.fromtimestamp(int(task.get('deadline')), hcm_tz).strftime('%d/%m')
                        except: pass
                    
                    overdue_table_html += f'<tr><td style="padding: 6px; border: 1px solid #ffcdd2;"><div style="font-weight: 600; color: #333;">{t_name}</div><div style="font-size: 11px; color: #666;">📂 {p_name}</div></td>'
                    overdue_table_html += f'<td style="padding: 6px; border: 1px solid #ffcdd2; text-align: center;">{created_date}</td><td style="padding: 6px; border: 1px solid #ffcdd2; text-align: center; color: #c62828; font-weight: bold;">{deadline_str}</td></tr>'
                overdue_table_html += '</table></div>'

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
            </div>
            """
    else:
        wework_content_box = ""

    # --- 3. CHECKIN SECTION ---
    if checkin_data:
        s = checkin_data['summary']
        daily_records = checkin_data.get('daily_records', [])
        
        early_arrival = 0
        standard_arrival = 0
        late_arrival = 0
        total_checkin_minutes = 0
        valid_checkin_count = 0
        
        for r in daily_records:
            if r['status'] == 'present':
                first_ci = r['checkin_details'].get('first_checkin')
                if first_ci:
                    try:
                        h, m, _ = map(int, first_ci.split(':'))
                        total_checkin_minutes += h * 60 + m
                        valid_checkin_count += 1
                        c_status = r['checkin_details'].get('checkin_status', 'standard')
                        if c_status == 'early': early_arrival += 1
                        elif c_status == 'late': late_arrival += 1
                        else: standard_arrival += 1
                    except: pass
        
        avg_checkin_str = "N/A"
        if valid_checkin_count > 0:
            avg_minutes = total_checkin_minutes / valid_checkin_count
            avg_checkin_str = f"{int(avg_minutes // 60):02d}:{int(avg_minutes % 60):02d}"

        if valid_checkin_count > 0:
            if early_arrival > (standard_arrival + late_arrival):
                style_tag, style_msg, style_color = "🌅 Early Bird (Đến sớm)", "Bạn thích bắt đầu ngày mới sớm.", "#28a745"
            elif late_arrival > 3:
                style_tag, style_msg, style_color = "⚠️ Late Start (Đến trễ)", "Giờ bắt đầu của bạn đang bị trễ.", "#dc3545"
            else:
                style_tag, style_msg, style_color = "⏰ Punctual (Đúng giờ)", "Bạn tuân thủ giờ giấc rất ổn định.", "#17a2b8"
        else:
            style_tag, style_msg, style_color = "Unknown", "Chưa đủ dữ liệu.", "#6c757d"

        total_days = early_arrival + standard_arrival + late_arrival
        p_early, p_std, p_late = 0,0,0
        if total_days > 0:
            p_early = (early_arrival / total_days) * 100
            p_std = (standard_arrival / total_days) * 100
            p_late = (late_arrival / total_days) * 100

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
                <span>📊 Tổng quan tháng {checkin_data['period']['month']}/{checkin_data['period']['year']}:</span>
                <span style="font-size: 12px; background: {style_color}; color: #fff; padding: 2px 8px; border-radius: 10px;">{style_tag}</span>
            </div>
            <div style="display: flex; justify-content: space-between; margin-bottom: 15px; text-align: center; border-bottom: 1px dashed #b3e5fc; padding-bottom: 15px;">
                <div style="flex: 1;"><div style="font-size: 20px; font-weight: 700; color: #01579b;">{s['days_present']}/{s['total_working_days']}</div><div style="font-size: 12px; color: #666;">Ngày công thực tế</div></div>
                <div style="flex: 1; border-left: 1px solid #eee; margin-left: 40px;"><div style="font-size: 20px; font-weight: 700; color: #01579b;">{avg_checkin_str}</div><div style="font-size: 12px; color: #666;">Check-in trung bình</div></div>
            </div>
            <div style="margin-bottom: 15px;">
                <div style="font-weight: 600; font-size: 14px; color: #444;">🎯 Xu hướng giờ giấc (Arrival Trend):</div>
                <div style="font-size: 13px; color: #555; margin-top: 4px;">Bạn có xu hướng check-in lúc <strong>{avg_checkin_str}</strong>. {style_msg}</div>
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
        checkin_content_box = ""

    # --- 4. INSIDE SECTION ---
    if inside_data:
        s = inside_data['summary']
        latest_posts = inside_data['latest_posts']
        posts_count = s['employee_posts']
        received_reactions = s['employee_reactions']
        
        if posts_count > 0 and received_reactions >= 10:
            archetype, archetype_desc, archetype_color, archetype_bg = "🌟 Người truyền cảm hứng", "Bạn chia sẻ tích cực.", "#6f42c1", "#f3e5f5"
        elif posts_count > 0:
            archetype, archetype_desc, archetype_color, archetype_bg = "✍️ Người chia sẻ", "Hãy tiếp tục đóng góp.", "#007bff", "#e1f5fe"
        elif s.get('employee_reactions_given', 0) >= 20:
             archetype, archetype_desc, archetype_color, archetype_bg = "❤️ Người ủng hộ", "Nguồn động viên tuyệt vời.", "#e91e63", "#fce4ec"
        elif s.get('employee_reactions_given', 0) > 0:
             archetype, archetype_desc, archetype_color, archetype_bg = "👀 Người quan sát", "Hãy thử thả tim nhiều hơn.", "#6c757d", "#f8f9fa"
        else:
             archetype, archetype_desc, archetype_color, archetype_bg = "👻 Người ẩn danh", "Hệ thống chưa ghi nhận tương tác.", "#343a40", "#e9ecef"
             
        posts_html = ""
        if latest_posts:
            for post in latest_posts[:3]:
                p_icon = "📰" if post['type'] == 'news' else "📝"
                posts_html += f"""
                <div style="padding: 10px; border-bottom: 1px dashed #e0e0e0; display: flex; align-items: flex-start;">
                    <div style="font-size: 20px; margin-right: 10px;">{p_icon}</div>
                    <div style="flex: 1;">
                        <a href="{post.get('link', '#')}" style="font-weight: 600; color: #2c3e50; text-decoration: none; display: block; margin-bottom: 4px;">{post['title']}</a>
                        <div style="font-size: 12px; color: #888;">👤 {post['author']} • {post['date']} • ❤️ {post['reactions_count']}</div>
                    </div>
                </div>"""
        else:
             posts_html = "<div style='padding:10px; font-style:italic; color:#999'>Chưa có bài viết mới.</div>"
             
        inside_content_box = f"""
        <div class="stats-box inside-box">
            <div style="background-color: {archetype_bg}; padding: 12px; border-radius: 6px; margin-bottom: 15px;">
                <div style="font-weight: 700; color: {archetype_color}; font-size: 15px;">{archetype}</div>
                <div style="font-size: 13px; color: #555;">{archetype_desc}</div>
            </div>
            <div style="display: flex; gap: 15px; margin-bottom: 15px;">
                 <div style="flex: 1; background: #fff; border: 1px solid #eee; border-radius: 6px; padding: 10px; text-align: center;">
                    <div style="font-size: 12px; font-weight: 700; color: #6f42c1; text-transform: uppercase;">📡 Sức lan tỏa</div>
                    <div style="font-size: 24px; font-weight: 700; color: #333;">{s['employee_views']}</div>
                    <div style="font-size: 11px; color: #777;">Lượt xem bài của bạn</div>
                 </div>
                 <div style="flex: 1; background: #fff; border: 1px solid #eee; border-radius: 6px; padding: 10px; text-align: center;">
                    <div style="font-size: 12px; font-weight: 700; color: #e91e63; text-transform: uppercase;">🤝 Sự gắn kết</div>
                    <div style="font-size: 24px; font-weight: 700; color: #333;">{s.get('employee_reactions_given', 0)}</div>
                    <div style="font-size: 11px; color: #777;">Lượt thả tim cho đồng nghiệp</div>
                 </div>
            </div>
            <div style="border-top: 1px solid #eee; padding-top: 15px;">
                <div style="font-weight: 600; color: #444; margin-bottom: 10px; font-size: 14px;">🗞️ Tiêu điểm truyền thông:</div>
                <div style="background: #fff; border: 1px solid #eee; border-radius: 6px;">{posts_html}</div>
            </div>
        </div>
        """
    else:
        inside_content_box = ""

    # --- 5. WORKFLOW SECTION ---
    if workflow_data and workflow_data.get('summary'):
        s = workflow_data['summary']
        stats_ext = workflow_data.get('stats_extended', {})
        latest_jobs = workflow_data['latest_jobs']
        completed_late = stats_ext.get('completed_late_count', 0)
        no_deadline = stats_ext.get('no_deadline_count', 0)
        overdue_jobs = stats_ext.get('overdue_jobs', [])
        upcoming_jobs = stats_ext.get('upcoming_deadline_jobs', [])
        
        completion_rate = s['completion_rate']
        if completion_rate >= 80:
             insight_msg, insight_bg = "🚀 <strong>Tốc độ xử lý Tốt:</strong> Hoàn tất nhanh.", "#e6fffa"
        elif completion_rate >= 50:
             insight_msg, insight_bg = "⚡ <strong>Hoạt động ổn định:</strong> Cần đẩy nhanh.", "#fff3e0"
        else:
             insight_msg, insight_bg = "🐢 <strong>Cần lưu ý:</strong> Tồn đọng nhiều.", "#fff5f5"
             
        upcoming_html = ""
        if upcoming_jobs:
            upcoming_list_items = ""
            for j in upcoming_jobs[:5]:
                days = j.get('days_left', 0)
                day_str = "Hôm nay" if days == 0 else f"{days} ngày nữa"
                upcoming_list_items += f"<div>• <span style='color:#e65100; font-weight:600;'>{j.get('name') or j.get('title')}</span> ({day_str})</div>"
            upcoming_html = f'<li style="margin-top: 10px; background-color: #fff3cd; padding: 8px; border-radius: 4px; border-left: 3px solid #ffc107;"><strong>⚠️ Sắp đến hạn:</strong><div style="font-size: 13px; margin-top: 4px;">{upcoming_list_items}</div></li>'
            
        active_jobs = [job for job in latest_jobs if job.get('stage_metatype') not in ['done', 'failed']]
        jobs_table_html = ""
        if active_jobs:
            jobs_table_html = '<div style="margin-top: 15px; border-top: 1px dashed #ccc; padding-top: 10px;"><div style="font-weight: 600; margin-bottom: 8px; color: #555;">⚙️ Các công việc đang xử lý:</div><table style="width: 100%; border-collapse: collapse; font-size: 13px;"><tr style="background-color: #f0f0f0; text-align: left;"><th style="padding: 6px; border: 1px solid #ddd;">Công việc</th><th style="padding: 6px; border: 1px solid #ddd; width: 120px;">Giai đoạn</th></tr>'
            for job in active_jobs[:10]:
                 jobs_table_html += f'<tr><td style="padding: 6px; border: 1px solid #ddd;"><div style="font-weight: 600; color: #333;">{job.get("title", "")}</div><div style="font-size: 11px; color: #666;">📂 {job.get("workflow_name", "")}</div></td><td style="padding: 6px; border: 1px solid #ddd; text-align: center;">{job.get("stage_name", "")}</td></tr>'
            jobs_table_html += '</table></div>'
            
        workflow_content_box = f"""
        <div class="stats-box workflow-box">
            <div class="sub-header">⚙️ Vận hành & Quy trình (1 tháng gần nhất):</div>
            <ul class="stat-list">
                <li>📋 Tổng quan: <strong>{s['total_jobs']} job</strong> (Done: {s['completion_rate']:.1f}%)</li>
                <li>🏁 Đang xử lý: <strong>{s['doing_jobs']} job</strong> | Hoàn thành muộn: <strong>{completed_late} job</strong></li>
                {upcoming_html}
            </ul>
            {jobs_table_html}
        </div>
        """
    else:
        workflow_content_box = ""

    # --- ASSEMBLY HTML ---
    # Minimal CSS styles inline for portability, based on template
    css_styles = """
    <style>
        body { font-family: -apple-system, system-ui, sans-serif; line-height: 1.6; color: #333; }
        .email-container { max-width: 700px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
        .section { margin-bottom: 30px; }
        .section-title { font-size: 18px; font-weight: bold; border-left: 4px solid #ccc; padding-left: 10px; margin-bottom: 10px; }
        .goal-title { border-color: #ffc107; } .wework-title { border-color: #20c997; }
        .checkin-title { border-color: #17a2b8; } .inside-title { border-color: #6f42c1; }
        .workflow-title { border-color: #fd7e14; }
        .stats-box { background: #fff; border: 1px solid #eee; padding: 15px; border-radius: 6px; }
        .success-box { border-left: 4px solid #28a745; background: #e6f7ec; }
        .warning-box { border-left: 4px solid #dc3545; background: #fff3f3; }
        .wework-box { border-left: 4px solid #20c997; background: #e0f2f1; }
        .checkin-box { border-left: 4px solid #17a2b8; background: #e0f7fa; }
        .inside-box { border-left: 4px solid #6f42c1; background: #f3e5f5; }
        .workflow-box { border-left: 4px solid #fd7e14; background: #fff3e0; }
        .footer-message { background: #eef6f8; padding: 15px; border-radius: 6px; border-left: 4px solid #17a2b8; margin-top: 30px; font-size: 14px; }
    </style>
    """

    main_html = f"""
    <html><head>{css_styles}</head><body>
    <div class="email-container">
        <div style="font-size: 24px; font-weight: bold; color: #004a99; border-bottom: 2px solid #004a99; padding-bottom: 15px; margin-bottom: 20px;">
            📊 BÁO CÁO TỔNG HỢP BASE.VN
        </div>
        <p>Thân gửi Anh/Chị: <strong>{employee_name}</strong></p>
        <p style="font-style: italic; color: #666; font-size: 13px;">Ngày tạo báo cáo: {current_time_str}</p>
        
        {f'<div class="section"><div class="section-title wework-title">🧭 BASE WEWORK</div>{wework_content_box}</div>' if wework_content_box else ''}
        {f'<div class="section"><div class="section-title goal-title">🥇 BASE GOAL</div>{goal_content_box}</div>' if goal_content_box else ''}
        {f'<div class="section"><div class="section-title workflow-title">⚙️ BASE WORKFLOW</div>{workflow_content_box}</div>' if workflow_content_box else ''}
        {f'<div class="section"><div class="section-title checkin-title">⏰ BASE CHECKIN</div>{checkin_content_box}</div>' if checkin_content_box else ''}
        {f'<div class="section"><div class="section-title inside-title">💬 BASE INSIDE</div>{inside_content_box}</div>' if inside_content_box else ''}
        
        <div class="footer-message">
            <strong>💬 THÔNG ĐIỆP TỪ APLUS</strong><br>
            Cảm ơn bạn vì đã hiện diện trọn vẹn...<br>
            Base là "tấm gương số" phản chiếu cách làm việc của chúng ta.
        </div>
    </div>
    </body></html>
    """

    return {
        "full_email_html": main_html,
        "sections": {
            "wework": wework_content_box,
            "goal": goal_content_box,
            "checkin": checkin_content_box,
            "inside": inside_content_box,
            "workflow": workflow_content_box
        }
    }
