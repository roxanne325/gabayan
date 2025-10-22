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
        fullname = request.form['fullname']
        username = request.form['username']
        password = request.form['password']
        if not username or not password:
            flash("Username and password required.")
            return redirect(url_for('register'))
        pw_hash = generate_password_hash(password)
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (fullname, username, password, role) VALUES (?, ?, ?, ?)',
                         (fullname, username, pw_hash, 'user'))
            conn.commit()
            flash("Account created. Please login.")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already taken.")
            return redirect(url_for('register'))
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash("Logged in successfully.")
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash("Invalid credentials.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for('index'))

@app.route('/user')
def user_dashboard():
    if 'user_id' not in session or session.get('role') != 'user':
        flash("Please login as user.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    available = conn.execute('SELECT * FROM books WHERE available = 1').fetchall()
    borrowed = conn.execute('''
        SELECT br.*, b.title, b.author FROM borrow_records br
        JOIN books b ON br.book_id = b.id
        WHERE br.user_id = ? AND br.return_date IS NULL
    ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('user_dashboard.html', available=available, borrowed=borrowed)

@app.route('/borrow/<int:book_id>', methods=['POST'])
def borrow_book(book_id):
    if 'user_id' not in session or session.get('role') != 'user':
        flash("Login as user to borrow.")
        return redirect(url_for('login'))
    user_id = session['user_id']
    borrow_date = datetime.now()
    due_date = borrow_date + timedelta(days=7)  
    conn = get_db_connection()
    book = conn.execute('SELECT * FROM books WHERE id = ? AND available = 1', (book_id,)).fetchone()
    if not book:
        flash("Book not available.")
        conn.close()
        return redirect(url_for('user_dashboard'))
    conn.execute('INSERT INTO borrow_records (user_id, book_id, borrow_date, due_date) VALUES (?, ?, ?, ?)',
                 (user_id, book_id, borrow_date.isoformat(), due_date.isoformat()))
    conn.execute('UPDATE books SET available = 0 WHERE id = ?', (book_id,))
    conn.commit()
    conn.close()

    flash(f"Book borrowed: {book['title']}. Due in 7 days.")
    return redirect(url_for('user_dashboard'))

@app.route('/return/<int:record_id>', methods=['POST'])
def return_book(record_id):
    if 'user_id' not in session or session.get('role') != 'user':
        flash("Login as user to return.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    rec = conn.execute('SELECT * FROM borrow_records WHERE id = ? AND user_id = ?', (record_id, session['user_id'])).fetchone()
    if not rec:
        flash("Record not found.")
        conn.close()
        return redirect(url_for('user_dashboard'))
    if rec['return_date']:
        flash("Already returned.")
        conn.close()
        return redirect(url_for('user_dashboard'))
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
    return redirect(url_for('user_dashboard'))

@app.route('/my_history')
def my_history():
    if 'user_id' not in session:
        flash("Login to view history.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    records = conn.execute('''
        SELECT br.*, b.title, b.author FROM borrow_records br
        JOIN books b ON br.book_id = b.id
        WHERE br.user_id = ?
        ORDER BY br.borrow_date DESC
    ''', (session['user_id'],)).fetchall()
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

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Admin login required.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    total_books = conn.execute('SELECT COUNT(*) as c FROM books').fetchone()['c']
    total_students = conn.execute('SELECT COUNT(*) as c FROM students').fetchone()['c']
    total_borrows = conn.execute('SELECT COUNT(*) as c FROM borrow_records').fetchone()['c']
    conn.close()
    return render_template('admin_dashboard.html', total_books=total_books,
                           total_students=total_students, total_borrows=total_borrows)

@app.route('/admin/books')
def admin_books():
    if session.get('role') != 'admin':
        flash("Admin only.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    books = conn.execute('SELECT * FROM books').fetchall()
    conn.close()
    return render_template('admin_books.html', books=books)

@app.route('/admin/books/add', methods=['POST'])
def admin_add_book():
    if session.get('role') != 'admin':
        flash("Admin only.")
        return redirect(url_for('login'))
    title = request.form['title']
    author = request.form['author']
    conn = get_db_connection()
    conn.execute('INSERT INTO books (title, author, available) VALUES (?, ?, 1)', (title, author))
    conn.commit()
    conn.close()
    flash("Book added.")
    return redirect(url_for('admin_books'))

@app.route('/admin/books/edit/<int:id>', methods=['GET', 'POST'])
def admin_edit_book(id):
    if session.get('role') != 'admin':
        flash("Admin only.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    if request.method == 'POST':
        conn.execute('UPDATE books SET title = ?, author = ?, available = ? WHERE id = ?',
                     (request.form['title'], request.form['author'], int(request.form.get('available',1)), id))
        conn.commit()
        conn.close()
        flash("Book updated.")
        return redirect(url_for('admin_books'))
    book = conn.execute('SELECT * FROM books WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('admin_edit_book.html', book=book)

@app.route('/admin/books/delete/<int:id>', methods=['POST'])
def admin_delete_book(id):
    if session.get('role') != 'admin':
        flash("Admin only.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM books WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Book deleted.")
    return redirect(url_for('admin_books'))

@app.route('/admin/students')
def admin_students():
    if session.get('role') != 'admin':
        flash("Admin only.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('admin_students.html', students=students)

@app.route('/admin/students/add', methods=['POST'])
def admin_add_student():
    if session.get('role') != 'admin':
        flash("Admin only.")
        return redirect(url_for('login'))
    fullname = request.form['fullname']
    sn = request.form['student_number']
    course = request.form['course']
    conn = get_db_connection()
    conn.execute('INSERT INTO students (fullname, student_number, course) VALUES (?, ?, ?)', (fullname, sn, course))
    conn.commit()
    conn.close()
    flash("Student added.")
    return redirect(url_for('admin_students'))

@app.route('/admin/students/edit/<int:id>', methods=['GET', 'POST'])
def admin_edit_student(id):
    if session.get('role') != 'admin':
        flash("Admin only.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    if request.method == 'POST':
        conn.execute('UPDATE students SET fullname = ?, student_number = ?, course = ? WHERE id = ?',
                     (request.form['fullname'], request.form['student_number'], request.form['course'], id))
        conn.commit()
        conn.close()
        flash("Student updated.")
        return redirect(url_for('admin_students'))
    student = conn.execute('SELECT * FROM students WHERE id = ?', (id,)).fetchone()
    conn.close()
    return render_template('admin_edit_student.html', student=student)

@app.route('/admin/students/delete/<int:id>', methods=['POST'])
def admin_delete_student(id):
    if session.get('role') != 'admin':
        flash("Admin only.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM students WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Student deleted.")
    return redirect(url_for('admin_students'))

@app.route('/admin/borrow_records')
def admin_borrow_records():
    if session.get('role') != 'admin':
        flash("Admin only.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    records = conn.execute('''
        SELECT br.*, u.username, b.title FROM borrow_records br
        JOIN users u ON br.user_id = u.id
        JOIN books b ON br.book_id = b.id
        ORDER BY br.borrow_date DESC
    ''').fetchall()
    conn.close()
    return render_template('admin_borrow_records.html', records=records)

@app.route('/admin/borrow_records/edit/<int:id>', methods=['GET', 'POST'])
def admin_edit_borrow(id):
    if session.get('role') != 'admin':
        flash("Admin only.")
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
        return redirect(url_for('admin_borrow_records'))
    rec = conn.execute('SELECT br.*, u.username, b.title FROM borrow_records br JOIN users u ON br.user_id=u.id JOIN books b ON br.book_id=b.id WHERE br.id = ?', (id,)).fetchone()
    conn.close()
    return render_template('admin_edit_borrow.html', rec=rec)

@app.route('/admin/borrow_records/delete/<int:id>', methods=['POST'])
def admin_delete_borrow(id):
    if session.get('role') != 'admin':
        flash("Admin only.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    conn.execute('DELETE FROM borrow_records WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    flash("Borrow record deleted.")
    return redirect(url_for('admin_borrow_records'))

@app.route('/admin/penalties')
def admin_penalties():
    if session.get('role') != 'admin':
        flash("Admin only.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT br.*, u.username, b.title FROM borrow_records br
        JOIN users u ON br.user_id = u.id
        JOIN books b ON br.book_id = b.id
        WHERE br.penalty > 0 AND (br.return_date IS NOT NULL)
    ''').fetchall()
    conn.close()
    return render_template('admin_penalties.html', rows=rows)

@app.route('/admin/reports')
def admin_reports():
    if session.get('role') != 'admin':
        flash("Admin only.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    total_books = conn.execute('SELECT COUNT(*) c FROM books').fetchone()['c']
    borrowed = conn.execute('SELECT COUNT(*) c FROM borrow_records WHERE return_date IS NULL').fetchone()['c']
    returned = conn.execute('SELECT COUNT(*) c FROM borrow_records WHERE return_date IS NOT NULL').fetchone()['c']
    conn.close()
    return render_template('admin_reports.html', total_books=total_books, borrowed=borrowed, returned=returned)

@app.route('/admin/reports/download')
def admin_reports_download():
    if session.get('role') != 'admin':
        flash("Admin only.")
        return redirect(url_for('login'))
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT br.id, u.username, b.title, br.borrow_date, br.due_date, br.return_date, br.penalty
        FROM borrow_records br
        JOIN users u ON br.user_id = u.id
        JOIN books b ON br.book_id = b.id
    ''').fetchall()
    conn.close()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['id','username','title','borrow_date','due_date','return_date','penalty'])
    for r in rows:
        cw.writerow([r['id'], r['username'], r['title'], r['borrow_date'], r['due_date'], r['return_date'], r['penalty']])
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition":"attachment;filename=borrow_report.csv"})

if __name__ == '__main__':
    app.run(debug=True)
