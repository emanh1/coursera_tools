import os
import re
import json
import time

from ollama import chat

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support import expected_conditions as EC

from dotenv import load_dotenv

load_dotenv()

email = os.getenv('EMAIL')
password = os.getenv('PASSWORD')
headless = os.getenv('HEADLESS')

captcha_str = os.getenv('CAPTCHA') # The string to look for after clicking login. If it doesn't exist the captcha is probably there asking.

# Not too sure if I should separate into smaller classes, gonna leave it like this for now 

class Main:
    def __init__(self, options: Options) -> None:
        self.driver = webdriver.Firefox(options=options)
        self.wait = WebDriverWait(self.driver,10)
        self.json = []
        self.courses = []

    def normalize_string(self, s: str) -> str:
        s = s.lower()
        s = s.strip()
        s = re.sub(r'\s+', ' ', s)
        return s

    def wait_for(self, by: By, inp: str) -> WebElement:
        return self.wait.until(EC.visibility_of_element_located((by, inp)))

    def scroll_to(self, e: WebElement) -> None:
        self.driver.execute_script("arguments[0].scrollIntoView(true);", e)

    def click(self, e: WebElement) -> None:
        ActionChains(self.driver).move_to_element(e).click().perform()

    def login(self) -> None:
        self.driver.get("https://www.coursera.org/?authMode=login")
        email_field = self.wait_for(By.NAME, "email")
        password_field = self.driver.find_element(By.NAME, "password")
        email_field.send_keys(email)
        password_field.send_keys(password)
        password_field.send_keys(Keys.RETURN)
        print(f"Logging in.")
        self.check_recaptcha()

    def check_recaptcha(self) -> None:
        try:
            self.wait_for(By.XPATH, f"//h1[contains(text(), '{captcha_str}')]")
        except:
            input("Please solve the captcha and press enter to continue.")


    def input_course_links(self) -> None:
        while True:
            print(f"Enter course url: (ex. https://www.coursera.org/learn/open-source-tools-for-data-science/home/), leave blank to end ({len(self.courses)})")
            course_link = input()
            if course_link == '':
                if len(self.courses)>0:
                    break
            else:
                if course_link[-1]=="/":
                    course_link += "assignments"
                else:
                    course_link += "/assignments"
                self.courses.append(course_link)

    def start(self) -> None:
        for course in self.courses:
            print(f"Completing {course}")
            self.driver.get(course)
            self.do_assignments()

    def continue_button(self) -> None:
        print("Looking for continue button")
        try:
            button = self.wait_for(By.XPATH, "//button[span[text()='Continue']]")
            self.click(button)
            print("Clicking continue button")
        except:
            print("No continue button")

    def do_assignments(self) -> None:
        self.continue_button()
        assignments_div = self.wait_for(By.XPATH, '/html/body/div[2]/div/div[1]/div/div/div[2]/div[2]/div/main/div/div/div/div/div[2]/div[3]/div/div[2]')
        assignments = [i.get_attribute('href') for i in assignments_div.find_elements(By.TAG_NAME, 'a')]
        for assignment in assignments:
            print("Going to", assignment)
            self.driver.get(assignment)
            if 'peer' in assignment:
                if 'give-feedback' in assignment:
                    self.review_peer_assignments()
                else:
                    self.do_peer_assignment()
            else:
                self.do_quiz()
            
    def do_quiz(self) -> None:
        self.continue_button()
        start_button = self.wait_for(By.XPATH, "/html/body/div[2]/div/div[1]/div/div/div[2]/div[2]/div[3]/div/div/div/div/main/div[1]/div/div/div[2]/div[2]/div[2]/div[2]/div/div/div/button/span")
        self.click(start_button)
        self.continue_button()
        questions_div = self.wait_for(By.XPATH, "/html/body/div[5]/div/div/div/div[2]/div[2]/div/div/div/div/div/div/div/div")
        questions = questions_div.find_elements(By.XPATH, "./div")
        for question in questions:
            try:
                self.solve_question(question)
            except Exception as e:
                print(e)
                continue
        checkbox = self.driver.find_element(By.ID, "agreement-checkbox-base")
        self.scroll_to(checkbox)
        self.click(checkbox)
        submit_button = self.wait_for(By.XPATH, "//span[text()='Submit']")
        self.click(submit_button)
        try:
            submit_button_2 = self.wait_for(By.XPATH, "/html/body/div[5]/div/div/div/div[2]/div[2]/div/div/div/div/div/div/div/div/div[14]/div[3]/div/div/div[2]/div[3]/div/button[1]/span")
            self.click(submit_button_2)
        except:
            pass
        time.sleep(11) # Wait for results screen
        
    def get_question_text(self, q: WebElement) -> str:
        try:
            question = q.find_element(By.CLASS_NAME, "rc-CML").get_attribute("innerText")
            return self.normalize_string(question)
        except:
            return ""

    def solve_question(self, q: WebElement) -> None:
        text = self.get_question_text(q)
        if text == "":
            print(f"Question text not found for element {q}")
            return
        answer = self.get_answer(text)
        if answer == "":
            print(f"No answer found")
            return
        answers = q.find_elements(By.CLASS_NAME, "rc-Option")
        for ans in answers:
            anstext = self.normalize_string(ans.get_attribute('innerText'))
            if anstext == answer:
                self.scroll_to(ans)
                self.click(ans)
                return

    def get_answer(self, inp: str) -> str:
        if self.json is not None:
            for i in self.json:
                for k,v in i.items():
                    qt = self.normalize_string(k.split("\n")[0].strip())
                    inp = inp.strip()
                    if qt == inp:
                        ans = v.strip()
                        return self.normalize_string(ans)
        else:
            response = chat(model='llama3.2', messages=[
                {
                    "role": "system",
                    "content": "You are an intelligent assistant. When given a question followed by multiple-choice answers, you must return only the complete text of the correct answer, without including any labels (such as 'a,' 'b,' 'c,' or 'd'). Provide no additional commentary or formatting.\n\nExample Input:\nQuestion: What is the capital of France?\na. Berlin\nb. Madrid\nc. Paris\nd. Rome\n\nExample Output:\nParis\n\nInstructions:\n- If the correct answer is given, repeat the exact text of that answer.\n- Do not include option labels or numbers in your response.\n- Do not provide explanations or comments unless explicitly asked for."
                },

                {
                    'role': 'user',
                    'content': inp,
                },
            ])
            return response['message']['content']
        return ""


    def do_peer_assignment(self) -> None:
        self.continue_button()
        link = self.driver.current_url
        try:
            submission_tab = self.wait_for(By.XPATH, '//span[text()="My submission"]')
            self.click(submission_tab)
            textarea = self.wait_for(By.XPATH, '//textarea[@placeholder="Share your thoughts..."]')
            textarea_id = textarea.get_attribute('id').rstrip("~comment")
            link += "/review/" + textarea_id
            print("Grade link: ",link)
        except:
            pass


    def auto_option(self) -> None:
        check_list = self.driver.find_elements(By.CSS_SELECTOR, '.rc-OptionsFormPart>div>div:first-child>label')
        print("autoOption checkList:", len(check_list))

        if len(check_list) == 0:
            print("No elements found for autoOption")
            return

        option_content = check_list[0].find_element(By.CSS_SELECTOR, '.option-contents>div:first-child>span').text.strip()
        print("autoOption optionContent:", option_content)

        if option_content[0] == '0':
            check_list = self.driver.find_elements(By.CSS_SELECTOR, '.rc-OptionsFormPart>div>div:last-child>label')
            print("autoOption updated checkList:", len(check_list))

            for check in check_list:
                self.click(check)

        else:
            for check in check_list:
                self.click(check)

    def auto_comment(self) -> None:
        form_parts = self.driver.find_elements(By.CLASS_NAME, "rc-FormPart")

        for form in form_parts:
            textareas = form.find_elements(By.CLASS_NAME, "c-peer-review-submit-textarea-field")
            for textarea in textareas:
                self.click(textarea)
                textarea.send_keys('star')  

    def auto_yes_no(self) -> None:
        check_list2 = self.driver.find_elements(By.CSS_SELECTOR, '.rc-YesNoFormPart>div>div:first-child>label')
        print("autoYesNo checkList2:", len(check_list2))

        for check in check_list2:
            self.click(check)


    def review_peer_assignments(self) -> None:
        time.sleep(10) #Wait to load
        review_txt = self.wait_for(By.XPATH, "//*[contains(text(), 'reviews left')]").text
        match = re.search(r"(\d+)", review_txt)
        if match:
            reviews = int(match.group(1))
        else:
            reviews = 1
        start = self.wait_for(By.XPATH, '//span[text()="Start Reviewing"]')
        self.scroll_to(start)
        self.click(start)
        for _ in range(reviews):
            time.sleep(10)
            self.auto_comment()
            self.auto_option()
            self.auto_yes_no()
            submit = self.driver.find_element(By.XPATH, "//*[text()='Submit Review']")
            self.scroll_to(submit)
            self.click(submit)
            
if __name__=='__main__':
    options = Options()

    if headless=="TRUE":
        options.add_argument("--headless")
    
    main = Main(options)
    try:
        main.login()
        main.input_course_links()
        mapping = input("Path to json file to solve quizzes? Leave blank to use AI (llama3.2): ")
        if mapping != "":
            with open(mapping, 'r') as f:
                main.json = json.load(f)
        main.start()
    except Exception as e:
        print(e)
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        print("Finished")
        main.driver.quit()