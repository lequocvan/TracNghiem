from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
import random
import sqlite3
import json
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import pandas as pd
import io
import datetime
import pytz

HANOI_TZ = pytz.timezone('Asia/Ho_Chi_Minh') # Hanoi's timezone

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here' # Rất quan trọng! Thay thế bằng một chuỗi ngẫu nhiên, khó đoán
# Bạn có thể tạo secret key bằng cách: import os; os.urandom(24)

# Khởi tạo Bcrypt
bcrypt = Bcrypt(app)

# Khởi tạo Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Đặt tên hàm view cho trang đăng nhập

DATABASE = 'quiz.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Để truy cập cột theo tên
    return conn

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

# User Model cho Flask-Login
class User(UserMixin):
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password # Password đã được hash
        # Bạn có thể thêm các thuộc tính khác như email, roles, v.v.

    @staticmethod
    def get(user_id):
        conn = get_db()
        user_data = conn.execute("SELECT id, username, password FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if user_data:
            return User(user_data['id'], user_data['username'], user_data['password'])
        return None

    @staticmethod
    def get_by_username(username):
        conn = get_db()
        user_data = conn.execute("SELECT id, username, password FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        if user_data:
            return User(user_data['id'], user_data['username'], user_data['password'])
        return None

# Hàm tải người dùng cho Flask-Login
@login_manager.user_loader
def load_user(user_id):
    user_data = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if user_data:
        return User(user_data['id'], user_data['username'], user_data['password'])
    return None

# --- Routes cho Đăng ký, Đăng nhập, Đăng xuất ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated: # Nếu đã đăng nhập, chuyển hướng về trang chủ
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8') # Băm mật khẩu

        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
            conn.commit()
            flash("Đăng ký thành công! Vui lòng đăng nhập.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Tên người dùng đã tồn tại. Vui lòng chọn tên khác.", "danger")
        except sqlite3.Error as e:
            flash(f"Lỗi cơ sở dữ liệu: {e}", "danger")
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: # Nếu đã đăng nhập, chuyển hướng về trang chủ
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_data = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)

        if user_data and bcrypt.check_password_hash(user_data['password'], password):
            user = User(user_data['id'], user_data['username'], user_data['password'])
            login_user(user) # Đăng nhập người dùng
            flash("Đăng nhập thành công!", "success")
            next_page = request.args.get('next') # Chuyển hướng đến trang mà người dùng muốn truy cập trước đó
            return redirect(next_page or url_for('index'))
        else:
            flash("Tên đăng nhập hoặc mật khẩu không đúng.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user() # Đăng xuất người dùng
    flash("Bạn đã đăng xuất.", "info")
    return redirect(url_for('index'))

@app.route('/admin/get_all_quiz_results', methods=['GET'])
def get_all_quiz_results():
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, player_name, score, total_questions, percentage, time_taken, timestamp FROM quiz_results ORDER BY timestamp DESC")
        results = cursor.fetchall()
        
        formatted_results = []
        for row in results:
            row_dict = dict(row)
            # Chuyển đổi chuỗi timestamp từ SQLite sang đối tượng datetime
            if row_dict['timestamp']:
                dt_object_utc = datetime.datetime.strptime(row_dict['timestamp'], '%Y-%m-%d %H:%M:%S')
                dt_object_utc = pytz.utc.localize(dt_object_utc)
                dt_object_hanoi = dt_object_utc.astimezone(HANOI_TZ)
                row_dict['timestamp_formatted'] = dt_object_hanoi.strftime('%d-%m-%Y %H:%M:%S') 
            else:
                row_dict['timestamp_formatted'] = 'N/A' # Xử lý trường hợp timestamp bị null
            formatted_results.append(row_dict)
            
        return jsonify(formatted_results)
    except sqlite3.Error as e:
        print(f"Lỗi cơ sở dữ liệu khi lấy tất cả kết quả bài kiểm tra: {e}")
        return jsonify({"error": f"Lỗi cơ sở dữ liệu: {e}"}), 500
    finally:
        conn.close()

@app.route('/admin/get_quiz_details/<int:quiz_result_id>', methods=['GET'])
def get_quiz_details(quiz_result_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT question_id, question_text, user_answer, correct_answer, is_correct, time_spent_on_question
            FROM quiz_question_details
            WHERE quiz_result_id = ?
            ORDER BY id ASC
        """, (quiz_result_id,))
        details = cursor.fetchall()
        return jsonify([dict(row) for row in details])
    except sqlite3.Error as e:
        print(f"Lỗi cơ sở dữ liệu khi lấy chi tiết bài kiểm tra: {e}")
        return jsonify({"error": f"Lỗi cơ sở dữ liệu: {e}"}), 500
    finally:
        conn.close()

@app.route('/admin/quiz_results_management')
def admin_quiz_results_management():
    return render_template('admin_quiz_results.html')

#admin: Lay tat ca chu de topic
@app.route('/admin/topics', methods=['GET'])

def admin_get_topics():
    try:
        topics = get_topics_from_db()
        return jsonify(topics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/topics/<topic_name>', methods=['DELETE'])
def admin_delete_topic(topic_name):
    conn = get_db()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN TRANSACTION;")

        # Lấy IDs của các câu hỏi thuộc chủ đề này
        question_ids_to_delete = cursor.execute("SELECT id FROM questions WHERE topic = ?", (topic_name,)).fetchall()
        question_ids = [q['id'] for q in question_ids_to_delete]

        if question_ids:
            # Xóa các options liên quan
            placeholders = ','.join(['?'] * len(question_ids))
            cursor.execute(f"DELETE FROM options WHERE question_id IN ({placeholders})", tuple(question_ids))
            # Xóa các câu hỏi
            cursor.execute("DELETE FROM questions WHERE topic = ?", (topic_name,))

        # Xóa các cấu hình preset liên quan
        cursor.execute("DELETE FROM preset_configurations WHERE topic = ?", (topic_name,))
        # Xóa chủ đề
        cursor.execute("DELETE FROM topics WHERE name = ?", (topic_name,))

        conn.commit()
        return jsonify({"message": f"Chủ đề '{topic_name}' và các câu hỏi, options, preset liên quan đã được xóa thành công."})
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Lỗi SQLite khi xóa chủ đề: {e}")
        return jsonify({"error": f"Lỗi cơ sở dữ liệu: {e}"}), 500
    finally:
        conn.close()

@app.route('/admin/questions', methods=['GET'])
def admin_get_questions():
    try:
        questions = get_all_questions() # Hàm này đã có, trả về tất cả câu hỏi với options
        return jsonify([dict(row) for row in questions])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/questions', methods=['POST'])
def admin_add_question():
    data = request.get_json()
    question_text = data.get('question_text')
    correct_answer = data.get('correct_answer')
    topic = data.get('topic')
    options_text = data.get('options') # Mảng các chuỗi option

    if not all([question_text, correct_answer, topic, options_text]):
        return jsonify({"error": "Vui lòng cung cấp đầy đủ thông tin câu hỏi, đáp án đúng, chủ đề và các lựa chọn."}), 400

    if correct_answer not in options_text:
        return jsonify({"error": "Đáp án đúng phải nằm trong danh sách các lựa chọn."}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor.execute("INSERT INTO questions (question_text, correct_answer, topic) VALUES (?, ?, ?)",
                       (question_text, correct_answer, topic))
        question_id = cursor.lastrowid

        for option_text in options_text:
            cursor.execute("INSERT INTO options (question_id, option_text) VALUES (?, ?)",
                           (question_id, option_text))

        conn.commit()
        return jsonify({"message": "Câu hỏi đã được thêm thành công!", "question_id": question_id}), 201
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Lỗi SQLite khi thêm câu hỏi: {e}")
        return jsonify({"error": f"Lỗi cơ sở dữ liệu: {e}"}), 500
    finally:
        conn.close()

@app.route('/admin/questions/<int:question_id>', methods=['PUT'])

def admin_update_question(question_id):
    data = request.get_json()
    question_text = data.get('question_text')
    correct_answer = data.get('correct_answer')
    topic = data.get('topic')
    options_text = data.get('options') # Mảng các chuỗi option

    if not all([question_text, correct_answer, topic, options_text]):
        return jsonify({"error": "Vui lòng cung cấp đầy đủ thông tin câu hỏi, đáp án đúng, chủ đề và các lựa chọn."}), 400

    if correct_answer not in options_text:
        return jsonify({"error": "Đáp án đúng phải nằm trong danh sách các lựa chọn."}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN TRANSACTION;")
        # Cập nhật thông tin câu hỏi
        cursor.execute("UPDATE questions SET question_text = ?, correct_answer = ?, topic = ? WHERE id = ?",
                       (question_text, correct_answer, topic, question_id))

        # Xóa tất cả các lựa chọn cũ
        cursor.execute("DELETE FROM options WHERE question_id = ?", (question_id,))

        # Thêm các lựa chọn mới
        for option_text in options_text:
            cursor.execute("INSERT INTO options (question_id, option_text) VALUES (?, ?)",
                           (question_id, option_text))

        conn.commit()
        return jsonify({"message": f"Câu hỏi ID {question_id} đã được cập nhật thành công!"})
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Lỗi SQLite khi cập nhật câu hỏi: {e}")
        return jsonify({"error": f"Lỗi cơ sở dữ liệu: {e}"}), 500
    finally:
        conn.close()

@app.route('/admin/questions/<int:question_id>', methods=['DELETE'])

def admin_delete_question(question_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor.execute("DELETE FROM options WHERE question_id = ?", (question_id,))
        cursor.execute("DELETE FROM questions WHERE id = ?", (question_id,))
        conn.commit()
        return jsonify({"message": f"Câu hỏi ID {question_id} đã được xóa thành công."})
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Lỗi SQLite khi xóa câu hỏi: {e}")
        return jsonify({"error": f"Lỗi cơ sở dữ liệu: {e}"}), 500
    finally:
        conn.close()

@app.route('/admin/presets', methods=['POST'])

def admin_add_update_preset():
    data = request.get_json()
    preset_name = data.get('preset_name')
    topic = data.get('topic')
    question_count = data.get('question_count')

    if not all([preset_name, topic, question_count is not None]):
        return jsonify({"error": "Vui lòng cung cấp tên preset, chủ đề và số lượng câu hỏi."}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        # Kiểm tra xem cấu hình đã tồn tại chưa để UPDATE hoặc INSERT
        cursor.execute("SELECT id FROM preset_configurations WHERE preset_name = ? AND topic = ?", (preset_name, topic))
        existing_config = cursor.fetchone()

        if existing_config:
            cursor.execute("UPDATE preset_configurations SET question_count = ? WHERE id = ?", (question_count, existing_config['id']))
            message = "Cấu hình preset đã được cập nhật!"
        else:
            cursor.execute("INSERT INTO preset_configurations (preset_name, topic, question_count) VALUES (?, ?, ?)",
                           (preset_name, topic, question_count))
            message = "Cấu hình preset đã được thêm mới!"

        conn.commit()
        return jsonify({"message": message}), 201
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Lỗi SQLite khi thêm/cập nhật preset: {e}")
        return jsonify({"error": f"Lỗi cơ sở dữ liệu: {e}"}), 500
    finally:
        conn.close()

@app.route('/admin/presets', methods=['DELETE'])

def admin_delete_preset_config():
    data = request.get_json()
    preset_name = data.get('preset_name')
    topic = data.get('topic')

    if not all([preset_name, topic]):
        return jsonify({"error": "Vui lòng cung cấp tên preset và chủ đề để xóa."}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM preset_configurations WHERE preset_name = ? AND topic = ?", (preset_name, topic))
        if cursor.rowcount > 0:
            conn.commit()
            return jsonify({"message": "Cấu hình preset đã được xóa thành công!"})
        else:
            conn.rollback()
            return jsonify({"error": "Không tìm thấy cấu hình preset để xóa."}), 404
    except sqlite3.Error as e:
        conn.rollback()
        print(f"Lỗi SQLite khi xóa preset: {e}")
        return jsonify({"error": f"Lỗi cơ sở dữ liệu: {e}"}), 500
    finally:
        conn.close()


# --- NEW: CSV/XLSX Import Routes ---
@app.route('/admin/import_questions', methods=['POST'])
def import_questions():
    if 'file' not in request.files:
        return jsonify({"error": "Không tìm thấy file trong request."}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Không có file nào được chọn."}), 400

    if file:
        try:
            # Đọc file vào DataFrame
            file_extension = file.filename.rsplit('.', 1)[1].lower()
            if file_extension == 'csv':
                df = pd.read_csv(io.StringIO(file.stream.read().decode('utf-8')))
            elif file_extension in ['xls', 'xlsx']:
                # Đọc toàn bộ nội dung file vào một đối tượng BytesIO
                file_content = file.stream.read()
                df = pd.read_excel(io.BytesIO(file_content))
            else:
                return jsonify({"error": "Định dạng file không được hỗ trợ. Chỉ chấp nhận CSV hoặc XLSX."}), 400

            # Kiểm tra các cột cần thiết (ví dụ: 'question_text', 'correct_answer', 'topic', 'options')
            required_columns = ['question_text', 'correct_answer', 'topic', 'options']
            if not all(col in df.columns for col in required_columns):
                missing = [col for col in required_columns if col not in df.columns]
                return jsonify({"error": f"File thiếu các cột bắt buộc: {', '.join(missing)}. Các cột cần có: {', '.join(required_columns)}"}), 400

            conn = get_db()
            cursor = conn.cursor()
            imported_count = 0
            errors = []

            for index, row in df.iterrows():
                try:
                    question_text = str(row['question_text']).strip()
                    correct_answer = str(row['correct_answer']).strip()
                    topic = str(row['topic']).strip()
                    options_str = str(row['options']).strip() # 'Option1#Option2#Option3'

                    # Chuyển đổi chuỗi options thành list
                    # Lọc bỏ các option rỗng hoặc chỉ chứa khoảng trắng
                    options = [opt.strip() for opt in options_str.split('#') if opt.strip()]

                    if not question_text or not correct_answer or not topic or not options:
                        errors.append(f"Hàng {index+2} bị bỏ qua do thiếu thông tin: {row.to_dict()}")
                        continue

                    if correct_answer not in options:
                        errors.append(f"Hàng {index+2}: Đáp án đúng '{correct_answer}' không có trong danh sách lựa chọn: {options_str}. Bỏ qua hàng này.")
                        continue

                    # Bắt đầu giao dịch cho mỗi hàng để nếu có lỗi thì không ảnh hưởng đến các hàng khác
                    # Hoặc bạn có thể dùng một transaction lớn bên ngoài vòng lặp
                    # conn.execute("BEGIN TRANSACTION;") # Nếu muốn transaction cho toàn bộ file
                    cursor.execute("INSERT INTO questions (question_text, correct_answer, topic) VALUES (?, ?, ?)",
                                   (question_text, correct_answer, topic))
                    question_id = cursor.lastrowid

                    for option_text in options:
                        cursor.execute("INSERT INTO options (question_id, option_text) VALUES (?, ?)",
                                       (question_id, option_text))
                    conn.commit() # Commit từng hàng, hoặc chuyển ra ngoài vòng lặp
                    imported_count += 1
                except Exception as row_error:
                    conn.rollback() # Nếu commit từng hàng
                    errors.append(f"Lỗi khi xử lý hàng {index+2} ({row.to_dict()}): {row_error}")

            # conn.commit() # Nếu dùng transaction lớn
            conn.close()

            if errors:
                return jsonify({
                    "message": f"Đã nhập {imported_count} câu hỏi thành công. Có lỗi xảy ra với {len(errors)} hàng:",
                    "errors": errors
                }), 200 # Trả về 200 nếu vẫn có câu hỏi được nhập thành công, kèm lỗi
            else:
                return jsonify({"message": f"Đã nhập thành công {imported_count} câu hỏi."}), 200

        except Exception as e:
            print(f"Lỗi khi nhập file: {e}")
            return jsonify({"error": f"Lỗi khi xử lý file: {e}"}), 500


# Admin Routes for serving HTML pages
@app.route('/admin')
def admin_index():
    return render_template('admin_index.html')

@app.route('/admin/questions_management')
def admin_questions_management():
    return render_template('admin_questions.html')

@app.route('/admin/topics_management')
def admin_topics_management():
    return render_template('admin_topics.html')

@app.route('/admin/presets_management')
def admin_presets_management():
    return render_template('admin_presets.html')

# New API endpoint to get all preset configurations (for admin_presets.html)
@app.route('/admin/get_all_presets_full', methods=['GET'])
def get_all_presets_full():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT preset_name, topic, question_count FROM preset_configurations ORDER BY preset_name, topic")
        rows = cursor.fetchall()
        # Convert Row objects to dictionaries
        presets = [dict(row) for row in rows]
        return jsonify(presets)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"error": "Lỗi cơ sở dữ liệu khi lấy tất cả cấu hình preset"}), 500
    finally:
        conn.close()


def get_topics_from_db():
    conn = get_db()
    topics_data = query_db("SELECT DISTINCT topic FROM questions")
    conn.close()
    return [row['topic'] for row in topics_data]

# Modified to accept a single topic and limit, or multiple topics if needed with different query
def get_questions_by_topic(topic, limit):
    query = """
        SELECT questions.id, questions.question_text, questions.correct_answer, questions.topic,
               GROUP_CONCAT(options.option_text, '|||') AS options
        FROM questions
        JOIN options ON questions.id = options.question_id
        WHERE questions.topic = ?
        GROUP BY questions.id
        ORDER BY RANDOM()
        LIMIT ?
    """
    return query_db(query, (topic, limit))

def get_all_questions():
    query = """
        SELECT questions.id, questions.question_text, questions.correct_answer, questions.topic,
               GROUP_CONCAT(options.option_text, '|||') AS options
        FROM questions
        JOIN options ON questions.id = options.question_id
        GROUP BY questions.id
        ORDER BY questions.id ASC
    """
    return query_db(query)

def get_options(question_id):
    return query_db("SELECT option_text FROM options WHERE question_id = ?", (question_id,))

def get_random_questions(num_questions):
    questions = query_db("SELECT id, question_text, correct_answer FROM questions")
    if num_questions > len(questions):
        num_questions = len(questions)
    return random.sample(questions, num_questions)

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()
    conn.close()
    return render_template('index.html')    # return render_template('index.html', topics=topics, presets=presets)

@app.route('/get_topics')
def get_topics():
    topics = get_topics_from_db()
    return jsonify(topics)

@app.route('/get_all_preset_names', methods=['GET'])
def get_all_preset_names():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT preset_name FROM preset_configurations")
        rows = cursor.fetchall()
        preset_names = [row['preset_name'] for row in rows]
        return jsonify(preset_names)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"error": "Lỗi cơ sở dữ liệu khi lấy tên preset"}), 500
    finally:
        conn.close()
        
@app.route('/get_preset_70a_5b_5c_5d_config', methods=['GET'])
def get_preset_70a_5b_5c_5d_config():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        # Truy vấn bảng cấu hình preset mới
        cursor.execute("SELECT topic, question_count FROM preset_configurations WHERE preset_name = 'Doituong2' OR preset_name = 'Kien_thuc_chung'")
        rows = cursor.fetchall()
        preset_data = {row['topic']: row['question_count'] for row in rows}
        return jsonify(preset_data)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"error": "Lỗi cơ sở dữ liệu khi lấy cấu hình Doituong2 và Kien_thuc_chung"}), 500
    finally:
        conn.close()

@app.route('/get_Doituong1_config', methods=['GET'])
def get_Doituong1_config():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT topic, question_count FROM preset_configurations WHERE preset_name = 'Doituong1' OR preset_name = 'Kien_thuc_chung' OR preset_name = 'Ky_nang_quan_ly'")
        rows = cursor.fetchall()
        preset_data = {row['topic']: row['question_count'] for row in rows}
        return jsonify(preset_data)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"error": "Lỗi cơ sở dữ liệu khi lấy cấu hình Doituong1"}), 500
    finally:
        conn.close()

@app.route('/update_topic', methods=['POST'])
def update_topic():
    try:
        data = request.get_json()
        old_topic = data.get('old_topic')
        new_topic = data.get('new_topic')

        if not old_topic or not new_topic:
            return jsonify({"error": "Vui lòng cung cấp cả tên topic cũ và mới."}), 400

        conn = get_db()
        cursor = conn.cursor()

        # Bắt đầu một giao dịch (transaction) để đảm bảo tính nhất quán
        conn.execute("BEGIN TRANSACTION;")

        try:
            # Cập nhật bảng questions
            cursor.execute("UPDATE questions SET topic = ? WHERE topic = ?", (new_topic, old_topic))
            questions_updated = cursor.rowcount

            # Cập nhật bảng preset_configurations
            cursor.execute("UPDATE preset_configurations SET topic = ? WHERE topic = ?", (new_topic, old_topic))
            presets_updated = cursor.rowcount

            conn.commit() # Hoàn thành giao dịch

            return jsonify({
                "message": "Cập nhật topic thành công!",
                "questions_updated": questions_updated,
                "presets_updated": presets_updated
            })

        except sqlite3.Error as e:
            conn.rollback() # Hoàn tác giao dịch nếu có lỗi
            print(f"Lỗi SQLite khi cập nhật topic: {e}")
            return jsonify({"error": f"Lỗi cơ sở dữ liệu khi cập nhật topic: {e}"}), 500
        finally:
            conn.close()

    except Exception as e:
        print(f"Lỗi chung khi cập nhật topic: {e}")
        return jsonify({"error": f"Lỗi không xác định: {e}"}), 400

@app.route('/start_quiz', methods=['POST'])
def start_quiz():
    print("request.form:", request.form)
    print("request.data:", request.data)
    try:
        data = request.get_json()
        num_questions_requested = int(data['num_questions']) # Changed variable name for clarity
        selected_topics_counts = data['topics']

        all_questions = []
        conn = get_db()
        cursor = conn.cursor()

        # Fetch questions for explicitly selected topics
        for topic, count in selected_topics_counts.items():
            questions = get_questions_by_topic(topic, count)
            all_questions.extend([dict(row) for row in questions])

        # If more questions are needed to reach num_questions_requested
        if len(all_questions) < num_questions_requested:
            remaining_needed = num_questions_requested - len(all_questions)
            topics_already_selected = list(selected_topics_counts.keys())
            
            # Get all topics and filter out those already selected
            all_available_topics = get_topics_from_db()
            remaining_topics = [topic for topic in all_available_topics if topic not in topics_already_selected]

            if remaining_topics:
                # Fetch random questions from remaining topics to fill the gap
                # Use a single query for multiple topics to get random questions
                placeholders = ','.join(['?'] * len(remaining_topics))
                query = f"""
                    SELECT q.id, q.question_text, q.topic, q.correct_answer,
                           GROUP_CONCAT(o.option_text, '|||') AS options
                    FROM questions q
                    JOIN options o ON q.id = o.question_id
                    WHERE q.topic IN ({placeholders})
                    GROUP BY q.id
                    ORDER BY RANDOM()
                    LIMIT ?
                """
                # Combine topic names with the limit for the query arguments
                cursor.execute(query, tuple(remaining_topics) + (remaining_needed,))
                remaining_questions = cursor.fetchall()
                all_questions.extend([dict(row) for row in remaining_questions])
            
        conn.close()

        # Ensure the final list of questions does not exceed num_questions_requested
        # and is randomized
        if len(all_questions) > num_questions_requested:
            all_questions = random.sample(all_questions, num_questions_requested)
        # If still less than requested, it's fine, return what's available

        return jsonify(all_questions)
    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 400 # Return the actual error message for debugging

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    answers = request.get_json()
    score = 0
    results = [] # Thêm một danh sách để lưu kết quả chi tiết
    for answer in answers:
        question_id = answer['question_id']
        selected_answer = answer['selected_answer']
        question_data = query_db("SELECT correct_answer, question_text FROM questions WHERE id = ?", (question_id,), one=True)

        if question_data:
            correct_answer = question_data['correct_answer']
            question_text = question_data['question_text'] # Lấy nội dung câu hỏi
            is_correct = (selected_answer == correct_answer)
            if is_correct:
                score += 1
            results.append({
                'question_id': question_id,
                'selected_answer': selected_answer,
                'correct_answer': correct_answer, # Trả về đáp án đúng
                'is_correct': is_correct,
                'question_text': question_text # Trả về nội dung câu hỏi
            })
    return jsonify({'score': score, 'total': len(answers), 'results': results}) # Trả về results

def init_db():
    with app.app_context():
        conn = get_db()
        cursor = conn.cursor()
        # Tạo bảng quiz_results nếu chưa tồn tại
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name TEXT NOT NULL,
                score INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                percentage REAL NOT NULL,
                time_taken INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Tạo bảng quiz_question_details để lưu chi tiết từng câu hỏi
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quiz_question_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                quiz_result_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                user_answer TEXT,
                correct_answer TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                time_spent_on_question INTEGER, -- Thời gian làm câu hỏi này
                FOREIGN KEY (quiz_result_id) REFERENCES quiz_results (id)
            )
        ''')
        conn.commit()


# Thêm hàm mới để lưu kết quả bài kiểm tra
@app.route('/save_quiz_result', methods=['POST'])
def save_quiz_result():
    data = request.get_json()
    player_name = data.get('player_name')
    score = data.get('score')
    total_questions = data.get('total_questions')
    percentage = data.get('percentage')
    time_taken = data.get('time_taken')
    # Thêm trường mới để nhận chi tiết từng câu hỏi
    question_details = data.get('question_details')

    if not all([player_name, score is not None, total_questions is not None, percentage is not None, time_taken is not None, question_details is not None]):
        return jsonify({"error": "Vui lòng cung cấp đầy đủ thông tin kết quả bài kiểm tra và chi tiết câu hỏi."}), 400

    conn = get_db()
    cursor = conn.cursor()
    try:
        conn.execute("BEGIN TRANSACTION;") # Bắt đầu transaction

        # Lưu kết quả tổng quan vào bảng quiz_results
        cursor.execute(
            "INSERT INTO quiz_results (player_name, score, total_questions, percentage, time_taken) VALUES (?, ?, ?, ?, ?)",
            (player_name, score, total_questions, percentage, time_taken)
        )
        quiz_result_id = cursor.lastrowid # Lấy ID của bản ghi vừa mới INSERT

        # Lưu chi tiết từng câu hỏi vào bảng quiz_question_details
        for detail in question_details:
            cursor.execute(
                "INSERT INTO quiz_question_details (quiz_result_id, question_id, question_text, user_answer, correct_answer, is_correct, time_spent_on_question) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (quiz_result_id, detail['question_id'], detail['question_text'], detail['user_answer'], detail['correct_answer'], detail['is_correct'], detail['time_spent_on_question'])
            )

        conn.commit() # Commit transaction nếu tất cả đều thành công
        return jsonify({"message": "Kết quả bài kiểm tra và chi tiết đã được lưu thành công!", "quiz_result_id": quiz_result_id}), 201
    except sqlite3.Error as e:
        conn.rollback() # Rollback nếu có lỗi
        print(f"Lỗi SQLite khi lưu kết quả bài kiểm tra hoặc chi tiết câu hỏi: {e}")
        return jsonify({"error": f"Lỗi cơ sở dữ liệu: {e}"}), 500

if __name__ == '__main__':
    # init_db() # Đảm bảo gọi hàm này khi ứng dụng chạy lần đầu để tạo bảng
    app.run(debug=True)
