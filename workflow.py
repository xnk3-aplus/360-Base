import requests
import json
import pytz
from datetime import datetime
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# Constants
WORKFLOW_ACCESS_TOKEN = os.getenv('WORKFLOW_ACCESS_TOKEN')
ACCOUNT_ACCESS_TOKEN = os.getenv('ACCOUNT_ACCESS_TOKEN')

hcm_tz = pytz.timezone('Asia/Ho_Chi_Minh')

# Global variable for user mapping
user_id_to_name_map = {}

# Token detection helpers
def get_account_auth_data():
    """Get authentication data dict with correct key for token v1 or v2"""
    key = "access_token_v2" if "~" in ACCOUNT_ACCESS_TOKEN else "access_token"
    return {key: ACCOUNT_ACCESS_TOKEN}

def get_workflow_auth_data():
    """Get authentication data dict for workflow API"""
    key = "access_token_v2" if "~" in WORKFLOW_ACCESS_TOKEN else "access_token"
    return {key: WORKFLOW_ACCESS_TOKEN}

def load_user_mapping():
    """Tải user mapping từ Account API và lưu vào biến global"""
    global user_id_to_name_map
    try:
        url = "https://account.base.vn/extapi/v1/users/get_list"
        payload = get_account_auth_data()
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

def get_user_name(user_id):
    """Lấy tên user từ user_id"""
    if not user_id:
        return 'N/A'
    return user_id_to_name_map.get(str(user_id), f"User_{user_id}")

def timestamp_to_hcm(timestamp_str):
    """Chuyển đổi timestamp sang datetime HCM"""
    try:
        timestamp = int(timestamp_str)
        dt = datetime.fromtimestamp(timestamp, tz=pytz.UTC)
        dt_hcm = dt.astimezone(hcm_tz)
        return dt_hcm.strftime('%d/%m/%Y %H:%M:%S')
    except:
        return 'N/A'

