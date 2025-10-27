from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file, Response
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import csv
import io

app = Flask(__name__)
app.secret_key = 'library_secret_key_change_this'

DB = 'library.db'

def get_db_connection():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    conn = get_db_connection()
    books = conn.execute('SELECT * FROM books WHERE available = 1').fetchall()
    conn.close()
    return render_template('index.html', books=books)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        register_type = request.form.get('register_type')
        conn = get_db_connection()

        if register_type == 'librarian':
            fullname = request.form['fullname']
            username = request.form['username']
            password = request.form['password']
            
            if not username or not password or not fullname:
                flash("All fields required for Librarian registration.")
                conn.close()
                return redirect(url_for('register'))
                
            pw_hash = generate_password_hash(password)
            try:
                conn.execute('INSERT INTO users (fullname, username, password, role) VALUES (?, ?, ?, ?)',
                             (fullname, username, pw_hash, 'librarian'))
                conn.commit()
                flash("Librarian account created. Please login.")
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash("Username already taken.")
                return redirect(url_for('register'))
            finally:
                conn.close()

        elif register_type == 'student':
            fullname = request.form['fullname']
            student_number = request.form['student_number'].strip()
            course = request.form['course']

            if not fullname or not student_number or not course:
                flash("All fields required for student registration.")
                conn.close()
                return redirect(url_for('register'))

            lastname = fullname.split()[-1] if fullname.split() else ''
            
            try:
                conn.execute('INSERT INTO students (fullname, lastname, student_number, course) VALUES (?, ?, ?, ?)', 
                             (fullname, lastname, student_number, course))
                conn.commit()
                flash(f"Student account created for {fullname}. Your login key is your Last Name: **{lastname}**. Please login.")
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                flash("Student Number is already registered.")
                return redirect(url_for('register'))
            finally:
                conn.close()

        else:
            flash("Please select a registration type.")
            return redirect(url_for('register'))
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login_type = request.form.get('login_type')

        if login_type == 'librarian':
            username = request.form['username']
            password = request.form['password']
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE username = ? AND role = "librarian"', (username,)).fetchone()
            conn.close()

            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = 'librarian'
                flash("Logged in successfully as Librarian.")
                return redirect(url_for('librarian_dashboard'))
            else:
                flash("Invalid Librarian credentials.")
                return redirect(url_for('login'))

        elif login_type == 'student':
            student_number = request.form['student_number'].strip()
            lastname = request.form['lastname'].strip()
            conn = get_db_connection()
            student = conn.execute(
                'SELECT * FROM students WHERE student_number = ? AND lastname = ?',
                (student_number, lastname)
            ).fetchone()
            conn.close()

            if student:
                session['student_id'] = student['id']
                session['student_fullname'] = student['fullname']
                session['role'] = 'student'
                flash(f"Welcome, {student['fullname']}!")
                return redirect(url_for('student_dashboard'))
            else:
                flash("Invalid Student ID or Last Name.")
                return redirect(url_for('login'))
        else:
            flash("Please select a login type.")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for('index'))

@app.route('/student') 
def student_dashboard():
    if 'student_id' not in session or session.get('role') != 'student':
        flash("Please login as student.")
        return redirect(url_for('login'))

    student_id = session['student_id']
    conn = get_db_connection()
    available = conn.execute('SELECT * FROM books WHERE available = 1').fetchall()
    borrowed = conn.execute('''
        SELECT br.*, b.title, b.author FROM borrow_records br
        JOIN books b ON br.book_id = b.id
        WHERE br.student_id = ? AND br.return_date IS NULL
    ''', (student_id,)).fetchall() 
    conn.close()
    return render_template('user_dashboard.html', available=available, borrowed=borrowed)

