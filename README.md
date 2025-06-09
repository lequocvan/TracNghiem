1. Download, setup Python
Cài đặt thành công Python trên Windows 11 thì sẽ là pip3 ; python 3

2. Cài đặt thêm thư viện, mở ứng dụng cmd và lần lượt từng lệnh sau, chạy trên cmd:
Pip3 install flask
Pip3 install pytz
Pip3 install db-sqlite3
Pip3 install pandas
Pip3 install openpyxl
Pip3 install flask-bcrypt
Pip3 install flask_login

3. Thư mục TracNghiem_PCRT (topic) như hình nhé. ()
Nhấn 2 lần chuột trái chạy tập tin app có thông báo như sau, thì cho minimize xuống nhé.

Mở trình duyệt (Chrome; Edge; …) gõ địa chỉ sau: http://localhost:5000/ hoặc http://127.0.0.1:5000/ 
để ôn tập kiểm tra trắc nghiệm

File cơ sở dữ liệu sqlite (.db) tôi tạo sẵn rồi nhé. Nhưng không public lên đây vì vậy bạn phải tự tạo quiz.db nhé

Sau 36 giây sẽ tự động hiển thị đáp án đúng và chuyển câu tiếp theo.
Hoặc là bạn chọn câu trả lời, nhấn tiếp theo thì đúng sẽ màu xanh, chưa đúng thì hiển thị đáp án đúng…

Tạo thư mục TracNghiem tại C: =>  Copy toàn bộ file vào thư mục TracNghiem
Trong thư mục TracNghiem có các files (quiz.db; app.py) và thư mục con là templates (trong đó có các tập tin *.html)
Dùng file [Tu file excel questions tao CSDL quiz_db.py] và [questions.xlsx] chạy trên python tạo ra quiz.db nhé!!!!!
