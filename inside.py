import requests
import re
from html import unescape
from datetime import datetime
import pytz

# Constants
INSIDE_API_KEY = "5654-KPE2LVMMXMGD856BQQXM87UXZW6CW8JZYW7HCHQPAKQHT3TH8R4RHGVHXCN7BNU3-CQMWCET7LQWX6KK66PPACVKEZ8MUPYUGKK7RBZXELB5CESLYR42L6FUEBW3LCGBA"
ACCOUNT_ACCESS_TOKEN = "5654-YSF4AEQETWWP9PQS6ZGM5S5UUEYDG8C4DTTW66AFYA5RBQQR3W4CPWWH97N5XF6E-XWJ22ZYFDPXKU4PJVDM3JC9ZVKPT2DKBQ8R57CBFMF3G8JKZAF7GESQNVZCEAR39"

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

def clean_html(text):
    """Loại bỏ HTML tags và decode HTML entities"""
    if not text:
        return ""
    text = unescape(text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def convert_inside_link(inside_link):
    """Chuyển đổi link từ base-inside:// sang https://inside.base.vn"""
    if not inside_link:
        return ""
    # Chuyển từ base-inside://news/... sang https://inside.base.vn/news/...
    if inside_link.startswith('base-inside://'):
        return inside_link.replace('base-inside://', 'https://inside.base.vn/')
    return inside_link

def get_all_news_and_articles(max_pages=10):
    """Lấy tất cả news và articles từ Inside API"""
    all_items = []
    
    # Lấy news
    print("   📰 Đang tải news...")
    page = 1
    while page <= max_pages:
        url = f"https://inside.base.vn/extapi/v2/companynews/get?access_token={INSIDE_API_KEY}&page={page}"
        try:
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                break
            
            data = response.json()
            if data.get('code') != 1 or not data.get('news'):
                break
            
            news_list = data.get('news', [])
            if not news_list:
                break
            
            # Thêm type để phân biệt
            for news in news_list:
                news['item_type'] = 'news'
            all_items.extend(news_list)
            print(f"      Trang {page}: {len(news_list)} news")
            
            if len(news_list) < 20:
                break
            page += 1
        except Exception as e:
            print(f"      ⚠️ Lỗi khi lấy news trang {page}: {e}")
            break
    
    # Lấy articles
    print("   📄 Đang tải articles...")
    page = 1
    while page <= max_pages:
        url = f"https://inside.base.vn/extapi/v2/articles/get?access_token={INSIDE_API_KEY}&page={page}"
        try:
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                break
            
            data = response.json()
            if data.get('code') != 1 or not data.get('updates'):
                break
            
            articles_list = data.get('updates', [])
            if not articles_list:
                break
            
            # Thêm type để phân biệt
            for article in articles_list:
                article['item_type'] = 'article'
            all_items.extend(articles_list)
            print(f"      Trang {page}: {len(articles_list)} articles")
            
            if len(articles_list) < 20:
                break
            page += 1
        except Exception as e:
            print(f"      ⚠️ Lỗi khi lấy articles trang {page}: {e}")
            break
    
    return all_items

def get_inside_data(employee_name, limit=5):
    """Lấy dữ liệu Inside - bài viết gần nhất"""
    try:
        print(f"\n🔄 Đang tải dữ liệu Inside cho {employee_name}...")
        
        # Tải user mapping nếu chưa có
        if not user_id_to_name_map:
            load_user_mapping()
        
        # Lấy tất cả bài viết (news + articles) từ nhiều trang
        all_items = get_all_news_and_articles(max_pages=50)
        
        if not all_items:
            print("⚠️ Không có dữ liệu bài viết từ Inside")
            return None
        
        # Sắp xếp tất cả bài viết theo thời gian (mới nhất trước)
        all_items.sort(key=lambda x: int(x.get('since', 0) or 0), reverse=True)
        
        # Lấy top N bài viết gần nhất để hiển thị
        latest_items = all_items[:limit]
        
        # Tính toán thống kê
        total_posts = len(all_items)
        total_reactions = 0
        total_views = 0
        
        # Đếm bài viết của nhân viên này (nếu có)
        employee_posts = 0
        employee_reactions_received = 0
        employee_views_received = 0
        employee_reactions_given = 0
        employee_views_given = 0
        
        # Tìm user_id của nhân viên từ mapping
        employee_user_id = None
        for uid, name in user_id_to_name_map.items():
            if name == employee_name:
                employee_user_id = uid
                break
        
        if not employee_user_id:
            print(f"⚠️ Không tìm thấy user_id cho nhân viên: {employee_name}")
            # Vẫn tiếp tục để hiển thị thống kê chung
        
        # Chuẩn bị các biến để so sánh user_id (theo nhiều cách như check_inside_user.py)
        employee_user_id_str = str(employee_user_id) if employee_user_id else None
        employee_user_id_int = int(employee_user_id) if employee_user_id and str(employee_user_id).isdigit() else None
        
        for item in all_items:
            # Đếm reactions
            reactions = item.get('reactions', [])
            total_reactions += len(reactions)
            
            # Đếm views
            seens = item.get('seens', [])
            total_views += len(seens)
            
            # Kiểm tra bài viết của nhân viên (so sánh theo nhiều cách)
            if employee_user_id:
                item_user_id = item.get('user_id')
                item_user_id_str = str(item_user_id) if item_user_id is not None else ''
                item_user_id_int = int(item_user_id) if item_user_id is not None and str(item_user_id).isdigit() else None
                
                # So sánh theo nhiều cách để đảm bảo tìm đúng
                match = False
                if item_user_id_str == employee_user_id_str:
                    match = True
                elif employee_user_id_int and item_user_id_int == employee_user_id_int:
                    match = True
                
                if match:
                    employee_posts += 1
                    employee_reactions_received += len(reactions)
                    employee_views_received += len(seens)
            
            # Đếm reactions và views mà nhân viên đã cho (tương tác với bài viết của người khác)
            if employee_user_id:
                # Đếm reactions đã cho
                for reaction in reactions:
                    reactor_id = str(reaction.get('user_id', ''))
                    if reactor_id == employee_user_id_str or (employee_user_id_int and reactor_id.isdigit() and int(reactor_id) == employee_user_id_int):
                        employee_reactions_given += 1
                
                # Đếm views đã cho
                for seen_id in seens:
                    seen_id_str = str(seen_id)
                    if seen_id_str == employee_user_id_str or (employee_user_id_int and seen_id_str.isdigit() and int(seen_id_str) == employee_user_id_int):
                        employee_views_given += 1
        
        # Chuẩn bị danh sách bài viết gần nhất để hiển thị
        latest_posts_info = []
        for item in latest_items:
            # Lấy và chuyển đổi link
            inside_link = item.get('link', '')
            web_link = convert_inside_link(inside_link)
            
            # Lấy tên bài viết (có thể là 'name' cho cả news và articles)
            title = item.get('name', 'Không có tiêu đề')
            
            post_info = {
                'title': title,
                'author': get_user_name(item.get('user_id')),
                'date': timestamp_to_hcm(item.get('since', '0')) if item.get('since') else 'N/A',
                'content_preview': clean_html(item.get('content', ''))[:150] + '...' if len(clean_html(item.get('content', ''))) > 150 else clean_html(item.get('content', '')),
                'reactions_count': len(item.get('reactions', [])),
                'views_count': len(item.get('seens', [])),
                'link': web_link,
                'type': item.get('item_type', 'unknown')  # 'news' hoặc 'article'
            }
            latest_posts_info.append(post_info)
        
        print(f"📊 Thống kê Inside:")
        print(f"   - Tổng bài viết: {total_posts}")
        print(f"   - Bài viết của nhân viên: {employee_posts}")
        print(f"   - Reactions nhận được: {employee_reactions_received}")
        print(f"   - Views nhận được: {employee_views_received}")
        print(f"   - Reactions đã cho: {employee_reactions_given}")
        print(f"   - Views đã cho: {employee_views_given}")
        
        return {
            'summary': {
                'total_posts': total_posts,
                'total_reactions': total_reactions,
                'total_views': total_views,
                'employee_posts': employee_posts,
                'employee_reactions': employee_reactions_received,  # Reactions nhận được
                'employee_views': employee_views_received,  # Views nhận được
                'employee_reactions_given': employee_reactions_given,  # Reactions đã cho
                'employee_views_given': employee_views_given  # Views đã cho
            },
            'latest_posts': latest_posts_info
        }
    except Exception as e:
        print(f"❌ Lỗi khi lấy dữ liệu Inside: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    data = get_inside_data("Nguyen Van A")
    if data:
        print(data)
