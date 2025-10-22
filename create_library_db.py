import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('library.db')
cur = conn.cursor()

cur.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fullname TEXT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user'
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fullname TEXT NOT NULL,
    student_number TEXT UNIQUE,
    course TEXT
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    available INTEGER DEFAULT 1
)
''')

cur.execute('''
CREATE TABLE IF NOT EXISTS borrow_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    borrow_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    return_date TEXT,
    penalty REAL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(book_id) REFERENCES books(id)
)
''')

admin_pw = generate_password_hash("admin123")
user_pw = generate_password_hash("user123")

cur.execute("INSERT OR IGNORE INTO users (fullname, username, password, role) VALUES (?, ?, ?, ?)",
            ("Admin Account", "admin", admin_pw, "admin"))
cur.execute("INSERT OR IGNORE INTO users (fullname, username, password, role) VALUES (?, ?, ?, ?)",
            ("Sample User", "user", user_pw, "user"))

sample_books = [
    ("The Great Gatsby", "F. Scott Fitzgerald"),
    ("To Kill a Mockingbird", "Harper Lee"),
    ("1984", "George Orwell"),
    ("Pride and Prejudice", "Jane Austen"),
    ("The Hobbit", "J.R.R. Tolkien")
]
cur.executemany("INSERT OR IGNORE INTO books (title, author) VALUES (?, ?)", sample_books)

conn.commit()
conn.close()
print("✅ library.db created/updated with tables and sample data.")
