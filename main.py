import os
import re
import json
import time
import requests
import subprocess
import difflib

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
        self.review_only = False 

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
        try:
            self.scroll_to(e)
            ActionChains(self.driver).move_to_element(e).click().perform()
            print(f"Clicked element with innertext {e.get_attribute('innerText')}")
        except:
            pass

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
        assignments_div = self.wait_for(By.XPATH, '//div[@aria-label="Assignments Table"]')
        quizzes_divs = assignments_div.find_elements(By.CSS_SELECTOR, "div[class^='rc-AssignmentsTableRowCds css-']")
        peer_divs = assignments_div.find_elements(By.CSS_SELECTOR, "div[data-e2e='ungrouped-peer-assignment-row']")
        
        for quiz_div in quizzes_divs:
            if self.review_only:
                break
            try:
                completed = quiz_div.find_element(By.XPATH, "//title[text()='Completed']")
                if completed:
                    print(f"Skipping {quiz_div.get_attribute('innerText')}")
                    continue
            except:
                quiz_link = quiz_div.find_element(By.TAG_NAME, 'a').get_attribute('href')
                print("Going to", quiz_link)
                self.driver.get(quiz_link)
                self.do_quiz()

        for peer_div in peer_divs:
            peer_link = peer_div.find_element(By.TAG_NAME, 'a').get_attribute('href')
            print("Going to", peer_link)
            self.driver.get(peer_link)
            if 'peer' in peer_link:
               if 'give-feedback' in peer_link:
                   self.review_peer_assignments()
               else:
                   self.do_peer_assignment()           
            
    def do_quiz(self) -> None:
        self.continue_button()
        start_button = self.wait_for(By.XPATH, "/html/body/div[2]/div/div[1]/div/div/div[2]/div[2]/div[3]/div/div/div/div/main/div[1]/div/div/div[2]/div[2]/div[2]/div[2]/div/div/div/button/span")
        self.click(start_button)
        self.continue_button()
        try:
            questions_div = self.wait_for(By.XPATH, "/html/body/div[5]/div/div/div/div[2]/div[2]/div/div/div/div/div/div/div/div")
        except:
            return
        questions = questions_div.find_elements(By.XPATH, "./div")
        for question in questions:
            try:
                self.solve_question(question)
                time.sleep(1)
            except Exception as e:
                print(e)
                continue
        checkbox = self.driver.find_element(By.ID, "agreement-checkbox-base")
        self.click(checkbox)
        submit_button = self.wait_for(By.XPATH, "//span[text()='Submit']")
        self.click(submit_button)
        try:
            submit_button_2 = self.wait_for(By.XPATH, "/html/body/div[5]/div/div/div/div[2]/div[2]/div/div/div/div/div/div/div/div/div[14]/div[3]/div/div/div[2]/div[3]/div/button[1]/span")
            self.click(submit_button_2)
        except:
            pass
        time.sleep(11) # Wait for results screen
        
    def get_question_text(self, q: WebElement) -> tuple[str, str]:
        try:
            question = self.normalize_string(q.find_element(By.CLASS_NAME, "rc-CML").get_attribute("innerText"))
            answers = q.find_elements(By.CLASS_NAME, "rc-Option")
            answerstext = ""
            for answer in answers:
                answerstext += "|" + answer.get_attribute("innerText")
            return (question, answerstext) 
        except:
            return None

    def solve_question(self, q: WebElement) -> None:
        text = self.get_question_text(q)
        if text is None:
            print(f"Question text not found for element {q} with innerText {q.get_attribute('innerText')}")
            return
        answer = self.get_answer(text)
        if answer == "":
            print(f"No answer found")
            return
        answers = q.find_elements(By.CLASS_NAME, "rc-Option")
        
        # Try exact match first
        for ans in answers:
            anstext = self.normalize_string(ans.get_attribute('innerText'))
            if anstext == answer:
                self.click(ans)
                return
        
        # If no exact match, find closest match
        closest_match = None
        highest_ratio = 0
        for ans in answers:
            anstext = self.normalize_string(ans.get_attribute('innerText'))
            ratio = difflib.SequenceMatcher(None, anstext, answer).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio
                closest_match = ans
        
        if closest_match and highest_ratio > 0.6:  # threshold of 60% similarity
            print(f"Using closest match (similarity: {highest_ratio:.2%})")
            self.click(closest_match)
        else:
            print("No suitable match found")

    def is_ollama_running(self) -> bool:
        try:
            response = requests.get("http://localhost:11434", timeout=5) 
            if response.status_code == 200:
                return True
        except requests.RequestException:
            return False
        return False

    def start_ollama(self) -> None:
        try:
            subprocess.Popen(["ollama", "run", "llama3.2"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("Starting ollama with model 'llama3.2'...")
            time.sleep(5) 
        except Exception as e:
            print(f"Failed to start ollama: {e}")

    def find_best_match(self, target: str, choices: list[str], threshold: float = 0.6) -> str:
        closest_match = ""
        highest_ratio = 0
        target = self.normalize_string(target)
        
        for choice in choices:
            choice = self.normalize_string(choice)
            ratio = difflib.SequenceMatcher(None, choice, target).ratio()
            if ratio > highest_ratio:
                highest_ratio = ratio
                closest_match = choice
        
        return closest_match if highest_ratio > threshold else ""

    def get_answer(self, inp: tuple[str, str]) -> str:
        if len(self.json) != 0:
            inp = self.normalize_string(inp[0])
            # Try exact match first
            for item in self.json:
                if self.normalize_string(item['term']) == inp:
                    return self.normalize_string(item['definition'])
            
            # If no exact match, try fuzzy matching
            terms = [item['term'] for item in self.json]
            best_match = self.find_best_match(inp, terms)
            if best_match:
                for item in self.json:
                    if self.normalize_string(item['term']) == self.normalize_string(best_match):
                        return self.normalize_string(item['definition'])
        else:
            if not self.is_ollama_running():
                self.start_ollama()
                if not self.is_ollama_running():
                    for _ in range(20): 
                        time.sleep(0.5)
                        if self.is_ollama_running():
                            break
                    else:
                        return "error starting"
            import ollama
            response = ollama.chat(model='llama3.2', messages=[
                {
                    "role": "system",
                    "content": "You are an intelligent assistant. When given a question followed by multiple-choice answers, you must return only the complete text of the correct answer, without including any labels (such as 'a,' 'b,' 'c,' or 'd'). Provide no additional commentary or formatting.\n\nExample Input:\nQuestion: What is the capital of France?|Berlin|Madrid|Paris|Rome\n\nExample Output:Paris\n\nInstructions:\n- If the correct answer is given, repeat the exact text of that answer.\n- Do not include option labels or numbers in your response.\n- Do not provide explanations or comments unless explicitly asked for."
                },
                {
                    'role': 'user',
                    'content': inp[0] + inp[1],
                },
            ])
            return self.normalize_string(response['message']['content'])
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
            print(f"\033[32mGrade link: {link}\033[0m")
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
        try:
            review_txt = self.wait_for(By.XPATH, "//*[contains(text(), 'left to complete')]").text
        except:
            try:
                review_txt = self.wait_for(By.XPATH, "//*[contains(text(), 'reviews left')]").text
            except:
                review_txt = "1"
        match = re.search(r"(\d+)", review_txt)
        if match:
            reviews = int(match.group(1))
        else:
            reviews = 1
        start = self.wait_for(By.XPATH, '//span[text()="Start Reviewing"]')
        self.click(start)
        for _ in range(reviews):
            time.sleep(10)
            self.auto_comment()
            self.auto_option()
            self.auto_yes_no()
            submit = self.driver.find_element(By.XPATH, "//*[text()='Submit Review']")
            self.click(submit)
            
if __name__=='__main__':
    options = Options()

    if headless=="TRUE":
        options.add_argument("--headless")
    
    main = Main(options)
    try:
        main.login()
        mode = input("Choose mode (1: Full course completion, 2: Peer reviews only): ")
        main.review_only = (mode == "2")
        main.input_course_links()
        if not main.review_only:
            mapping = input("Path to json file to solve quizzes? Leave blank to use AI (llama3.2): ")
            if mapping != "":
                with open(mapping, 'r') as f:
                    main.json = json.load(f)
        main.start()
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        print("Finished")
        main.driver.quit()