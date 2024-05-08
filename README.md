# Terminal-Commander
A helpful terminal assistant that uses the Command-R-Plus model from Cohere. It figures out what commands need to be run based on the user's instructions and will attempt to automatically fix errors. It also tries to do one command at a time, like how you would use the terminal.

# ⚠ WARNING ⚠
By using this software, you understand and agree that:
1. Risk of Errors: Terminal-Commander operates based on user instructions and attempts to fix errors automatically. However, there is a risk of errors occurring during command execution or error correction. You acknowledge that such errors may occur and agree to use Terminal-Commander at your own risk.
2. Data Loss: Incorrect commands or errors in execution could result in data loss or corruption. It is your responsibility to ensure that you have backups of important data before using Terminal-Commander.
3. Limited Liability: The developers of Terminal-Commander are not liable for any damages or losses incurred due to the use of this software, including but not limited to data loss, system damage, or any other consequential or incidental damages.
4. Security Risks: Executing commands in the terminal, especially with automated assistance, may pose security risks. Exercise caution when running commands, especially those involving sensitive data or system operations.
5. No Warranty: Terminal-Commander is provided "as is" without any warranty of any kind, express or implied. The developers make no guarantees regarding the accuracy, reliability, or performance of the software.

# How to use Terminal-Commander
Here's a step-by-step list of instructions to get you up and running:
1. Install python3 and python3-pip. How you do this will depend on what OS or distro you are using.
2. Clone the repo with <br> `git clone https://github.com/m5kro/Terminal-Commander`
3. Go into the directory <br> `cd Terminal-Commander`
4. Install the requirements <br> `python3 -m pip install -r requirements.txt`
5. Open up Terminal-Commander with your favorite text editor. Look for 'KEY HERE' and replace it with your cohere API key. Remember to keep the single quotes around it.
6. Run Terminal-Commander <br> `python3 Terminal-Commander.py`
7. Terminal-Commander will now ask for a task, try to be as specific as possible to prevent unwanted results. It is recommended you read the prompt tips before starting.

# Prompt Tips
These will change regularly as the code gets updated.
1. Be specific, don't give the AI vague ideas or you run the risk of something breaking.
2. Do step-by-step instructions if you can. This lets the AI know what order to execute commands and which steps caused an error.
3. Don't ask for the impossible. The AI won't stop trying till it deems the task completed. You run the risk of breaking something.
Example Task:<br>
Look for the folder test-3. If it exists, create a file called test-8.txt with the contents "This is a test file". Otherwise, create the folder and the file.
