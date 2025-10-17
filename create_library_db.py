import sqlite3

conn = sqlite3.connect('library.db')
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    course TEXT NOT NULL,
    year_level INTEGER NOT NULL
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    available INTEGER DEFAULT 1  -- 1 = available, 0 = borrowed
)
''')

c.execute('''
CREATE TABLE IF NOT EXISTS borrow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    book_id INTEGER NOT NULL,
    date_borrowed TEXT NOT NULL,
    date_returned TEXT,
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (book_id) REFERENCES books(id)
)
''')

c.execute("INSERT INTO students (name, course, year_level) VALUES ('Roxanne Mae Gabayan', 'BSIT', 2)")
c.execute("INSERT INTO books (title, author, available) VALUES ('Python for Beginners', 'John Smith', 1)")
c.execute("INSERT INTO books (title, author, available) VALUES ('Database Systems', 'Maria Lopez', 1)")
c.execute("INSERT INTO borrow (student_id, book_id, date_borrowed, date_returned) VALUES (1, 1, '2025-10-14', NULL)")

conn.commit()
conn.close()

print("✅ library.db created successfully!")
print("📚 Tables created: students, books, borrow")
print("🎉 Sample data inserted successfully!")
