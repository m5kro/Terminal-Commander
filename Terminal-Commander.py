import cohere
import subprocess
import platform
import sys

co = cohere.Client('KEY HERE')
msg=[]
request = input("Enter the task: ")
task = 'I am using ' + platform.system() + '.' + request

def terminal_commander(task):
    response = co.chat(
            temperature=0,
            preamble='You are commander, a genius coder and AI assistant. If the user asks for a terminal command, return the terminal command and nothing else. If multiple commands are needed, only return one command at a time and wait for a response from the user with the output before giving the next command. Try not to use && or create functions. If an error is given, return a command that will fix the error. When you are done with all the commands, return in the exact words: I have finished the requested task.',
            model='command-r-plus',
            chat_history=msg,
            message=task
        )
    return response.text


def run_command(command):
    print('Running command: ' + command)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    output, error = process.communicate()
    print(output.decode('utf-8') + error.decode('utf-8'))
    return output, error

AIresponse = terminal_commander(task)
msg.append({'role': 'USER', 'message': task})
msg.append({'role': 'CHATBOT', 'message': AIresponse})
run = run_command(AIresponse)

while True:
    task = run[0] + run[1]
    task = task.decode('utf-8')
    if task == '' or task == b'':
        task = 'success'
    print(task)
    AIresponse = terminal_commander(task)
    print(AIresponse)
    if AIresponse == 'I have finished the requested task.':
        break
    msg.append({'role': 'USER', 'message': task})
    msg.append({'role': 'CHATBOT', 'message': AIresponse})
    run = run_command(AIresponse)


print('Task completed!')