@app.route('/borrow/<int:book_id>', methods=['POST'])
def borrow_book(book_id):
    if 'student_id' not in session or session.get('role') != 'student':
        flash("Login as student to borrow.")
        return redirect(url_for('login'))

    student_id = session['student_id'] 
    borrow_date = datetime.now()
    due_date = borrow_date + timedelta(days=7)

    conn = get_db_connection()
    book = conn.execute('SELECT * FROM books WHERE id = ? AND available = 1', (book_id,)).fetchone()

    if not book:
        flash("Book not available.")
        conn.close()
        return redirect(url_for('student_dashboard'))

    conn.execute('INSERT INTO borrow_records (student_id, book_id, borrow_date, due_date) VALUES (?, ?, ?, ?)',
                 (student_id, book_id, borrow_date.isoformat(), due_date.isoformat())) 
    conn.execute('UPDATE books SET available = 0 WHERE id = ?', (book_id,))
    conn.commit()
    conn.close()

    flash(f"Book borrowed: {book['title']}. Due in 7 days.")
    return redirect(url_for('student_dashboard'))

@app.route('/return/<int:record_id>', methods=['POST'])
def return_book(record_id):
    if 'student_id' not in session or session.get('role') != 'student':
        flash("Login as student to return.")
        return redirect(url_for('login'))

    student_id = session['student_id'] 
    conn = get_db_connection()
    rec = conn.execute('SELECT * FROM borrow_records WHERE id = ? AND student_id = ?', (record_id, student_id)).fetchone()
    if not rec:
        flash("Record not found.")
        conn.close()
        return redirect(url_for('student_dashboard'))

    if rec['return_date']:
        flash("Already returned.")
        conn.close()
        return redirect(url_for('student_dashboard'))

    return_date = datetime.now()
    due = datetime.fromisoformat(rec['due_date'])
    penalty = 0
    if return_date > due:
        days_late = (return_date - due).days
        penalty = days_late * 5.0

    conn.execute('UPDATE borrow_records SET return_date = ?, penalty = ? WHERE id = ?',
                 (return_date.isoformat(), penalty, record_id))
    conn.execute('UPDATE books SET available = 1 WHERE id = ?', (rec['book_id'],))
    conn.commit()
    conn.close()

    flash(f"Book returned. Penalty ₱{penalty:.2f}")
    return redirect(url_for('student_dashboard'))

@app.route('/my_history')
def my_history():
    if 'student_id' not in session:
        flash("Login to view history.")
        return redirect(url_for('login'))

    student_id = session['student_id']
    conn = get_db_connection()
    records = conn.execute('''
        SELECT br.*, b.title, b.author FROM borrow_records br
        JOIN books b ON br.book_id = b.id
        WHERE br.student_id = ?
        ORDER BY br.borrow_date DESC
    ''', (student_id,)).fetchall() 
    conn.close()
    return render_template('history.html', records=records)

@app.route('/search', methods=['GET', 'POST'])
def search():
    results = []
    q = ''
    if request.method == 'POST':
        q = request.form['keyword']
        conn = get_db_connection()
        results = conn.execute("SELECT * FROM books WHERE title LIKE ? OR author LIKE ?", ('%'+q+'%', '%'+q+'%')).fetchall()
        conn.close()
    return render_template('search.html', books=results, q=q)

@app.route('/librarian') 
def librarian_dashboard():
    if 'user_id' not in session or session.get('role') != 'librarian': 
        flash("Librarian login required.") 
        return redirect(url_for('login'))
    conn = get_db_connection()
    total_books = conn.execute('SELECT COUNT(*) as c FROM books').fetchone()['c']
    total_students = conn.execute('SELECT COUNT(*) as c FROM students').fetchone()['c']
    total_borrows = conn.execute('SELECT COUNT(*) as c FROM borrow_records').fetchone()['c']
    conn.close()
    return render_template('admin_dashboard.html', total_books=total_books,
                           total_students=total_students, total_borrows=total_borrows)

@app.route('/librarian/books') 
def librarian_books():
    if session.get('role') != 'librarian': 
        flash("Librarian only.") 
        return redirect(url_for('login'))
    conn = get_db_connection()
    books = conn.execute('SELECT * FROM books').fetchall()
    conn.close()
    return render_template('admin_books.html', books=books)

