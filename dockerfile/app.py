import logging
import os
import json
import time
import boto3
import requests
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

secrets_manager_client = boto3.client('secretsmanager') 
server_url = os.environ.get('SERVER_URL')
user_secret_manager_name = os.environ.get('USER_SECRET_MANAGER_NAME')
cookie_secret_manager_name = os.environ.get('COOKIE_SECRET_MANAGER_NAME')

log = logging.getLogger()
log.setLevel('INFO')

def handler(event, context):
    api_url = f"{server_url}/collect"
    cookie = get_valid_cookie_from_secret_manager()
    if cookie != None:
        log.info("cookie is existing, and not expire")
        return {
            "statusCode": 200,
            "body": json.dumps("successful!")
        }
    
    secret_values = get_secret_values(user_secret_manager_name)
    
    user_name = secret_values['username']
    password = secret_values['password']
    login_url = f"{server_url}/login"

    log.info(f"login_url: {login_url}")
    log.info(f"user_name: {user_name}")
    log.info(f"password: {password}")

    cookie = get_cookies(login_url, user_name, password)
    if cookie == None:
        return {
            "statusCode": 400,
            "body": json.dumps("Get authentiction cookie failed!")
        }        
    store_cookie(cookie)

    return {
        "statusCode": 200,
        "body": json.dumps("successful!")
    }

def get_cookies(alb_url, username, password):

    log.info(f"login: {alb_url}, username: {username}")
    chrome_options = ChromeOptions()
    chrome_options.binary_location = "/opt/chrome/chrome"
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-tools")
    chrome_options.add_argument("--no-zygote")
    chrome_options.add_argument("--single-process")

    log.info(chrome_options.arguments)

    service = Service(executable_path="/opt/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(alb_url)
    
    WebDriverWait(driver, 20).until(lambda driver: driver.execute_script('return document.readyState') == 'complete')
    e_index = 0
    username_input = driver.find_elements(by=By.NAME, value="username")[e_index]
    username_input.send_keys(username)
    password_input = driver.find_elements(by=By.NAME, value="password")[e_index]
    password_input.send_keys(password)
    submit_button = driver.find_elements(by=By.NAME, value="login")[e_index]
    submit_button.click()      


    cookies = driver.get_cookies()
    current_url = driver.current_url
    driver.quit()
    log.info(f"current_url: {current_url}")
    
    if current_url == alb_url:
        log.info("Login successfully")
    else:
        log.info("Login failed")
        return None

    cookies_values=[]
    for c in cookies:
        c_name = c['name']
        c_value = c['value']
        cookies_values.append(f"{c_name}={c_value}")
    cookies_header = "; ".join(cookies_values)
    return cookies_header

def get_secret_values(secret_arn):
    response = secrets_manager_client.get_secret_value(SecretId=secret_arn)
    secret_string = response['SecretString']
    secret_values = json.loads(secret_string)
    
    return secret_values

def store_cookie(cookie):
    createTime = int(time.time())
    try:
        secrets_manager_client.describe_secret(SecretId=cookie_secret_manager_name)
    except secrets_manager_client.exceptions.ResourceNotFoundException:
        secrets_manager_client.create_secret(
          Name=cookie_secret_manager_name,
          Description='This secret stores the ALB cookie',
          SecretString=json.dumps({
              "Cookie": cookie,
              "expireAt": createTime + 14400   # 4 hours
            })
        )
    else:
        secrets_manager_client.put_secret_value(
            SecretId=cookie_secret_manager_name,
            SecretString=json.dumps({
                "Cookie": cookie,
                "expireAt": createTime + 14400   # 4 hours
              })
        )

def get_valid_cookie_from_secret_manager():
    current_time = int(time.time())
    try:
        secrets_manager_client.describe_secret(SecretId=cookie_secret_manager_name)
    except secrets_manager_client.exceptions.ResourceNotFoundException:
        return None
    else:
        response = secrets_manager_client.get_secret_value(SecretId=cookie_secret_manager_name)
        secret_string = response['SecretString']
        secret_values = json.loads(secret_string)
        expire_at = int(secret_values['expireAt'])
        if (current_time > expire_at + 600):
            return None
        cookie = secret_values['Cookie']

        return cookie


    
     



