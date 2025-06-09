import pandas as pd
import sqlite3

# Tên file Excel và tên cơ sở dữ liệu
excel_file = 'questions.xlsx'  # Thay bằng tên file Excel của bạn
database_file = 'quiz.db'

# Tên các bảng trong Excel (nếu có nhiều sheet) hoặc tên sheet chứa dữ liệu
questions_sheet = 'Questions'  # Thay bằng tên sheet chứa câu hỏi
options_sheet = 'Options'      # Thay bằng tên sheet chứa đáp án

# Tên bảng trong cơ sở dữ liệu SQLite
questions_table = 'questions'
options_table = 'options'

def init_db(conn):
    cursor = conn.cursor()
    # Tạo bảng quiz_results nếu chưa tồn tại
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
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
    # Tạo bảng preset_configurations số lượng câu hỏi mặc định cho mỗi chủ đề
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS preset_configurations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            preset_name TEXT,
            topic TEXT,
            question_count INTEGER
        )
    ''')
    # Tạo bảng users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT,
            role TEXT
        )
    ''')
    conn.commit()
    print("Đã tạo tất cả các bảng cần thiết trong cơ sở dữ liệu.") # Thêm thông báo này

# Dữ liệu bạn muốn chèn vào preset_configurations
preset_data = [
    (1, 'Doituong2', 'PCRT', 170),
    (2, 'Doituong1', 'PCRT01', 70),
    (3, 'Kien_thuc_chung', 'Đạo đức nghề nghiệp', 3),
    (4, 'Kien_thuc_chung', 'Lễ tân ngoại giao', 3),
    (5, 'Kien_thuc_chung', 'Văn hóa doanh nghiệp', 3),
    (6, 'Kien_thuc_chung', 'Pháp luật liên quan đến hoạt động ngân hàng', 3),
    (7, 'Kien_thuc_chung', 'Công nghệ số trong hoạt động ngân hàng', 3),
    (8, 'Kien_thuc_chung', 'Tín dụng', 3),
    (9, 'Kien_thuc_chung', 'Huy động vốn', 3),
    (10, 'Kien_thuc_chung', 'Ebanking', 3),
    (11, 'Kien_thuc_chung', 'Thẻ', 3),
    (12, 'Kien_thuc_chung', 'Thanh toán trong nước', 3),
    (13, 'Kien_thuc_chung', 'Chuyển tiền trong nước', 3),
    (14, 'Ky_nang_quan_ly', 'Ky_nang_quan_ly', 10),
    (15, 'Kien_thuc_chung', 'Nội quy lao động, an toàn thông tin, elearning', 3),
    (16, 'Kien_thuc_chung', 'Bo_sung_20250607', 3)
]

if __name__ == '__main__':
    try:
        conn = sqlite3.connect(database_file)
        cursor = conn.cursor()

        # --- Đọc dữ liệu từ sheet 'Questions' và tạo bảng 'questions' ---
        try:
            df_questions = pd.read_excel(excel_file, sheet_name=questions_sheet)

            # Cập nhật câu lệnh CREATE TABLE để có PRIMARY KEY
            # Quan trọng: Đảm bảo có một cột ID duy nhất trong Excel để tránh trùng lặp
            # Ví dụ: nếu cột đầu tiên trong Excel là 'QuestionID'
            columns_questions_with_types = []
            for col in df_questions.columns:
                if col == 'QuestionID': # Thay 'QuestionID' bằng tên cột ID thực tế của bạn
                    columns_questions_with_types.append(f"{col} TEXT PRIMARY KEY") # Hoặc INTEGER PRIMARY KEY
                else:
                    columns_questions_with_types.append(f"{col} TEXT") # Hoặc loại dữ liệu phù hợp khác
            create_table_questions_sql = f'''
                CREATE TABLE IF NOT EXISTS {questions_table} ({', '.join(columns_questions_with_types)})
            '''
            cursor.execute(create_table_questions_sql)

            # Thay thế INSERT INTO bằng INSERT OR IGNORE INTO để tránh trùng lặp
            placeholders_questions = ', '.join(['?'] * len(df_questions.columns))
            insert_sql = f'''
                INSERT OR IGNORE INTO {questions_table} ({', '.join(df_questions.columns)}) VALUES ({placeholders_questions})
            '''
            for row in df_questions.itertuples(index=False):
                cursor.execute(insert_sql, tuple(row))
            conn.commit()
            print(f"Đã tạo và nhập dữ liệu vào bảng '{questions_table}' thành công (tránh trùng lặp).")
        except Exception as e:
            print(f"Lỗi khi xử lý sheet '{questions_sheet}': {e}")
            conn.rollback()

        # --- Đọc dữ liệu từ sheet 'Options' và tạo bảng 'options' ---
        try:
            df_options = pd.read_excel(excel_file, sheet_name=options_sheet)

            # Cập nhật câu lệnh CREATE TABLE để có PRIMARY KEY
            # Quan trọng: Đảm bảo có một cột ID duy nhất trong Excel cho các option (ví dụ OptionID, hoặc kết hợp QuestionID và OptionText)
            columns_options_with_types = []
            for col in df_options.columns:
                if col == 'OptionID': # Thay 'OptionID' bằng tên cột ID thực tế của bạn
                    columns_options_with_types.append(f"{col} TEXT PRIMARY KEY")
                elif col == 'QuestionID': # Nếu QuestionID cũng có trong bảng options
                    columns_options_with_types.append(f"{col} TEXT")
                else:
                    columns_options_with_types.append(f"{col} TEXT") # Hoặc loại dữ liệu phù hợp khác
            create_table_options_sql = f'''
                CREATE TABLE IF NOT EXISTS {options_table} ({', '.join(columns_options_with_types)})
            '''
            cursor.execute(create_table_options_sql)

            # Thay thế INSERT INTO bằng INSERT OR IGNORE INTO để tránh trùng lặp
            placeholders_options = ', '.join(['?'] * len(df_options.columns))
            insert_sql = f'''
                INSERT OR IGNORE INTO {options_table} ({', '.join(df_options.columns)}) VALUES ({placeholders_options})
            '''
            for row in df_options.itertuples(index=False):
                cursor.execute(insert_sql, tuple(row))
            conn.commit()
            print(f"Đã tạo và nhập dữ liệu vào bảng '{options_table}' thành công (tránh trùng lặp).")
        except Exception as e:
            print(f"Lỗi khi xử lý sheet '{options_sheet}': {e}")
            conn.rollback()

        # Phần 2: Khởi tạo các bảng quiz_results, quiz_question_details, preset_configurations, users
        try:
            init_db(conn) # Truyền đối tượng kết nối vào init_db

            # Chèn dữ liệu vào bảng preset_configurations (tránh trùng lặp theo id)
            insert_preset_sql = '''
                INSERT OR IGNORE INTO preset_configurations (id, preset_name, topic, question_count)
                VALUES (?, ?, ?, ?)
            '''
            cursor.executemany(insert_preset_sql, preset_data)
            conn.commit()
            print("Đã chèn dữ liệu vào bảng 'preset_configurations' thành công.")

        except Exception as e:
            print(f"Lỗi khi khởi tạo hoặc chèn dữ liệu vào cơ sở dữ liệu: {e}")
            conn.rollback()
        finally:
            conn.close()
            print("Đã đóng kết nối đến cơ sở dữ liệu.")

    except Exception as e:
        print(f"Đã xảy ra lỗi tổng thể trong quá trình kết nối hoặc xử lý file Excel: {e}")
