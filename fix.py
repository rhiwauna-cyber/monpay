from werkzeug.security import generate_password_hash
password_asli = "admin123"
password_terenskripsi = generate_password_hash(password_asli)
print("hasil hash")
print(password_terenskripsi)