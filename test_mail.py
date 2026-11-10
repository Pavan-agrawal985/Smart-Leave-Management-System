import os
import smtplib
from dotenv import load_dotenv

load_dotenv()
user = os.environ.get("MAIL_USERNAME", "")
pw = os.environ.get("MAIL_PASSWORD", "")
print("Username:", user, "| password length (should be 16):", len(pw))

try:
    s = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15)
    s.login(user, pw)
    print("Port 465 OK")
    s.quit()
except Exception as e:
    print("Port 465 failed:", repr(e))

try:
    s = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
    s.starttls()
    s.login(user, pw)
    print("Port 587 OK")
    s.quit()
except Exception as e:
    print("Port 587 failed:", repr(e))