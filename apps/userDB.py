from flask import Flask, render_template, request, redirect, url_for, flash
from flask_mysqldb import MySQL

app = Flask(__name__)
app.secret_key = "mysecretkey"

# MySQL 연결 설정
app.config['MYSQL_HOST'] = 'hometraining-db.cb4mie8sg76i.ap-northeast-2.rds.amazonaws.com'  # 엔드포인트
app.config['MYSQL_PORT'] = 3306  
app.config['MYSQL_USER'] = 'admin'  
app.config['MYSQL_PASSWORD'] = 'ufks6020110'
app.config['MYSQL_DB'] = 'userdb'
app.config['MYSQL_CHARSET'] = 'utf8mb4'

mysql = MySQL(app)

# 루트 경로 → 로그인 페이지 리디렉션
@app.route('/')
def home():
    return redirect(url_for('login'))

# 로그인 화면
@app.route('/login', methods=['GET'])
def login():
    return render_template('Login.html')

# 로그인 처리
@app.route('/login', methods=['POST'])
def login_post():
    user_id = request.form['id']
    password = request.form['password']

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id=%s AND password=%s", (user_id, password))
    user = cur.fetchone()

    if user:
        flash("로그인 성공")
        return redirect(url_for('pickex'))  
    else:
        flash("아이디 또는 비밀번호가 틀렸습니다.")
        return redirect(url_for('login'))

# 운동 선택 페이지
@app.route('/pickex')
def pickex():
    return render_template('PickEX.html')

@app.route("/playex")
def playex():
    return render_template("PlayEX.html")


# 회원가입 화면
@app.route("/signup", methods=['GET'])
def signup():
    return render_template("signUp.html")

# 회원가입 처리
@app.route('/signup', methods=['POST'])
def signup_post():
    user_id = request.form['id']
    name = request.form['name']
    password = request.form['password']
    email = request.form['email']

    if not user_id or not name or not password or not email:
        flash("❗ 모든 항목을 입력하세요.")
        return redirect(url_for('signup'))

    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO users (id, name, password, email) VALUES (%s, %s, %s, %s)",
            (user_id, name, password, email)
        )
        mysql.connection.commit()
        cur.close()
        flash("✅ 회원가입 완료! 로그인해 주세요.")
        return redirect(url_for('login'))
    except Exception as e:
        flash("❌ 회원가입 실패: 이미 존재하는 ID 또는 이름입니다.")
        return redirect(url_for('signup'))

if __name__ == '__main__':
    app.run(debug=True)
