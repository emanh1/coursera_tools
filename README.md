
# Coursera Tools

A python script to automate solving quizzes and grade peer assignments


## What it does

This script automate the process of solving quizzes on Coursera using a json file that contains the question and answers key, or in case that no file is given, uses llama3.2 to answer the questions. It also automate the process of grading peer assignments, assuming you did yours. This script does NOT automate the doing of YOUR peer graded assignment, though I might try to code that in the future.
## Requirements
Install with:
```
pip install -r requirements.txt
```
## How to use
- First, obtain a json file that contains all the questions and answer keys of the courses you're going to automate. I recommend going to Quizlet to find some flash card sets and use [quizlet-dl](https://github.com/emanh1/Quizlet-dl). Make sure the json file looks like [this](/example.json)
- Create a .env file:
```.env
EMAIL=example@example.com #email of your coursera account
PASSWORD=password #password of your coursera account
HEADLESS=FALSE #set to anything other than TRUE to disable it. i recommend keeping it like this to solve any captcha that might pop up
CAPTCHA=ABC #the script looks for this string after clicking the log in button to check for captcha
```
- Run the script with this and follow the instructions
```
python main.py
```
- Make sure the path of the json file is an absoulte path (ex. D:\ababc\hello.json)