@app.route('/librarian/books/add', methods=['POST']) 
def librarian_add_book():
    if session.get('role') != 'librarian': 
        flash("Librarian only.") 
        return redirect(url_for('login'))
    title = request.form['title']
    author = request.form['author']
    conn = get_db_connection()
    conn.execute('INSERT INTO books (title, author, available) VALUES (?, ?, 1)', (title, author))
    conn.commit()
    conn.close()
    flash("Book added.")
    return redirect(url_for('librarian_books')) 

@app.route('/librarian/books/edit/<int:id>', methods=['GET', 'POST']) 
def librarian_edit_book(id):
    if session.get('role') != 'librarian': 
        flash("Librarian only.") 
        return redirect(url_for('login'))
    conn = get_db_connection()
    if request.method == 'POST':
        conn.execute('UPDATE books SET title = ?, author = ?, available = ? WHERE id = ?',
                     (request.form['title'], request.form['author'], int(request.form.get('available',1)), id))
        conn.commit()
        conn.close()
        flash("Book updated.")
        return redirect(url_for('librarian_books')) 
    book = conn.execute('SELECT * FROM books WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('admin_edit_book.html', book=book)

@app.route('/librarian/books/delete/<int:id>', methods=['POST']) 
def librarian_delete_book(id):
    if session.get('role') != 'librarian': 
        flash("Librarian only.") 
        return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM books WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Book deleted.")
    return redirect(url_for('librarian_books')) 

@app.route('/librarian/students') 
def librarian_students():
    if session.get('role') != 'librarian': 
        flash("Librarian only.") 
        return redirect(url_for('login'))
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('admin_students.html', students=students)

@app.route('/librarian/students/add', methods=['POST']) 
def librarian_add_student():
    if session.get('role') != 'librarian': 
        flash("Librarian only.") 
        return redirect(url_for('login'))
    fullname = request.form['fullname']
    lastname = fullname.split()[-1] if fullname.split() else ''
    sn = request.form['student_number']
    course = request.form['course']
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO students (fullname, lastname, student_number, course) VALUES (?, ?, ?, ?)', (fullname, lastname, sn, course))
        conn.commit()
        flash(f"Student {fullname} added. Login Last Name is: {lastname}.")
    except sqlite3.IntegrityError:
        flash("Student Number already exists.")
    conn.close()
    return redirect(url_for('librarian_students')) 

@app.route('/librarian/students/edit/<int:id>', methods=['GET', 'POST']) 
def librarian_edit_student(id):
    if session.get('role') != 'librarian': 
        flash("Librarian only.") 
        return redirect(url_for('login'))
    conn = get_db_connection()
    if request.method == 'POST':
        fullname = request.form['fullname']
        lastname = fullname.split()[-1] if fullname.split() else ''
        conn.execute('UPDATE students SET fullname = ?, lastname = ?, student_number = ?, course = ? WHERE id = ?',
                     (fullname, lastname, request.form['student_number'], request.form['course'], id))
        conn.commit()
        conn.close()
        flash(f"Student updated. Login Last Name is: {lastname}.")
        return redirect(url_for('librarian_students')) 
    student = conn.execute('SELECT * FROM students WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('admin_edit_student.html', student=student)

@app.route('/librarian/students/delete/<int:id>', methods=['POST']) 
def librarian_delete_student(id):
    if session.get('role') != 'librarian': 
        flash("Librarian only.") 
        return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM students WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Student deleted.")
    return redirect(url_for('librarian_students')) 

@app.route('/librarian/borrow_records') 
def librarian_borrow_records():
    if session.get('role') != 'librarian': 
        flash("Librarian only.") 
        return redirect(url_for('login'))
    conn = get_db_connection()
    records = conn.execute('''
        SELECT br.*, s.fullname, b.title FROM borrow_records br
        JOIN students s ON br.student_id = s.id -- Changed from users u on user_id
        JOIN books b ON br.book_id = b.id
        ORDER BY br.borrow_date DESC
    ''').fetchall()
    conn.close()
    return render_template('admin_borrow_records.html', records=records)

@app.route('/librarian/borrow_records/edit/<int:id>', methods=['GET', 'POST']) 
def librarian_edit_borrow(id):
    if session.get('role') != 'librarian': 
        flash("Librarian only.") 
        return redirect(url_for('login'))
    conn = get_db_connection()
    if request.method == 'POST':
        return_date = request.form.get('return_date') or None
        penalty = float(request.form.get('penalty') or 0)
        conn.execute('UPDATE borrow_records SET return_date = ?, penalty = ? WHERE id = ?', (return_date, penalty, id))
        rec = conn.execute('SELECT * FROM borrow_records WHERE id = ?', (id,)).fetchone()
        if return_date:
            conn.execute('UPDATE books SET available = 1 WHERE id = ?', (rec['book_id'],))
        conn.commit()
        conn.close()
        flash("Record updated.")
        return redirect(url_for('librarian_borrow_records')) 
    rec = conn.execute('SELECT br.*, s.fullname, b.title FROM borrow_records br JOIN students s ON br.student_id=s.id JOIN books b ON br.book_id=b.id WHERE br.id = ?', (id,)).fetchone() # Updated JOIN
    conn.close()
    return render_template('admin_edit_borrow.html', rec=rec)

@app.route('/librarian/borrow_records/delete/<int:id>', methods=['POST']) 
def librarian_delete_borrow(id):
    if session.get('role') != 'librarian': 
        flash("Librarian only.") 
        return redirect(url_for('login'))
    conn = get_db_connection()
    rec = conn.execute('SELECT * FROM borrow_records WHERE id = ?', (id,)).fetchone()
    if rec and not rec['return_date']:
        conn.execute('UPDATE books SET available = 1 WHERE id = ?', (rec['book_id'],))
    conn.execute('DELETE FROM borrow_records WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Borrow record deleted.")
    return redirect(url_for('librarian_borrow_records')) 

@app.route('/librarian/penalties') 
def librarian_penalties():
    if session.get('role') != 'librarian':
        flash("Librarian only.") 
        return redirect(url_for('login'))
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT br.*, s.fullname, b.title FROM borrow_records br
        JOIN students s ON br.student_id = s.id -- Changed from users u on user_id
        JOIN books b ON br.book_id = b.id
        WHERE br.penalty > 0 AND (br.return_date IS NOT NULL)
    ''').fetchall()
    conn.close()
    return render_template('admin_penalties.html', rows=rows)

@app.route('/librarian/reports') 
def librarian_reports():
    if session.get('role') != 'librarian': 
        flash("Librarian only.") 
        return redirect(url_for('login'))
    conn = get_db_connection()
    total_books = conn.execute('SELECT COUNT(*) c FROM books').fetchone()['c']
    borrowed = conn.execute('SELECT COUNT(*) c FROM borrow_records WHERE return_date IS NULL').fetchone()['c']
    returned = conn.execute('SELECT COUNT(*) c FROM borrow_records WHERE return_date IS NOT NULL').fetchone()['c']
    conn.close()
    return render_template('admin_reports.html', total_books=total_books, borrowed=borrowed, returned=returned)

@app.route('/librarian/reports/download') 
def librarian_reports_download():
    if session.get('role') != 'librarian': 
        flash("Librarian only.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT br.id, s.fullname, b.title, br.borrow_date, br.due_date, br.return_date, br.penalty
        FROM borrow_records br
        JOIN students s ON br.student_id = s.id -- Changed from users u on user_id
        JOIN books b ON br.book_id = b.id
    ''').fetchall()
    conn.close()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['id','student_name','title','borrow_date','due_date','return_date','penalty'])
    for r in rows:
        cw.writerow([r['id'], r['fullname'], r['title'], r['borrow_date'], r['due_date'], r['return_date'], r['penalty']])
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=borrow_report.csv"})

if __name__ == '__main__':
    app.run(debug=True)
