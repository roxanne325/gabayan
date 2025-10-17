from flask import Flask, render_template, request, redirect, url_for  
import sqlite3

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('library.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    total_students = conn.execute('SELECT COUNT(*) FROM students').fetchone()[0]
    total_books = conn.execute('SELECT COUNT(*) FROM books').fetchone()[0]
    total_borrowed = conn.execute('SELECT COUNT(*) FROM borrow').fetchone()[0]
    pending_count = conn.execute('SELECT COUNT(*) FROM borrow WHERE date_returned IS NULL').fetchone()[0]

    borrow_list = conn.execute('''
        SELECT b.id, s.name AS student, bk.title AS book, 
               b.date_borrowed,
               CASE 
                   WHEN b.date_returned IS NULL THEN 'Pending'
                   ELSE 'Returned'
               END AS status
        FROM borrow b
        JOIN students s ON b.student_id = s.id
        JOIN books bk ON b.book_id = bk.id
    ''').fetchall()

    students = conn.execute('SELECT * FROM students').fetchall()
    available_books = conn.execute('SELECT * FROM books WHERE available = 1').fetchall()
    conn.close()

    return render_template('dashboard.html',
                           total_students=total_students,
                           total_books=total_books,
                           borrowed_books=total_borrowed,
                           pending_returns=pending_count,
                           borrowed=borrow_list,
                           students=students,
                           available_books=available_books)

@app.route('/return_book/<int:borrow_id>')
def return_book(borrow_id):
    conn = get_db_connection()
    conn.execute("UPDATE borrow SET date_returned = DATE('now') WHERE id = ?", (borrow_id,))
    conn.execute("UPDATE books SET available = 1 WHERE id = (SELECT book_id FROM borrow WHERE id = ?)", (borrow_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/delete_borrow/<int:borrow_id>')
def delete_borrow(borrow_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM borrow WHERE id = ?", (borrow_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/borrow_book', methods=['POST'])
def borrow_book():
    student_id = request.form['student_id']
    book_id = request.form['book_id']
    conn = get_db_connection()
    conn.execute("INSERT INTO borrow (student_id, book_id, date_borrowed) VALUES (?, ?, DATE('now'))",
                 (student_id, book_id))
    conn.execute("UPDATE books SET available = 0 WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/students')
def students():
    conn = get_db_connection()
    students = conn.execute('SELECT * FROM students').fetchall()
    conn.close()
    return render_template('students.html', students=students)

@app.route('/add_student', methods=['POST'])
def add_student():
    name = request.form['student_name']
    course = request.form['course']
    year = request.form['year']

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO students (name, course, date_added, year) VALUES (?, ?, DATE('now'), ?)",
        (name, course, year)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('students'))

@app.route('/borrowed')
def borrowed():
    conn = get_db_connection()
    borrow = conn.execute('''
        SELECT b.id, s.name AS student_name, bk.title AS book_title,
               b.date_borrowed, b.date_returned
        FROM borrow b
        JOIN students s ON b.student_id = s.id
        JOIN books bk ON b.book_id = bk.id
    ''').fetchall()
    conn.close()
    return render_template('borrowed.html', borrow=borrow)

@app.route('/pending')
def pending():
    conn = get_db_connection()
    pending_books = conn.execute('''
        SELECT b.id, s.name AS student_name, bk.title AS book_title, b.date_borrowed
        FROM borrow b
        JOIN students s ON b.student_id = s.id
        JOIN books bk ON b.book_id = bk.id
        WHERE b.date_returned IS NULL
    ''').fetchall()
    conn.close()
    return render_template('pending.html', pending=pending_books)

@app.route('/books')
def books():
    conn = get_db_connection()
    books = conn.execute('SELECT * FROM books').fetchall()
    conn.close()
    return render_template('books.html', books=books)

@app.route('/add_book', methods=['POST'])
def add_book():
    title = request.form['title']
    author = request.form['author']
    conn = get_db_connection()
    conn.execute("INSERT INTO books (title, author, available) VALUES (?, ?, 1)", (title, author))
    conn.commit()
    conn.close()
    return redirect(url_for('books'))

@app.route('/delete_book/<int:book_id>')
def delete_book(book_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('books'))

if __name__ == '__main__':
    app.run(debug=True)
