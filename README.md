# Terminal Commander
A helpful terminal assistant that uses the Command family of llms from Cohere (also supports openai apis). It figures out what commands need to be run based on the user's instructions and will attempt to automatically fix errors. It also tries to do one command at a time, like how you would use the terminal.

# ⚠ WARNING ⚠
By using this software, you understand and agree that:
1. Risk of Errors: Terminal Commander operates based on user instructions and attempts to fix errors automatically. However, there is a risk of errors occurring during command execution or error correction. You acknowledge that such errors may occur and agree to use Terminal Commander at your own risk.
2. Data Loss: Incorrect commands or errors in execution could result in data loss or corruption. It is your responsibility to ensure that you have backups of important data before using Terminal Commander.
3. Limited Liability: The developers of Terminal Commander are not liable for any damages or losses incurred due to the use of this software, including but not limited to data loss, system damage, or any other consequential or incidental damages.
4. Security Risks: Executing commands in the terminal, especially with automated assistance, may pose security risks. Exercise caution when running commands, especially those involving sensitive data or system operations.
5. No Warranty: Terminal Commander is provided "as is" without any warranty of any kind, express or implied. The developers make no guarantees regarding the accuracy, reliability, or performance of the software.

# How to use Terminal Commander
Here's a step-by-step list of instructions to get you up and running:
1. Install python3, python3-pip, and tmux. How you do this will depend on what OS or distro you are using.
2. Clone the repo with <br> `git clone https://github.com/m5kro/Terminal-Commander`
3. Go into the directory <br> `cd Terminal-Commander`
4. Create a venv <br> `python3 -m venv venv`
5. Activate the venv <br> `source venv/bin/activate`
6. Install the requirements <br> `python3 -m pip install -r requirements.txt`
7. Edit the .env file with your values
6. Run Terminal Commander <br> `python3 terminal_commander.py` <br> Add `--cohere` if you are using the cohere API
7. Terminal Commander will now ask for a task, try to be as specific as possible to prevent unwanted results.
8. You can also edit the system message in the Python file if you feel like it. This will usually change how the responses are formatted. If you can make it better feel free to make a pull request.

# Prompt Tips
These will change regularly as the code gets updated.
1. Vague instructions may cause issues on smaller models
2. Do step-by-step instructions if you can. This lets the AI know what order to execute commands and which steps caused an error.

**Example Tasks:**<br>
1. Create a folder called testdir with a file called test.txt inside.<br>
2. Run interactivetest.py<br>
3. Update the system

# Known Possible Issues/Missing Features
1. Some models have trouble knowing if the command has finished executing.
2. Some models like to make things up when they can't find something, instead of just using ls or find
3. Some models have trouble wrapping special commands in `[tspecial][/tspecial]` and instead tend to wrap in `[tinput][/tinput]`
4. No traditional chat history, this is more of a fix to prevent system message loss but may hinder larger/smarter models
5. No modifier keys available except for Ctrl C

# Credits
## Big thanks to the following people!
 - [mamei16](https://github.com/mamei16) - web_search.py from [LLM_web_search](https://github.com/mamei16/LLM_Web_search)