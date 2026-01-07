from flask import Flask, request, render_template, send_file, jsonify, redirect, url_for, session
import os
import secrets
import hashlib
from datetime import datetime
from werkzeug.utils import secure_filename
import json

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# تنظیمات
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'zip', 'rar', 'doc', 'docx', 'xls', 'xlsx', 'mp4', 'mp3', 'avi', 'mov'}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
PASSWORD_FILE = 'password.txt'

# ایجاد پوشه‌های لازم
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('data', exist_ok=True)

# فایل برای ذخیره اطلاعات فایل‌ها
FILES_DB = 'data/files.json'

def load_files_db():
    """بارگذاری دیتابیس فایل‌ها"""
    if os.path.exists(FILES_DB):
        with open(FILES_DB, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_files_db(data):
    """ذخیره دیتابیس فایل‌ها"""
    with open(FILES_DB, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_password():
    """بارگذاری پسورد از فایل"""
    if os.path.exists(PASSWORD_FILE):
        with open(PASSWORD_FILE, 'r', encoding='utf-8') as f:
            return f.read().strip()
    return None

def save_password(password):
    """ذخیره پسورد در فایل"""
    with open(PASSWORD_FILE, 'w', encoding='utf-8') as f:
        f.write(password)

def allowed_file(filename):
    """بررسی مجاز بودن پسوند فایل"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_download_link(filename):
    """تولید لینک دانلود یکتا"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    random_str = secrets.token_urlsafe(8)
    file_hash = hashlib.md5(f"{filename}{timestamp}{random_str}".encode()).hexdigest()[:12]
    return f"{file_hash}"

@app.route('/')
def index():
    """صفحه اصلی"""
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    """صفحه آپلود فایل"""
    if request.method == 'GET':
        return render_template('upload.html')
    
    # بررسی پسورد
    password = request.form.get('password')
    stored_password = load_password()
    
    if not stored_password:
        return jsonify({'error': 'لطفاً ابتدا پسورد را تنظیم کنید'}), 400
    
    if password != stored_password:
        return jsonify({'error': 'پسورد اشتباه است'}), 401
    
    # بررسی وجود فایل
    if 'file' not in request.files:
        return jsonify({'error': 'هیچ فایلی انتخاب نشده است'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'هیچ فایلی انتخاب نشده است'}), 400
    
    # بررسی اندازه فایل
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > MAX_FILE_SIZE:
        return jsonify({'error': f'حجم فایل بیشتر از {MAX_FILE_SIZE // (1024*1024)} مگابایت است'}), 400
    
    # بررسی پسوند فایل
    if not allowed_file(file.filename):
        return jsonify({'error': 'نوع فایل مجاز نیست'}), 400
    
    # ذخیره فایل
    filename = secure_filename(file.filename)
    original_filename = filename
    
    # تولید نام یکتا برای فایل
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name_parts = filename.rsplit('.', 1)
    if len(name_parts) == 2:
        unique_filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
    else:
        unique_filename = f"{filename}_{timestamp}"
    
    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(filepath)
    
    # تولید لینک دانلود
    download_link = generate_download_link(unique_filename)
    
    # ذخیره اطلاعات فایل
    files_db = load_files_db()
    files_db[download_link] = {
        'original_filename': original_filename,
        'stored_filename': unique_filename,
        'filepath': filepath,
        'size': file_size,
        'upload_date': datetime.now().isoformat(),
        'download_count': 0
    }
    save_files_db(files_db)
    
    # تولید URL کامل
    base_url = request.host_url.rstrip('/')
    download_url = f"{base_url}/download/{download_link}"
    
    return jsonify({
        'success': True,
        'message': 'فایل با موفقیت آپلود شد',
        'download_link': download_url,
        'filename': original_filename
    })

@app.route('/download/<link>')
def download_file(link):
    """دانلود فایل با لینک"""
    files_db = load_files_db()
    
    if link not in files_db:
        return render_template('error.html', message='لینک دانلود معتبر نیست'), 404
    
    file_info = files_db[link]
    filepath = file_info['filepath']
    original_filename = file_info['original_filename']
    
    # بررسی وجود فایل
    if not os.path.exists(filepath):
        return render_template('error.html', message='فایل یافت نشد'), 404
    
    # افزایش تعداد دانلود
    file_info['download_count'] += 1
    save_files_db(files_db)
    
    return send_file(filepath, as_attachment=True, download_name=original_filename)

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    """تنظیم پسورد (فقط یک بار)"""
    if request.method == 'GET':
        has_password = load_password() is not None
        return render_template('setup.html', has_password=has_password)
    
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    
    if not password:
        return jsonify({'error': 'لطفاً پسورد را وارد کنید'}), 400
    
    if password != confirm_password:
        return jsonify({'error': 'پسوردها یکسان نیستند'}), 400
    
    if len(password) < 4:
        return jsonify({'error': 'پسورد باید حداقل 4 کاراکتر باشد'}), 400
    
    stored_password = load_password()
    if stored_password:
        return jsonify({'error': 'پسورد قبلاً تنظیم شده است'}), 400
    
    save_password(password)
    return jsonify({'success': True, 'message': 'پسورد با موفقیت تنظیم شد'})

@app.route('/change-password', methods=['GET', 'POST'])
def change_password():
    """تغییر پسورد"""
    if request.method == 'GET':
        return render_template('change_password.html')
    
    old_password = request.form.get('old_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    stored_password = load_password()
    
    if not stored_password:
        return jsonify({'error': 'ابتدا باید پسورد را تنظیم کنید'}), 400
    
    if old_password != stored_password:
        return jsonify({'error': 'پسورد قدیمی اشتباه است'}), 401
    
    if not new_password:
        return jsonify({'error': 'لطفاً پسورد جدید را وارد کنید'}), 400
    
    if new_password != confirm_password:
        return jsonify({'error': 'پسوردهای جدید یکسان نیستند'}), 400
    
    if len(new_password) < 4:
        return jsonify({'error': 'پسورد باید حداقل 4 کاراکتر باشد'}), 400
    
    save_password(new_password)
    return jsonify({'success': True, 'message': 'پسورد با موفقیت تغییر کرد'})

@app.route('/files')
def list_files():
    """لیست فایل‌های آپلود شده"""
    files_db = load_files_db()
    files_list = []
    
    for link, info in files_db.items():
        base_url = request.host_url.rstrip('/')
        files_list.append({
            'link': link,
            'download_url': f"{base_url}/download/{link}",
            'filename': info['original_filename'],
            'size': info['size'],
            'upload_date': info['upload_date'],
            'download_count': info.get('download_count', 0)
        })
    
    # مرتب‌سازی بر اساس تاریخ آپلود (جدیدترین اول)
    files_list.sort(key=lambda x: x['upload_date'], reverse=True)
    
    return render_template('files.html', files=files_list)

if __name__ == '__main__':
    # تنظیم پسورد پیش‌فرض اگر وجود ندارد
    if not load_password():
        print("⚠️  توجه: پسورد تنظیم نشده است. لطفاً به /setup بروید و پسورد را تنظیم کنید.")
    
    app.run(host='0.0.0.0', port=5000, debug=True)