def get_workflow_data(employee_name, limit=10):
    """Lấy dữ liệu Workflow - công việc gần nhất"""
    try:
        print(f"\n🔄 Đang tải dữ liệu Workflow cho {employee_name}...")
        
        # Tải user mapping nếu chưa có
        if not user_id_to_name_map:
            load_user_mapping()
        
        # Tìm user_id của nhân viên từ mapping
        employee_user_id = None
        for uid, name in user_id_to_name_map.items():
            if name == employee_name:
                employee_user_id = uid
                break
        
        if not employee_user_id:
            print(f"⚠️ Không tìm thấy user_id cho nhân viên: {employee_name}")
            return None
        
        # Lấy dữ liệu từ API Workflow với pagination
        url = "https://workflow.base.vn/extapi/v1/jobs/get"
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        all_jobs = []
        current_page_id = 0
        max_pages = 10
        
        while current_page_id < max_pages:
            payload = {
                **get_workflow_auth_data(),
                'page_id': current_page_id
            }
            
            try:
                response = requests.post(url, headers=headers, data=payload, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get('code') == 1 and 'jobs' in data:
                    jobs_on_page = data.get('jobs', [])
                    if jobs_on_page:
                        all_jobs.extend(jobs_on_page)
                        current_page_id += 1
                    else:
                        break
                else:
                    break
            except Exception as e:
                print(f"⚠️ Lỗi khi lấy trang {current_page_id}: {e}")
                break
        
        if not all_jobs:
            print("⚠️ Không có dữ liệu công việc từ Workflow")
            return None
        
        # Lọc các công việc của nhân viên (theo user_id)
        employee_jobs = []
        for job in all_jobs:
            job_user_id = str(job.get('user_id', ''))
            if job_user_id == str(employee_user_id):
                employee_jobs.append(job)
        
        if not employee_jobs:
            print(f"⚠️ Không có công việc nào của nhân viên {employee_name}")
            return None
        
        # Sắp xếp theo thời gian tạo (mới nhất trước)
        employee_jobs.sort(key=lambda x: int(x.get('since', 0) or 0), reverse=True)
        
        # Lấy top N công việc gần nhất
        latest_jobs = employee_jobs[:limit]
        
        # Tính toán thống kê cơ bản
        total_jobs = len(employee_jobs)
        done_jobs = sum(1 for job in employee_jobs if job.get('status') == 'done' or job.get('state') == 'done')
        doing_jobs = total_jobs - done_jobs
        
        # --- TÍNH TOÁN CÁC CHỈ SỐ MỞ RỘNG (Similar to WeWork) ---
        now_ts = datetime.now().timestamp()
        
        # 1. Completed Late (Hoàn thành muộn)
        completed_late_count = 0
        done_job_list = [job for job in employee_jobs if job.get('status') == 'done' or job.get('state') == 'done']
        for job in done_job_list:
            deadline = job.get('deadline')
            finish_at = job.get('finish_at')
            if deadline and finish_at and str(deadline) != '0' and str(finish_at) != '0':
                try:
                    if float(finish_at) > float(deadline):
                        completed_late_count += 1
                except:
                    pass
        
        # 2. Active jobs (jobs đang làm)
        active_jobs = [job for job in employee_jobs if job.get('status') != 'done' and job.get('state') != 'done']
        
        # 3. No Deadline (Không có deadline) - Chỉ tính các job đang làm
        no_deadline_count = 0
        for job in active_jobs:
            deadline = job.get('deadline')
            if not deadline or str(deadline) == '0':
                no_deadline_count += 1
        
        # 4. Overdue Jobs (Quá hạn) - Job chưa xong và deadline < now
        overdue_jobs = []
        for job in active_jobs:
            deadline = job.get('deadline')
            if deadline and str(deadline) != '0':
                try:
                    if float(deadline) < now_ts:
                        # Xử lý workflow_name
                        workflow_export = job.get('workflow_export', 'N/A')
                        if isinstance(workflow_export, dict):
                            workflow_name = workflow_export.get('name', 'N/A')
                        elif isinstance(workflow_export, str) and workflow_export:
                            try:
                                import json
                                wf_dict = json.loads(workflow_export)
                                workflow_name = wf_dict.get('name', 'N/A')
                            except:
                                workflow_name = workflow_export
                        else:
                            workflow_name = 'N/A'
                        
                        job['workflow_name'] = workflow_name
                        overdue_jobs.append(job)
                except:
                    pass
        
        # Sắp xếp overdue jobs theo deadline (cũ nhất lên đầu)
        overdue_jobs.sort(key=lambda x: float(x.get('deadline', 0)))
        
        # 5. Upcoming Deadlines (Sắp đến hạn) - Job chưa xong và deadline trong 7 ngày tới
        upcoming_deadline_jobs = []
        for job in active_jobs:
            deadline = job.get('deadline')
            if deadline and str(deadline) != '0':
                try:
                    dl_ts = float(deadline)
                    if now_ts <= dl_ts <= now_ts + 7 * 86400:
                        days_left = (dl_ts - now_ts) / 86400
                        job['days_left'] = max(0, int(days_left))
                        
                        # Xử lý workflow_name
                        workflow_export = job.get('workflow_export', 'N/A')
                        if isinstance(workflow_export, dict):
                            workflow_name = workflow_export.get('name', 'N/A')
                        elif isinstance(workflow_export, str) and workflow_export:
                            try:
                                import json
                                wf_dict = json.loads(workflow_export)
                                workflow_name = wf_dict.get('name', 'N/A')
                            except:
                                workflow_name = workflow_export
                        else:
                            workflow_name = 'N/A'
                        
                        job['workflow_name'] = workflow_name
                        upcoming_deadline_jobs.append(job)
                except:
                    pass
        
        upcoming_deadline_jobs.sort(key=lambda x: float(x.get('deadline', 0)))
        
        # Chuẩn bị danh sách công việc gần nhất để hiển thị
        latest_jobs_info = []
        for job in latest_jobs:
            # Xử lý workflow_name
            workflow_export = job.get('workflow_export', 'N/A')
            if isinstance(workflow_export, dict):
                workflow_name = workflow_export.get('name', 'N/A')
            elif isinstance(workflow_export, str) and workflow_export:
                workflow_name = workflow_export
            else:
                workflow_name = 'N/A'
            
            # Xử lý stage_name và stage_metatype từ stage_export
            stage_export = job.get('stage_export', {})
            stage_name = None
            stage_metatype = None
            if isinstance(stage_export, dict):
                stage_name = stage_export.get('name')
                stage_metatype = stage_export.get('metatype')
            elif isinstance(stage_export, str) and stage_export:
                try:
                    import json
                    stage_dict = json.loads(stage_export)
                    stage_name = stage_dict.get('name')
                    stage_metatype = stage_dict.get('metatype')
                except:
                    pass
            
            job_info = {
                'title': job.get('name') or job.get('title', 'Không có tiêu đề'),
                'status': job.get('status') or job.get('state', 'N/A'),
                'creator': get_user_name(job.get('creator_id')),
                'date': timestamp_to_hcm(job.get('since', '0')) if job.get('since') else 'N/A',
                'deadline': timestamp_to_hcm(job.get('deadline', '0')) if job.get('deadline') else 'N/A',
                'workflow_name': workflow_name,
                'stage_name': stage_name or 'N/A',
                'stage_metatype': stage_metatype or 'N/A'
            }
            latest_jobs_info.append(job_info)
        
        print(f"📊 Kết quả phân tích Workflow (Mở rộng):")
        print(f"   - Tổng jobs: {total_jobs}")
        print(f"   - Hoàn thành muộn: {completed_late_count}")
        print(f"   - Không deadline: {no_deadline_count}")
        print(f"   - Quá hạn: {len(overdue_jobs)}")
        print(f"   - Sắp đến hạn: {len(upcoming_deadline_jobs)}")
        
        raw_df_records = pd.DataFrame(employee_jobs).astype(str).to_dict(orient="records") if employee_jobs else []

        return {
            'summary': {
                'total_jobs': total_jobs,
                'done_jobs': done_jobs,
                'doing_jobs': doing_jobs,
                'pending_jobs': 0,
                'completion_rate': (done_jobs / total_jobs * 100) if total_jobs > 0 else 0
            },
            'latest_jobs': latest_jobs_info,
            'stats_extended': {
                'completed_late_count': completed_late_count,
                'no_deadline_count': no_deadline_count,
                'overdue_jobs': overdue_jobs,
                'upcoming_deadline_jobs': upcoming_deadline_jobs
            },
            'raw_df_records': raw_df_records
        }
    except Exception as e:
        print(f"❌ Lỗi khi lấy dữ liệu Workflow: {e}")
        return None

if __name__ == "__main__":
    data = get_workflow_data("Nguyen Van A")
    if data:
        print(data)
